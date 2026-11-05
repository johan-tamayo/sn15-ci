#!/usr/bin/env python3
"""merge job: concatenate the per-(nonce, shard) world_sim outputs into `<label>_n<nonce>.jsonl` (+ `.log`) and summarise.

Input dir holds `out_<nonce>_<shard>.jsonl|.log` and `meta_<nonce>_<shard>.json` (downloaded shard artifacts, merged).
Output dir gets `<label>_n<nonce>.jsonl` (one episode json per line, sorted by task_id exactly like world_sim's final
write), `<label>_n<nonce>.log`, `summary.json`, `summary.md`.  Standard library only.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path


def list_price_usd(call: dict) -> float:
    """Same list-price estimate as tools/gsim.py summarize() (reader calls excluded)."""
    m_name = str(call.get("served") or call.get("model") or "?")
    if "sonnet" in m_name:
        pin, pout = (3.0, 15.0)
    elif "flash" in m_name or "gemini" in m_name:
        pin, pout = (0.825, 4.125)
    else:
        pin, pout = (1.0, 5.0)
    pt, ct, ch = int(call.get("pt") or 0), int(call.get("ct") or 0), int(call.get("cached") or 0)
    return float(call.get("cost") or 0) or ((pt - ch) * pin + ch * pin * 0.1 + ct * pout) / 1e6


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--nonces", default="0,1")
    ap.add_argument("--expected-tasks", default="", help="csv of the task ids every nonce should have")
    ap.add_argument("--meta", default="", help="json string with run metadata to copy into summary.json")
    a = ap.parse_args(argv)

    sdir = Path(a.shards_dir)
    odir = Path(a.out)
    odir.mkdir(parents=True, exist_ok=True)
    expected = [t.strip() for t in a.expected_tasks.split(",") if t.strip()]
    nonces = [n.strip() for n in a.nonces.split(",") if n.strip()]
    rx = re.compile(r"^out_(?P<nonce>[^_]+)_(?P<shard>\d+)\.jsonl$")
    summary: dict = {"label": a.label, "nonces": {}, "pass_total": 0, "episodes_total": 0}
    try:
        summary["run"] = json.loads(a.meta) if a.meta else {}
    except Exception:
        summary["run"] = {"meta_raw": a.meta}
    md = [f"## {a.label}", "", "| nonce | episodes | passed | missing | shards ok/total | list-price USD | max shard wall | served models |", "|---|---|---|---|---|---|---|---|"]
    for nonce in nonces:
        files = []
        for p in sdir.glob(f"out_{nonce}_*.jsonl"):
            m = rx.match(p.name)
            if m and m.group("nonce") == nonce:
                files.append((int(m.group("shard")), p))
        files.sort()
        rows: dict[str, dict] = {}
        bad_lines = 0
        for _s, p in files:
            for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
                s = ln.strip()
                if not s:
                    continue
                try:
                    r = json.loads(s)
                except Exception:
                    bad_lines += 1
                    continue
                tid = str(r.get("task_id") or "")
                if tid and tid not in rows:
                    rows[tid] = r
        ordered = [rows[t] for t in sorted(rows)]
        out_jsonl = odir / f"{a.label}_n{nonce}.jsonl"
        with out_jsonl.open("w", encoding="utf-8") as f:
            for r in ordered:
                f.write(json.dumps(r) + "\n")
        # log: shard logs back to back, with a header per shard
        out_log = odir / f"{a.label}_n{nonce}.log"
        with out_log.open("w", encoding="utf-8") as lf:
            for s, p in files:
                lp = sdir / f"out_{nonce}_{s}.log"
                lf.write(f"===== shard {s} ({p.name}) =====\n")
                if lp.is_file():
                    lf.write(lp.read_text(encoding="utf-8", errors="replace"))
                    if not lp.read_text(encoding="utf-8", errors="replace").endswith("\n"):
                        lf.write("\n")
        metas = []
        for mp in sorted(sdir.glob(f"meta_{nonce}_*.json")):
            try:
                metas.append(json.loads(mp.read_text(encoding="utf-8")))
            except Exception:
                pass
        passed = sum(1 for r in ordered if r.get("passed"))
        cats = collections.Counter(str(r.get("category") or "passed") for r in ordered)
        models: collections.Counter = collections.Counter()
        cost = 0.0
        for r in ordered:
            for c in r.get("agent_model_calls") or []:
                models[str(c.get("served") or c.get("model") or "?")] += 1
                cost += list_price_usd(c)
        present = set(rows)
        missing = [t for t in expected if t not in present] if expected else []
        shards_ok = sum(1 for m in metas if int(m.get("rc", 1)) == 0)
        max_wall = max([int(m.get("wall_s") or 0) for m in metas] or [0])
        elapsed = sum(float(r.get("elapsed_s") or 0) for r in ordered)
        stops = sum(1 for r in ordered if float(r.get("elapsed_s") or 0) >= 284.0)
        summary["nonces"][nonce] = {
            "file": out_jsonl.name,
            "episodes": len(ordered),
            "passed": passed,
            "missing_tasks": missing,
            "bad_lines": bad_lines,
            "categories": dict(cats),
            "served_models": dict(models),
            "list_price_usd": round(cost, 4),
            "episode_seconds": round(elapsed, 1),
            "stops_ge_284s": stops,
            "shards": metas,
            "shards_ok": shards_ok,
            "shards_total": len(files),
            "max_shard_wall_s": max_wall,
        }
        summary["pass_total"] += passed
        summary["episodes_total"] += len(ordered)
        md.append(
            f"| {nonce} | {len(ordered)} | {passed} | {len(missing)} | {shards_ok}/{len(files)} | {cost:.4f} | {max_wall}s | "
            + ", ".join(f"{k} x{v}" for k, v in sorted(models.items()))
            + " |"
        )
        print(f"[merge] n{nonce}: {passed}/{len(ordered)} passed, missing={len(missing)}, shards ok {shards_ok}/{len(files)}, list-price ${cost:.4f}, max shard wall {max_wall}s", flush=True)
    md.append("")
    md.append(f"**pooled: {summary['pass_total']}/{summary['episodes_total']} passed**")
    for nonce, d in summary["nonces"].items():
        if d["missing_tasks"]:
            md.append(f"- n{nonce} missing: {', '.join(d['missing_tasks'])}")
        md.append(f"- n{nonce} categories: {d['categories']}")
    (odir / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    (odir / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

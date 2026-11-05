#!/usr/bin/env python3
"""plan job: split the task ids of a pack into N shards per nonce and emit the job matrix.

Writes `matrix=<json>`, `label=<label>`, `n_tasks=<int>`, `n_jobs=<int>`, `pack_dir=<path>`, `tasks_csv=<csv>` lines
(GITHUB_OUTPUT format) to stdout.  Only the standard library is used (runs on the runner's system python).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKS = REPO / "suites" / "graded30_v2" / "packs"


def resolve_pack(pack: str) -> Path:
    cands = [PACKS / pack, REPO / pack, Path(pack)]
    for c in cands:
        if (c / "manifest.json").is_file():
            return c.resolve()
    raise SystemExit(f"pack not found (no manifest.json): {pack} (looked in {[str(c) for c in cands]})")


def pack_task_ids(pack_dir: Path) -> list[str]:
    return sorted(p.stem for p in (pack_dir / "tasks").glob("*.json"))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--tasks", default="all", help="comma-separated task ids, or all")
    ap.add_argument("--nonces", default="0,1")
    ap.add_argument("--shards", default="10")
    ap.add_argument("--label", default="")
    ap.add_argument("--agent-sha8", default="")
    a = ap.parse_args(argv)

    pack_dir = resolve_pack(a.pack)
    all_ids = pack_task_ids(pack_dir)
    want = (a.tasks or "all").strip()
    if want.lower() in ("", "all"):
        tids = list(all_ids)
    else:
        tids = []
        for tok in want.replace("\n", ",").split(","):
            t = tok.strip()
            if t and t not in tids:
                tids.append(t)
        unknown = [t for t in tids if t not in all_ids]
        if unknown:
            raise SystemExit(f"unknown task ids for pack {pack_dir.name}: {unknown}")
    if not tids:
        raise SystemExit("no tasks selected")
    agent_p = REPO / "agents" / f"{a.agent_sha8}.py"
    if a.agent_sha8 and not agent_p.is_file():
        raise SystemExit(f"agent file missing in the repo: {agent_p} (sn15 gh-run commits it before dispatch)")

    nonces = [n.strip() for n in a.nonces.split(",") if n.strip()]
    if not nonces:
        raise SystemExit("no nonces")
    try:
        n_shards = max(1, int(a.shards))
    except ValueError:
        raise SystemExit(f"bad --shards {a.shards!r}")
    n_shards = min(n_shards, len(tids))
    label = a.label.strip() or f"gh_{a.agent_sha8 or 'agent'}_{pack_dir.name}"

    matrix = []
    for nonce in nonces:
        for s in range(n_shards):
            shard_tids = tids[s::n_shards]  # round-robin: the shards stay balanced to +-1 task
            matrix.append({"nonce": nonce, "shard": s, "tasks": ",".join(shard_tids), "n": len(shard_tids)})

    rel_pack = os.path.relpath(pack_dir, REPO)
    print(f"matrix={json.dumps(matrix, separators=(',', ':'))}")
    print(f"label={label}")
    print(f"n_tasks={len(tids)}")
    print(f"n_jobs={len(matrix)}")
    print(f"pack_dir={rel_pack}")
    print(f"tasks_csv={','.join(tids)}")
    print(f"nonces_csv={','.join(nonces)}")
    print(f"n_shards={n_shards}")
    print(
        f"[plan] pack={pack_dir.name} tasks={len(tids)} nonces={nonces} shards={n_shards} jobs={len(matrix)} label={label}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

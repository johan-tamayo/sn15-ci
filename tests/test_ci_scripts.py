"""The plan / merge jobs of sim.yml and the run-name contract that `sn15 gh-run watch` parses ($0, standard library)."""
from __future__ import annotations

import json
import re
import subprocess
import sys

import pytest

from conftest import PACKS, REPO

PY = sys.executable


def _plan(*args: str) -> dict[str, str]:
    r = subprocess.run([PY, str(REPO / "ci" / "plan.py"), *args], capture_output=True, text=True, cwd=str(REPO), timeout=60)
    assert r.returncode == 0, r.stderr
    return dict(line.split("=", 1) for line in r.stdout.splitlines() if "=" in line)


def test_plan_shards_every_task_once_per_nonce():
    out = _plan("--pack", "s14_qual", "--nonces", "0,1", "--shards", "4", "--label", "t")
    matrix = json.loads(out["matrix"])
    tids = out["tasks_csv"].split(",")
    assert int(out["n_tasks"]) == len(tids) == len(list((PACKS / "s14_qual" / "tasks").glob("*.json")))
    assert int(out["n_jobs"]) == len(matrix) == 8
    for nonce in ("0", "1"):
        jobs = [j for j in matrix if j["nonce"] == nonce]
        got = [t for j in jobs for t in j["tasks"].split(",")]
        assert sorted(got) == sorted(tids) and len(got) == len(set(got))
        sizes = [j["n"] for j in jobs]
        assert max(sizes) - min(sizes) <= 1
    assert out["pack_dir"] == "suites/graded30_v2/packs/s14_qual"


def test_plan_caps_shards_and_rejects_unknown_tasks():
    two = sorted(p.stem for p in (PACKS / "s14_qual" / "tasks").glob("*.json"))[:2]
    out = _plan("--pack", "s14_qual", "--tasks", ",".join(two), "--nonces", "0", "--shards", "10")
    assert out["n_shards"] == "2" and out["tasks_csv"] == ",".join(two)
    r = subprocess.run([PY, str(REPO / "ci" / "plan.py"), "--pack", "s14_qual", "--tasks", "t-0000000000"], capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode != 0 and "unknown task ids" in r.stderr


def test_merge_sorts_dedups_and_reports_missing(tmp_path):
    sh = tmp_path / "shards"
    sh.mkdir()
    ep = lambda tid, ok: json.dumps({"task_id": tid, "passed": ok, "category": None if ok else "request not met", "elapsed_s": 10,
                                     "agent_model_calls": [{"served": "anthropic/claude-haiku-5.5", "pt": 1000, "ct": 100, "cached": 0}]})
    (sh / "out_0_0.jsonl").write_text(ep("t-b", True) + "\n" + ep("t-a", False) + "\n")
    (sh / "out_0_1.jsonl").write_text(ep("t-a", True) + "\n{not json\n" + ep("t-c", False) + "\n")
    (sh / "out_0_0.log").write_text("shard 0 log")
    (sh / "meta_0_0.json").write_text(json.dumps({"rc": 0, "wall_s": 30}))
    (sh / "meta_0_1.json").write_text(json.dumps({"rc": 1, "wall_s": 50}))
    out = tmp_path / "merged"
    r = subprocess.run([PY, str(REPO / "ci" / "merge.py"), "--shards-dir", str(sh), "--out", str(out), "--label", "lab",
                        "--nonces", "0", "--expected-tasks", "t-a,t-b,t-c,t-d"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    rows = [json.loads(l) for l in (out / "lab_n0.jsonl").read_text().splitlines()]
    assert [x["task_id"] for x in rows] == ["t-a", "t-b", "t-c"]
    assert rows[0]["passed"] is False  # first shard's row wins for a duplicated task id
    s = json.loads((out / "summary.json").read_text())
    n0 = s["nonces"]["0"]
    assert (s["pass_total"], s["episodes_total"]) == (1, 3)
    assert n0["missing_tasks"] == ["t-d"] and n0["bad_lines"] == 1
    assert (n0["shards_ok"], n0["shards_total"], n0["max_shard_wall_s"]) == (1, 2, 50)
    assert "===== shard 0" in (out / "lab_n0.log").read_text()


def test_sim_run_name_keeps_the_shape_gh_run_watch_parses():
    """`sn15 gh-run watch` / `pull` read label, sha8, pack, nonces and shards back from the run title."""
    text = (REPO / ".github" / "workflows" / "sim.yml").read_text()
    m = re.search(r'^run-name:\s*"(.*)"\s*$', text, re.M)
    assert m, "sim.yml lost its run-name"
    assert m.group(1) == ("${{ inputs.label }} [${{ inputs.agent_sha8 }}] ${{ inputs.pack }} "
                          "n=${{ inputs.nonces }} x${{ inputs.shards }} ${{ inputs.run_token }}")


@pytest.mark.parametrize("script", ["ci/plan.py", "ci/merge.py", "simrace/world_sim.py"])
def test_scripts_compile(script):
    path = REPO / script
    compile(path.read_text(encoding="utf-8"), str(path), "exec")

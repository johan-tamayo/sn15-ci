"""world_sim replay identity ($0): `run --from-jsonl <stored> --from-step 999` rebuilds every step of a stored episode from
its recorded model answers (no branch, no live call) and must reproduce the stored episode."""
from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys

import pytest

from conftest import DIVERGENT_TASK, FIXTURE, FIXTURE_AGENT, FIXTURE_PACK, IDENTICAL_TASK, OFFLINE_ENV, REPO, spend_note

ROW_FIELDS = ("passed", "score", "category", "steps", "turns", "inference_calls", "prompt_tokens", "cached_tokens", "completion_tokens")
VERDICT_FIELDS = ("score", "category", "ledger_sha256", "grading_sha256")
SPEND_FIELDS = ("usd", "usd_list", "prompt_tokens_cached", "completion_tokens")
REPLAY_503_GAP = (
    "world_sim: pre-branch replay (_serve_pre_branch_inference) returns before the 503 injection, so the stored injected "
    "failures are not re-applied (the agent's calls / failed_calls counters drop by the stored 503s). Remove the xfail when "
    "replay re-injects them.")


@pytest.fixture(scope="module")
def replayed(tmp_path_factory, stored_rows) -> dict[str, dict]:
    work = tmp_path_factory.mktemp("replay")
    stored = work / "stored.jsonl"
    with gzip.open(FIXTURE, "rt", encoding="utf-8") as src, stored.open("w", encoding="utf-8") as dst:
        dst.write(src.read())
    out, log = work / "replay.jsonl", work / "replay.log"
    env = dict(os.environ, **OFFLINE_ENV, WORLD_SIM_CACHE_DIR=str(work / "cache"), SN15_TMP=str(work / "tmp"))
    cmd = [sys.executable, str(REPO / "simrace" / "world_sim.py"), "run", "--agent", str(FIXTURE_AGENT), "--pack", str(FIXTURE_PACK),
           "--tasks", ",".join(sorted(stored_rows)), "--nonce", "0", "--workers", "2", "--inference-failure-rate", "0.07",
           "--from-jsonl", str(stored), "--from-step", "999", "--out", str(out)]
    with log.open("w") as fh:
        rc = subprocess.run(cmd, cwd=str(REPO), env=env, stdout=fh, stderr=subprocess.STDOUT, timeout=600).returncode
    text = log.read_text(errors="replace")
    assert rc == 0, f"world_sim rc={rc}\n{text[-3000:]}"
    assert "Claude Reader Calls: 0 live" in text, text[-2000:]
    return {r["task_id"]: r for r in (json.loads(l) for l in out.read_text().splitlines() if l.strip())}


def _diffs(stored: dict, replay: dict) -> list[str]:
    out = [f"{k}: stored {stored.get(k)!r} replay {replay.get(k)!r}" for k in ROW_FIELDS if stored.get(k) != replay.get(k)]
    out += [f"verdict.{k}: stored {stored['verdict'].get(k)!r} replay {replay['verdict'].get(k)!r}"
            for k in VERDICT_FIELDS if stored["verdict"].get(k) != replay["verdict"].get(k)]
    s, r = spend_note(stored), spend_note(replay)
    out += [f"spend.{k}: stored {s.get(k)!r} replay {r.get(k)!r}" for k in SPEND_FIELDS if s.get(k) != r.get(k)]
    served = lambda n: int(n.get("calls") or 0) - int(n.get("failed_calls") or 0)
    if served(s) != served(r):
        out.append(f"spend.served calls: stored {served(s)} replay {served(r)}")
    return out


def test_replay_makes_no_live_call(replayed):
    for tid, row in replayed.items():
        assert row.get("post_branch_live_calls") == 0, tid
        assert row.get("branched_from_step") == 999, tid


def test_replay_reproduces_the_stored_episode(replayed, stored_rows):
    """Outcome, step / turn / token counts, the agent's own spend meter and the ledger digest all match."""
    diffs = _diffs(stored_rows[IDENTICAL_TASK], replayed[IDENTICAL_TASK])
    assert not diffs, "\n".join(diffs)


@pytest.mark.xfail(strict=True, reason=REPLAY_503_GAP)
def test_replay_reapplies_the_stored_injected_failures(replayed, stored_rows):
    for tid in stored_rows:
        s, r = spend_note(stored_rows[tid]), spend_note(replayed[tid])
        assert (r["calls"], r["failed_calls"]) == (s["calls"], s["failed_calls"]), tid


@pytest.mark.xfail(strict=True, reason=REPLAY_503_GAP + " With three stored 503s the agent diverges: no item_check at "
                   "step 15, two judge calls at step 17 the stored run never made, ledger digest and spend differ.")
def test_replay_reproduces_an_episode_with_three_injected_failures(replayed, stored_rows):
    diffs = _diffs(stored_rows[DIVERGENT_TASK], replayed[DIVERGENT_TASK])
    assert not diffs, "\n".join(diffs)


def test_divergent_replay_keeps_the_outcome(replayed, stored_rows):
    """Even where the replay diverges (xfail above) the graded outcome is unchanged; a change here is a new regression."""
    s, r = stored_rows[DIVERGENT_TASK], replayed[DIVERGENT_TASK]
    assert (r["passed"], r["category"], r["steps"]) == (s["passed"], s["category"], s["steps"])

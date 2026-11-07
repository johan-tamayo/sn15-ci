"""$0 regression tests for the simulator and the CI scripts: no model call, no secret, no network.

Every test runs offline: HTTP(S)_PROXY points at a closed local port and OPENROUTER_API_KEY is a placeholder, so a code
path that tries to reach OpenRouter fails fast instead of spending. The fixture episodes are two stored race-15-fit2 rows
of agent 12a50f9c (agents/12a50f9c.py), pack suites/graded30_v2/packs/s14_r15_fit2, nonce 0.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PACKS = REPO / "suites" / "graded30_v2" / "packs"
FIXTURE = REPO / "tests" / "fixtures" / "r15fit2_12a50f9c_n0.jsonl.gz"
FIXTURE_AGENT = REPO / "agents" / "12a50f9c.py"
FIXTURE_PACK = PACKS / "s14_r15_fit2"
IDENTICAL_TASK = "t-31117d3b7b"  # 1 injected 503; replays bit-identically
DIVERGENT_TASK = "t-67309e70a1"  # 3 injected 503s; pre-branch replay does not re-inject them (see test_replay_identity)

OFFLINE_ENV = {
    "HTTPS_PROXY": "http://127.0.0.1:9",
    "HTTP_PROXY": "http://127.0.0.1:9",
    "https_proxy": "http://127.0.0.1:9",
    "http_proxy": "http://127.0.0.1:9",
    "NO_PROXY": "",
    "no_proxy": "",
    "OPENROUTER_API_KEY": "offline-test-placeholder",
    "SN15_WORLD_LIVE_LABELERS": "0",
}
os.environ.update(OFFLINE_ENV)
sys.path.insert(0, str(REPO / "simrace"))
sys.path.insert(1, str(REPO / "vendor" / "rt401"))  # world_sim puts ~/sn15-ops/venvs/rt401 (ci/prepare.sh) first; this is the fallback


@pytest.fixture(scope="session")
def world_sim():
    import world_sim as ws

    return ws


@pytest.fixture(scope="session")
def stored_rows() -> dict[str, dict]:
    with gzip.open(FIXTURE, "rt", encoding="utf-8") as fh:
        rows = [json.loads(l) for l in fh if l.strip()]
    return {r["task_id"]: r for r in rows}


def spend_note(row: dict) -> dict:
    """The agent's own end-of-episode meter (`[agent_s stats]` spend dialogue entry)."""
    return [d for d in row.get("dialogue") or [] if isinstance(d, dict) and d.get("kind") == "spend"][-1]

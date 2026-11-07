"""Pack integrity and grader oracle ($0): every pack verifies, its answer key resolves, and the pack's own grader re-grades
stored ledgers to the stored verdict."""
from __future__ import annotations

import copy
import json
import re
import sys

import pytest

from conftest import FIXTURE_PACK, PACKS, REPO

PACK_DIRS = sorted(p for p in PACKS.iterdir() if (p / "manifest.json").is_file())
LISTING_ID = re.compile(r"p-[0-9a-f]{12}")


@pytest.fixture(scope="module")
def runtime(world_sim):
    from oro_env_runtime.pack import load_pack
    from oro_env_runtime.session import _recorded_then, grade_episode

    return load_pack, grade_episode, _recorded_then, world_sim.SIM_KEYRING


@pytest.mark.parametrize("pack_dir", PACK_DIRS, ids=[p.name for p in PACK_DIRS])
def test_pack_verifies_and_answer_key_resolves(runtime, pack_dir):
    """load_pack checks the signature and the sha256 of every part (a git eol/lfs rewrite or a partial sync fails here)."""
    load_pack, _, _, keyring = runtime
    pack = load_pack(pack_dir, keyring)
    assert pack.tasks, "pack has no tasks"
    assert set(pack.tasks) == set(pack.answers), "every task needs exactly one answer"
    assert len(pack.catalog) > 0
    for tid, ans in pack.answers.items():
        ids = set(LISTING_ID.findall(json.dumps(ans)))
        assert ids, f"{tid}: answer names no listing"
        missing = sorted(ids - set(pack.catalog))
        assert not missing, f"{tid}: answer names {len(missing)} listing(s) not in the catalog, e.g. {missing[:3]}"


@pytest.mark.parametrize("pack_dir", PACK_DIRS, ids=[p.name for p in PACK_DIRS])
def test_plan_sees_every_task(pack_dir):
    sys.path.insert(0, str(REPO / "ci"))
    import plan

    assert plan.pack_task_ids(pack_dir) == sorted(p.stem for p in (pack_dir / "tasks").glob("*.json"))
    assert set(plan.pack_task_ids(pack_dir)) == {p.stem for p in (pack_dir / "answers").glob("*.json")}


def test_grader_regrades_stored_ledgers_to_the_stored_verdict(runtime, stored_rows):
    """Oracle: the pack's grader, fed only the readings recorded in the stored ledger, returns the stored score, category
    and ledger / grading digests. A reading the ledger did not record raises instead of reaching a model."""
    load_pack, grade_episode, recorded_then, keyring = runtime
    pack = load_pack(FIXTURE_PACK, keyring)

    def no_live_reading(service, request):
        raise AssertionError(f"grader asked for a live {service} reading")

    for tid, row in stored_rows.items():
        ledger = copy.deepcopy(row["ledger"])
        verdict = grade_episode(pack, ledger, recorded_then(list(row["ledger"].get("grading") or []), no_live_reading))
        for key in ("score", "category", "ledger_sha256", "grading_sha256"):
            assert verdict[key] == row["verdict"][key], f"{tid}: {key} {verdict[key]!r} != stored {row['verdict'][key]!r}"

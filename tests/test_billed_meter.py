"""Branch spend restore ($0). BILLEDLINE1 (11-06): `_WorldEpisodeBridge.activate_branch()` overwrote the agent's `spend_usd`
with a LIST-price sum of the stored pre-branch calls, so an agent that meters cached prompt tokens at its own
CACHED_PROMPT_PRICE_PER_M started every branch about 0.03 USD over its line. The fix re-meters with the agent's constants."""
from __future__ import annotations

import sys
import time
import types

import pytest

from conftest import FIXTURE_AGENT, spend_note


@pytest.fixture(scope="module")
def agent(world_sim):
    mod, _legacy = world_sim._load_agent_module(FIXTURE_AGENT)
    assert getattr(mod, "CACHED_PROMPT_PRICE_PER_M", None), "fixture agent must meter cached prompt tokens"
    return mod


def _branch(world_sim, row: dict, model, n_used: int) -> None:
    """activate_branch() as if the first `n_used` stored (non-injected) calls had been served before the branch."""
    bridge = object.__new__(world_sim._WorldEpisodeBridge)
    bridge.branch_active = False
    bridge._branch_t0 = time.time()
    bridge.stored_row = row
    bridge.captured_ep = None
    bridge._pre_branch_trace = [{"idx": i, "used": True} for i in range(n_used)]
    bridge.session = types.SimpleNamespace(steps=0)
    bridge.pre_branch_cached_calls = 0
    bridge.activate_branch(types.SimpleNamespace(model=model))


def _fresh_model(cls):
    m = object.__new__(cls)
    m.spend_usd, m.list_usd, m.cached_tokens, m.completion_tokens = 0.0, 0.0, 0, 0
    return m


def _served(row: dict) -> list[dict]:
    return [m for m in row["agent_model_calls"] if not m.get("injected_failure")]


def test_full_trace_restores_the_agents_own_charged_meter(world_sim, agent, stored_rows):
    """Branching after the last stored call must leave spend_usd where the agent's own meter ended (`usd`, 5 decimals),
    not at the list-price sum (`usd_list`)."""
    for tid, row in stored_rows.items():
        note = spend_note(row)
        model = _fresh_model(agent.ModelClient)
        _branch(world_sim, row, model, len(_served(row)))
        assert model.spend_usd == pytest.approx(note["usd"], abs=6e-6), tid
        assert model.list_usd == pytest.approx(note["usd_list"], abs=6e-6), tid
        assert model.completion_tokens == note["completion_tokens"], tid
        assert model.spend_usd < 0.8 * model.list_usd, f"{tid}: restored spend is the list sum again"


def test_partial_branch_charges_cached_tokens_at_the_cached_price(world_sim, agent, stored_rows):
    row = stored_rows[sorted(stored_rows)[0]]
    served = _served(row)
    k = len(served) // 2
    want = 0.0
    for m in served[:k]:
        pt, ct, ca = int(m["pt"]), int(m["ct"]), min(int(m.get("cached") or 0), int(m["pt"]))
        mid = str(m.get("served") or m.get("model"))
        u_in, u_out = agent.PRICE_PER_M[mid]
        want += ((pt - ca) * u_in + ca * agent.CACHED_PROMPT_PRICE_PER_M.get(mid, u_in) + ct * u_out) / 1e6
    model = _fresh_model(agent.ModelClient)
    _branch(world_sim, row, model, k)
    assert model.spend_usd == pytest.approx(want, rel=1e-9)
    assert model.cached_tokens == sum(min(int(m.get("cached") or 0), int(m["pt"])) for m in served[:k])


def test_agent_without_cached_price_keeps_the_list_sum(world_sim, agent, stored_rows):
    """An agent that has PRICE_PER_M but no CACHED_PROMPT_PRICE_PER_M (the pre-BILLEDLINE1 meter) is restored at list price."""
    legacy = types.ModuleType("legacy_meter_agent")
    legacy.PRICE_PER_M = dict(agent.PRICE_PER_M)
    sys.modules[legacy.__name__] = legacy
    LegacyClient = type("LegacyClient", (), {"__module__": legacy.__name__})
    for tid, row in stored_rows.items():
        model = _fresh_model(LegacyClient)
        _branch(world_sim, row, model, len(_served(row)))
        assert model.spend_usd == pytest.approx(spend_note(row)["usd_list"], abs=6e-6), tid

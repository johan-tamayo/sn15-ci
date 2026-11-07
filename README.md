# sn15-ci (private)

GitHub-Actions runner for the SN15 (ORO) Design S store-only simulator reads (`simrace/world_sim.py`), so that 12-task
smokes and 90-episode two-nonce reads run on GitHub-hosted `ubuntu-latest` runners instead of our cloud hosts.

Driven from the Mac by `sn15 gh-run <agent_s.py> [--pack s14_r9] [--tasks ids|all] [--nonces 0,1] [--shards 10] [--label L]`
(`~/sn15-ops/tools/gh_run.py`), which commits the agent as `agents/<sha8>.py`, dispatches `.github/workflows/sim.yml`,
waits, and downloads `<label>_n0.jsonl` / `<label>_n1.jsonl` (+ `.log`, `.launch`) into `~/sn15-ops/runs/live/`.

Layout

| path | what |
|---|---|
| `simrace/world_sim.py` | byte copy of `~/sn15-ops/simrace/world_sim.py` (re-sync: `sn15 gh-run sync`) |
| `vendor/rt401/` | the `oro_env_runtime` 4.0.1 tree world_sim pins first on `sys.path` (`~/sn15-ops/venvs/rt401`); `ci/prepare.sh` copies it there on the runner |
| `requirements.txt` | `cryptography`, `starlark-pyo3` pinned from `~/sn15-ops/venvs/sn15venv` (the pack manifests pin the starlark-pyo3 version) |
| `suites/graded30_v2/packs/` | private store-only packs `s14_r9`, `s14_r8`, `s14_qual` (signed; `.gitattributes` keeps every byte) |
| `cache/claude_world_reader_cache.jsonl.gz` | seed of the shopper-reader cache (`~/.sn15-world-sim-cache/`), like `gsim_setup.sh` seeds the hosts |
| `agents/<sha8>.py` | agent files committed by the trigger (content-addressed, sha256[:8]) |
| `ci/plan.py`, `ci/run_shard.sh`, `ci/merge.py`, `ci/prepare.sh` | the three workflow jobs |
| `tests/`, `.github/workflows/tests.yml` | $0 regression tests (no model call, no secret, offline): pack signatures + answer keys, grader re-grade of stored ledgers, world_sim replay identity, branch spend restore, plan / merge, the run-name contract; runs on pull requests touching the simulator / ci / packs and on manual dispatch. Locally: `python -m pytest tests -q` |

Workflow `sim.yml` (`workflow_dispatch`): `plan` splits the task ids round-robin into `shards` per nonce -> `run` matrix
(max-parallel 20, 120 min per job, secret `OPENROUTER_API_KEY` as env; the Claude BYOK shopper reader and the agent's
calls both use that one key) -> `merge` concatenates the shards into `<label>_n<nonce>.jsonl` (sorted by task_id, exactly
one episode json per line as world_sim writes them) and uploads `merged-<label>` with `summary.json` / `summary.md`.

`live_labelers` defaults to `0`: every shopper call runs on the Claude BYOK reader. With `1` (the simulator's own default)
the pack's completion models (`google/gemma-4-31b-it`, `openai/gpt-oss-120b`, `meta-llama/llama-4-maverick`) are called
over OpenRouter, which bills prepaid credits; the decisions labeler (`typesafe/jev-1.13`) is never called in either mode.

Never commit secrets here. The packs are private test data: this repository must stay private.

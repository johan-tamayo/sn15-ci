#!/usr/bin/env bash
# Runner preparation (after `pip install -r requirements.txt`):
#  1. vendor/rt401 -> ~/sn15-ops/venvs/rt401  (world_sim.py hardcodes RT401_DIR there and puts it first on sys.path)
#  2. reader-cache seed  -> ~/.sn15-world-sim-cache/claude_world_reader_cache.jsonl (world_sim CACHE_DIR default)
#  3. import + `run --help` check, exactly like tools/gsim_setup.sh step 5 on the cloud hosts
set -euo pipefail
cd "$(dirname "$0")/.."
RT="$HOME/sn15-ops/venvs/rt401"
mkdir -p "$HOME/sn15-ops/venvs" "$HOME/sn15-ops/runs/tmp" "$HOME/.sn15-world-sim-cache"
rm -rf "$RT"
cp -r vendor/rt401 "$RT"
if [ -f cache/claude_world_reader_cache.jsonl.gz ]; then
  gunzip -c cache/claude_world_reader_cache.jsonl.gz > "$HOME/.sn15-world-sim-cache/claude_world_reader_cache.jsonl"
  echo "[prepare] reader cache seeded: $(wc -l < "$HOME/.sn15-world-sim-cache/claude_world_reader_cache.jsonl") rows"
fi
python - <<'PY'
import importlib.metadata, os, sys
sys.path.insert(0, os.path.expanduser("~/sn15-ops/venvs/rt401"))
import cryptography, starlark  # noqa: F401
import oro_env_runtime
from oro_env_runtime.session import Session, grade_episode  # noqa: F401
print("[prepare] python", sys.version.split()[0],
      "| cryptography", cryptography.__version__,
      "| starlark-pyo3", importlib.metadata.version("starlark-pyo3"),
      "| oro_env_runtime", importlib.metadata.version("oro-env-runtime"), "from", os.path.dirname(oro_env_runtime.__file__))
PY
python simrace/world_sim.py run --help > /dev/null
echo "[prepare] world_sim.py loads (run --help ok)"

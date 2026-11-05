#!/usr/bin/env bash
# One (nonce, shard) job: run world_sim on the shard's task ids, keep the streamed jsonl + log + a meta json in out/.
# usage: ci/run_shard.sh <agent.py> <pack_dir> <nonce> <shard>
# env:   SHARD_TASKS (csv), WORKERS, FAILURE_RATE, OPENROUTER_API_KEY (secret), SN15_WORLD_LIVE_LABELERS
set -uo pipefail
cd "$(dirname "$0")/.."
agent="$1"; pack="$2"; nonce="$3"; shard="$4"
mkdir -p out
out="out/out_${nonce}_${shard}.jsonl"
log="out/out_${nonce}_${shard}.log"
meta="out/meta_${nonce}_${shard}.json"
n_tasks=$(printf '%s' "${SHARD_TASKS:-}" | tr ',' '\n' | grep -c . || true)
workers="${WORKERS:-4}"
if [ "$n_tasks" -gt 0 ] && [ "$n_tasks" -lt "$workers" ]; then workers="$n_tasks"; fi
[ -n "${OPENROUTER_API_KEY:-}" ] || { echo "[shard] OPENROUTER_API_KEY secret is not set" | tee "$log"; exit 2; }
echo "[shard] nonce=$nonce shard=$shard tasks=$n_tasks workers=$workers failure_rate=${FAILURE_RATE:-0.07} live_labelers=${SN15_WORLD_LIVE_LABELERS:-1} agent=$agent pack=$pack"
t0=$(date +%s)
python simrace/world_sim.py run \
  --agent "$agent" --pack "$pack" --tasks "${SHARD_TASKS:-}" --nonce "$nonce" --workers "$workers" \
  --inference-failure-rate "${FAILURE_RATE:-0.07}" --out "$out" > "$log" 2>&1
rc=$?
t1=$(date +%s)
rows=0; [ -f "$out" ] && rows=$(grep -c . "$out" || true)
python3 - "$meta" "$nonce" "$shard" "$rc" "$t0" "$t1" "$n_tasks" "$rows" "$workers" <<'PY'
import json, platform, sys
m, nonce, shard, rc, t0, t1, n_tasks, rows, workers = sys.argv[1:]
json.dump({"nonce": nonce, "shard": int(shard), "rc": int(rc), "started_at": int(t0), "ended_at": int(t1),
           "wall_s": int(t1) - int(t0), "n_tasks": int(n_tasks), "rows": int(rows), "workers": int(workers),
           "runner": platform.platform(), "cpus": __import__("os").cpu_count()}, open(m, "w"), indent=1)
PY
echo "[shard] rc=$rc wall=$((t1 - t0))s rows=$rows/$n_tasks"
echo "--- tail of $log ---"
tail -n 40 "$log" || true
exit "$rc"

#!/usr/bin/env bash
# Larger cross-model runs (100 docs) for VLDB rebuttal: Qwen3-32B + Kimi-K2.
# Usage:
#   tmux new -d -s xmodel "bash scripts/run_crossmodel_medium.sh"

set -uo pipefail
cd "$(dirname "$0")/.."

LOG=logs/crossmodel_medium.log
mkdir -p logs
echo "[xmodel] start at $(date)" | tee -a "$LOG"

export PYTHONUNBUFFERED=1
python -u scripts/heartbeat.py 60 2>&1 | tee -a "$LOG" &
HB_PID=$!
trap 'kill $HB_PID 2>/dev/null || true' EXIT INT TERM

run_smoke () {
  local model="$1" runname="$2"
  echo "" | tee -a "$LOG"
  echo "[xmodel] === $runname ($model) ===" | tee -a "$LOG"
  OPENAI_MODEL="$model" python scripts/run_paper_experiment.py \
    --config configs/experiments/docred_paper.yaml --profile medium \
    --run-name "$runname" --fresh --stop-after viz \
    2>&1 | tee -a "$LOG"
  rc=$?; echo "[xmodel] $runname rc=$rc" | tee -a "$LOG"
  python scripts/visualize_contracts.py --run-dir "reports/runs/$runname" \
    2>&1 | tee -a "$LOG" || true
}

run_smoke "qwen3-32b"                   "docred_qwen3_medium"
run_smoke "Moonshot-Kimi-K2-Instruct"   "docred_kimi_medium"

echo "[xmodel] re-aggregating cross-run summary" | tee -a "$LOG"
python scripts/aggregate_cross_run.py 2>&1 | tee -a "$LOG" || true

# Recompute K6 with the larger pool
python scripts/run_k5_cross_model.py 2>&1 | tee -a "$LOG" || true
python scripts/compute_amp_ci.py 2>&1 | tee -a "$LOG" || true

echo "[xmodel] done at $(date)" | tee -a "$LOG"

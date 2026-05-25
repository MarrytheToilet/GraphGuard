#!/usr/bin/env bash
# Round-7 full re-run on the new Aliyun MaaS token-plan endpoint.
#
# Datasets (4): DocRED, Re-DocRED, SciERC, BC5CDR (new biomedical).
# Models (5):   glm-5, kimi-k2.5, MiniMax-M2.5, deepseek-v4-flash, qwen3.6-flash.
#
# Allocation:
#   * Primary  = deepseek-v4-flash  on every dataset at main300 (300 docs).
#   * Cross-model: the other four models each on DocRED at medium (100 docs).
#
# Usage:
#   tmux new -d -s v5 "bash scripts/run_full_v5.sh"
#   tmux attach -t v5         # to watch
#   tail -f logs/full_v5.log

set -uo pipefail
cd "$(dirname "$0")/.."

LOG=logs/full_v5.log
mkdir -p logs reports/cross_run reports/runs_v5
echo "[v5] start at $(date)" | tee -a "$LOG"

export PYTHONUNBUFFERED=1

python -u scripts/heartbeat.py 60 2>&1 | tee -a "$LOG" &
HB_PID=$!
trap 'kill $HB_PID 2>/dev/null || true' EXIT INT TERM

stage () {
  echo "" | tee -a "$LOG"
  echo "[v5] === $* ===  ($(date +%H:%M:%S))" | tee -a "$LOG"
}

run () {
  local cfg="$1" profile="$2" runname="$3" model="$4"
  stage "$runname  ($model · $profile)"
  OPENAI_MODEL="$model" python scripts/run_paper_experiment.py \
    --config "$cfg" --profile "$profile" \
    --run-name "$runname" --fresh --stop-after viz \
    2>&1 | tee -a "$LOG"
  rc=$?; echo "[v5] $runname rc=$rc" | tee -a "$LOG"
  python scripts/visualize_contracts.py --run-dir "reports/runs/$runname" \
    2>&1 | tee -a "$LOG" || true
}

PRIMARY=deepseek-v4-flash

# --- 1. Primary: deepseek-v4-flash @ main300 on all 4 datasets ---
run configs/experiments/docred_paper.yaml    main300 docred__deepseek-v4-flash__300d    "$PRIMARY"
run configs/experiments/redocred_paper.yaml  main300 redocred__deepseek-v4-flash__300d  "$PRIMARY"
run configs/experiments/scierc_smoke.yaml    main300 scierc__deepseek-v4-flash__50d    "$PRIMARY"
run configs/experiments/cdr_paper.yaml       main300 cdr__deepseek-v4-flash__300d       "$PRIMARY"

# --- 2. Cross-model on DocRED (medium = 100 docs) ---
run configs/experiments/docred_paper.yaml    medium  docred__glm-5__100d       glm-5
run configs/experiments/docred_paper.yaml    medium  docred_v5_kimi25     kimi-k2.5
run configs/experiments/docred_paper.yaml    medium  docred_v5_minimax25  MiniMax-M2.5
run configs/experiments/docred_paper.yaml    medium  docred_v5_qwen36     qwen3.6-flash

# --- 3. Aggregate cross-run summary ---
stage "aggregate cross-run summary"
python scripts/aggregate_cross_run.py 2>&1 | tee -a "$LOG" || true

# --- 4. K5 cross-model recall stability ---
stage "K5 cross-model recall stability"
python scripts/run_k5_cross_model.py 2>&1 | tee -a "$LOG" || true

# --- 5. Bootstrap Amp CIs on DocRED main ---
stage "bootstrap Amp CIs"
python scripts/compute_amp_ci.py 2>&1 | tee -a "$LOG" || true

# --- 6. Per-dataset post-processing (monitoring / budget / SLA / e2e QA) ---
post () {
  local rn="$1"
  local db="data/processed/runs/$rn/$rn.db"
  if [[ ! -f "$db" ]]; then
    echo "[v5] post: skip $rn (no db)" | tee -a "$LOG"; return
  fi
  stage "post-process: $rn"
  python scripts/run_monitoring_baselines.py --db "$db" \
    --out "reports/cross_run/monitoring_${rn}.json" 2>&1 | tee -a "$LOG" || true
  python scripts/run_budget_stopping.py --db "$db" \
    --out "reports/cross_run/budget_${rn}.json" 2>&1 | tee -a "$LOG" || true
  python scripts/run_threshold_sla.py --db "$db" \
    --out "reports/cross_run/sla_${rn}.json" 2>&1 | tee -a "$LOG" || true
  python scripts/run_e2e_qa.py --db "$db" 2>&1 | tee -a "$LOG" || true
  mv -f reports/cross_run/e2e_qa.json "reports/cross_run/e2e_qa_${rn}.json" 2>/dev/null || true
}
post docred__deepseek-v4-flash__300d
post redocred__deepseek-v4-flash__300d
post scierc__deepseek-v4-flash__50d
post cdr__deepseek-v4-flash__300d

# --- 7. Regenerate paper figures ---
stage "regenerate paper figures"
python scripts/make_paper_figures.py 2>&1 | tee -a "$LOG" || true

echo "[v5] done at $(date)" | tee -a "$LOG"

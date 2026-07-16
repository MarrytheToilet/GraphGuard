# Scripts

Operational entry points for the GraphGuard pipeline, grouped by stage.
Anything not listed here has been retired.

## End-to-end driver
- `run_paper_experiment.py` — orchestrator for a single paper run; drives the
  stage scripts below in order
  (`prepare → extract → interventions → oracle → main → score → baselines → e0 → evals → report → viz`).

## Pipeline stages (invoked by the driver)
- `prepare_docred.py` — convert DocRED/Re-DocRED/SciERC/BC5CDR corpora to the internal format.
- `run_extract.py` — primary LLM extraction loop.
- `generate_interventions.py` — generate perturbation specs.
- `run_planners.py` — materialize counterfactuals under a budgeted planner
  (`exhaustive` for the oracle subset, `graphguard` for the main audit set).
- `compute_scores.py` — per-pair monitor scores.
- `run_baselines.py` — no-LLM baseline detectors (confidence, co-occurrence, ...).
- `run_e0_stability.py` — repeated no-op extraction for the stochastic baseline.
- `run_contracts.py` — evaluate the drift-contract catalogue on a run.
- `run_repair.py` — repair / filtering-strategy evaluation.
- `run_matching_validation.py` — entity-alias matching validation.
- `make_report.py` — human-readable per-run report.
- `visualize.py` — per-run diagnostic figures.

## Cross-run analyses (write `reports/cross_run/*.json`)
- `aggregate_cross_run.py` — pool per-corpus runs into the cross-run summary.
- `compute_amp_ci.py` — bootstrap CIs for query amplification.
- `run_k5_cross_model.py` — cross-model recall-stability contract.
- `run_e2e_qa.py` — downstream QA regression pipeline
  (query workload lives in `graphguard/qa.py`).
- `run_e2e_kuzu_case_study.py` — Kuzu release-gate experiment.
- `run_graph_vs_query_ablation.py` — query-aware vs graph-only contract ablation.
- `run_baselines_matched.py` — matched-alarm baseline comparison.
- `run_monitoring_baselines.py` — confidence-only / self-consistency / graph-only monitors.
- `run_nli_baseline.py` — NLI triple-verification baseline.
- `run_threshold_sla.py` — SLA threshold sweep.
- `run_budget_stopping.py` — CI-based early stopping.

## Paper artifacts (consume cached `reports/`; no LLM calls)
- `make_paper_figures.py` — **unified entry point for paper figures** (cross-run
  violation heatmap, Amp(Q) consistency, strict-vs-soft bars, calibration,
  noise floor, 2-D sensitivity, AUROC/AUPRC). CLI targets:
  `replacement`, `phase_w`, `all`.
- `make_kuzu_gate_artifacts.py` — risk-coverage figure + Kuzu gate table.
- `run_budget_planner.py` — budget-planner figure (greedy / balanced / random / oracle).
- `make_baseline_table.py` — baseline LaTeX tables.

## Tools
- `query.py` — small CLI for inspecting a run DB.
- `visualize_contracts.py` — ad-hoc per-run contract plots.
- `heartbeat.py` — long-run progress monitor for background extractions.

## Shell drivers
- `run_crossmodel_medium.sh` — 100-doc cross-model runs on DocRED.

## Conventions
All Python scripts assume the repo root is on `PYTHONPATH` and read inputs from
`reports/cross_run/` and `data/processed/runs/`; paper figures land in
`assets/figures/`.

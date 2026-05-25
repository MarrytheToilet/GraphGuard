# Scripts

Operational entry points for the GraphGuard pipeline, grouped by stage.
Anything not listed has been retired in the 2025-Q2 cleanup.

## Data preparation
- `prepare_docred.py` — convert DocRED/Re-DocRED JSON to internal format.
- `clone_db_for_model.py` — clone a base run DB to a new extractor tag.

## Extraction
- `run_extract.py` — primary LLM extraction loop.
- `run_multi_model.py`, `run_multi_model_full.py` — cross-model extraction wrappers.
- `run_counterfactuals.py` — materialize counterfactual paired views.
- `generate_interventions.py` — generate perturbation specs.
- `heartbeat.py` — long-run progress monitor for background extractions.

## Contracts and scoring
- `run_contracts.py` — evaluate the drift-contract catalogue on a run.
- `compute_scores.py` — per-pair monitor scores.
- `compute_amp_ci.py` — bootstrap CIs for query amplification.
- `run_k5_cross_model.py` — K5 cross-model contract.
- `run_matching_validation.py` — entity-alias matching validation.

## Baselines and monitoring
- `run_baselines.py` — no-LLM baseline detectors (confidence, co-occurrence, ...).
- `run_baselines_matched.py` — matched-alarm baseline comparison.
- `run_monitoring_baselines.py` — confidence-only / self-consistency / graph-only.
- `run_nli_baseline.py` — NLI triple-verification baseline.
- `run_graph_vs_query_ablation.py` — query-aware vs graph-only contract ablation.

## Calibration and planning
- `run_threshold_sla.py` — two-dimensional (τ\_g, τ\_q) sensitivity sweep.
- `run_planners.py` — budget-aware planner comparison.
- `run_budget_planner.py` — paper Figure 13 (greedy / balanced / random / oracle).
- `run_budget_stopping.py` — CI-based early stopping.

## End-to-end / case studies
- `run_e2e_kuzu_case_study.py` — Kuzu release gate experiment.
- `run_e2e_qa.py` — downstream QA pipeline.
- `run_paper_experiment.py` — orchestrator for a single paper run.
- `run_repair.py` — recover partial runs.

## Aggregation, reporting, paper artifacts
- `aggregate_cross_run.py` — pool per-corpus runs into the cross-run summary.
- `make_report.py` — human-readable per-run report.
- `make_baseline_table.py` — baseline LaTeX tables.
- `make_kuzu_gate_artifacts.py` — paper Figure 9 (risk-coverage) + Kuzu gate table.
- `make_paper_figures.py` — **unified entry point for paper figures** (cross-run
  violation heatmap, Amp(Q) consistency, strict-vs-soft bars, calibration,
  noise floor, 2-D sensitivity, AUROC/AUPRC). CLI targets:
  `replacement`, `phase_w`, `all`.
- `visualize.py`, `visualize_contracts.py` — ad-hoc diagnostic plots.
- `query.py` — small CLI for inspecting a run DB.

## Shell drivers
- `run_full_v5.sh` — Round-7 full re-run on Aliyun MaaS.
- `run_crossmodel_medium.sh` — 100-doc cross-model runs.

## Conventions
All Python scripts assume the repo root is on `PYTHONPATH` and read inputs from
`reports/cross_run/` and `data/processed/runs/`, writing figures to
`paper/figures/` and tables to `paper/tables/`.

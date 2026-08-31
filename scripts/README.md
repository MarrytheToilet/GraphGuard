# Scripts

Operational entry points for the GraphGuard pipeline, grouped by stage.
Anything not listed here has been retired.

## End-to-end driver
- `run_paper_experiment.py` — orchestrator for a single paper run; drives the
  stage scripts below in order
  (`prepare → extract → interventions → oracle → main → e0 → contracts`).

## Pipeline stages (invoked by the driver)
- `prepare_docred.py` — convert DocRED/Re-DocRED/SciERC/BC5CDR corpora to the internal format.
- `run_extract.py` — primary LLM extraction loop.
- `generate_interventions.py` — generate perturbation specs.
- `run_planners.py` — materialize counterfactuals under a budgeted planner
  (`exhaustive` for the oracle subset, `graphguard` for the main audit set).
- `run_e0_stability.py` — repeated no-op extraction for the stochastic baseline.
- `run_contracts.py` — evaluate the drift-contract catalogue on a run.

## Cross-run analyses (write `reports/cross_run/*.json`)
- `aggregate_cross_run.py` — pool per-corpus runs into the cross-run summary.
- `run_diagnostic_queries.py` — evaluate canonical graph-wide diagnostics
  D1–D5 on every authoritative materialized pair and compute document-cluster
  bootstrap CIs.
- `compute_amp_ci.py` — compact the canonical D1–D5 artifacts for paper
  figures and the human-readable amplification table.
- `run_k5_cross_model.py` — cross-model recall-stability contract.
- `run_graph_vs_query_ablation.py` — query-aware vs graph-only contract ablation.
- `run_endpoint_reuse_analysis.py` — compare independent per-contract
  materialization with the unique endpoint-union plan, using both calls and
  observed token volume on the four primary runs.

## Deployment workload (RQ8--RQ10)
- `run_deployment_queries.py` — execute the deterministic deployment Q1--Q4
  workload over the four primary lineage DBs.
- `validate_deployment_kuzu_parity.py` — compare the deterministic executor
  with Kuzu 0.11.3 on the registered parity cohort.
- `run_deployment_downstream.py` — derive the schema-eligible downstream
  pair population from Q1--Q4 results and checked parity records.
- `build_deployment_cohorts.py` — build the label-blind RQ8 anchored
  cohort and the four N=300 RQ10 cohorts.
- `run_deployment_kuzu_cohort.py` — execute every registered RQ10 pair and query
  in Kuzu and record complete per-pair aggregates.
- `package_deployment_evidence.py` — maintainer tool that deterministically
  compresses and hash-indexes the 17 registered artifacts after their logical
  JSON sources have been rebuilt.

## Additional analyses
- `run_magnitude_analysis.py` — controlled nested token attenuation for schema
  descriptions, prompt instructions, and evidence text (Sec. 5.5 / Fig. 7).
  `--run-controlled` performs the API-backed extraction, `--analyze-only`
  rebuilds reports from its raw checkpoint, and `--fig-only` rebuilds the
  figure from cached `reports/cross_run/magnitude_*.json`. Each report also
  gives the pooled document-fixed-effects slope in graph drift per additional
  0.10 of realized masking, with a document-cluster bootstrap interval.
- `run_extended_queries.py` — extended query templates Q5–Q7 (shortest path,
  aggregation, GraphRAG retrieval) on all materialized pairs (Sec. 6.1 / Fig. 9a).
- `run_cross_document_experiment.py` — registered BC5CDR two-document
  joint-context stress test with oracle MeSH linking, source-provenance-aware
  fanout/shared-tail queries, an alternate-seed reference, and Kuzu 0.11.3
  parity (Sec. 6.1). `--analyze-only` reads the registered BC5CDR source and
  CDR lineage DB to reconstruct the cohort and historical per-document
  baseline. It makes no API call, but the historical runner still requires the
  registered model and endpoint fingerprints in the maintainer environment.
- `package_cross_document_checkpoint.py` — strips provider response text from
  the append-only cross-document checkpoint while retaining normalized edges,
  endpoint fingerprints, token counts, and status history. It verifies the
  private manifest hash, rebinds the result to the byte-identical public
  manifest, and commits the hash audit last for fail-closed verification.
- `run_graph_vs_query_ablation.py` — graph-only, mean-query, and maximum-query
  scores for the RQ9 mean-change target, with threshold-free metrics and exact
  30/50/70/90% review budgets (Sec. 6.3).
- `run_regime_analysis.py` — the same exact-budget comparison split into local
  and multi-hop registered workloads (Sec. 6.2 / Fig. 9b).
- `run_drift_accuracy_analysis.py` — deterministic DocRED query-divergence
  correlations from the registered RQ8 cohort and the K1 accuracy contrast from
  the DocRED lineage DB (Sec. 6.2).
- `run_stability_bucket_analysis.py` — deterministic L1/L2/L3 stability
  buckets and query-divergence rates (Sec. 5.4 / Fig. 6); also refreshes the
  corresponding LaTeX table.
- `export_sampled_document_ids.py` — export the exact ordered document samples
  for the four primary and three cross-model runs.
- `run_family_decomposition.py` — repeated-extraction decomposition extended to
  every perturbation family (Sec. 5.1 / Table 5).
- `run_langchain_toolchain.py` — LangChain `LLMGraphTransformer`
  external-toolchain run (Sec. 5.6 / Table 6); `--analyze-only` replays the
  published checkpoint without API credentials, while extraction needs them.
- `run_additional_toolchains.py` — Neo4j GraphRAG
  `LLMEntityRelationExtractor` external-toolchain run (Sec. 5.6 / Table 6);
  `--analyze-only` replays its published checkpoint without API credentials.
- `run_external_toolchain_queries.py` — maps both published external-toolchain
  outputs into one exact-name/declared-alias identifier namespace, materializes
  every successful endpoint in Kuzu 0.11.3, executes the shared Q1–Q4
  catalogue, and checks every answer set against the deterministic executor
  (Sec. 5.6 / Table 6).
- `run_model_size_k5.py` — K5 across the Qwen3 size ladder (Sec. 5.2).
- `run_model_size_k5_expressible.py` — K5 ladder with gold restricted to the
  declared schema relations (metric-ceiling sensitivity, Sec. 5.2).
- `run_gate_split_analysis.py` — release-gate calibration/deployment split:
  thresholds selected on a 50/50 document-level calibration half, frozen, and
  evaluated held-out (Sec. 6.4; consumes the registered Kuzu cohort package).

## Paper artifacts (consume cached `reports/`; no LLM calls)
- `build_reproducibility_manifest.py` — sole producer of the seven-run
  provenance manifest; records named lineage DB paths, hashes, sizes, counts,
  and the four repeated-extraction baselines.
- `verify_paper_results.py` — validates the deployment evidence package,
  reconstructs every RQ9 fixed-budget cell from the registered pair records,
  and checks the paper's headline claims; `--lineage` additionally recounts
  events, edges, counterfactual views, and tokens from the seven local run
  databases.
- `verify_manuscript_artifacts.py` — final-mile checker for the private,
  git-ignored manuscript: validates all 13 figure copies, the active
  source-backed tables, and the RQ9 statements shared by `main.tex`,
  `response.tex`, and the root README.
- `sync_paper_figures.py` — checks the 13 `assets/figures` ↔ `paper/figures`
  pairs byte-for-byte; `--write` performs the explicit copy.
- `make_paper_figures.py` — entry point for seven paper figures (cross-run
  violation heatmap, Amp(Q) consistency, strict-vs-soft bars, calibration,
  noise floor, 2-D sensitivity, AUROC/AUPRC). CLI targets:
  `contracts`, `evaluation`, `all`.
- `make_kuzu_gate_artifacts.py` — risk-coverage figure (paper Fig. 12, top) + the
  per-policy gate table shipped as an artifact.
- `run_budget_planner.py` — budget-planner curves (greedy / balanced / random / oracle;
  paper Fig. 12, bottom).
- `make_gate_figure.py` — release-gate outcome bars (paper Fig. 11).
- `make_extqueries_figure.py` — extended-template amplification + regime
  dumbbells (paper Fig. 9).

`fig_contract_overview.pdf` is an author-created conceptual vector figure; it
is the only active paper figure without a code producer.
`verify_manuscript_artifacts.py` still includes it in the canonical-asset hash
check.

## Tools
- `visualize_contracts.py` — ad-hoc per-run contract plots.
- `heartbeat.py` — long-run progress monitor for background extractions.

## Conventions
All Python scripts assume the repo root is on `PYTHONPATH` and read inputs from
`reports/cross_run/` and `data/processed/runs/`; paper figures land in
`assets/figures/`. Run `python scripts/sync_paper_figures.py --write` before
`paper/build.sh`, then run `python scripts/verify_manuscript_artifacts.py`.
The reported Kuzu workload uses the exact dependency pin `kuzu==0.11.3` from
`pyproject.toml`.

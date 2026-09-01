# Drift Contracts for Stochastic Graph Views Extracted by LLMs [Experiment, Analysis & Benchmark]

GraphGuard is the implementation and reproducibility artifact for this paper. It treats graphs extracted by large language models as persistent materialized views and checks whether their structure and query answers remain stable under declared extraction-configuration changes.

GraphGuard provides declarative drift contracts, lineage-aware reuse of paired counterfactual views, graph- and query-level diagnostics, and a Kuzu-backed release-gating evaluation.

![GraphGuard overview](assets/pr_fig.png)

## Overview

A drift contract combines:

- a controlled perturbation family, such as schema presentation, prompt presentation, evidence order, model choice, or decoding resampling;
- a graph- or query-level drift metric; and
- an invariance or bounded-drift expectation.

The checker materializes the required counterfactual graph views, reuses shared endpoints across contracts and queries, reports violations by perturbation family, and evaluates whether graph and answer-set drift can identify harmful re-extractions before Kuzu ingestion.

The study covers four graph-extraction benchmarks and four LLM extractors, with additional tests on the LangChain `LLMGraphTransformer` and Neo4j GraphRAG `LLMEntityRelationExtractor` components.

## Main results

- Controlled decoding resamples retain a mean edge overlap of 0.57 on DocRED and Re-DocRED, showing substantial stochastic variation even when the document and intended extraction task are fixed.
- LangChain and Neo4j GraphRAG exhibit the same qualitative instability as the primary pipeline. Mean graph drift is 0.59–0.65 and 0.43–0.62, respectively, across the five tested perturbation axes.
- Query behavior can amplify or absorb structural drift. Query-mean AUROC is 0.90–0.99, compared with 0.61–0.91 for graph drift; at identical review budgets, it improves 14 of 16 corpus–budget cells and ties in two. The local and multi-hop workload splits improve 28 of 32 cells and tie in four.
- In the Kuzu-backed release-gating evaluation, combining graph and answer-set drift reduces harmful publications from 20–30% to 0–13% at the selected operating point and to 0–8% on held-out documents, with paired-view F1 fidelity of at least 0.96.

The complete paper-facing results are stored in `reports/runs/` and `reports/cross_run/` and checked directly by the verification script below.

## Quick verification

GraphGuard targets Python 3.10. The locked environment includes Kuzu 0.11.3, the version used in the reported database experiments.

```bash
uv sync --locked --extra dev
uv run pytest -q
uv run python scripts/verify_paper_results.py
```

The last command checks the committed result artifacts and headline claims without raw corpora, local lineage databases, or API credentials.

For maintainers with the seven local lineage databases:

```bash
uv run python scripts/verify_paper_results.py --lineage
```

## Reproducibility paths

| Path | Required inputs | Purpose |
| --- | --- | --- |
| Cached-artifact verification | Repository checkout | Verify reported results and generated-figure inputs |
| Lineage re-analysis | Seven local SQLite lineage databases | Recount runs and recompute pair-level analyses |
| End-to-end extraction | Raw corpora, API credentials, and locked environment | Rebuild extraction events and downstream artifacts |

The submitted numbers are reproduced from the committed artifacts or local lineage databases. Hosted model APIs may remain nondeterministic even with fixed decoding parameters, so a fresh extraction is a behavioral replication rather than a bitwise reconstruction.

Three files provide the main evidence index:

- `reports/cross_run/reproducibility_manifest.json` records the registered runs and stochastic baselines.
- `reports/cross_run/sampled_document_ids.json` records the exact document samples.
- `reports/cross_run/deployment_evidence.json` indexes the RQ8–RQ10 workload and gate artifacts.

## Result-to-script map

| Result family | Main producer or analysis entry point | Canonical output |
| --- | --- | --- |
| Base runs and drift contracts | `run_paper_experiment.py`, `run_e0_stability.py`, `run_contracts.py`, `aggregate_cross_run.py` | `reports/runs/`, `cross_run_summary.json` |
| Perturbation magnitude | `run_magnitude_analysis.py` | `magnitude_*.json` |
| Query amplification and Q5–Q7 | `run_diagnostic_queries.py`, `compute_amp_ci.py`, `run_extended_queries.py` | `diagnostic_*.json`, `amp_ci.json`, `extqueries_*.json` |
| Cross-document workload | `run_cross_document_experiment.py` | `cross_document_cdr*.json` |
| Query-aware analysis | `run_graph_vs_query_ablation.py`, `run_regime_analysis.py`, `run_drift_accuracy_analysis.py` | `graph_vs_query_*.json`, `regimes_*.json`, `drift_accuracy_*.json` |
| Kuzu gate and planner | `run_deployment_kuzu_cohort.py`, `package_deployment_evidence.py`, `run_gate_split_analysis.py`, `run_budget_planner.py` | `deployment_evidence.json`, `gate_split.json`, `budget_planner.json` |
| External extraction components | `run_langchain_toolchain.py`, `run_additional_toolchains.py`, `run_external_toolchain_queries.py` | `langchain_toolchain.json`, `neo4j_toolchain.json`, `external_toolchain_q1q4_kuzu.json` |
| Paper figures and verification | `make_paper_figures.py` and the specialized figure scripts below | `assets/figures/` |

See [`scripts/README.md`](scripts/README.md) for the complete script inventory, required inputs, and command-line options.

## Rebuild generated figures

The following commands use the committed artifacts and do not call an LLM API:

```bash
uv run python scripts/make_paper_figures.py
uv run python scripts/run_magnitude_analysis.py --fig-only
uv run python scripts/make_extqueries_figure.py
uv run python scripts/make_gate_figure.py
uv run python scripts/make_kuzu_gate_artifacts.py
uv run python scripts/run_budget_planner.py
uv run python scripts/verify_paper_results.py
```

The generated data figures are exported as vector PDFs with PNG previews under `assets/figures/`.

## Dataset setup

Raw corpora are not redistributed because they retain their original licenses. They are needed only for end-to-end extraction; cached verification and figure rebuilding use the committed reports.

| Corpus | Expected location | Source |
| --- | --- | --- |
| DocRED | Downloaded through the `docred` Hugging Face dataset adapter | [Hugging Face](https://huggingface.co/datasets/docred) |
| Re-DocRED | `data/raw/redocred/{train,dev}_revised.json` | [Re-DocRED](https://github.com/tonytan48/Re-DocRED) |
| SciERC | `data/raw/scierc/processed_data/json/{train,dev,test}.json` | [SciERC release](http://nlp.cs.washington.edu/sciIE/data/sciie.tar.gz) |
| BC5CDR | `data/raw/cdr/CDR_Data/CDR.Corpus.v010516/` | [BioCreative V CDR](https://biocreative.bioinformatics.udel.edu/tasks/biocreative-v/track-3-cdr/) |

The DocRED checksum refers to the local mirror created by the preparation stage. Run the DocRED preparation command in the next section before checking all inputs.

## End-to-end extraction

Copy `.env.example` to `.env` and set `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`. Load the variables before commands that call the hosted model API:

```bash
cp .env.example .env
# Edit .env, then:
set -a && . ./.env && set +a
```

Exact verification and fresh extraction are different paths. The committed artifacts reproduce the submitted numbers. A fresh API run rebuilds the same experiment structure but may produce different samples because hosted models are not bitwise deterministic.

### 1. Primary extraction runs

First create the DocRED mirror used by `data/CHECKSUMS.sha256`, then verify all four corpora:

```bash
uv run python scripts/run_paper_experiment.py \
  --config configs/experiments/docred_paper.yaml \
  --profile main300 \
  --run-name docred__deepseek-v4-flash__300d \
  --model deepseek-v4-flash \
  --workers 8 \
  --stop-after prepare

sha256sum --check data/CHECKSUMS.sha256
```

Run the four primary experiments:

<details>
<summary>Primary run commands</summary>

```bash
uv run python scripts/run_paper_experiment.py \
  --config configs/experiments/docred_paper.yaml \
  --profile main300 \
  --run-name docred__deepseek-v4-flash__300d \
  --model deepseek-v4-flash \
  --workers 8 \
  --start-at extract

uv run python scripts/run_paper_experiment.py \
  --config configs/experiments/redocred_paper.yaml \
  --profile main300 \
  --run-name redocred__deepseek-v4-flash__300d \
  --model deepseek-v4-flash \
  --workers 8

uv run python scripts/run_paper_experiment.py \
  --config configs/experiments/scierc_paper.yaml \
  --profile main100 \
  --run-name scierc__deepseek-v4-flash__100d \
  --model deepseek-v4-flash \
  --workers 8

uv run python scripts/run_paper_experiment.py \
  --config configs/experiments/cdr_paper.yaml \
  --profile main300 \
  --run-name cdr__deepseek-v4-flash__300d \
  --model deepseek-v4-flash \
  --workers 8
```

</details>

Each driver executes `prepare → extract → interventions → oracle → main → e0 → contracts`. Outputs are written to `data/processed/runs/<run-name>/` and `reports/runs/<run-name>/`. Completed extraction events are reused; use `--start-at <stage>` to resume. Use `--fresh` only when intentionally discarding a local run database.

### 2. Cross-model and model-size runs

The three 100-document cross-model runs are needed by K5, the seven-run manifest, query amplification, and sample export.

<details>
<summary>Cross-model and Qwen3 size commands</summary>

```bash
uv run python scripts/run_paper_experiment.py \
  --config configs/experiments/docred_paper.yaml \
  --profile medium \
  --run-name docred__glm-5__100d \
  --model glm-5 \
  --workers 8

uv run python scripts/run_paper_experiment.py \
  --config configs/experiments/docred_paper.yaml \
  --profile medium \
  --run-name docred__kimi-k2__100d \
  --model Moonshot-Kimi-K2-Instruct \
  --workers 8

uv run python scripts/run_paper_experiment.py \
  --config configs/experiments/docred_paper.yaml \
  --profile medium \
  --run-name docred__qwen3-32b__100d \
  --model qwen3-32b \
  --workers 8

uv run python scripts/run_k5_cross_model.py

uv run python scripts/run_paper_experiment.py \
  --config configs/experiments/docred_paper.yaml \
  --profile medium \
  --run-name docred__qwen3-8b__100d \
  --model qwen3-8b \
  --workers 8 \
  --stop-after extract

uv run python scripts/run_paper_experiment.py \
  --config configs/experiments/docred_paper.yaml \
  --profile medium \
  --run-name docred__qwen3-14b__100d \
  --model qwen3-14b \
  --workers 8 \
  --stop-after extract

uv run python scripts/run_model_size_k5.py
uv run python scripts/run_model_size_k5_expressible.py
```

</details>

### 3. Cross-run analyses

After the four primary and three cross-model lineage databases exist, rebuild the shared analyses:

```bash
uv run python scripts/build_reproducibility_manifest.py
uv run python scripts/export_sampled_document_ids.py
uv run python scripts/run_endpoint_reuse_analysis.py
uv run python scripts/run_family_decomposition.py
uv run python scripts/run_diagnostic_queries.py --overwrite
uv run python scripts/compute_amp_ci.py
uv run python scripts/run_extended_queries.py
uv run python scripts/aggregate_cross_run.py
```

`run_stability_bucket_analysis.py` also writes a private manuscript table when all four runs are passed together. In a public checkout without that manuscript, generate the four JSON artifacts one run at a time:

```bash
for run in \
  docred__deepseek-v4-flash__300d \
  redocred__deepseek-v4-flash__300d \
  scierc__deepseek-v4-flash__100d \
  cdr__deepseek-v4-flash__300d
do
  uv run python scripts/run_stability_bucket_analysis.py --runs "$run"
done
```

### 4. Perturbation magnitude

The committed `magnitude_*.json` files support API-free figure rebuilding with `--fig-only`. A fresh controlled extraction requires the four primary databases and API credentials:

```bash
uv run python scripts/run_magnitude_analysis.py --dry-run --docs 100
uv run python scripts/run_magnitude_analysis.py --run-controlled --docs 100

# Repeat only if the first pass leaves failed endpoints.
uv run python scripts/run_magnitude_analysis.py \
  --run-controlled --docs 100 --retry-failures
```

The controlled command analyzes the checkpoint and generates the magnitude reports and figure. The raw response checkpoint is local and is not committed.

### 5. Cross-document experiment

The fresh cross-document run requires the BC5CDR corpus, the primary BC5CDR lineage database, and API credentials:

```bash
uv run python scripts/run_cross_document_experiment.py --build-cohort
uv run python scripts/run_cross_document_experiment.py --extract

# Repeat only if failed endpoints remain.
uv run python scripts/run_cross_document_experiment.py \
  --extract --retry-failures

uv run python scripts/run_cross_document_experiment.py --analyze-only
uv run python scripts/package_cross_document_checkpoint.py
```

The committed public cache can instead be checked without an API by running `verify_paper_results.py`.

### 6. RQ8–RQ10 and the Kuzu release gate

The deployment analyses depend on the four primary lineage databases and must be run in order.

<details>
<summary>Deployment evidence commands</summary>

```bash
uv run python scripts/run_deployment_queries.py --overwrite

runs=(
  docred__deepseek-v4-flash__300d
  redocred__deepseek-v4-flash__300d
  scierc__deepseek-v4-flash__100d
  cdr__deepseek-v4-flash__300d
)
for run in "${runs[@]}"; do
  uv run python scripts/validate_deployment_kuzu_parity.py \
    --db "data/processed/runs/${run}/${run}.db" \
    --artifact "reports/cross_run/deployment_q1q4_${run}.json" \
    --out "reports/cross_run/deployment_q1q4_${run}__kuzu_parity.json" \
    --overwrite
done

uv run python scripts/run_deployment_downstream.py --overwrite
uv run python scripts/build_deployment_cohorts.py --overwrite
```

The cohort builder and complete Kuzu runner are fail-closed against the registered database anchors and cohort manifest. If a fresh API run produces different identifiers, stop here and review the candidate cohort; do not bypass the registration checks or overwrite the submitted evidence package. After an approved cohort is registered, continue with:

```bash
uv run python scripts/run_deployment_kuzu_cohort.py \
  --mode complete --overwrite
uv run python scripts/package_deployment_evidence.py

uv run python scripts/run_drift_accuracy_analysis.py

for run in "${runs[@]}"; do
  uv run python scripts/run_graph_vs_query_ablation.py --run "$run"
done

uv run python scripts/run_regime_analysis.py
uv run python scripts/run_gate_split_analysis.py
uv run python scripts/run_budget_planner.py
```

</details>

For exact replay of the registered package, use the committed `deployment_evidence.json` and the cached verifier. A two-pair-per-corpus Kuzu smoke replay is available when the matching local lineage databases are present:

```bash
uv run python scripts/run_deployment_kuzu_cohort.py --mode smoke
```

### 7. External extraction components

The submitted external-component summaries can be replayed from their committed checkpoints:

```bash
uv sync --locked --extra dev --extra toolchain
uv run python scripts/run_langchain_toolchain.py --analyze-only
uv run python scripts/run_additional_toolchains.py \
  --toolchain neo4j --analyze-only
uv run python scripts/run_external_toolchain_queries.py --workers 4
```

Fresh LangChain extraction uses the root environment and local cache:

```bash
uv run python scripts/run_langchain_toolchain.py \
  --limit 100 --workers 8 --ignore-tool-usage
```

Fresh Neo4j GraphRAG extraction uses a separate Python 3.10 environment because its recorded dependencies are not covered by the root lock:

<details>
<summary>Fresh Neo4j GraphRAG extraction</summary>

```bash
python3.10 -m venv .venv-neo4j
source .venv-neo4j/bin/activate
python -m pip install \
  "neo4j-graphrag==1.18.0" \
  "openai==1.109.1" \
  "numpy==2.2.6" \
  "pydantic==2.13.4"

set -a && . ./.env && set +a
OPENAI_MODEL=deepseek-v4-flash \
  python scripts/run_additional_toolchains.py \
  --toolchain neo4j \
  --limit 100 \
  --workers 4 \
  --cache data/processed/neo4j_toolchain_cache.jsonl

deactivate
```

</details>

To run the shared Kuzu Q1–Q4 workload over fresh local caches rather than the committed checkpoints:

```bash
uv run python scripts/run_external_toolchain_queries.py \
  --langchain-cache data/processed/langchain_toolchain_cache.jsonl \
  --neo4j-cache data/processed/neo4j_toolchain_cache.jsonl \
  --workers 4
```

### 8. Final figures and checks

After the analyses above, regenerate all derived figures and validate the artifacts:

```bash
uv run python scripts/make_paper_figures.py
uv run python scripts/run_magnitude_analysis.py --fig-only
uv run python scripts/make_extqueries_figure.py
uv run python scripts/make_gate_figure.py
uv run python scripts/make_kuzu_gate_artifacts.py
uv run python scripts/verify_paper_results.py
```

The final verifier checks the registered submitted artifacts. Fresh API results that differ from the registered evidence should be reviewed as a new replication rather than forced through that check.

Additional script entry points and analysis modes are documented in [`scripts/README.md`](scripts/README.md).

## Evidence boundaries

- The release gate is evaluated in a Kuzu-backed workload; it is not presented as a production deployment. Its decision signals compare paired graph and answer sets, while benchmark annotations define the offline workload and evaluation labels.
- Paired-view F1 fidelity measures change between the base and counterfactual views, not absolute extraction accuracy.
- The cross-document experiment uses 100 enriched BC5CDR document pairs with shared MeSH identifiers and provenance-aware queries. It does not evaluate open-domain entity linking or unrestricted cross-document reasoning.
- LangChain and Neo4j GraphRAG are tested as external extraction components, not as complete application stacks. Full Neo4j re-extraction uses the recorded direct dependency pins outside the root lock; cached analysis does not require that environment.
- Controlled masking provides an ordered perturbation-intensity scale. Natural paraphrases remain a separate presentation family rather than points on that scale.

## Repository layout

```text
GraphGuard/
├── graphguard/        # Contracts, extraction, lineage, metrics, queries, planning
├── configs/           # Dataset, schema, prompt, model, and experiment configs
├── scripts/           # Experiment, analysis, verification, and figure entry points
├── reports/           # Canonical per-run and cross-run result artifacts
├── assets/            # Overview image and generated figure previews
└── data/              # Local raw corpora, caches, and lineage databases
```

Additional references:

- [`scripts/README.md`](scripts/README.md): complete operational script guide
- [`uv.lock`](uv.lock): locked Python environment
- [`data/CHECKSUMS.sha256`](data/CHECKSUMS.sha256): identities of the paper input files
- [`CITATION.cff`](CITATION.cff): software citation metadata

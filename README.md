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
| Kuzu gate and planner | `run_deployment_kuzu_cohort.py`, `run_gate_split_analysis.py`, `run_budget_planner.py` | `deployment_evidence.json`, `gate_split.json`, `budget_planner.json` |
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

After the corpora are in place, verify the paper inputs with:

```bash
sha256sum --check data/CHECKSUMS.sha256
```

## End-to-end extraction

Copy `.env.example` to `.env` and set `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`. Each registered run is driven by one experiment configuration:

| Corpus | Config | Profile | Registered run name |
| --- | --- | --- | --- |
| DocRED | `configs/experiments/docred_paper.yaml` | `main300` | `docred__deepseek-v4-flash__300d` |
| Re-DocRED | `configs/experiments/redocred_paper.yaml` | `main300` | `redocred__deepseek-v4-flash__300d` |
| SciERC | `configs/experiments/scierc_paper.yaml` | `main100` | `scierc__deepseek-v4-flash__100d` |
| BC5CDR | `configs/experiments/cdr_paper.yaml` | `main300` | `cdr__deepseek-v4-flash__300d` |

Use the corresponding values in this command:

```bash
set -a && . ./.env && set +a

uv run python scripts/run_paper_experiment.py \
  --config configs/experiments/<corpus>_paper.yaml \
  --profile <profile> \
  --run-name <registered-run-name> \
  --model deepseek-v4-flash \
  --workers 8
```

Outputs are written to `data/processed/runs/<run-name>/` and `reports/runs/<run-name>/`. Existing runs reuse completed extraction events; detailed replay, cross-model, cross-document, and external-component commands are documented in [`scripts/README.md`](scripts/README.md).

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


<div align="center">

# 🛡️ GraphGuard

### 🔬 Reliability Auditing for LLM-Extracted Graph Databases

#### 🧭 Treat the LLM-extracted graph as a materialized view — and audit it like one

**📜 Drift contracts · 🧩 Lineage-based counterfactuals · 🚦 Kuzu release gate**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Kuzu](https://img.shields.io/badge/Kuzu-0.4+-orange.svg)](https://kuzudb.com/)
[![License](https://img.shields.io/badge/License-Research-green.svg)](#)

</div>

**GraphGuard** is a reliability-auditing framework for graphs that LLMs extract from text and that downstream systems (Neo4j, LangChain `LLMGraphTransformer`, LlamaIndex property graphs, Microsoft GraphRAG, …) treat as persistent knowledge. Instead of asking *"is this extraction accurate?"*, GraphGuard asks *"does this graph behave like a stable materialized view when the corpus and intended schema do not change?"*. It encodes that question as a catalogue of declarative **drift contracts**, evaluates them with paired counterfactual extractions, and deploys the resulting drift signals as a **release gate** before ingestion into a graph database.

<div align="center">
  <img src="assets/pr_fig.png" alt="GraphGuard overview" width="100%">
  <br/>
  <sub><b>Project overview.</b> A base extraction materializes a graph view; controlled perturbations to schema, prompt, evidence, decoding, and model produce paired counterfactual views; drift contracts compare the two at the graph and at the query level; the same signals drive a release gate before Kuzu ingestion.</sub>
</div>

---

## 🧭 Why LLM-extracted graphs need view-level auditing

Real systems already treat LLM extractions as graphs that live downstream of the model: Neo4j's *LLM Knowledge Graph Builder* persists extracted entities and relations; LangChain's `LLMGraphTransformer` turns documents into graph documents; LlamaIndex builds property-graph indexes; Microsoft GraphRAG indexes entities, relationships, and claims. In all of these, the extracted graph is **stored, indexed, and queried** — it is a materialized graph view, not an intermediate model output.

That view turns out to be surprisingly unstable. Even when the document, schema, prompt template, model, seed, and output format are all held fixed, repeated extraction materializes different graphs: on both DocRED and Re-DocRED the **mean edge overlap between two no-op reruns is only 0.57**. A schema reorder, a prompt paraphrase, or a one-degree temperature bump is then enough to flip downstream join-query answers. Conventional extraction metrics (accuracy, micro/macro F1) do not catch this, because they are computed against a single sampled view.

GraphGuard fixes this with a contracts-first design: instability is reframed as **violations of declarative stability contracts over paired graph views**, and those violations become the unit of monitoring, calibration, and release-gate decisions.

---

## 🧪 Method

GraphGuard has three layers.

### 1. 📐 Stochastic graph views and drift contracts

Each extraction is modelled as a sample from a configuration-conditioned distribution $P(G \mid C, \theta)$ over graph views. A **drift contract** $\mathcal{K} = (\mathcal{F}, \mathcal{M}, \tau, \alpha, \kappa)$ specifies a perturbation family $\mathcal{F}$ (e.g. schema-presentation, prompt paraphrase, decoding resample), a metric $\mathcal{M}$ (edge Jaccard, type agreement, answer-set drift, …), a tolerance $\tau$, a population budget $\alpha$, and a severity $\kappa$. The paper instantiates six families:

| ID  | Contract                       | Perturbation                                          |
| --- | ------------------------------ | ----------------------------------------------------- |
| K1  | Schema-presentation invariance | Relation reorder / rename, keeping semantics fixed    |
| K1b | Prompt-paraphrase invariance   | Paraphrased prompt template                           |
| K1c | Schema-description invariance  | Added / removed schema descriptions                   |
| K2  | Evidence-presentation invariance | Sentence reorder, entity-alias substitution         |
| K3  | Evidence-masking robustness    | Removing irrelevant sentences                         |
| K4  | Query-answer robustness        | Answer-set drift across lookup / neighbor / join / two-hop |
| K6  | Decoding-resample stability    | Repeated extraction at temperature 0.2                |

### 2. 🧩 Lineage layer and paired counterfactuals

Every base and counterfactual extraction is recorded with a **configuration fingerprint** (model, schema, prompt, evidence presentation, retrieval policy, decoding parameters). A logical `paired_runs` view joins each base extraction with the matching counterfactual for the same document, so a single materialized endpoint can be reused across many contracts, metrics, and query templates. Across the four paper DeepSeek-V4-Flash runs, each extracted document supports **23–70 counterfactual views**, keeping the total API cost bounded (≈33 K extraction events, ≈138 M tokens).

### 3. 🚦 Materialization planning and release gate

A **budgeted scheduler** picks which counterfactual to materialize next given a token budget, prioritizing perturbation families that contribute most to recent violations. The same drift signals — edge-set drift and answer-set drift through Cypher templates — are then deployed as a **gold-free release gate** before Kuzu ingestion: a graph is published only when both signals fall under their calibrated thresholds.

---

## 🔍 What the paper finds

### 🌀 Repeated extraction is already unstable (K6, no-op reruns)

When document, schema, prompt, evidence, model, seed, and output format are all fixed, repeated extraction still materializes different graphs. On DocRED and Re-DocRED, **mean edge overlap is only 0.57**, and relation-type agreement is 0.79 and 0.78. Both disappearing-edge and new-edge rates are non-trivial, so a no-op rerun is not a no-op at the graph level. This establishes the non-zero stochastic baseline that the rest of the catalogue is compared against.

### ⚠️ Most stability contracts fail under default tolerances

On the DocRED + DeepSeek-V4-Flash primary run, schema-presentation (K1), schema-description (K1c), prompt-presentation (K1b), and decoding-resample (K6) contracts all have **violation rates above 0.90**; evidence-presentation invariance (K3) stays lower but still violates its budget at 0.64. The query-level robustness contract reaches a violation rate of 0.93 on join queries, and cross-model recall stability is the only contract that stays low (0.13).

<div align="center">
  <img src="assets/figures/fig_crossrun_violations.png" alt="Cross-run contract violation rates" width="92%">
  <br/>
  <sub><b>Cross-run violations.</b> Darker cells = higher violation rates. The same qualitative pattern reappears across DocRED, Re-DocRED, SciERC, BC5CDR and four LLM extractors; BC5CDR drift is lower but still non-negligible.</sub>
</div>

### 🎯 Calibration and stability buckets

GraphGuard does **not** treat its default tolerances as universal constants. Three complementary checks confirm the diagnostics are robust:

<div align="center">
  <img src="assets/figures/fig_noise_floor.png" alt="Baseline-normalized drift" width="80%">
  <br/>
  <sub><b>Baseline-normalized drift.</b> Schema-presentation and evidence-order perturbations retain positive excess drift above the repeated-extraction baseline; pure entity-alias perturbations fall back to baseline after canonicalization.</sub>
</div>

<div align="center">
  <img src="assets/figures/fig_calibration.png" alt="SLA-driven threshold calibration" width="80%">
  <br/>
  <sub><b>SLA calibration.</b> Coverage and harmful-publication rate as the graph-drift threshold τ varies, with τ* = the largest τ satisfying a 5% harm-rate target. Re-DocRED and SciERC admit feasible thresholds under graph drift alone; DocRED and BC5CDR require the answer-aware gate.</sub>
</div>

<div align="center">
  <img src="assets/figures/fig_2d_sensitivity.png" alt="Two-dimensional gate sensitivity" width="80%">
  <br/>
  <sub><b>2D sensitivity.</b> The chosen operating point τ<sub>g</sub>=0.45, τ<sub>q</sub>=0.70 (gold-bordered cell) sits inside a contiguous low-risk region where harm ≤ 0.05 and retained utility ≥ 0.90 on all four corpora.</sub>
</div>

<div align="center">
  <img src="assets/figures/fig_strict_vs_soft.png" alt="Stability buckets" width="80%">
  <br/>
  <sub><b>Stability buckets.</b> Instability already shows up under L1 (repeated extraction + order-only changes): DocRED L1 violation rate 0.69, harmful-regression rate 0.35. Failures are not only artifacts of presentation or schema-definition rewrites.</sub>
</div>

### 🔁 Queries can amplify or absorb graph drift

Graph-level drift does not translate uniformly into query-answer drift. On the DocRED primary run, **join-query amplification reaches 1.32 (95% bootstrap CI [1.25, 1.40])**, while lookup, neighbor, and two-hop queries absorb part of the edge drift. Schema-density matters: on the sparser SciERC and BC5CDR schemas, join amplification falls to 0.68 and 0.02, because paired join answers are often empty on both sides. Query-visible drift depends on **both schema density and query topology**.

<div align="center">
  <img src="assets/figures/fig_amp_crossrun.png" alt="Cross-run query amplification" width="92%">
  <br/>
  <sub><b>Query amplification.</b> Lookup and join amplification across the paper runs; the dashed line marks no amplification. Join amplification stays above 1 on the DocRED family.</sub>
</div>

### 🎯 Drift signals predict harmful query regression

On 3,921 gold-annotated paired comparisons with at least one non-empty answer, the harmful-regression base rate is **38.7%**. Drift correlates with answer-side error: ρ(Drift, |ΔR|) = 0.345 and ρ(Drift, |ΔP|) = 0.208 (p < 10⁻³). K1 violations show a sharper contrast: violating pairs have mean ΔR = 0.064 and ΔP = 0.091, vs. 0.003 and 0.009 for satisfied pairs. Across the four corpora, **AUROC is 0.56–0.73 for graph drift and 0.64–0.91 for answer-set drift**, and the combined GraphGuard gate tracks the answer-side signal.

<div align="center">
  <img src="assets/figures/fig_auroc.png" alt="ROC and PR curves" width="92%">
  <br/>
  <sub><b>Threshold-free harmful-regression detection.</b> Answer-set drift is a stronger predictor than graph drift; the combined GraphGuard gate follows the answer-side curve.</sub>
</div>

### 🚦 Kuzu release gate reduces direct violations with gold-free signals

Deployed as a release gate before Kuzu ingestion, GraphGuard uses only gold-free signals — edge-set drift and Cypher answer-set drift — to publish or block each counterfactual graph. On the offline harm label (counterfactual mean per-query F1 drops by > 0.05), **18–31% of evaluated pairs are true regressions**, 9–22% are improvements, and the gate reduces direct two-hop violations relative to confidence-only and self-consistency baselines.

<div align="center">
  <img src="assets/figures/fig_riskcoverage.png" alt="Risk-coverage of the Kuzu gate" width="80%">
  <br/>
  <sub><b>Kuzu gate risk–coverage.</b> Decision-time signals are gold-free; gold labels are used only for offline harm annotation.</sub>
</div>

<div align="center">
  <img src="assets/figures/fig_budget_planner.png" alt="Budget planner" width="80%">
  <br/>
  <sub><b>Materialization planner.</b> Token-budget vs. discovered-violation curve for the contract-prioritized scheduler.</sub>
</div>

---

## ⚙️ Reproducing the paper

The repository ships cached extraction reports for every paper run under `reports/runs/` and `reports/cross_run/`, so **all figures and tables in the paper can be regenerated without any LLM calls**.

### 1. 🛠️ Install

```bash
conda create -n graphguard python=3.10 -y
conda activate graphguard
pip install -e .

# Optional, for tests
pip install -e .[dev]

# Only needed for end-to-end re-extraction:
cp .env.example .env
# Set OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL in .env
```

### 2. 📦 Dataset setup

Raw corpora are **not** shipped with the repo (they have separate licences); you only need them if you plan to re-run the extraction pipeline. All paper figures and tables can be regenerated from the cached reports in `reports/` without any raw data.

If you do want to re-extract, place each corpus under `data/raw/` exactly as below — every adapter under `graphguard/data/` and every config in `configs/*.yaml` expects this layout.

```text
data/raw/
├── docred/                                        # auto-downloaded via 🤗 datasets ("docred")
│   └── (left empty — cached into data/cache/hf/ on first run)
├── redocred/                                      # Re-DocRED revised splits
│   ├── train_revised.json
│   └── dev_revised.json
├── scierc/processed_data/json/                    # SciERC official JSON release
│   ├── train.json
│   ├── dev.json
│   └── test.json
└── cdr/CDR_Data/CDR.Corpus.v010516/               # BioCreative V CDR corpus
    ├── CDR_TrainingSet.BioC.xml
    ├── CDR_DevelopmentSet.BioC.xml
    └── CDR_TestSet.BioC.xml
```

Where to download each one:

| Corpus       | Source                                                                                          | Notes                                                                                                  |
| ------------ | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **DocRED**     | Hugging Face hub: [`docred`](https://huggingface.co/datasets/docred)                            | Fetched automatically by `graphguard/data/docred.py` on first call; cached under `data/cache/hf/`.     |
| **Re-DocRED**  | GitHub: [`tonytan48/Re-DocRED`](https://github.com/tonytan48/Re-DocRED) → `data/`                | Copy `train_revised.json` and `dev_revised.json` into `data/raw/redocred/`.                            |
| **SciERC**     | AllenAI release: [`sciie.tar.gz`](http://nlp.cs.washington.edu/sciIE/data/sciie.tar.gz)         | Untar and keep the inner `processed_data/json/{train,dev,test}.json`.                                  |
| **BC5CDR**     | BioCreative V CDR: [BioC.zip](https://biocreative.bioinformatics.udel.edu/tasks/biocreative-v/track-3-cdr/) | Place the `CDR.Corpus.v010516/` directory (BioC XML files) under `data/raw/cdr/CDR_Data/`.             |

Each dataset path is referenced exactly once, from its YAML in `configs/`:

| Config                  | `local_files` / `local_dir`                                       |
| ----------------------- | ----------------------------------------------------------------- |
| `configs/docred.yaml`   | none (Hugging Face `hf_name: docred`)                             |
| `configs/redocred.yaml` | `data/raw/redocred/{train,dev}_revised.json`                       |
| `configs/scierc.yaml`   | `data/raw/scierc/processed_data/json/{train,dev,test}.json`        |
| `configs/cdr.yaml`      | `data/raw/cdr/CDR_Data/CDR.Corpus.v010516/`                        |

You can sanity-check the layout with:

```bash
ls data/raw/redocred/{train,dev}_revised.json \
   data/raw/scierc/processed_data/json/{train,dev,test}.json \
   data/raw/cdr/CDR_Data/CDR.Corpus.v010516/CDR_DevelopmentSet.BioC.xml \
  && echo "raw data layout OK"
```

### 3. 🖼️ Regenerate the figures and dependent tables (no API calls)

```bash
# All 7 figures produced by the unified figure script
python scripts/make_paper_figures.py            # writes assets/figures/*.png

# Risk-coverage figure (fig_riskcoverage) + tab_e2ekuzu table
python scripts/make_kuzu_gate_artifacts.py

# Budget-planner figure (fig_budget_planner)
python scripts/run_budget_planner.py
```

`make_paper_figures.py` accepts a target argument: `all` (default), `replacement` (cross-run violations / amp / strict-vs-soft) or `phase_w` (noise-floor / calibration / 2D-sensitivity / AUROC).

### 4. 🔁 Re-run an experiment end to end (needs API credentials)

End-to-end experiments are driven by `scripts/run_paper_experiment.py` using profiles from `configs/experiments/`. Each profile fixes the document count, counterfactual budget, oracle subset size, and stability-subset size. The driver runs the full pipeline:

```text
prepare → extract → interventions → oracle → main → score → baselines → e0 → evals → report → viz
```

Stage outputs land in `data/processed/runs/<run>/` (lineage SQLite) and `reports/runs/<run>/` (per-stage JSON).

```bash
set -a && . ./.env && set +a   # so subprocesses inherit API credentials

# Primary DocRED run (300 docs, DeepSeek-V4-Flash)
python scripts/run_paper_experiment.py \
  --config  configs/experiments/docred_paper.yaml \
  --profile main300 \
  --run-name docred__deepseek-v4-flash__300d \
  --workers 8

# Replication runs (uses the same driver with different configs/profiles):
#   configs/experiments/redocred_paper.yaml  --profile main300
#   configs/experiments/cdr_paper.yaml       --profile main300
#   configs/experiments/scierc_paper.yaml    --profile main100
```

Use `--start-at <stage>` to resume from any stage; `--skip-extracted` is applied automatically so cached extractions are not re-issued.

### 5. 🧮 Refresh cross-run aggregations and amplification CIs

After any end-to-end re-run, rebuild the cross-run summaries that feed the paper figures:

```bash
python scripts/aggregate_cross_run.py   # writes reports/cross_run/cross_run_summary.json
python scripts/compute_amp_ci.py        # writes reports/cross_run/amp_ci.json
python scripts/make_paper_figures.py    # regenerate every figure that consumes them
```

### 6. 🔬 Cross-model checks on DocRED

```bash
# All three additional extractors at once (uses cached DocRED extraction events
# for the same documents, only the cross-model swap is materialized)
bash scripts/run_crossmodel_medium.sh
```

---

## 📊 Paper runs and where they live

| Corpus     | Run size | Profile / config                              | Lineage DB                                                              |
| ---------- | -------: | --------------------------------------------- | ----------------------------------------------------------------------- |
| DocRED     | 300 docs | `main300` / `configs/experiments/docred_paper.yaml` | `data/processed/runs/docred__deepseek-v4-flash__300d/…`        |
| Re-DocRED  | 300 docs | `main300` / `configs/experiments/redocred_paper.yaml` | `data/processed/runs/redocred__deepseek-v4-flash__300d/…`     |
| SciERC     | 100 docs | `main100` / `configs/experiments/scierc_paper.yaml`   | `data/processed/runs/scierc__deepseek-v4-flash__100d/…`        |
| BC5CDR     | 300 docs | `main300` / `configs/experiments/cdr_paper.yaml`      | `data/processed/runs/cdr__deepseek-v4-flash__300d/…`           |
| DocRED ×3  | 100 docs | cross-model swap (Kimi-K2 / Qwen3-32B / GLM-5) | `data/processed/runs/docred__<model>__100d/…`                          |

Primary extractor is **DeepSeek-V4-Flash**; cross-model checks add **Kimi-K2-Instruct**, **Qwen3-32B**, and **GLM-5** (all via the Alibaba Cloud Bailian OpenAI-compatible chat-completion API). All runs use the validation split with deterministic positional sampling — the first $N$ documents from the validation iterator. Default decoding is temperature 0.0 with seed 7; K6 deliberately uses temperature 0.2.

---

## 🗃️ Repository layout

```text
GraphGuard/
├── graphguard/        # 📚 Library: contracts, lineage DB, planners, metrics, viz
│   ├── contracts/     #    Declarative contract definitions and runtime
│   ├── data/          #    Dataset adapters (DocRED, Re-DocRED, SciERC, BC5CDR)
│   ├── db/            #    SQLite lineage schema + repositories
│   ├── extraction/    #    Per-document extractors and adapters
│   ├── interventions/ #    Perturbation families (schema, prompt, evidence, …)
│   ├── matching/      #    Entity canonicalization and edge alignment
│   ├── metrics/       #    Edge / type / answer-set drift metrics
│   ├── planning/      #    Materialization scheduler / budget planner
│   ├── queries.py     #    Cypher-style query templates (lookup/neighbor/join/two-hop)
│   ├── scoring/       #    Per-edge risk scoring
│   ├── reports/       #    Report builders consumed by paper figures
│   └── viz/           #    Plot primitives
├── configs/           # ⚙️ Dataset / model / prompt / schema YAMLs
│   └── experiments/   #    Per-run profiles (main100, main300, pilot, …)
├── scripts/           # 🚀 Stage-by-stage drivers + paper figure/table generators
│   ├── run_paper_experiment.py   # the end-to-end pipeline driver
│   ├── make_paper_figures.py     # unified figure generator (7 figures)
│   ├── make_kuzu_gate_artifacts.py
│   ├── run_budget_planner.py
│   ├── aggregate_cross_run.py
│   └── compute_amp_ci.py
├── paper/             # 📝 LaTeX source (out-of-tree; see paper PDF in releases)
├── data/raw/          # 🌐 Raw corpora — populate per "Dataset setup" above
├── data/processed/    # 🗄️ Per-run lineage SQLite (re-buildable from scripts/)
├── reports/runs/      # 📊 Per-run JSON reports (contracts, e0, baselines, evals, …)
├── reports/cross_run/ # 📈 Cross-run aggregations consumed by paper figures
└── assets/            # 🖼️ README header image + regenerated paper figures (assets/figures/)
```

Useful documentation:

| Document                                       | Focus                                                            |
| ---------------------------------------------- | ---------------------------------------------------------------- |
| 🚀 [`scripts/README.md`](scripts/README.md)    | Per-script inventory and CLI flags for every stage.              |
| ⚙️ `configs/experiments/`                      | Run profiles (document count, budgets, oracle/e0 subsets).       |

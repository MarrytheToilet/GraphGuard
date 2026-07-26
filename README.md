<div align="center">

# 🛡️ GraphGuard

### 🔬 Reliability Auditing for LLM-Extracted Graph Databases

#### 🧭 Treat the LLM-extracted graph as a materialized view — and audit it like one

**📜 Drift contracts · 🧩 Lineage-based counterfactuals · 🚦 Kuzu release gate**

📄 Paper: *Drift Contracts for Stochastic Graph Views Extracted by LLMs* \[Experiment, Analysis & Benchmark\]

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Kuzu](https://img.shields.io/badge/Kuzu-0.11.3-orange.svg)](https://kuzudb.com/)
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

That view turns out to be surprisingly unstable. With the document, schema, prompt template, evidence, and model held fixed, five controlled decoding samples (temperature 0.3; seeds 7, 13, 23, 37, and 53) have **mean edge overlap of only 0.57** on both DocRED and Re-DocRED. Schema reordering and prompt paraphrasing likewise flip downstream join-query answers. Conventional extraction metrics (accuracy, micro/macro F1) do not measure this paired-view stability because they score one materialization at a time.

GraphGuard fixes this with a contracts-first design: instability is reframed as **violations of declarative stability contracts over paired graph views**, and those violations become the unit of monitoring, calibration, and release-gate decisions.

---

## 🧪 Method

GraphGuard has three layers.

### 1. 📐 Stochastic graph views and drift contracts

Each extraction is modelled as a sample from a configuration-conditioned distribution $P(G \mid C, \theta)$ over graph views. A **drift contract** $\mathcal{K} = (\mathcal{F}, \mathcal{M}, \tau, \alpha, \kappa)$ specifies a perturbation family $\mathcal{F}$ (e.g. schema-presentation, prompt paraphrase, decoding resample), a metric $\mathcal{M}$ (edge Jaccard, type agreement, answer-set drift, …), a tolerance $\tau$, a population budget $\alpha$, and a class $\kappa\in\{\mathrm{I},\mathrm{B}\}$ for invariance or bounded drift. The default catalogue (paper Table 1):

| ID    | Operator expectation                                | Perturbation family / metric                          |
| ----- | --------------------------------------------------- | ----------------------------------------------------- |
| K1    | Schema names and order should not change the view   | `schema_rename`, `schema_reorder` (invariance)        |
| K1b   | Schema descriptions should not change the view      | `schema_desc` (invariance)                            |
| K1c   | Schema edits should have bounded graph drift        | `schema_coarse`, `schema_drop` (bounded drift)        |
| K2    | Prompt presentation should preserve the view        | `prompt_tone`, `persona`, `schema_first` (invariance) |
| K3    | Evidence order and aliases should preserve the view | `entity_alias`, `evidence_reorder` (invariance)       |
| K4    | Diagnostic fan-out-join drift should remain bounded | answer-set drift on canonical D3 (bounded, query-level) |
| K4b–d | Path / aggregation / RAG-retrieval drift bounded    | answer-set drift on Q5–Q7 (bounded, query-level)      |
| K5    | Model replacement should not cause large recall drift | `model_swap`, per-document \|Δrecall\| (bounded)    |
| K6    | Controlled decoding samples should produce a stable view | `decoding_resample` (invariance)                 |

### 2. 🧩 Lineage layer and paired counterfactuals

Every base and counterfactual extraction is recorded with a **configuration fingerprint** (model, schema, prompt, evidence presentation, retrieval policy, decoding parameters). A logical `paired_runs` view joins each base extraction with the matching counterfactual for the same document, so a single materialized endpoint can be reused across many contracts, metrics, and query templates. Relative to independently materializing both endpoints for every contract-pair evaluation, endpoint union achieves savings factors of **7.3×–8.1× for calls** and **7.3×–7.9× for token volume** across the four primary runs; counterfactual-only factors are **4.0×–4.5×** when base graphs already exist. The seven catalogue runs contain 33,043 extraction events (≈138 M tokens); the LangChain and Qwen-size experiments are reported separately.

### 3. 🚦 Materialization planning and release gate

A **budgeted scheduler** picks which counterfactual to materialize next given a token budget, using per-family harmful-regression rates estimated on a calibration split. The same drift signals — edge-set drift and answer-set drift through Cypher templates — are then deployed as a **gold-free release gate** before Kuzu ingestion: a graph is published only when both signals fall under their calibrated thresholds.

---

## 🔍 What the paper finds

### 🌀 Controlled decoding samples are unstable (K6)

With document, schema, prompt, evidence, and model fixed, we draw five controlled decoding samples per document (temperature 0.3; seeds 7, 13, 23, 37, and 53). On DocRED and Re-DocRED, **mean edge overlap is only 0.57**, and relation-type agreement is 0.79 and 0.78. Both disappearing-edge and new-edge rates are non-trivial. This establishes the non-zero stochastic baseline used by the remaining analyses; it is not evidence from literally identical decoding configurations.

### ⚠️ Most stability contracts fail under default tolerances

On the DocRED + DeepSeek-V4-Flash primary run, schema-presentation (K1, 0.97), schema-description (K1b, 0.93), prompt-presentation (K2, 0.92), diagnostic fan-out-join robustness (K4, 0.91), and decoding-resample (K6, 0.91) contracts all have **violation rates above 0.90**; the bounded schema-edit contract (K1c) violates at 0.72 and evidence-order/alias invariance (K3) at 0.64. Cross-model recall stability (K5) stays much lower (0.13); the revision artifacts use the registered identifier-first metric throughout.

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
  <sub><b>SLA calibration.</b> Coverage and harmful-publication rate as the typed graph-drift threshold τ varies, with τ* = the largest τ satisfying a 5% harm-rate target. On the deterministic N=300 samples, graph-only coverage at that target spans 3–60%; at a 15% target it spans 8–92%, showing that usable thresholds are corpus-specific.</sub>
</div>

<div align="center">
  <img src="assets/figures/fig_2d_sensitivity.png" alt="Two-dimensional gate sensitivity" width="80%">
  <br/>
  <sub><b>2D sensitivity.</b> All four corpora are shown. At the chosen operating point τ<sub>g</sub>=0.45, τ<sub>q</sub>=0.70 (gold-bordered cell), published harm is 0–13% and paired-view F1 fidelity is 0.97–1.00; SciERC is the limiting case, and the neighboring cells show that safe regions are corpus-specific.</sub>
</div>

<div align="center">
  <img src="assets/figures/fig_strict_vs_soft.png" alt="Stability buckets" width="80%">
  <br/>
  <sub><b>Stability buckets.</b> Instability already shows up under L1 (controlled decoding resampling + order-only changes): DocRED L1 answer-drift violation rate 0.69 and absolute query-divergence rate 0.35. Failures are not only artifacts of presentation or schema-definition rewrites.</sub>
</div>

### 🔁 Queries can amplify or absorb graph drift

Graph-level drift does not translate uniformly into query-answer drift. In the canonical graph-wide diagnostic workload, DocRED **fan-out-join amplification D3 reaches 1.15 (95% document-cluster bootstrap CI [1.12, 1.17])**, while other diagnostics absorb part of the edge drift; edge-identity diagnostic D1 reproduces the typed edge set and serves as the no-amplification reference. On the sparser SciERC and BC5CDR schemas, D3 amplification falls to 0.82 and 0.12 because paired fan-out answers are often empty on both sides. D1–D5 are distinct from the gold-instantiated deployment Q1–Q4 used in RQ8–RQ10.

<div align="center">
  <img src="assets/figures/fig_amp_crossrun.png" alt="Cross-run query amplification" width="92%">
  <br/>
  <sub><b>Diagnostic query amplification.</b> Edge identity (D1) and fan-out join (D3) across the paper runs; the dashed line marks Amp=1, while D1 is the empirical no-amplification reference (ε-damping places it below 1). D3 is above 1 on the primary DocRED, Re-DocRED, and Qwen3-32B runs, and near 1 on Kimi-K2 and GLM-5.</sub>
</div>

### 🎯 Drift signals track query divergence and directional regressions

On 4,000 gold-annotated paired comparisons with a non-empty gold-derived query workload, **43.6%** have a mean absolute per-query F1 change above 0.05. Graph drift has moderate correlations with absolute answer-side error: ρ(Drift, |ΔR|) = 0.219 and ρ(Drift, |ΔP|) = 0.135 (p < 10⁻³). K1 violations show a sharper contrast: violating pairs have mean |ΔR| = 0.070 and |ΔP| = 0.117, vs. 0.031 and 0.032 for satisfied pairs. In the separate directional-regression evaluation across four corpora, **AUROC is 0.58–0.89 for graph drift and 0.62–0.91 for answer-set drift**; answer drift leads on three corpora and is effectively tied with graph drift on SciERC.

<div align="center">
  <img src="assets/figures/fig_auroc.png" alt="ROC and PR curves" width="92%">
  <br/>
  <sub><b>Threshold-free harmful-regression detection.</b> Answer-set drift is the stronger predictor on three of the four corpora (SciERC is effectively tied). The fixed OR gate is an operating policy, not a learned ranker, so its ROC need not dominate either input.</sub>
</div>

### 🚦 Kuzu release gate reduces harmful publications with gold-free signals

Deployed as a release gate before Kuzu ingestion, GraphGuard uses decision-time gold-free signals (typed-edge drift and Cypher answer-set drift) to publish or block each counterfactual graph. In this benchmark, gold relations deterministically instantiate the fixed query workload and gold answers define offline labels; once that workload is fixed, the gate decision only compares paired graph and answer sets. On the offline harm label (counterfactual mean per-query F1 drops by > 0.05), **20–30% of evaluated pairs are true regressions**; at the fixed operating point (τ<sub>g</sub>=0.45, τ<sub>q</sub>=0.70), the gate cuts published harm to **0–13% at paired-view F1 fidelity 0.97–1.00**, compared with 4–23% for graph-only gating and 18–30% for an exactly block-rate-matched random gate. Here F1 fidelity is `1 - mean(abs(F1_base - F1_cf))`, not absolute task utility. Under a strict 50/50 document-level split, the same fixed operating point gives held-out harm of **0–8%** at F1 fidelity ≥0.96, versus 21–29% for publish-all. Thresholds re-selected on the calibration half miss the 5% target on held-out BC5CDR (11%), exposing finite-sample calibration uncertainty (`reports/cross_run/gate_split_formal_v1.json`).

<div align="center">
  <img src="assets/figures/fig_riskcoverage.png" alt="Risk-coverage of the Kuzu gate" width="80%">
  <br/>
  <sub><b>Kuzu gate risk–coverage.</b> Decision-time signals are gold-free; gold labels are used only for offline harm annotation.</sub>
</div>

<div align="center">
  <img src="assets/figures/fig_budget_planner.png" alt="Budget planner" width="80%">
  <br/>
  <sub><b>Materialization planner.</b> Harm recall on the held-out deployment split vs. fraction of the full endpoint-union budget: the family-prior greedy planner reaches 39–52% at a 40% budget, with corpus- and budget-dependent advantages over the alternatives.</sub>
</div>

---

## 📒 Audited results ledger

The ledger below maps the paper's headline claims to their authoritative machine-readable artifacts. It was re-audited on 2026-07-26. Paths abbreviated as `RC` refer to `reports/cross_run/`; `RR` refers to `reports/runs/<run>/`. The complete ledger can be checked automatically with `python scripts/verify_paper_results.py`.

<details>
<summary><strong>Expand the claim-to-artifact ledger</strong></summary>

### §5.1 Stochastic baseline (RQ1)

| Claim | Value | Source |
| ----- | ----- | ------ |
| Controlled decoding-sample mean edge overlap, DocRED / Re-DocRED | 0.57 / 0.57 (raw view; temperature 0.3; seeds 7/13/23/37/53) | `RR/{docred,redocred}__deepseek-v4-flash__300d/report.md` |
| Type agreement | 0.79 / 0.78 | same reports |
| Disappearing / new-edge rate | 0.28–0.29 | same reports |
| Type-flip rate | 0.13 | same reports |
| Label-erased vs. full-triple gap in Table 5 | 0.13–0.15 on rerun and presentation families only; alias 0.02 and semantic 0.25 are excluded | `RC/family_decomp_*.json` |

### §5.2 Contract catalogue outcomes (Table 4)

K1–K4 and K6 come from `RR/docred__deepseek-v4-flash__300d/eval/contracts.json`; K5 comes from `RC/k5_cross_model.json`.

| Contract | n | Mean metric | Violation rate |
| -------- | -: | ----------: | -------------: |
| K1 schema-presentation | 676 | 0.66 | 0.97 |
| K1b schema-description | 337 | 0.64 | 0.93 |
| K1c schema-definition (bounded) | 676 | 0.64 | 0.72 |
| K2 prompt-presentation | 534 | 0.62 | 0.92 |
| K3 evidence/alias | 78 | 0.41 | 0.64 |
| K4 diagnostic fan-out-join robustness | 2,301 | 0.76 | 0.91 |
| K4b path | 872 | 0.74 | 0.82 |
| K4c aggregation | 2,301 | 0.31 | 0.55 |
| K4d RAG retrieval | 2,301 | 0.63 | 0.88 |
| K5 cross-model recall | 294 | 0.10 | 0.13 |
| K6 stochastic repeatability | 78 | 0.51 | 0.91 |

K5 pools three DeepSeek-vs.-{Kimi, Qwen3-32B, GLM-5} comparisons using the identifier-first recall metric. One model-pair verdict is satisfied and two are inconclusive; the pooled violation rate is 0.13, below $\alpha=0.20$. Figure 2 excludes K5 because it is a cross-model contract. Its K1–K4 and K6 values are read from `RC/cross_run_summary.json` and match Table 4 at the catalogue tolerances.

### §5.2 K5 model-size ladder

Sources: `RC/k5_model_size.json` and `RC/k5_model_size_expressible.json`.

| Claim | Value |
| ----- | ----- |
| Mean recall, Qwen3 8B → 14B → 32B; DeepSeek | 0.107 → 0.122 → 0.140; 0.206 |
| Within-family mean \|Δrecall\|; fraction above tolerance | 0.05–0.08; 5–9% |
| Cross-family fraction above tolerance | 0.12–0.14; one satisfied and two inconclusive |
| Expressible-relation recall, excluding `OTHER` | 0.134 → 0.148 → 0.174; 0.260 |
| Expressible within-family fraction above tolerance | ≤0.14; 8B-vs.-14B is borderline inconclusive |
| Cross-family expressible fraction | 0.20, at the contract boundary |
| Pairwise graph drift between size variants | 0.75–0.86 |

### §5.3 Why BC5CDR has lower drift

Sources: `RC/family_decomp_cdr__deepseek-v4-flash__300d.json` and the contract reports.

| Mechanism | Value |
| --------- | ----- |
| Type agreement under binary CID + `OTHER` schema | 0.96–0.98; DocRED presentation edits flip labels on 24–26% of preserved pairs |
| MeSH identifiers absorb alias changes | Edge overlap 1.00, vs. 0.51–0.82 elsewhere |
| Edges per document; rerun overlap | 2.5–3.2 vs. 7.4–10.7; 0.83 vs. 0.46–0.49 |
| Dropping CID | Drift 0.98 |

### §5.4 Calibration checks

| Figure | Claim | Source |
| ------ | ----- | ------ |
| Fig. 3, noise floor | D0 is 0.43 DocRED, 0.43 Re-DocRED, 0.42 SciERC, and 0.19 BC5CDR | Lineage stability reports, read by `noise_floor_from_db` |
| Fig. 4, SLA calibration | At $\epsilon=0.05$, graph-only coverage is 0.03–0.60; at $\epsilon=0.15$, it is 0.08–0.92 | `compute_calibration` on deterministic N=300 pairs |
| Fig. 5, 2D sensitivity | At (0.45, 0.70), harm is 0–0.13 and F1 fidelity is 0.97–1.00; all four corpora are shown | Formal Kuzu cohort artifacts indexed by `RC/formal_artifacts_v1.json` |
| Fig. 6, DocRED L1 | Answer-drift violation is 0.69; absolute query-divergence rate is 0.35 | `RC/strict_vs_soft_*.json` |

### §5.5 Perturbation magnitude (RQ5, Fig. 7)

Source: `RC/magnitude_*.json`, covering 25,720 pairs.

| Claim | Value |
| ----- | ----- |
| Presentation edits, within-family Spearman correlation | $\lvert\rho\rvert\le 0.13$ |
| Semantic dose response: DocRED drop 1/26 and ambiguous 3/26; SciERC 1/6; BC5CDR CID | 0.71, 0.89; 0.81; 0.98 drift |
| Positive within-family semantic correlation | Spearman 0.13–0.40, each with n≥1,019 |

### §5.6 LangChain toolchain (RQ6, Table 6)

Source: `RC/langchain_toolchain.json`.

| Claim | Value |
| ----- | ----- |
| Invariance axes violated | 92–100% of documents |
| Mean drift vs. the custom pipeline | Within 0.03 on schema, prompt, and evidence axes; the resampling axis differs by 0.16 and is not included in this comparison |

### §6.1 Query amplification (RQ7, Figs. 8 and 9a)

Sources: `RC/diagnostic_v2_*.json` and its compact `RC/amp_ci.json` summary for canonical graph-wide diagnostics D1–D5, plus `RC/extqueries_*.json` for Q5–Q7.

| Claim | Value | Scope |
| ----- | ----- | ----- |
| DocRED fan-out join Amp(D3) | 1.15, document-cluster CI [1.12, 1.17] | All 6,419 authoritative pairs from 299 documents |
| Edge-identity Amp(D1) | 0.901 DocRED, 0.910 Re-DocRED, 0.898 SciERC, 0.471 BC5CDR; ratio of means is 1.000 for all | D1 answer-set drift equals graph drift by construction; it is the empirical no-amplification reference |
| Cross-domain fan-out join Amp(D3) | 0.82 SciERC; 0.12 BC5CDR | Empty-vs.-empty answers are common |
| Q6 aggregation / Q7 RAG / Q5 path | 0.22–0.57 / 0.48–0.92 / 1.00–1.01 on the DocRED family | Q5 is conditioned on a base 2–3-hop path: 2,431 of 6,419 pairs |
| K4b/c/d presentation-class violation | 82% / 55% / 88% | Registered query-level contracts |
| BC5CDR shortest-path amplification | 1.27 | Conditioned on path existence |

### §6.2 Drift and accuracy (RQ8, Fig. 10)

Sources: `RC/drift_accuracy_formal_v1_docred__deepseek-v4-flash__300d.json`, `RC/baselines_matched_*.json`, `RC/monitoring_*.json`, and the formal pair records indexed by `RC/formal_artifacts_v1.json`.

| Claim | Value | Scope |
| ----- | ----- | ----- |
| Absolute query-divergence population / base rate | 4,000 / 43.6% | Mean absolute per-query F1 change >0.05; not directional |
| $\rho(\mathrm{Drift},\lvert\Delta R\rvert)$; $\rho(\mathrm{Drift},\lvert\Delta P\rvert)$ | 0.219; 0.135, both p<10⁻³ | |
| K1 violated vs. satisfied mean $\lvert\Delta R\rvert/\lvert\Delta P\rvert$ | 0.070/0.117 vs. 0.031/0.032 | 656 vs. 20 pairs |
| Directional-regression AUROC, graph vs. answer-set | 0.58–0.89 vs. 0.62–0.91 | |
| Directional-regression AUPRC, graph vs. answer-set | 0.32–0.70 vs. 0.67–0.73 | Trapezoidal PR integration |
| SciERC AUROC | Graph 0.627; answer 0.623; gate 0.643 | Effectively tied; answer-set leads on the other three corpora |
| Matched-baseline diagnostic | Graph-only 0.49; GraphGuard 0.47; confidence 0.34; self-consistency 0.39 | Pooled-label artifact retained but not shown in the manuscript |

### §6.2 Regime detection (Fig. 9b)

Source: `RC/regimes_formal_v1_*.json`.

| Claim | Value | Scope |
| ----- | ----- | ----- |
| Query-aware F1 improvement in both regimes | +0.10 to +0.20 | The local regime is lookup + neighbor; the multi-hop regime is join + two-hop. Alarm rates are not matched in this analysis. |

### §6.3 Query-aware vs. graph-only policy (RQ9)

Source: `RC/graph_vs_query_formal_v1_*.json`, field `monitors_at_matched_alarm`.

| Corpus | Graph F1 (alarm rate) | Query F1 (alarm rate) | ΔF1 |
| ------ | ---------------------: | ---------------------: | ---: |
| BC5CDR | 0.780 (0.434) | 0.893 (0.434) | +0.11 |
| DocRED | 0.628 (0.910) | 0.651 (0.910) | +0.02 |
| Re-DocRED | 0.653 (0.925) | 0.673 (0.925) | +0.02 |
| SciERC | 0.836 (0.937) | 0.845 (0.937) | +0.01 |

The pooled comparison uses exactly equal alarm counts. Score ties are broken by SHA-256 of the run ID without using labels. The target is absolute query change, not directional harm.

### §6.4 Kuzu release gate (RQ10, Figs. 11 and 12)

Sources: the formal Kuzu cohort artifacts indexed by `RC/formal_artifacts_v1.json` for full data and `RC/gate_split_formal_v1.json` for held-out results.

| Setting | Harm | F1 fidelity | Recall |
| ------- | ---- | ----------- | ------ |
| Publish-all, full data | 20–30% | — | — |
| GraphGuard at (0.45, 0.70), full data | 0–13% | 0.97–1.00 | 0.90–1.00 |
| GraphGuard at (0.45, 0.70), held out with frozen thresholds | 0–8% (DocRED 8.0%, Re-DocRED 0%, SciERC 0%, BC5CDR 5.3%) | ≥0.96, minimum 0.963 | 0.85–1.00 |
| GraphGuard held out, thresholds re-selected on calibration split | 0–11% | 0.93–1.00 | 0.61–1.00 |
| Publish-all, held out | 21–29% | — | — |
| Graph-only, full data | 4–23% | — | — |
| Exactly block-rate-matched random, seed 0 | 18–30% | — | — |
| Budget planner harm recall at 40% / 60% budget | 39–52% / 58–78% | — | — |

The matched-random row is generated from the formal pair records in `RC/tab_e2ekuzu_v2.tex`; the budget row comes from `RC/budget_planner_formal_v1.json`.

### Known limitations of the reported results

- The full-data operating point was selected on the same 300-pair samples; the frozen 50/50 document split is the stricter estimate.
- Re-selecting thresholds on the calibration half misses the 5% target on held-out BC5CDR (11%), so the paper does not present threshold re-selection as an improvement.
- Diagnostic D1 drift equals graph drift by definition because it returns the complete typed edge set; it is a reference, not an independent stability signal.
- The pooled K5 Table 4 violation rate of 0.13 masks two inconclusive model-pair comparisons; the manuscript therefore reports that model-pair verdicts are mixed.

</details>

---

## ⚙️ Reproducing the paper

The repository ships machine-readable result artifacts under `reports/runs/` and `reports/cross_run/`. The paper's headline numbers can be checked and its generated figures/tables can be rebuilt without raw corpora, lineage databases, or LLM calls.

Run all commands below from the repository root.

There are three reproducibility levels:

| Level | What it verifies or rebuilds | Raw corpora | Lineage DBs | API |
| ----- | ---------------------------- | :---------: | :---------: | :-: |
| Cached-artifact check | Headline claims, generated figures, gate/baseline tables | No | No | No |
| Pair-level re-analysis | Magnitude, stability, drift/accuracy, family, extended-query, regime, and K5 JSON | No | Yes | No |
| End-to-end re-extraction | Extraction events and every downstream artifact | Yes | Rebuilt | Yes |

End-to-end extraction is not bitwise deterministic because the hosted model provider can remain nondeterministic even with `temperature=0` and a fixed seed. Cached-artifact and lineage re-analysis are the appropriate checks for the submitted numbers.

### 0. ✅ Verify the reported results

```bash
# Works from the versioned reports alone.
python scripts/verify_paper_results.py

# Additionally recount the seven tabulated runs from local lineage SQLite DBs.
python scripts/verify_paper_results.py --lineage

# Rebuild endpoint-union call/token savings from the four primary lineage DBs.
python scripts/run_endpoint_reuse_analysis.py
```

The first command validates the authoritative JSON artifacts, including the 17-entry formal RQ8–RQ10 package, and checks the exact sampled-document lists, raw repeated-extraction baseline, run totals, contract table, endpoint-union savings, revision analyses, query-divergence statistics, directional-regression AUROC/AUPRC, release gate, and budget planner. `reports/cross_run/formal_artifacts_v1.json` records the size, SHA-256, schema version, source run, and cross-artifact provenance of every frozen formal artifact; its deterministic gzip transports are versioned. With `--lineage`, the verifier also checks the samples against the seven run databases, recomputes endpoint-union savings on the four primary runs, and recounts 33,043 events (28,482 primary + 4,561 cross-model) and 137,646,379 tokens directly from SQLite.

### 1. 🛠️ Install

```bash
conda create -n graphguard python=3.10 -y
conda activate graphguard
python -m pip install -e '.[dev]'

# Software checks (expected: 156 passed)
pytest -q

# Only needed for the LangChain toolchain experiment in step 7:
python -m pip install \
  'langchain-openai==1.3.5' \
  'langchain-experimental==0.4.2'

# Only needed for end-to-end re-extraction:
cp .env.example .env
# Set OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL in .env
```

### 2. 📦 Dataset setup

Raw corpora are **not** shipped with the repo (they have separate licences); you only need them if you plan to re-run the extraction pipeline. Cached-result verification and figure/table regeneration use only `reports/`.

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

### 3. 🖼️ Regenerate the generated figures and tables (no API calls)

```bash
# Rebuild formal RQ9 summaries from the shipped, hash-checked evidence.
for run in \
  docred__deepseek-v4-flash__300d \
  redocred__deepseek-v4-flash__300d \
  scierc__deepseek-v4-flash__100d \
  cdr__deepseek-v4-flash__300d
do
  python scripts/run_graph_vs_query_ablation.py --run "$run"
done
python scripts/run_regime_analysis.py

# Rebuild formal RQ10 derived summaries.
python scripts/run_gate_split_analysis.py
python scripts/run_budget_planner.py

# Core figure set (cross-run violations, noise floor, calibration,
# 2-D sensitivity, strict-vs-soft, Amp(Q) consistency, AUROC)
python scripts/make_paper_figures.py            # writes assets/figures/*.png

# Perturbation-magnitude figure (paper Fig. 7)
python scripts/run_magnitude_analysis.py --fig-only

# Extended-query + regime figure (paper Fig. 9)
python scripts/make_extqueries_figure.py

# Release-gate outcome bars (paper Fig. 11)
python scripts/make_gate_figure.py

# Risk-coverage figure (paper Fig. 12, top) + per-policy gate table
python scripts/make_kuzu_gate_artifacts.py

# Verify that regenerated summaries and figures still match the paper.
python scripts/verify_paper_results.py
```

`make_paper_figures.py` accepts a target argument: `all` (default), `replacement` (cross-run violations / diagnostic amplification / strict-vs-soft) or `phase_w` (noise-floor / calibration / 2D-sensitivity / AUROC). The other commands above consume cached JSONs under `reports/`; `make_paper_figures.py` additionally reads the four primary lineage DBs to rebuild the noise-floor panel. No command in this section needs raw corpora or API access. Rebuilding the RQ8 K1 contrast with `scripts/run_drift_accuracy_analysis.py` additionally requires the local DocRED lineage DB; the shipped formal summary is still checked by `verify_paper_results.py` without that DB.

The Kuzu-backed workload is pinned to `kuzu==0.11.3`, the version used for the reported gate experiment.

### 4. 🔁 Re-run an experiment end to end (needs API credentials)

End-to-end experiments are driven by `scripts/run_paper_experiment.py` using profiles from `configs/experiments/`. Each profile fixes the document count, counterfactual budget, oracle subset size, and stability-subset size. The driver runs the full pipeline:

```text
prepare → extract → interventions → oracle → main → score → baselines → e0 → evals → report → viz
```

The lineage database and intermediate stage reports land in `data/processed/runs/<run>/`; paper-facing reports and figures are copied to `reports/runs/<run>/`.

```bash
set -a && . ./.env && set +a   # so subprocesses inherit API credentials

# Four primary runs used in the paper
python scripts/run_paper_experiment.py \
  --config configs/experiments/docred_paper.yaml \
  --profile main300 \
  --run-name docred__deepseek-v4-flash__300d \
  --model deepseek-v4-flash \
  --workers 8

python scripts/run_paper_experiment.py \
  --config configs/experiments/redocred_paper.yaml \
  --profile main300 \
  --run-name redocred__deepseek-v4-flash__300d \
  --model deepseek-v4-flash \
  --workers 8

python scripts/run_paper_experiment.py \
  --config configs/experiments/scierc_paper.yaml \
  --profile main100 \
  --run-name scierc__deepseek-v4-flash__100d \
  --model deepseek-v4-flash \
  --workers 8

python scripts/run_paper_experiment.py \
  --config configs/experiments/cdr_paper.yaml \
  --profile main300 \
  --run-name cdr__deepseek-v4-flash__300d \
  --model deepseek-v4-flash \
  --workers 8
```

The four commands write lineage databases to `data/processed/runs/<run-name>/<run-name>.db` and reports to `reports/runs/<run-name>/`. Existing runs resume safely: use `--start-at <stage>` to resume from a particular stage, and already cached extraction events are skipped automatically. Do not use `--fresh` unless you intend to delete that run's local database and start it again.

### 5. 🧮 Refresh cross-run aggregations and amplification CIs

After any end-to-end re-run, rebuild the cross-run summaries that feed the paper figures:

```bash
python scripts/run_diagnostic_queries.py --overwrite
python scripts/aggregate_cross_run.py   # writes reports/cross_run/cross_run_summary.json
python scripts/compute_amp_ci.py        # writes reports/cross_run/amp_ci.json
python scripts/make_paper_figures.py    # regenerate every figure that consumes them
```

### 6. 🔬 Cross-model checks on DocRED

```bash
set -a && . ./.env && set +a

# The paper uses the same first 100 DocRED validation documents for each model.
python scripts/run_paper_experiment.py \
  --config configs/experiments/docred_paper.yaml \
  --profile medium \
  --run-name docred__glm-5__100d \
  --model glm-5 \
  --workers 8

python scripts/run_paper_experiment.py \
  --config configs/experiments/docred_paper.yaml \
  --profile medium \
  --run-name docred__kimi-k2__100d \
  --model Moonshot-Kimi-K2-Instruct \
  --workers 8

python scripts/run_paper_experiment.py \
  --config configs/experiments/docred_paper.yaml \
  --profile medium \
  --run-name docred__qwen3-32b__100d \
  --model qwen3-32b \
  --workers 8

python scripts/run_k5_cross_model.py
python scripts/aggregate_cross_run.py
python scripts/compute_amp_ci.py
```

The historical convenience script `scripts/run_crossmodel_medium.sh` covers only Qwen3-32B and Kimi-K2 and uses different run names; the explicit commands above reproduce the complete three-model catalogue expected by the analysis scripts.

### 7. 🔁 Revision analyses

The cached outputs of every revision analysis ship under `reports/cross_run/`
and `reports/runs/<run>/` (magnitude, extended queries, regimes, per-family
decomposition, LangChain toolchain, K5 model-size ladder and its
expressible-schema sensitivity, gate calibration/deployment split, and the
drift/accuracy analysis). Use
`python scripts/verify_paper_results.py` to validate their paper-facing
numbers. Re-deriving pair-level JSON needs the local per-run lineage databases
under `data/processed/runs/` (rebuilt by step 4); these SQLite files are not
versioned.

With the four primary databases from step 4, the following analyses are
offline:

```bash
python scripts/run_magnitude_analysis.py        # Sec. 5.5: magnitude vs. drift
python scripts/run_family_decomposition.py      # Sec. 5.1: per-family decomposition
python scripts/run_regime_analysis.py           # Sec. 6.2: regime detection
python scripts/run_drift_accuracy_analysis.py   # Sec. 6.2: drift/accuracy statistics
python scripts/run_stability_bucket_analysis.py # Sec. 5.4: L1/L2/L3 buckets
```

After the three cross-model databases from step 6 also exist, regenerate the
seven-run analyses and exact sample manifest:

```bash
python scripts/run_extended_queries.py
python scripts/export_sampled_document_ids.py
```

The Qwen3 model-size analysis additionally needs base extractions for Qwen3-8B
and Qwen3-14B. Qwen3-32B is reused from step 6; only the `extract` stage is
needed for the two smaller models:

```bash
set -a && . ./.env && set +a

python scripts/run_paper_experiment.py \
  --config configs/experiments/docred_paper.yaml \
  --profile medium \
  --run-name docred__qwen3-8b__100d \
  --model qwen3-8b \
  --workers 8 \
  --stop-after extract

python scripts/run_paper_experiment.py \
  --config configs/experiments/docred_paper.yaml \
  --profile medium \
  --run-name docred__qwen3-14b__100d \
  --model qwen3-14b \
  --workers 8 \
  --stop-after extract

python scripts/run_model_size_k5.py
python scripts/run_model_size_k5_expressible.py
```

Finally, the submitted LangChain result uses the transformer's JSON-prompt
mode. This command performs API calls and checkpoints every document-condition
pair to `data/processed/langchain_toolchain_cache.jsonl` before writing
`reports/cross_run/langchain_toolchain.json`:

```bash
set -a && . ./.env && set +a

OPENAI_MODEL=deepseek-v4-flash \
  python scripts/run_langchain_toolchain.py \
    --limit 100 \
    --workers 8 \
    --ignore-tool-usage

# Recompute only the JSON summary from an existing local checkpoint:
python scripts/run_langchain_toolchain.py --analyze-only
```

---

## 📊 Paper runs and where they live

| Corpus / extractor | Run size | Profile / config | Expected local lineage DB (not versioned) |
| ------------------ | -------: | ---------------- | ----------------------------------------- |
| DocRED / DeepSeek-V4-Flash | 300 docs | `main300` / `configs/experiments/docred_paper.yaml` | `data/processed/runs/docred__deepseek-v4-flash__300d/…` |
| Re-DocRED / DeepSeek-V4-Flash | 300 docs | `main300` / `configs/experiments/redocred_paper.yaml` | `data/processed/runs/redocred__deepseek-v4-flash__300d/…` |
| SciERC / DeepSeek-V4-Flash | 100 docs | `main100` / `configs/experiments/scierc_paper.yaml` | `data/processed/runs/scierc__deepseek-v4-flash__100d/…` |
| BC5CDR / DeepSeek-V4-Flash | 300 docs | `main300` / `configs/experiments/cdr_paper.yaml` | `data/processed/runs/cdr__deepseek-v4-flash__300d/…` |
| DocRED / GLM-5 | 100 docs | `medium` / `configs/experiments/docred_paper.yaml` | `data/processed/runs/docred__glm-5__100d/…` |
| DocRED / Kimi-K2-Instruct | 100 docs | `medium` / `configs/experiments/docred_paper.yaml` | `data/processed/runs/docred__kimi-k2__100d/…` |
| DocRED / Qwen3-32B | 100 docs | `medium` / `configs/experiments/docred_paper.yaml` | `data/processed/runs/docred__qwen3-32b__100d/…` |
| DocRED / Qwen3-8B | 100 docs | `medium`, base extraction only | `data/processed/runs/docred__qwen3-8b__100d/…` |
| DocRED / Qwen3-14B | 100 docs | `medium`, base extraction only | `data/processed/runs/docred__qwen3-14b__100d/…` |

Primary extractor is **DeepSeek-V4-Flash**; cross-model checks add **Kimi-K2-Instruct**, **Qwen3-32B**, and **GLM-5** (all via the Alibaba Cloud Bailian OpenAI-compatible chat-completion API). DocRED, Re-DocRED, and BC5CDR use the first $N$ validation documents ordered by document ID. The 100-document SciERC run uses all 50 dev documents and the first 50 test documents under the same deterministic ordering. Default decoding is temperature 0.0 with seed 7. The catalogue K6 endpoint uses a declared temperature/seed change (temperature 0.2), while the RQ1 noise-floor experiment uses five samples at temperature 0.3 with seeds 7, 13, 23, 37, and 53.

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
│   ├── qa.py          #    Kuzu workload helpers (Q1–Q4; Q5–Q7 are evaluated by scripts/run_extended_queries.py)
│   ├── scoring/       #    Per-edge risk scoring
│   ├── reports/       #    Report builders consumed by paper figures
│   └── viz/           #    Plot primitives
├── configs/           # ⚙️ Dataset / model / prompt / schema YAMLs
│   └── experiments/   #    Per-run profiles (main100, main300, pilot, …)
├── scripts/           # 🚀 Stage-by-stage drivers + paper figure/table generators
│   ├── run_paper_experiment.py   # the end-to-end pipeline driver
│   ├── verify_paper_results.py    # API-free checks for paper-facing results
│   ├── make_paper_figures.py     # core figure generator
│   ├── make_gate_figure.py / make_extqueries_figure.py / make_kuzu_gate_artifacts.py
│   ├── run_magnitude_analysis.py / run_extended_queries.py / run_regime_analysis.py
│   ├── run_gate_split_analysis.py / run_drift_accuracy_analysis.py
│   ├── run_model_size_k5.py / run_model_size_k5_expressible.py
│   └── aggregate_cross_run.py / compute_amp_ci.py   # (full inventory: scripts/README.md)
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

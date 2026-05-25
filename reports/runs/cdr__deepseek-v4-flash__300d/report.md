# GraphGuard experiment report

> **Claim.** GraphGuard enables reliability auditing of LLM-extracted graph databases. Current evidence supports audit prioritization; F1 repair remains a secondary, in-progress claim.

## Database summary

- documents: 300
- sentences: 2763
- entities: 2009
- gold_edges: 594
- extraction_events: 7051
- extracted_edges: 22167
- intervention_candidates: 11826
- counterfactual_runs: 6351
- edge_outcomes: 19751
- edge_reliability_scores: 1362
- edge_correctness: 982
- stability_reports: 80

## E0 stability

```json
{
  "docs": [
    {
      "document_id": "cdr-validation-000000-6794356",
      "event_ids": [
        "evt-cdr-validation-000000-6794356-72392a6c6d",
        "evt-cdr-validation-000000-6794356-b3d880bed4",
        "evt-cdr-validation-000000-6794356-e91e97fe89",
        "evt-cdr-validation-000000-6794356-2537fe126e",
        "evt-cdr-validation-000000-6794356-2c3871b5e3"
      ],
      "metrics": {
        "avg_edge_overlap": 0.76,
        "type_agreement": 1.0,
        "disappearance_rate": 0.2,
        "type_flip_rate": 0.0,
        "new_edge_rate": 0.1333
      }
    },
    {
      "document_id": "cdr-validation-000001-6504332",
      "event_ids": [
        "evt-cdr-validation-000001-6504332-37fca280dc",
        "evt-cdr-validation-000001-6504332-e952b20c0f",
        "evt-cdr-validation-000001-6504332-7b5c5a670f",
        "evt-cdr-validation-000001-6504332-2e65c76e27",
        "evt-cdr-validation-000001-6504332-b639402894"
      ],
      "metrics": {
        "avg_edge_overlap": 1.0,
        "type_agreement": 1.0,
        "disappearance_rate": 0.0,
        "type_flip_rate": 0.0,
        "new_edge_rate": 0.0
      }
    },
    {
      "document_id": "cdr-validation-000002-6436733",
      "event_ids": [
        "evt-cdr-validation-000002-6436733-329eab3f5e",
        "evt-cdr-validation-000002-6436733-614a54abbe",
        "evt-cdr-validation-000002-6436733-f3e45fb9b3",
        "evt-cdr-validation-000002-6436733-60c800fb76",
        "evt-cdr-validation-000002-6436733-260c559cac
```

## E2 error detection (multi-mode)

- correct=488 wrong=11 unmatched=483 ambiguous=0

**Mode `strict`** — positive = wrong + unmatched (assumes DocRED gold is complete) (n_eval=982, prevalence=0.5031)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.793 | 0.770 | 1.00 | 0.96 | 0.86 |
| prompt_sensitivity | 0.787 | 0.749 | 0.98 | 0.98 | 0.85 |
| schema_sensitivity | 0.751 | 0.712 | 1.00 | 0.89 | 0.83 |
| stochastic_variance | 0.522 | 0.500 | 0.51 | 0.57 | 0.53 |
| 1_minus_stability | 0.802 | 0.782 | 1.00 | 0.94 | 0.87 |
| random | 0.516 | 0.509 | 0.55 | 0.52 | 0.54 |
| baseline:confidence_inv | 0.748 | 0.750 | 0.88 | 0.85 | 0.81 |
| baseline:majority_vote_inv | 0.794 | 0.762 | 1.00 | 0.96 | 0.87 |
| baseline:source_prov_inv | 0.526 | 0.501 | 0.53 | 0.57 | 0.53 |
| baseline:subj_obj_cooccur_inv | 0.551 | 0.541 | 0.53 | 0.66 | 0.62 |

**Mode `clean`** — drop unmatched; correct vs wrong only (robust to gold incompleteness) (n_eval=499, prevalence=0.022)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.513 | 0.967 | 0.28 | 0.22 | 0.11 |
| prompt_sensitivity | 0.399 | 0.950 | 0.20 | 0.20 | 0.10 |
| schema_sensitivity | 0.501 | 0.960 | 0.28 | 0.16 | 0.11 |
| stochastic_variance | 0.028 | 0.500 | 0.00 | 0.02 | 0.01 |
| 1_minus_stability | 0.494 | 0.965 | 0.28 | 0.20 | 0.11 |
| random | 0.026 | 0.489 | 0.00 | 0.04 | 0.02 |
| baseline:confidence_inv | 0.241 | 0.883 | 0.20 | 0.12 | 0.09 |
| baseline:majority_vote_inv | 0.369 | 0.961 | 0.20 | 0.18 | 0.11 |
| baseline:source_prov_inv | 0.028 | 0.500 | 0.00 | 0.02 | 0.01 |
| baseline:subj_obj_cooccur_inv | 0.055 | 0.695 | 0.00 | 0.02 | 0.07 |

**Mode `wrong_only`** — positive = wrong only; unmatched treated as negative (n_eval=982, prevalence=0.0112)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.045 | 0.865 | 0.06 | 0.04 | 0.04 |
| prompt_sensitivity | 0.037 | 0.831 | 0.02 | 0.03 | 0.04 |
| schema_sensitivity | 0.048 | 0.870 | 0.06 | 0.05 | 0.04 |
| stochastic_variance | 0.014 | 0.500 | 0.00 | 0.01 | 0.01 |
| 1_minus_stability | 0.039 | 0.851 | 0.02 | 0.03 | 0.04 |
| random | 0.019 | 0.532 | 0.00 | 0.02 | 0.03 |
| baseline:confidence_inv | 0.043 | 0.779 | 0.04 | 0.04 | 0.03 |
| baseline:majority_vote_inv | 0.035 | 0.835 | 0.02 | 0.03 | 0.03 |
| baseline:source_prov_inv | 0.014 | 0.499 | 0.00 | 0.01 | 0.01 |
| baseline:subj_obj_cooccur_inv | 0.024 | 0.677 | 0.00 | 0.01 | 0.04 |

## E5 audit prioritization (primary)


**Mode `strict`** — positive = wrong + unmatched (n_eval=982, prevalence=0.5031)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 96.0 | 1.00 | 1.00 | 0.96 | 94 | 168 |
| prompt_sensitivity | 97.0 | 1.00 | 0.98 | 0.97 | 96 | 167 |
| schema_sensitivity | 89.0 | 1.00 | 1.00 | 0.89 | 87 | 163 |
| stochastic_variance | 57.0 | 0.40 | 0.52 | 0.57 | 55 | 102 |
| 1_minus_stability | 94.0 | 1.00 | 1.00 | 0.94 | 92 | 170 |
| 1_minus_confidence | 86.0 | 0.90 | 0.88 | 0.86 | 84 | 159 |
| random | 55.0 | 0.60 | 0.54 | 0.55 | 53 | 104 |
| baseline:confidence_inv | 86.0 | 0.90 | 0.88 | 0.86 | 84 | 159 |
| baseline:majority_vote_inv | 96.0 | 1.00 | 1.00 | 0.96 | 94 | 170 |
| baseline:source_prov_inv | 57.0 | 0.50 | 0.54 | 0.57 | 56 | 103 |
| baseline:subj_obj_cooccur_inv | 63.0 | 0.80 | 0.56 | 0.63 | 63 | 121 |

**Mode `clean`** — drop unmatched; correct vs wrong only (n_eval=499, prevalence=0.022)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 11.0 | 0.50 | 0.22 | 0.11 | 11 | 11 |
| prompt_sensitivity | 10.0 | 0.40 | 0.20 | 0.10 | 10 | 10 |
| schema_sensitivity | 11.0 | 0.50 | 0.18 | 0.11 | 9 | 11 |
| stochastic_variance | 1.0 | 0.00 | 0.02 | 0.01 | 1 | 1 |
| 1_minus_stability | 11.0 | 0.40 | 0.20 | 0.11 | 10 | 11 |
| 1_minus_confidence | 9.0 | 0.30 | 0.12 | 0.09 | 6 | 9 |
| random | 2.0 | 0.00 | 0.02 | 0.02 | 1 | 2 |
| baseline:confidence_inv | 9.0 | 0.30 | 0.12 | 0.09 | 6 | 9 |
| baseline:majority_vote_inv | 11.0 | 0.40 | 0.18 | 0.11 | 9 | 11 |
| baseline:source_prov_inv | 1.0 | 0.00 | 0.02 | 0.01 | 1 | 1 |
| baseline:subj_obj_cooccur_inv | 7.0 | 0.00 | 0.04 | 0.07 | 2 | 7 |

**Mode `wrong_only`** — positive = wrong only; unmatched treated as negative (n_eval=982, prevalence=0.0112)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 4.0 | 0.00 | 0.06 | 0.04 | 4 | 8 |
| prompt_sensitivity | 3.0 | 0.00 | 0.02 | 0.03 | 3 | 8 |
| schema_sensitivity | 5.0 | 0.00 | 0.06 | 0.05 | 5 | 8 |
| stochastic_variance | 1.0 | 0.00 | 0.00 | 0.01 | 1 | 1 |
| 1_minus_stability | 3.0 | 0.00 | 0.02 | 0.03 | 3 | 7 |
| 1_minus_confidence | 4.0 | 0.00 | 0.04 | 0.04 | 4 | 6 |
| random | 1.0 | 0.00 | 0.00 | 0.01 | 1 | 2 |
| baseline:confidence_inv | 4.0 | 0.00 | 0.04 | 0.04 | 4 | 6 |
| baseline:majority_vote_inv | 4.0 | 0.00 | 0.02 | 0.04 | 3 | 6 |
| baseline:source_prov_inv | 1.0 | 0.00 | 0.00 | 0.01 | 1 | 1 |
| baseline:subj_obj_cooccur_inv | 1.0 | 0.00 | 0.00 | 0.01 | 1 | 7 |

## E1 known-cause

```json
{
  "n": 789,
  "top1_acc": 0.7946768060836502,
  "top3_recall": 0.9100126742712294,
  "mrr": 0.8457963667089143,
  "macro_f1": 0.45224126156329547,
  "per_cause_f1": {
    "noop": 0.0,
    "prompt_clause": 0.5238095238095238,
    "schema": 0.8748991121872478,
    "sentence": 0.41025641025641024
  },
  "per_cause_n": {
    "noop": 0,
    "prompt_clause": 92,
    "schema": 675,
    "sentence": 22
  }
}
```

## E3 schema debugging — flip rates per variant

- **coarse**: {'n_observations': 1085, 'type_flip_rate': 0.023963133640552997, 'disappearance_rate': 0.0792626728110599, 'percent_downgraded_to_other': 0.01935483870967742, 'percent_correct_to_wrong': 0.011059907834101382, 'percent_wrong_to_correct': 0.003686635944700461}
- **desc_added**: {'n_observations': 1083, 'type_flip_rate': 0.0332409972299169, 'disappearance_rate': 0.0729455216989843, 'percent_downgraded_to_other': 0.046168051708217916, 'percent_correct_to_wrong': 0.018467220683287166, 'percent_wrong_to_correct': 0.0046168051708217915}
- **desc_removed**: {'n_observations': 1086, 'type_flip_rate': 0.0432780847145488, 'disappearance_rate': 0.037753222836095765, 'percent_downgraded_to_other': 0.08839779005524862, 'percent_correct_to_wrong': 0.011970534069981584, 'percent_wrong_to_correct': 0.0}
- **drop:CID**: {'n_observations': 1086, 'type_flip_rate': 0.7578268876611418, 'disappearance_rate': 0.1694290976058932, 'percent_downgraded_to_other': 0.8305709023941068, 'percent_correct_to_wrong': 0.4880294659300184, 'percent_wrong_to_correct': 0.0}
- **hierarchical**: {'n_observations': 1086, 'type_flip_rate': 0.03959484346224678, 'disappearance_rate': 0.0423572744014733, 'percent_downgraded_to_other': 0.05985267034990792, 'percent_correct_to_wrong': 0.011049723756906077, 'percent_wrong_to_correct': 0.0055248618784530384}
- **rename**: {'n_observations': 1086, 'type_flip_rate': 0.02302025782688766, 'disappearance_rate': 0.058931860036832415, 'percent_downgraded_to_other': 0.049723756906077346, 'percent_correct_to_wrong': 0.007366482504604052, 'percent_wrong_to_correct': 0.004604051565377533}
- **reorder**: {'n_observations': 1086, 'type_flip_rate': 0.03959484346224678, 'disappearance_rate': 0.06813996316758748, 'percent_downgraded_to_other': 0.052486187845303865, 'percent_correct_to_wrong': 0.01289134438305709, 'percent_wrong_to_correct': 0.0055248618784530384}
- **with_other**: {'n_observations': 1086, 'type_flip_rate': 0.0285451197053407, 'disappearance_rate': 0.03867403314917127, 'percent_downgraded_to_other': 0.05156537753222836, 'percent_correct_to_wrong': 0.006445672191528545, 'percent_wrong_to_correct': 0.003683241252302026}

## E4 cost-quality

> `recall@k` = (oracle causes recovered) / (total oracle causes)  ·  `hit` = fraction of selected interventions hitting ≥1 cause.

- planner=exhaustive     budget=1    recall@k=1.000  hit=0.48  reuse=3.45  tok_in=5572555  tok_out=7113058
- planner=exhaustive     budget=2    recall@k=1.000  hit=0.48  reuse=3.45  tok_in=5572555  tok_out=7113058
- planner=exhaustive     budget=3    recall@k=1.000  hit=0.48  reuse=3.45  tok_in=5572555  tok_out=7113058
- planner=exhaustive     budget=4    recall@k=1.000  hit=0.48  reuse=3.45  tok_in=5572555  tok_out=7113058
- planner=exhaustive     budget=6    recall@k=1.000  hit=0.48  reuse=3.45  tok_in=5572555  tok_out=7113058
- planner=exhaustive     budget=8    recall@k=1.000  hit=0.48  reuse=3.45  tok_in=5572555  tok_out=7113058
- planner=random         budget=1    recall@k=0.005  hit=0.25  reuse=3.19  tok_in=71607  tok_out=83786
- planner=random         budget=2    recall@k=0.020  hit=0.38  reuse=3.20  tok_in=217845  tok_out=271011
- planner=random         budget=3    recall@k=0.087  hit=0.45  reuse=3.35  tok_in=385446  tok_out=510264
- planner=random         budget=4    recall@k=0.097  hit=0.49  reuse=3.43  tok_in=551755  tok_out=723242
- planner=random         budget=6    recall@k=0.120  hit=0.46  reuse=3.44  tok_in=795093  tok_out=1023761
- planner=random         budget=8    recall@k=0.126  hit=0.43  reuse=3.43  tok_in=992921  tok_out=1281125
- planner=span_only      budget=1    recall@k=0.001  hit=0.13  reuse=2.58  tok_in=32141  tok_out=42250
- planner=span_only      budget=2    recall@k=0.002  hit=0.13  reuse=2.58  tok_in=64692  tok_out=77788
- planner=span_only      budget=3    recall@k=0.003  hit=0.13  reuse=2.58  tok_in=96883  tok_out=112168
- planner=span_only      budget=4    recall@k=0.005  hit=0.13  reuse=2.58  tok_in=129104  tok_out=145149
- planner=span_only      budget=6    recall@k=0.008  hit=0.13  reuse=2.58  tok_in=192814  tok_out=218761
- planner=span_only      budget=8    recall@k=0.008  hit=0.13  reuse=2.58  tok_in=257373  tok_out=287644
- planner=prompt_only    budget=1    recall@k=0.033  hit=0.99  reuse=3.66  tok_in=304180  tok_out=391462
- planner=prompt_only    budget=2    recall@k=0.034  hit=0.56  reuse=3.48  tok_in=337875  tok_out=426859
- planner=prompt_only    budget=3    recall@k=0.087  hit=0.70  reuse=3.54  tok_in=632195  tok_out=812444
- planner=prompt_only    budget=4    recall@k=0.127  hit=0.77  reuse=3.57  tok_in=934864  tok_out=1177206
- planner=prompt_only    budget=6    recall@k=0.213  hit=0.85  reuse=3.60  tok_in=1533148  tok_out=1955859
- planner=prompt_only    budget=8    recall@k=0.325  hit=0.88  reuse=3.61  tok_in=2133688  tok_out=2739411
- planner=schema_only    budget=1    recall@k=0.008  hit=0.99  reuse=3.66  tok_in=300502  tok_out=384454
- planner=schema_only    budget=2    recall@k=0.031  hit=0.99  reuse=3.66  tok_in=589363  tok_out=767301
- planner=schema_only    budget=3    recall@k=0.056  hit=0.99  reuse=3.66  tok_in=895512  tok_out=1160784
- planner=schema_only    budget=4    recall@k=0.577  hit=0.99  reuse=3.66  tok_in=1185412  tok_out=1569125
- planner=schema_only    budget=6    recall@k=0.591  hit=0.99  reuse=3.66  tok_in=1786632  tok_out=2358601
- planner=schema_only    budget=8    recall@k=0.623  hit=0.99  reuse=3.66  tok_in=2379074  tok_out=3188127
- planner=graphguard  budget=1    recall@k=0.521  hit=0.99  reuse=3.66  tok_in=289900  tok_out=408341
- planner=graphguard  budget=2    recall@k=0.535  hit=0.99  reuse=3.66  tok_in=590211  tok_out=807623
- planner=graphguard  budget=3    recall@k=0.541  hit=0.99  reuse=3.66  tok_in=888568  tok_out=1207818
- planner=graphguard  budget=4    recall@k=0.556  hit=0.99  reuse=3.66  tok_in=1183753  tok_out=1603185
- planner=graphguard  budget=6    recall@k=0.589  hit=0.99  reuse=3.66  tok_in=1780604  tok_out=2401137
- planner=graphguard  budget=8    recall@k=0.623  hit=0.99  reuse=3.66  tok_in=2379074  tok_out=3188127
- planner=adaptive_graphguard budget=1    recall@k=0.044  hit=0.97  reuse=3.54  tok_in=284277  tok_out=375781
- planner=adaptive_graphguard budget=2    recall@k=0.103  hit=0.98  reuse=3.57  tok_in=572814  tok_out=759140
- planner=adaptive_graphguard budget=3    recall@k=0.205  hit=0.98  reuse=3.57  tok_in=858193  tok_out=1133470
- planner=adaptive_graphguard budget=4    recall@k=0.039  hit=0.27  reuse=2.61  tok_in=250993  tok_out=263625
- planner=adaptive_graphguard budget=6    recall@k=0.096  hit=0.28  reuse=3.40  tok_in=404291  tok_out=507240
- planner=adaptive_graphguard budget=8    recall@k=0.399  hit=0.48  reuse=3.45  tok_in=991724  tok_out=1261098

**Cost-quality AUC (higher = better):**
- exhaustive: 1.0
- graphguard: 0.5675
- schema_only: 0.3946
- prompt_only: 0.1542
- adaptive_graphguard: 0.1399
- random: 0.0886
- span_only: 0.0051

## Repair (secondary, exploratory)

> F1-improving repair is **not yet supported by current data**; reported for completeness only.

- raw               best F1=0.622 at frac=0.0
- random            best F1=0.622 at frac=0.0
- by_confidence     best F1=0.660 at frac=0.3
- by_risk           best F1=0.685 at frac=0.3
- by_schema_sens    best F1=0.665 at frac=0.3
- by_stability      best F1=0.679 at frac=0.3

## Case studies (one per category when available)

### Case 1 [prompt_induced_wrong]: (apomorphine) -[OTHER]-> (Parkinson disease)
- risk=2.6, stab=0.0, label=None
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs

### Case 2 [schema_forced_flip]: (cyclophosphamide) -[CID]-> (haemorrhagic myocarditis)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: switch_schema on schema 'drop:CID' → edge disappears in 1/1 runs

### Case 3 [schema_forced_flip]: (epsilon-aminocaproic acid) -[CID]-> (subarachnoid haemorrhage)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: switch_schema on schema 'drop:CID' → edge disappears in 1/1 runs

### Case 4 [schema_forced_flip]: (methyldopa) -[CID]-> (hypertensive)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: switch_schema on schema 'drop:CID' → edge disappears in 1/1 runs

### Case 5 [schema_forced_flip]: (5,7-dihydroxytryptamine) -[CID]-> (hypotensive)
- risk=2.6, stab=0.0, label=unmatched
- top type cause:      switch_schema on schema 'desc_removed' → relation type flips in 1/1 runs

### Case 6 [schema_forced_flip]: (Hydrocortisone) -[OTHER]-> (norepinephrine)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs

### Case 7 [schema_forced_flip]: (Paclitaxel) -[OTHER]-> (carboplatin)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs

### Case 8 [schema_forced_flip]: (azelastine) -[CID]-> (spring allergic rhinitis)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs

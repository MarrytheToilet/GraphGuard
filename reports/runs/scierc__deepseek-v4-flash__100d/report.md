# GraphGuard experiment report

> **Claim.** GraphGuard enables reliability auditing of LLM-extracted graph databases. Current evidence supports audit prioritization; F1 repair remains a secondary, in-progress claim.

## Database summary

- documents: 150
- sentences: 826
- entities: 2004
- gold_edges: 1429
- extraction_events: 5047
- extracted_edges: 39977
- intervention_candidates: 1676
- counterfactual_runs: 4589
- edge_outcomes: 33331
- edge_reliability_scores: 2165
- edge_correctness: 1208
- stability_reports: 50

## E0 stability

```json
{
  "docs": [
    {
      "document_id": "scierc-dev-000000-ICCV_2003_158_abs",
      "event_ids": [
        "evt-scierc-dev-000000-ICCV_2003_158_abs-937539b43f",
        "evt-scierc-dev-000000-ICCV_2003_158_abs-a4b89c2908",
        "evt-scierc-dev-000000-ICCV_2003_158_abs-6a9b12feb6",
        "evt-scierc-dev-000000-ICCV_2003_158_abs-fe80746d9c"
      ],
      "metrics": {
        "avg_edge_overlap": 0.3247,
        "type_agreement": 0.8,
        "disappearance_rate": 0.5039,
        "type_flip_rate": 0.1096,
        "new_edge_rate": 0.5427
      }
    },
    {
      "document_id": "scierc-dev-000001-C04-1096",
      "event_ids": [
        "evt-scierc-dev-000001-C04-1096-39157606fa",
        "evt-scierc-dev-000001-C04-1096-489df8f649",
        "evt-scierc-dev-000001-C04-1096-3fc2cb7ed8",
        "evt-scierc-dev-000001-C04-1096-a0c8b9fb4d"
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
      "document_id": "scierc-dev-000002-P84-1047",
      "event_ids": [
        "evt-scierc-dev-000002-P84-1047-3313160fa3",
        "evt-scierc-dev-000002-P84-1047-613dbf3050",
        "evt-scierc-dev-000002-P84-1047-8adcb78bb5",
        "evt-scierc-dev-000002-P84-1047-45972f566c"
      ],
      "metrics": {
        "avg_edge_overlap": 0.3574,
        "type_agreement": 0.75,
        "disappearance_rate": 0.4744,
        "type_flip_rate"
```

## E2 error detection (multi-mode)

- correct=331 wrong=123 unmatched=754 ambiguous=0

**Mode `strict`** — positive = wrong + unmatched (assumes DocRED gold is complete) (n_eval=1208, prevalence=0.726)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.817 | 0.647 | 0.90 | 0.86 | 0.84 |
| prompt_sensitivity | 0.817 | 0.632 | 0.95 | 0.79 | 0.83 |
| schema_sensitivity | 0.824 | 0.629 | 0.95 | 0.87 | 0.85 |
| stochastic_variance | 0.772 | 0.506 | 0.88 | 0.81 | 0.81 |
| 1_minus_stability | 0.836 | 0.676 | 0.87 | 0.93 | 0.88 |
| random | 0.731 | 0.494 | 0.75 | 0.74 | 0.73 |
| baseline:confidence_inv | 0.799 | 0.631 | 0.78 | 0.88 | 0.81 |
| baseline:majority_vote_inv | 0.825 | 0.659 | 0.87 | 0.88 | 0.83 |
| baseline:source_prov_inv | 0.772 | 0.500 | 0.88 | 0.81 | 0.81 |
| baseline:subj_obj_cooccur_inv | 0.811 | 0.588 | 0.95 | 0.92 | 0.88 |

**Mode `clean`** — drop unmatched; correct vs wrong only (robust to gold incompleteness) (n_eval=454, prevalence=0.2709)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.400 | 0.669 | 0.35 | 0.47 | 0.41 |
| prompt_sensitivity | 0.405 | 0.637 | 0.61 | 0.42 | 0.40 |
| schema_sensitivity | 0.432 | 0.645 | 0.70 | 0.58 | 0.41 |
| stochastic_variance | 0.229 | 0.498 | 0.00 | 0.16 | 0.22 |
| 1_minus_stability | 0.405 | 0.682 | 0.61 | 0.49 | 0.37 |
| random | 0.271 | 0.506 | 0.26 | 0.29 | 0.25 |
| baseline:confidence_inv | 0.241 | 0.467 | 0.22 | 0.11 | 0.26 |
| baseline:majority_vote_inv | 0.371 | 0.659 | 0.39 | 0.40 | 0.42 |
| baseline:source_prov_inv | 0.229 | 0.500 | 0.00 | 0.16 | 0.22 |
| baseline:subj_obj_cooccur_inv | 0.222 | 0.461 | 0.26 | 0.13 | 0.16 |

**Mode `wrong_only`** — positive = wrong only; unmatched treated as negative (n_eval=1208, prevalence=0.1018)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.119 | 0.558 | 0.12 | 0.08 | 0.10 |
| prompt_sensitivity | 0.117 | 0.541 | 0.13 | 0.16 | 0.10 |
| schema_sensitivity | 0.121 | 0.553 | 0.12 | 0.17 | 0.12 |
| stochastic_variance | 0.076 | 0.493 | 0.00 | 0.01 | 0.03 |
| 1_minus_stability | 0.108 | 0.540 | 0.08 | 0.10 | 0.10 |
| random | 0.104 | 0.482 | 0.13 | 0.13 | 0.09 |
| baseline:confidence_inv | 0.070 | 0.355 | 0.03 | 0.04 | 0.03 |
| baseline:majority_vote_inv | 0.105 | 0.547 | 0.07 | 0.10 | 0.10 |
| baseline:source_prov_inv | 0.076 | 0.500 | 0.00 | 0.01 | 0.03 |
| baseline:subj_obj_cooccur_inv | 0.069 | 0.386 | 0.00 | 0.03 | 0.02 |

## E5 audit prioritization (primary)


**Mode `strict`** — positive = wrong + unmatched (n_eval=1208, prevalence=0.726)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 85.0 | 1.00 | 0.88 | 0.85 | 104 | 203 |
| prompt_sensitivity | 89.0 | 0.90 | 0.96 | 0.89 | 98 | 200 |
| schema_sensitivity | 88.0 | 0.90 | 0.96 | 0.88 | 105 | 205 |
| stochastic_variance | 77.0 | 1.00 | 0.78 | 0.77 | 90 | 173 |
| 1_minus_stability | 91.0 | 0.90 | 0.90 | 0.91 | 112 | 213 |
| 1_minus_confidence | 88.0 | 0.20 | 0.80 | 0.88 | 106 | 206 |
| random | 80.0 | 0.60 | 0.76 | 0.80 | 95 | 180 |
| baseline:confidence_inv | 88.0 | 0.20 | 0.80 | 0.88 | 106 | 206 |
| baseline:majority_vote_inv | 88.0 | 0.50 | 0.80 | 0.88 | 104 | 212 |
| baseline:source_prov_inv | 75.0 | 0.80 | 0.76 | 0.75 | 90 | 166 |
| baseline:subj_obj_cooccur_inv | 72.0 | 0.70 | 0.78 | 0.72 | 92 | 198 |

**Mode `clean`** — drop unmatched; correct vs wrong only (n_eval=454, prevalence=0.2709)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 40.0 | 0.50 | 0.42 | 0.40 | 21 | 37 |
| prompt_sensitivity | 39.0 | 0.70 | 0.44 | 0.39 | 19 | 36 |
| schema_sensitivity | 40.0 | 0.70 | 0.56 | 0.40 | 26 | 37 |
| stochastic_variance | 31.0 | 0.20 | 0.26 | 0.31 | 11 | 29 |
| 1_minus_stability | 40.0 | 0.50 | 0.48 | 0.40 | 22 | 34 |
| 1_minus_confidence | 20.0 | 0.00 | 0.26 | 0.20 | 11 | 18 |
| random | 27.0 | 0.30 | 0.24 | 0.27 | 10 | 24 |
| baseline:confidence_inv | 20.0 | 0.00 | 0.26 | 0.20 | 11 | 18 |
| baseline:majority_vote_inv | 41.0 | 0.30 | 0.54 | 0.41 | 23 | 40 |
| baseline:source_prov_inv | 31.0 | 0.20 | 0.28 | 0.31 | 11 | 30 |
| baseline:subj_obj_cooccur_inv | 24.0 | 0.00 | 0.14 | 0.24 | 6 | 20 |

**Mode `wrong_only`** — positive = wrong only; unmatched treated as negative (n_eval=1208, prevalence=0.1018)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 8.0 | 0.20 | 0.12 | 0.08 | 10 | 25 |
| prompt_sensitivity | 19.0 | 0.10 | 0.10 | 0.19 | 19 | 25 |
| schema_sensitivity | 17.0 | 0.10 | 0.12 | 0.17 | 21 | 28 |
| stochastic_variance | 9.0 | 0.00 | 0.04 | 0.09 | 11 | 31 |
| 1_minus_stability | 8.0 | 0.10 | 0.12 | 0.08 | 11 | 25 |
| 1_minus_confidence | 5.0 | 0.00 | 0.02 | 0.05 | 5 | 13 |
| random | 15.0 | 0.10 | 0.12 | 0.15 | 18 | 28 |
| baseline:confidence_inv | 5.0 | 0.00 | 0.02 | 0.05 | 5 | 13 |
| baseline:majority_vote_inv | 14.0 | 0.00 | 0.10 | 0.14 | 15 | 30 |
| baseline:source_prov_inv | 11.0 | 0.10 | 0.06 | 0.11 | 11 | 31 |
| baseline:subj_obj_cooccur_inv | 3.0 | 0.00 | 0.00 | 0.03 | 4 | 7 |

## E1 known-cause

```json
{
  "n": 746,
  "top1_acc": 0.4168900804289544,
  "top3_recall": 0.7024128686327078,
  "mrr": 0.5355227882037531,
  "macro_f1": 0.45266860398275,
  "per_cause_f1": {
    "noop": 0.0,
    "prompt_clause": 0.5166666666666666,
    "schema": 0.4504504504504504,
    "sentence": 0.3307086614173228,
    "stochastic": 0.9655172413793104
  },
  "per_cause_n": {
    "noop": 0,
    "prompt_clause": 242,
    "schema": 296,
    "sentence": 194,
    "stochastic": 14
  }
}
```

## E3 schema debugging — flip rates per variant

- **coarse**: {'n_observations': 1378, 'type_flip_rate': 0.12481857764876633, 'disappearance_rate': 0.29825834542815677, 'percent_downgraded_to_other': 0.00362844702467344, 'percent_correct_to_wrong': 0.08563134978229318, 'percent_wrong_to_correct': 0.023222060957910014}
- **desc_added**: {'n_observations': 1392, 'type_flip_rate': 0.09123563218390805, 'disappearance_rate': 0.305316091954023, 'percent_downgraded_to_other': 0.014367816091954023, 'percent_correct_to_wrong': 0.09051724137931035, 'percent_wrong_to_correct': 0.020833333333333332}
- **desc_removed**: {'n_observations': 1386, 'type_flip_rate': 0.14574314574314573, 'disappearance_rate': 0.3217893217893218, 'percent_downgraded_to_other': 0.013708513708513708, 'percent_correct_to_wrong': 0.08513708513708514, 'percent_wrong_to_correct': 0.032467532467532464}
- **drop:FEATURE-OF**: {'n_observations': 319, 'type_flip_rate': 0.11598746081504702, 'disappearance_rate': 0.36990595611285265, 'percent_downgraded_to_other': 0.0219435736677116, 'percent_correct_to_wrong': 0.08150470219435736, 'percent_wrong_to_correct': 0.003134796238244514}
- **drop:USED-FOR**: {'n_observations': 1363, 'type_flip_rate': 0.30887747615553923, 'disappearance_rate': 0.458547322083639, 'percent_downgraded_to_other': 0.05282465150403522, 'percent_correct_to_wrong': 0.2619222303741746, 'percent_wrong_to_correct': 0.028613352898019074}
- **hierarchical**: {'n_observations': 1406, 'type_flip_rate': 0.12233285917496443, 'disappearance_rate': 0.25391180654338547, 'percent_downgraded_to_other': 0.021337126600284494, 'percent_correct_to_wrong': 0.09103840682788052, 'percent_wrong_to_correct': 0.034139402560455195}
- **rename**: {'n_observations': 1412, 'type_flip_rate': 0.10552407932011332, 'disappearance_rate': 0.28824362606232296, 'percent_downgraded_to_other': 0.013456090651558074, 'percent_correct_to_wrong': 0.08994334277620397, 'percent_wrong_to_correct': 0.012747875354107648}
- **drop:HYPONYM-OF**: {'n_observations': 260, 'type_flip_rate': 0.12307692307692308, 'disappearance_rate': 0.4153846153846154, 'percent_downgraded_to_other': 0.03461538461538462, 'percent_correct_to_wrong': 0.12692307692307692, 'percent_wrong_to_correct': 0.03076923076923077}
- **reorder**: {'n_observations': 1412, 'type_flip_rate': 0.1359773371104816, 'disappearance_rate': 0.3356940509915014, 'percent_downgraded_to_other': 0.03824362606232295, 'percent_correct_to_wrong': 0.11614730878186968, 'percent_wrong_to_correct': 0.016288951841359773}
- **with_other**: {'n_observations': 1412, 'type_flip_rate': 0.07861189801699717, 'disappearance_rate': 0.2762039660056657, 'percent_downgraded_to_other': 0.009206798866855524, 'percent_correct_to_wrong': 0.07223796033994334, 'percent_wrong_to_correct': 0.02762039660056657}
- **drop:PART-OF**: {'n_observations': 429, 'type_flip_rate': 0.2564102564102564, 'disappearance_rate': 0.2937062937062937, 'percent_downgraded_to_other': 0.009324009324009324, 'percent_correct_to_wrong': 0.12354312354312354, 'percent_wrong_to_correct': 0.11888111888111888}
- **drop:CONJUNCTION**: {'n_observations': 181, 'type_flip_rate': 0.12154696132596685, 'disappearance_rate': 0.2265193370165746, 'percent_downgraded_to_other': 0.0055248618784530384, 'percent_correct_to_wrong': 0.06629834254143646, 'percent_wrong_to_correct': 0.03867403314917127}
- **drop:EVALUATE-FOR**: {'n_observations': 279, 'type_flip_rate': 0.12186379928315412, 'disappearance_rate': 0.27956989247311825, 'percent_downgraded_to_other': 0.021505376344086023, 'percent_correct_to_wrong': 0.08243727598566308, 'percent_wrong_to_correct': 0.03942652329749104}
- **drop:COMPARE**: {'n_observations': 263, 'type_flip_rate': 0.10266159695817491, 'disappearance_rate': 0.2889733840304182, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.09885931558935361, 'percent_wrong_to_correct': 0.015209125475285171}

## E4 cost-quality

> `recall@k` = (oracle causes recovered) / (total oracle causes)  ·  `hit` = fraction of selected interventions hitting ≥1 cause.

- planner=exhaustive     budget=1    recall@k=1.000  hit=0.89  reuse=21.16  tok_in=4852022  tok_out=17760795
- planner=exhaustive     budget=2    recall@k=1.000  hit=0.89  reuse=21.16  tok_in=4852022  tok_out=17760795
- planner=exhaustive     budget=3    recall@k=1.000  hit=0.89  reuse=21.16  tok_in=4852022  tok_out=17760795
- planner=exhaustive     budget=4    recall@k=1.000  hit=0.89  reuse=21.16  tok_in=4852022  tok_out=17760795
- planner=exhaustive     budget=6    recall@k=1.000  hit=0.89  reuse=21.16  tok_in=4852022  tok_out=17760795
- planner=exhaustive     budget=8    recall@k=1.000  hit=0.89  reuse=21.16  tok_in=4852022  tok_out=17760795
- planner=random         budget=1    recall@k=0.007  hit=0.80  reuse=19.65  tok_in=114522  tok_out=392724
- planner=random         budget=2    recall@k=0.028  hit=0.86  reuse=19.16  tok_in=246330  tok_out=893214
- planner=random         budget=3    recall@k=0.055  hit=0.91  reuse=20.21  tok_in=418414  tok_out=1549674
- planner=random         budget=4    recall@k=0.091  hit=0.91  reuse=20.65  tok_in=573727  tok_out=2207109
- planner=random         budget=6    recall@k=0.153  hit=0.88  reuse=20.48  tok_in=833861  tok_out=3105540
- planner=random         budget=8    recall@k=0.172  hit=0.88  reuse=20.41  tok_in=1099196  tok_out=4043142
- planner=span_only      budget=1    recall@k=0.005  hit=0.78  reuse=17.69  tok_in=99644  tok_out=359466
- planner=span_only      budget=2    recall@k=0.009  hit=0.78  reuse=17.85  tok_in=201547  tok_out=728523
- planner=span_only      budget=3    recall@k=0.013  hit=0.78  reuse=17.90  tok_in=302447  tok_out=1076255
- planner=span_only      budget=4    recall@k=0.014  hit=0.78  reuse=17.85  tok_in=402368  tok_out=1423398
- planner=span_only      budget=6    recall@k=0.018  hit=0.78  reuse=17.79  tok_in=602138  tok_out=2121268
- planner=span_only      budget=8    recall@k=0.025  hit=0.78  reuse=17.77  tok_in=800797  tok_out=2797259
- planner=prompt_only    budget=1    recall@k=0.029  hit=1.00  reuse=20.38  tok_in=154526  tok_out=536671
- planner=prompt_only    budget=2    recall@k=0.037  hit=0.89  reuse=17.71  tok_in=252538  tok_out=897151
- planner=prompt_only    budget=3    recall@k=0.161  hit=0.93  reuse=21.44  tok_in=456202  tok_out=1618364
- planner=prompt_only    budget=4    recall@k=0.177  hit=0.94  reuse=20.98  tok_in=607349  tok_out=2171086
- planner=prompt_only    budget=6    recall@k=0.295  hit=0.96  reuse=21.37  tok_in=938062  tok_out=3435506
- planner=prompt_only    budget=8    recall@k=0.532  hit=0.97  reuse=22.23  tok_in=1302902  tok_out=4811211
- planner=schema_only    budget=1    recall@k=0.035  hit=1.00  reuse=27.84  tok_in=201056  tok_out=712647
- planner=schema_only    budget=2    recall@k=0.058  hit=1.00  reuse=27.90  tok_in=400842  tok_out=1475731
- planner=schema_only    budget=3    recall@k=0.080  hit=1.00  reuse=27.84  tok_in=602703  tok_out=2259541
- planner=schema_only    budget=4    recall@k=0.098  hit=1.00  reuse=27.86  tok_in=805586  tok_out=3030058
- planner=schema_only    budget=6    recall@k=0.200  hit=1.00  reuse=27.03  tok_in=1175430  tok_out=4440018
- planner=schema_only    budget=8    recall@k=0.256  hit=1.00  reuse=27.21  tok_in=1583386  tok_out=6077844
- planner=graphguard  budget=1    recall@k=0.039  hit=1.00  reuse=25.38  tok_in=181419  tok_out=700306
- planner=graphguard  budget=2    recall@k=0.111  hit=1.00  reuse=25.70  tok_in=371030  tok_out=1401839
- planner=graphguard  budget=3    recall@k=0.132  hit=1.00  reuse=25.93  tok_in=566980  tok_out=2128819
- planner=graphguard  budget=4    recall@k=0.155  hit=1.00  reuse=26.45  tok_in=769442  tok_out=2905404
- planner=graphguard  budget=6    recall@k=0.181  hit=1.00  reuse=26.94  tok_in=1185013  tok_out=4424597
- planner=graphguard  budget=8    recall@k=0.224  hit=1.00  reuse=27.18  tok_in=1589260  tok_out=6017262
- planner=adaptive_graphguard budget=1    recall@k=0.037  hit=1.00  reuse=17.24  tok_in=124529  tok_out=430533
- planner=adaptive_graphguard budget=2    recall@k=0.069  hit=0.96  reuse=17.78  tok_in=247153  tok_out=848256
- planner=adaptive_graphguard budget=3    recall@k=0.100  hit=0.97  reuse=17.78  tok_in=375216  tok_out=1273369
- planner=adaptive_graphguard budget=4    recall@k=0.095  hit=0.79  reuse=21.57  tok_in=385773  tok_out=1440738
- planner=adaptive_graphguard budget=6    recall@k=0.156  hit=0.82  reuse=19.99  tok_in=640964  tok_out=2304583
- planner=adaptive_graphguard budget=8    recall@k=0.398  hit=0.87  reuse=20.98  tok_in=964118  tok_out=3503722

**Cost-quality AUC (higher = better):**
- exhaustive: 1.0
- prompt_only: 0.2286
- graphguard: 0.1544
- adaptive_graphguard: 0.1485
- schema_only: 0.1368
- random: 0.1002
- span_only: 0.0149

## Repair (secondary, exploratory)

> F1-improving repair is **not yet supported by current data**; reported for completeness only.

- raw               best F1=0.398 at frac=0.0
- random            best F1=0.398 at frac=0.0
- by_confidence     best F1=0.415 at frac=0.2
- by_risk           best F1=0.420 at frac=0.3
- by_schema_sens    best F1=0.423 at frac=0.3
- by_stability      best F1=0.418 at frac=0.2

## Case studies (one per category when available)

### Case 1 [prompt_induced_wrong]: (RANSAC techniques) -[EVALUATE-FOR]-> (efficient robust estimation algorithm)
- risk=2.6, stab=0.0, label=wrong
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs
- top type cause:      switch_schema on schema 'hierarchical' → relation type flips in 1/1 runs

### Case 2 [schema_forced_flip]: (robust estimation) -[HYPONYM-OF]-> (robust estimation procedure)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs

### Case 3 [schema_forced_flip]: (sampling process) -[PART-OF]-> (RANSAC techniques)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs
- top type cause:      switch_schema on schema 'with_other' → relation type flips in 1/1 runs

### Case 4 [prompt_induced_wrong]: (chunking) -[HYPONYM-OF]-> (tagging task)
- risk=2.6, stab=0.0, label=None
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs

### Case 5 [prompt_induced_wrong]: (data set) -[USED-FOR]-> (memory-based learning chunker)
- risk=2.6, stab=0.0, label=None
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs

### Case 6 [schema_forced_flip]: (strategies) -[CONJUNCTION]-> (technique)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs

### Case 7 [prompt_induced_wrong]: (core-selecting rules) -[HYPONYM-OF]-> (rules)
- risk=2.511111111111111, stab=0.0, label=None
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs

### Case 8 [schema_forced_flip]: (component) -[PART-OF]-> (components)
- risk=2.466666666666667, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C3_use_schema' → edge disappears in 1/1 runs
- top type cause:      switch_schema on schema 'hierarchical' → relation type flips in 1/1 runs

# GraphGuard experiment report

> **Claim.** GraphGuard enables reliability auditing of LLM-extracted graph databases. Current evidence supports audit prioritization; F1 repair remains a secondary, in-progress claim.

## Database summary

- documents: 100
- sentences: 801
- entities: 1905
- gold_edges: 1315
- extraction_events: 530
- extracted_edges: 4148
- intervention_candidates: 4296
- counterfactual_runs: 431
- edge_outcomes: 3307
- edge_reliability_scores: 200
- edge_correctness: 849
- stability_reports: 0

## E0 stability

```json
{
  "docs": []
}
```

## E2 error detection (multi-mode)

- correct=280 wrong=67 unmatched=502 ambiguous=0

**Mode `strict`** — positive = wrong + unmatched (assumes DocRED gold is complete) (n_eval=849, prevalence=0.6702)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.679 | 0.505 | 0.79 | 0.67 | 0.67 |
| prompt_sensitivity | 0.675 | 0.516 | 0.79 | 0.69 | 0.66 |
| schema_sensitivity | 0.668 | 0.491 | 0.74 | 0.64 | 0.66 |
| stochastic_variance | 0.663 | 0.500 | 0.62 | 0.64 | 0.66 |
| 1_minus_stability | 0.673 | 0.499 | 0.81 | 0.67 | 0.66 |
| random | 0.707 | 0.560 | 0.69 | 0.69 | 0.72 |
| baseline:confidence_inv | 0.777 | 0.677 | 0.74 | 0.79 | 0.85 |
| baseline:majority_vote_inv | 0.675 | 0.516 | 0.79 | 0.69 | 0.66 |
| baseline:source_prov_inv | 0.663 | 0.500 | 0.62 | 0.64 | 0.66 |
| baseline:subj_obj_cooccur_inv | 0.702 | 0.546 | 0.71 | 0.76 | 0.76 |

**Mode `clean`** — drop unmatched; correct vs wrong only (robust to gold incompleteness) (n_eval=347, prevalence=0.1931)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.220 | 0.507 | 0.29 | 0.20 | 0.20 |
| prompt_sensitivity | 0.219 | 0.510 | 0.29 | 0.23 | 0.19 |
| schema_sensitivity | 0.204 | 0.486 | 0.18 | 0.17 | 0.19 |
| stochastic_variance | 0.205 | 0.500 | 0.18 | 0.14 | 0.19 |
| 1_minus_stability | 0.215 | 0.501 | 0.24 | 0.23 | 0.19 |
| random | 0.244 | 0.525 | 0.29 | 0.29 | 0.23 |
| baseline:confidence_inv | 0.266 | 0.669 | 0.24 | 0.26 | 0.23 |
| baseline:majority_vote_inv | 0.219 | 0.510 | 0.29 | 0.23 | 0.19 |
| baseline:source_prov_inv | 0.205 | 0.500 | 0.18 | 0.14 | 0.19 |
| baseline:subj_obj_cooccur_inv | 0.262 | 0.570 | 0.29 | 0.40 | 0.33 |

**Mode `wrong_only`** — positive = wrong only; unmatched treated as negative (n_eval=849, prevalence=0.0789)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.092 | 0.504 | 0.10 | 0.08 | 0.09 |
| prompt_sensitivity | 0.093 | 0.500 | 0.10 | 0.08 | 0.08 |
| schema_sensitivity | 0.085 | 0.491 | 0.07 | 0.07 | 0.08 |
| stochastic_variance | 0.089 | 0.500 | 0.07 | 0.07 | 0.08 |
| 1_minus_stability | 0.092 | 0.502 | 0.10 | 0.09 | 0.08 |
| random | 0.088 | 0.558 | 0.10 | 0.05 | 0.06 |
| baseline:confidence_inv | 0.079 | 0.529 | 0.02 | 0.05 | 0.06 |
| baseline:majority_vote_inv | 0.093 | 0.500 | 0.10 | 0.08 | 0.08 |
| baseline:source_prov_inv | 0.089 | 0.500 | 0.07 | 0.07 | 0.08 |
| baseline:subj_obj_cooccur_inv | 0.107 | 0.543 | 0.10 | 0.15 | 0.13 |

## E5 audit prioritization (primary)


**Mode `strict`** — positive = wrong + unmatched (n_eval=849, prevalence=0.6702)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 67.0 | 0.70 | 0.80 | 0.67 | 57 | 107 |
| prompt_sensitivity | 67.0 | 0.70 | 0.78 | 0.67 | 58 | 105 |
| schema_sensitivity | 65.0 | 0.60 | 0.66 | 0.65 | 53 | 105 |
| stochastic_variance | 63.0 | 0.30 | 0.54 | 0.63 | 53 | 105 |
| 1_minus_stability | 66.0 | 0.70 | 0.78 | 0.66 | 57 | 105 |
| 1_minus_confidence | 81.0 | 0.70 | 0.74 | 0.81 | 67 | 143 |
| random | 63.0 | 0.50 | 0.58 | 0.63 | 53 | 107 |
| baseline:confidence_inv | 81.0 | 0.70 | 0.74 | 0.81 | 67 | 143 |
| baseline:majority_vote_inv | 67.0 | 0.70 | 0.78 | 0.67 | 58 | 105 |
| baseline:source_prov_inv | 63.0 | 0.30 | 0.54 | 0.63 | 53 | 105 |
| baseline:subj_obj_cooccur_inv | 72.0 | 0.20 | 0.74 | 0.72 | 57 | 131 |

**Mode `clean`** — drop unmatched; correct vs wrong only (n_eval=347, prevalence=0.1931)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 18.0 | 0.40 | 0.18 | 0.18 | 7 | 10 |
| prompt_sensitivity | 18.0 | 0.40 | 0.18 | 0.18 | 6 | 10 |
| schema_sensitivity | 18.0 | 0.20 | 0.18 | 0.18 | 5 | 10 |
| stochastic_variance | 18.0 | 0.10 | 0.18 | 0.18 | 5 | 10 |
| 1_minus_stability | 18.0 | 0.40 | 0.16 | 0.18 | 8 | 10 |
| 1_minus_confidence | 28.0 | 0.10 | 0.26 | 0.28 | 9 | 18 |
| random | 27.0 | 0.20 | 0.32 | 0.27 | 14 | 22 |
| baseline:confidence_inv | 28.0 | 0.10 | 0.26 | 0.28 | 9 | 18 |
| baseline:majority_vote_inv | 18.0 | 0.40 | 0.18 | 0.18 | 6 | 10 |
| baseline:source_prov_inv | 18.0 | 0.10 | 0.18 | 0.18 | 5 | 10 |
| baseline:subj_obj_cooccur_inv | 26.0 | 0.20 | 0.26 | 0.26 | 7 | 23 |

**Mode `wrong_only`** — positive = wrong only; unmatched treated as negative (n_eval=849, prevalence=0.0789)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 8.0 | 0.10 | 0.08 | 0.08 | 7 | 10 |
| prompt_sensitivity | 7.0 | 0.20 | 0.10 | 0.07 | 6 | 10 |
| schema_sensitivity | 6.0 | 0.10 | 0.06 | 0.06 | 6 | 10 |
| stochastic_variance | 6.0 | 0.00 | 0.06 | 0.06 | 5 | 10 |
| 1_minus_stability | 8.0 | 0.20 | 0.08 | 0.08 | 8 | 10 |
| 1_minus_confidence | 4.0 | 0.00 | 0.06 | 0.04 | 4 | 11 |
| random | 10.0 | 0.10 | 0.10 | 0.10 | 9 | 16 |
| baseline:confidence_inv | 4.0 | 0.00 | 0.06 | 0.04 | 4 | 11 |
| baseline:majority_vote_inv | 7.0 | 0.20 | 0.10 | 0.07 | 6 | 10 |
| baseline:source_prov_inv | 6.0 | 0.00 | 0.06 | 0.06 | 5 | 10 |
| baseline:subj_obj_cooccur_inv | 10.0 | 0.10 | 0.08 | 0.10 | 7 | 22 |

## E1 known-cause

```json
{
  "n": 93,
  "top1_acc": 0.43010752688172044,
  "top3_recall": 0.6774193548387096,
  "mrr": 0.5322580645161292,
  "macro_f1": 0.2864969653048283,
  "per_cause_f1": {
    "noop": 0.0,
    "prompt_clause": 0.31578947368421056,
    "schema": 0.6024096385542168,
    "sentence": 0.5142857142857142,
    "stochastic": 0.0
  },
  "per_cause_n": {
    "noop": 0,
    "prompt_clause": 21,
    "schema": 56,
    "sentence": 16,
    "stochastic": 0
  }
}
```

## E3 schema debugging — flip rates per variant

- **ambiguous:P131,P17,P150**: {'n_observations': 28, 'type_flip_rate': 0.6071428571428571, 'disappearance_rate': 0.39285714285714285, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4642857142857143, 'percent_wrong_to_correct': 0.0}
- **coarse**: {'n_observations': 135, 'type_flip_rate': 0.8296296296296296, 'disappearance_rate': 0.14074074074074075, 'percent_downgraded_to_other': 0.014814814814814815, 'percent_correct_to_wrong': 0.3925925925925926, 'percent_wrong_to_correct': 0.0}
- **desc_added**: {'n_observations': 135, 'type_flip_rate': 0.007407407407407408, 'disappearance_rate': 0.1111111111111111, 'percent_downgraded_to_other': 0.07407407407407407, 'percent_correct_to_wrong': 0.014814814814814815, 'percent_wrong_to_correct': 0.0}
- **desc_removed**: {'n_observations': 135, 'type_flip_rate': 0.05925925925925926, 'disappearance_rate': 0.1037037037037037, 'percent_downgraded_to_other': 0.06666666666666667, 'percent_correct_to_wrong': 0.05925925925925926, 'percent_wrong_to_correct': 0.0}
- **drop:P131**: {'n_observations': 87, 'type_flip_rate': 0.25287356321839083, 'disappearance_rate': 0.1839080459770115, 'percent_downgraded_to_other': 0.09195402298850575, 'percent_correct_to_wrong': 0.13793103448275862, 'percent_wrong_to_correct': 0.0}
- **drop:P150**: {'n_observations': 39, 'type_flip_rate': 0.0, 'disappearance_rate': 0.20512820512820512, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P570,P137,P19**: {'n_observations': 12, 'type_flip_rate': 0.5, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P159,P361**: {'n_observations': 10, 'type_flip_rate': 0.4, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.6, 'percent_wrong_to_correct': 0.0}
- **drop:P17**: {'n_observations': 84, 'type_flip_rate': 0.19047619047619047, 'disappearance_rate': 0.15476190476190477, 'percent_downgraded_to_other': 0.047619047619047616, 'percent_correct_to_wrong': 0.17857142857142858, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P175,P27**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **hierarchical**: {'n_observations': 100, 'type_flip_rate': 0.01, 'disappearance_rate': 0.08, 'percent_downgraded_to_other': 0.06, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **rename**: {'n_observations': 100, 'type_flip_rate': 0.06, 'disappearance_rate': 0.11, 'percent_downgraded_to_other': 0.07, 'percent_correct_to_wrong': 0.09, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P69,P131**: {'n_observations': 29, 'type_flip_rate': 0.10344827586206896, 'disappearance_rate': 0.2413793103448276, 'percent_downgraded_to_other': 0.10344827586206896, 'percent_correct_to_wrong': 0.20689655172413793, 'percent_wrong_to_correct': 0.0}
- **reorder**: {'n_observations': 100, 'type_flip_rate': 0.01, 'disappearance_rate': 0.19, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.02, 'percent_wrong_to_correct': 0.0}
- **drop:P159**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **with_other**: {'n_observations': 100, 'type_flip_rate': 0.01, 'disappearance_rate': 0.16, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P175**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.1, 'percent_downgraded_to_other': 0.2, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P361**: {'n_observations': 26, 'type_flip_rate': 0.07692307692307693, 'disappearance_rate': 0.23076923076923078, 'percent_downgraded_to_other': 0.07692307692307693, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P27**: {'n_observations': 10, 'type_flip_rate': 0.0, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.2, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **drop:P137**: {'n_observations': 12, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P150**: {'n_observations': 11, 'type_flip_rate': 0.18181818181818182, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.18181818181818182, 'percent_wrong_to_correct': 0.0}
- **drop:P19**: {'n_observations': 12, 'type_flip_rate': 0.16666666666666666, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.16666666666666666, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **drop:P570**: {'n_observations': 12, 'type_flip_rate': 0.16666666666666666, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.16666666666666666, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **drop:P577**: {'n_observations': 10, 'type_flip_rate': 0.0, 'disappearance_rate': 0.1, 'percent_downgraded_to_other': 0.2, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P17,P361**: {'n_observations': 16, 'type_flip_rate': 0.625, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **drop:P69**: {'n_observations': 29, 'type_flip_rate': 0.0, 'disappearance_rate': 0.3448275862068966, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.20689655172413793, 'percent_wrong_to_correct': 0.0}
- **drop:P108**: {'n_observations': 16, 'type_flip_rate': 0.125, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}

## E4 cost-quality

> `recall@k` = (oracle causes recovered) / (total oracle causes)  ·  `hit` = fraction of selected interventions hitting ≥1 cause.

- planner=exhaustive     budget=1    recall@k=1.000  hit=0.60  reuse=10.44  tok_in=621020  tok_out=3124640
- planner=exhaustive     budget=2    recall@k=1.000  hit=0.60  reuse=10.44  tok_in=621020  tok_out=3124640
- planner=exhaustive     budget=3    recall@k=1.000  hit=0.60  reuse=10.44  tok_in=621020  tok_out=3124640
- planner=exhaustive     budget=4    recall@k=1.000  hit=0.60  reuse=10.44  tok_in=621020  tok_out=3124640
- planner=exhaustive     budget=6    recall@k=1.000  hit=0.60  reuse=10.44  tok_in=621020  tok_out=3124640
- planner=exhaustive     budget=8    recall@k=1.000  hit=0.60  reuse=10.44  tok_in=621020  tok_out=3124640
- planner=random         budget=1    recall@k=0.002  hit=0.54  reuse=12.57  tok_in=17973  tok_out=85985
- planner=random         budget=2    recall@k=0.043  hit=0.62  reuse=10.70  tok_in=32498  tok_out=158785
- planner=random         budget=3    recall@k=0.098  hit=0.64  reuse=11.10  tok_in=51910  tok_out=262979
- planner=random         budget=4    recall@k=0.104  hit=0.63  reuse=10.60  tok_in=63198  tok_out=330562
- planner=random         budget=6    recall@k=0.154  hit=0.69  reuse=11.03  tok_in=103238  tok_out=531936
- planner=random         budget=8    recall@k=0.167  hit=0.62  reuse=10.71  tok_in=118845  tok_out=598233
- planner=span_only      budget=1    recall@k=0.000  hit=0.31  reuse=6.25  tok_in=5410  tok_out=26756
- planner=span_only      budget=2    recall@k=0.004  hit=0.38  reuse=7.50  tok_in=13864  tok_out=66585
- planner=span_only      budget=3    recall@k=0.006  hit=0.41  reuse=8.29  tok_in=22120  tok_out=106653
- planner=span_only      budget=4    recall@k=0.006  hit=0.42  reuse=8.29  tok_in=30478  tok_out=143287
- planner=span_only      budget=6    recall@k=0.008  hit=0.40  reuse=8.29  tok_in=42585  tok_out=194866
- planner=span_only      budget=8    recall@k=0.008  hit=0.41  reuse=8.29  tok_in=59749  tok_out=273996
- planner=prompt_only    budget=1    recall@k=0.098  hit=0.92  reuse=16.25  tok_in=34936  tok_out=191476
- planner=prompt_only    budget=2    recall@k=0.098  hit=0.85  reuse=13.50  tok_in=49699  tok_out=263319
- planner=prompt_only    budget=3    recall@k=0.100  hit=0.79  reuse=12.69  tok_in=62939  tok_out=329031
- planner=prompt_only    budget=4    recall@k=0.120  hit=0.79  reuse=12.18  tok_in=77402  tok_out=389509
- planner=prompt_only    budget=6    recall@k=0.161  hit=0.81  reuse=10.77  tok_in=109709  tok_out=587527
- planner=prompt_only    budget=8    recall@k=0.223  hit=0.82  reuse=10.23  tok_in=142018  tok_out=736799
- planner=schema_only    budget=1    recall@k=0.012  hit=0.69  reuse=15.00  tok_in=31026  tok_out=135882
- planner=schema_only    budget=2    recall@k=0.035  hit=0.69  reuse=15.00  tok_in=54384  tok_out=252672
- planner=schema_only    budget=3    recall@k=0.321  hit=0.69  reuse=15.00  tok_in=76212  tok_out=393598
- planner=schema_only    budget=4    recall@k=0.448  hit=0.67  reuse=15.00  tok_in=99250  tok_out=534340
- planner=schema_only    budget=6    recall@k=0.509  hit=0.65  reuse=15.00  tok_in=144898  tok_out=740020
- planner=schema_only    budget=8    recall@k=0.544  hit=0.64  reuse=15.00  tok_in=191398  tok_out=1001326
- planner=graphguard  budget=1    recall@k=0.037  hit=0.62  reuse=14.50  tok_in=23052  tok_out=122262
- planner=graphguard  budget=2    recall@k=0.133  hit=0.65  reuse=15.00  tok_in=49106  tok_out=267534
- planner=graphguard  budget=3    recall@k=0.190  hit=0.64  reuse=15.00  tok_in=71732  tok_out=385660
- planner=graphguard  budget=4    recall@k=0.223  hit=0.63  reuse=15.00  tok_in=94798  tok_out=504128
- planner=graphguard  budget=6    recall@k=0.308  hit=0.64  reuse=15.00  tok_in=143966  tok_out=771736
- planner=graphguard  budget=8    recall@k=0.408  hit=0.62  reuse=15.00  tok_in=187308  tok_out=980314
- planner=adaptive_graphguard budget=1    recall@k=0.042  hit=0.69  reuse=9.11  tok_in=16396  tok_out=60942
- planner=adaptive_graphguard budget=2    recall@k=0.147  hit=0.73  reuse=9.58  tok_in=34203  tok_out=151416
- planner=adaptive_graphguard budget=3    recall@k=0.195  hit=0.69  reuse=9.92  tok_in=50398  tok_out=244167
- planner=adaptive_graphguard budget=4    recall@k=0.050  hit=0.66  reuse=8.91  tok_in=43991  tok_out=208756
- planner=adaptive_graphguard budget=6    recall@k=0.090  hit=0.66  reuse=9.68  tok_in=72884  tok_out=344577
- planner=adaptive_graphguard budget=8    recall@k=0.167  hit=0.74  reuse=9.58  tok_in=112441  tok_out=568465

**Cost-quality AUC (higher = better):**
- exhaustive: 1.0
- schema_only: 0.3709
- graphguard: 0.2427
- prompt_only: 0.1385
- adaptive_graphguard: 0.1122
- random: 0.1103
- span_only: 0.0062

## Repair (secondary, exploratory)

> F1-improving repair is **not yet supported by current data**; reported for completeness only.

- raw               best F1=0.262 at frac=0.0
- random            best F1=0.262 at frac=0.0
- by_confidence     best F1=0.262 at frac=0.0
- by_risk           best F1=0.262 at frac=0.0
- by_schema_sens    best F1=0.262 at frac=0.0
- by_stability      best F1=0.262 at frac=0.0

## Case studies (one per category when available)

### Case 1 [prompt_induced_wrong]: (IBM Research – Brazil) -[P361]-> (IBM)
- risk=2.6, stab=0.0, label=None
- top existence cause: switch_schema on schema 'ambiguous:P108,P17,P361' → edge disappears in 1/1 runs

### Case 2 [schema_forced_flip]: (Annie) -[OTHER]-> (Susan Blue Parsons)
- risk=2.477777777777778, stab=0.05555555555555558, label=unmatched
- top existence cause: repeat on noop 'seed1' → edge disappears in 1/1 runs

### Case 3 [plausible_unmatched]: (Allen County) -[P527]-> (OH Metropolitan Statistical Area)
- risk=1.55, stab=0.25, label=unmatched
- top type cause:      repeat on noop 'seed0' → relation type flips in 1/1 runs

### Case 4 [prompt_induced_wrong]: (Ulisses Mello) -[P108]-> (IBM)
- risk=2.6, stab=0.0, label=None
- top existence cause: switch_schema on schema 'ambiguous:P108,P17,P361' → edge disappears in 1/1 runs

### Case 5 [schema_forced_flip]: (Romney) -[P131]-> (West Virginia)
- risk=2.177777777777778, stab=0.2222222222222222, label=unmatched
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs

### Case 6 [prompt_induced_wrong]: (Nicki Minaj) -[P175]-> (Lookin Ass)
- risk=2.131818181818182, stab=0.25, label=None
- top existence cause: remove on prompt_clause 'C2_infer_implicit' → edge disappears in 1/1 runs
- top type cause:      switch_schema on schema 'coarse' → relation type flips in 1/1 runs

### Case 7 [prompt_induced_wrong]: (Young Money : Rise of an Empires) -[P527]-> (Lookin Ass)
- risk=2.131818181818182, stab=0.25, label=None
- top existence cause: remove on prompt_clause 'C2_infer_implicit' → edge disappears in 1/1 runs

### Case 8 [prompt_induced_wrong]: (Edward P. "Ned" McEvoy) -[P569]-> (1886)
- risk=1.975757575757576, stab=0.33333333333333337, label=None
- top existence cause: switch_schema on schema 'coarse' → edge disappears in 1/1 runs

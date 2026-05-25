# GraphGuard experiment report

> **Claim.** GraphGuard enables reliability auditing of LLM-extracted graph databases. Current evidence supports audit prioritization; F1 repair remains a secondary, in-progress claim.

## Database summary

- documents: 300
- sentences: 2493
- entities: 5838
- gold_edges: 10642
- extraction_events: 7314
- extracted_edges: 80463
- intervention_candidates: 13084
- counterfactual_runs: 6614
- edge_outcomes: 72357
- edge_reliability_scores: 4698
- edge_correctness: 3285
- stability_reports: 80

## E0 stability

```json
{
  "docs": [
    {
      "document_id": "redocred-validation-000000-Willi_Schneider__skeleton_racer_",
      "event_ids": [
        "evt-redocred-validation-000000-Willi_Schneider__skeleton_racer_-19b4b8a788",
        "evt-redocred-validation-000000-Willi_Schneider__skeleton_racer_-72a01b0133",
        "evt-redocred-validation-000000-Willi_Schneider__skeleton_racer_-1534e921ce",
        "evt-redocred-validation-000000-Willi_Schneider__skeleton_racer_-5405e2762b",
        "evt-redocred-validation-000000-Willi_Schneider__skeleton_racer_-61ab55fd97"
      ],
      "metrics": {
        "avg_edge_overlap": 0.5381,
        "type_agreement": 0.8,
        "disappearance_rate": 0.2611,
        "type_flip_rate": 0.1068,
        "new_edge_rate": 0.2917
      }
    },
    {
      "document_id": "redocred-validation-000001-Ross_Alger",
      "event_ids": [
        "evt-redocred-validation-000001-Ross_Alger-2790980089",
        "evt-redocred-validation-000001-Ross_Alger-01a3e649fd",
        "evt-redocred-validation-000001-Ross_Alger-3643742e51",
        "evt-redocred-validation-000001-Ross_Alger-cd732c2162",
        "evt-redocred-validation-000001-Ross_Alger-98506fddd0"
      ],
      "metrics": {
        "avg_edge_overlap": 0.7286,
        "type_agreement": 0.7857,
        "disappearance_rate": 0.1159,
        "type_flip_rate": 0.1,
        "new_edge_rate": 0.1743
      }
    },
    {
      "document_id": "redocred-validation-000002-Mess_of_Blues__Jeff_Healey_album_",
      "event_ids": 
```

## E2 error detection (multi-mode)

- correct=1040 wrong=752 unmatched=1493 ambiguous=0

**Mode `strict`** — positive = wrong + unmatched (assumes DocRED gold is complete) (n_eval=3285, prevalence=0.6834)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.862 | 0.779 | 0.89 | 0.91 | 0.89 |
| prompt_sensitivity | 0.859 | 0.763 | 0.94 | 0.90 | 0.90 |
| schema_sensitivity | 0.823 | 0.726 | 0.84 | 0.86 | 0.86 |
| stochastic_variance | 0.670 | 0.500 | 0.57 | 0.61 | 0.67 |
| 1_minus_stability | 0.868 | 0.791 | 0.96 | 0.91 | 0.90 |
| random | 0.688 | 0.510 | 0.70 | 0.67 | 0.68 |
| baseline:confidence_inv | 0.861 | 0.734 | 0.99 | 0.96 | 0.93 |
| baseline:majority_vote_inv | 0.873 | 0.790 | 0.93 | 0.95 | 0.91 |
| baseline:source_prov_inv | 0.673 | 0.501 | 0.57 | 0.62 | 0.67 |
| baseline:subj_obj_cooccur_inv | 0.747 | 0.608 | 0.75 | 0.76 | 0.77 |

**Mode `clean`** — drop unmatched; correct vs wrong only (robust to gold incompleteness) (n_eval=1792, prevalence=0.4196)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.655 | 0.750 | 0.70 | 0.72 | 0.70 |
| prompt_sensitivity | 0.662 | 0.742 | 0.82 | 0.74 | 0.70 |
| schema_sensitivity | 0.590 | 0.695 | 0.61 | 0.67 | 0.65 |
| stochastic_variance | 0.416 | 0.500 | 0.33 | 0.36 | 0.42 |
| 1_minus_stability | 0.664 | 0.761 | 0.76 | 0.72 | 0.70 |
| random | 0.420 | 0.499 | 0.41 | 0.42 | 0.43 |
| baseline:confidence_inv | 0.610 | 0.662 | 0.83 | 0.72 | 0.64 |
| baseline:majority_vote_inv | 0.684 | 0.772 | 0.82 | 0.79 | 0.75 |
| baseline:source_prov_inv | 0.419 | 0.501 | 0.34 | 0.37 | 0.42 |
| baseline:subj_obj_cooccur_inv | 0.476 | 0.570 | 0.44 | 0.50 | 0.52 |

**Mode `wrong_only`** — positive = wrong only; unmatched treated as negative (n_eval=3285, prevalence=0.2289)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.264 | 0.572 | 0.29 | 0.26 | 0.26 |
| prompt_sensitivity | 0.271 | 0.573 | 0.32 | 0.30 | 0.27 |
| schema_sensitivity | 0.256 | 0.553 | 0.27 | 0.26 | 0.25 |
| stochastic_variance | 0.235 | 0.500 | 0.21 | 0.21 | 0.25 |
| 1_minus_stability | 0.261 | 0.576 | 0.26 | 0.26 | 0.25 |
| random | 0.234 | 0.506 | 0.24 | 0.22 | 0.23 |
| baseline:confidence_inv | 0.224 | 0.492 | 0.25 | 0.22 | 0.19 |
| baseline:majority_vote_inv | 0.267 | 0.584 | 0.27 | 0.29 | 0.28 |
| baseline:source_prov_inv | 0.236 | 0.500 | 0.21 | 0.21 | 0.25 |
| baseline:subj_obj_cooccur_inv | 0.231 | 0.495 | 0.24 | 0.23 | 0.21 |

## E5 audit prioritization (primary)


**Mode `strict`** — positive = wrong + unmatched (n_eval=3285, prevalence=0.6834)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 91.0 | 0.90 | 0.96 | 0.91 | 299 | 586 |
| prompt_sensitivity | 96.0 | 0.90 | 0.94 | 0.96 | 295 | 593 |
| schema_sensitivity | 88.0 | 0.60 | 0.90 | 0.88 | 282 | 566 |
| stochastic_variance | 56.0 | 0.10 | 0.40 | 0.56 | 202 | 442 |
| 1_minus_stability | 95.0 | 1.00 | 0.92 | 0.95 | 300 | 588 |
| 1_minus_confidence | 100.0 | 1.00 | 1.00 | 1.00 | 315 | 609 |
| random | 61.0 | 0.40 | 0.62 | 0.61 | 228 | 449 |
| baseline:confidence_inv | 100.0 | 1.00 | 1.00 | 1.00 | 315 | 609 |
| baseline:majority_vote_inv | 89.0 | 1.00 | 0.96 | 0.89 | 311 | 601 |
| baseline:source_prov_inv | 57.0 | 0.40 | 0.44 | 0.57 | 203 | 442 |
| baseline:subj_obj_cooccur_inv | 72.0 | 0.50 | 0.72 | 0.72 | 248 | 503 |

**Mode `clean`** — drop unmatched; correct vs wrong only (n_eval=1792, prevalence=0.4196)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 72.0 | 0.90 | 0.76 | 0.72 | 128 | 252 |
| prompt_sensitivity | 82.0 | 0.70 | 0.88 | 0.82 | 132 | 249 |
| schema_sensitivity | 61.0 | 0.50 | 0.60 | 0.61 | 119 | 231 |
| stochastic_variance | 29.0 | 0.10 | 0.24 | 0.29 | 62 | 147 |
| 1_minus_stability | 77.0 | 0.70 | 0.86 | 0.77 | 128 | 250 |
| 1_minus_confidence | 82.0 | 1.00 | 0.90 | 0.82 | 128 | 230 |
| random | 39.0 | 0.30 | 0.36 | 0.39 | 79 | 155 |
| baseline:confidence_inv | 82.0 | 1.00 | 0.90 | 0.82 | 128 | 230 |
| baseline:majority_vote_inv | 83.0 | 0.80 | 0.76 | 0.83 | 147 | 269 |
| baseline:source_prov_inv | 30.0 | 0.20 | 0.26 | 0.30 | 63 | 148 |
| baseline:subj_obj_cooccur_inv | 47.0 | 0.20 | 0.44 | 0.47 | 88 | 185 |

**Mode `wrong_only`** — positive = wrong only; unmatched treated as negative (n_eval=3285, prevalence=0.2289)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 26.0 | 0.40 | 0.26 | 0.26 | 85 | 171 |
| prompt_sensitivity | 34.0 | 0.30 | 0.36 | 0.34 | 98 | 179 |
| schema_sensitivity | 24.0 | 0.30 | 0.26 | 0.24 | 83 | 167 |
| stochastic_variance | 15.0 | 0.10 | 0.12 | 0.15 | 67 | 156 |
| 1_minus_stability | 26.0 | 0.00 | 0.20 | 0.26 | 82 | 164 |
| 1_minus_confidence | 19.0 | 0.40 | 0.22 | 0.19 | 72 | 121 |
| random | 19.0 | 0.00 | 0.12 | 0.19 | 72 | 158 |
| baseline:confidence_inv | 19.0 | 0.40 | 0.22 | 0.19 | 72 | 121 |
| baseline:majority_vote_inv | 23.0 | 0.10 | 0.18 | 0.23 | 95 | 178 |
| baseline:source_prov_inv | 16.0 | 0.20 | 0.12 | 0.16 | 67 | 157 |
| baseline:subj_obj_cooccur_inv | 20.0 | 0.20 | 0.16 | 0.20 | 72 | 141 |

## E1 known-cause

```json
{
  "n": 2695,
  "top1_acc": 0.5840445269016697,
  "top3_recall": 0.8679035250463822,
  "mrr": 0.709400123685836,
  "macro_f1": 0.3402911646102977,
  "per_cause_f1": {
    "noop": 0.0,
    "prompt_clause": 0.5691600501462599,
    "schema": 0.6307142857142857,
    "sentence": 0.16129032258064516
  },
  "per_cause_n": {
    "noop": 0,
    "prompt_clause": 784,
    "schema": 1825,
    "sentence": 86
  }
}
```

## E3 schema debugging — flip rates per variant

- **ambiguous:P131,P17,P1344**: {'n_observations': 21, 'type_flip_rate': 0.47619047619047616, 'disappearance_rate': 0.047619047619047616, 'percent_downgraded_to_other': 0.23809523809523808, 'percent_correct_to_wrong': 0.38095238095238093, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P159**: {'n_observations': 15, 'type_flip_rate': 0.6, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.13333333333333333, 'percent_correct_to_wrong': 0.13333333333333333, 'percent_wrong_to_correct': 0.0}
- **coarse**: {'n_observations': 3675, 'type_flip_rate': 0.6614965986394558, 'disappearance_rate': 0.28489795918367344, 'percent_downgraded_to_other': 0.06802721088435375, 'percent_correct_to_wrong': 0.26693877551020406, 'percent_wrong_to_correct': 0.0}
- **desc_added**: {'n_observations': 3675, 'type_flip_rate': 0.1564625850340136, 'disappearance_rate': 0.24272108843537415, 'percent_downgraded_to_other': 0.08625850340136054, 'percent_correct_to_wrong': 0.05061224489795919, 'percent_wrong_to_correct': 0.026122448979591838}
- **ambiguous:P131,P175,P17**: {'n_observations': 16, 'type_flip_rate': 0.3125, 'disappearance_rate': 0.3125, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1875, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P37**: {'n_observations': 29, 'type_flip_rate': 0.20689655172413793, 'disappearance_rate': 0.41379310344827586, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.10344827586206896, 'percent_wrong_to_correct': 0.0}
- **desc_removed**: {'n_observations': 3675, 'type_flip_rate': 0.17387755102040817, 'disappearance_rate': 0.23510204081632652, 'percent_downgraded_to_other': 0.060136054421768705, 'percent_correct_to_wrong': 0.057414965986394555, 'percent_wrong_to_correct': 0.030204081632653063}
- **ambiguous:P131,P17,P150**: {'n_observations': 450, 'type_flip_rate': 0.5222222222222223, 'disappearance_rate': 0.2733333333333333, 'percent_downgraded_to_other': 0.07777777777777778, 'percent_correct_to_wrong': 0.2288888888888889, 'percent_wrong_to_correct': 0.008888888888888889}
- **drop:P131**: {'n_observations': 2225, 'type_flip_rate': 0.209438202247191, 'disappearance_rate': 0.24674157303370786, 'percent_downgraded_to_other': 0.0602247191011236, 'percent_correct_to_wrong': 0.11280898876404494, 'percent_wrong_to_correct': 0.024719101123595506}
- **drop:P1344**: {'n_observations': 156, 'type_flip_rate': 0.14743589743589744, 'disappearance_rate': 0.1987179487179487, 'percent_downgraded_to_other': 0.05128205128205128, 'percent_correct_to_wrong': 0.057692307692307696, 'percent_wrong_to_correct': 0.01282051282051282}
- **drop:P159**: {'n_observations': 33, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.2727272727272727, 'percent_downgraded_to_other': 0.030303030303030304, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.06060606060606061}
- **drop:P17**: {'n_observations': 1997, 'type_flip_rate': 0.18077115673510266, 'disappearance_rate': 0.2794191286930396, 'percent_downgraded_to_other': 0.04707060590886329, 'percent_correct_to_wrong': 0.04006009013520281, 'percent_wrong_to_correct': 0.05958938407611417}
- **hierarchical**: {'n_observations': 3675, 'type_flip_rate': 0.1545578231292517, 'disappearance_rate': 0.2473469387755102, 'percent_downgraded_to_other': 0.058503401360544216, 'percent_correct_to_wrong': 0.04380952380952381, 'percent_wrong_to_correct': 0.023401360544217688}
- **ambiguous:P131,P40,P3373**: {'n_observations': 37, 'type_flip_rate': 0.16216216216216217, 'disappearance_rate': 0.2972972972972973, 'percent_downgraded_to_other': 0.10810810810810811, 'percent_correct_to_wrong': 0.32432432432432434, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P131,P1344**: {'n_observations': 16, 'type_flip_rate': 0.5, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **rename**: {'n_observations': 3675, 'type_flip_rate': 0.171156462585034, 'disappearance_rate': 0.24789115646258503, 'percent_downgraded_to_other': 0.04435374149659864, 'percent_correct_to_wrong': 0.06258503401360545, 'percent_wrong_to_correct': 0.0}
- **drop:P37**: {'n_observations': 33, 'type_flip_rate': 0.15151515151515152, 'disappearance_rate': 0.030303030303030304, 'percent_downgraded_to_other': 0.030303030303030304, 'percent_correct_to_wrong': 0.030303030303030304, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P800,P86,P50**: {'n_observations': 31, 'type_flip_rate': 0.06451612903225806, 'disappearance_rate': 0.4838709677419355, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P175**: {'n_observations': 478, 'type_flip_rate': 0.2280334728033473, 'disappearance_rate': 0.3075313807531381, 'percent_downgraded_to_other': 0.07112970711297072, 'percent_correct_to_wrong': 0.100418410041841, 'percent_wrong_to_correct': 0.010460251046025104}
- **reorder**: {'n_observations': 3675, 'type_flip_rate': 0.14884353741496598, 'disappearance_rate': 0.2163265306122449, 'percent_downgraded_to_other': 0.06285714285714286, 'percent_correct_to_wrong': 0.05170068027210884, 'percent_wrong_to_correct': 0.027210884353741496}
- **drop:P150**: {'n_observations': 559, 'type_flip_rate': 0.15384615384615385, 'disappearance_rate': 0.2504472271914132, 'percent_downgraded_to_other': 0.04293381037567084, 'percent_correct_to_wrong': 0.03935599284436494, 'percent_wrong_to_correct': 0.017889087656529516}
- **with_other**: {'n_observations': 3675, 'type_flip_rate': 0.16680272108843539, 'disappearance_rate': 0.2182312925170068, 'percent_downgraded_to_other': 0.06884353741496599, 'percent_correct_to_wrong': 0.03619047619047619, 'percent_wrong_to_correct': 0.03428571428571429}
- **ambiguous:P131,P17,P19**: {'n_observations': 79, 'type_flip_rate': 0.13924050632911392, 'disappearance_rate': 0.4050632911392405, 'percent_downgraded_to_other': 0.06329113924050633, 'percent_correct_to_wrong': 0.08860759493670886, 'percent_wrong_to_correct': 0.02531645569620253}
- **drop:P3373**: {'n_observations': 56, 'type_flip_rate': 0.0, 'disappearance_rate': 0.16071428571428573, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.03571428571428571, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P27**: {'n_observations': 164, 'type_flip_rate': 0.16463414634146342, 'disappearance_rate': 0.1402439024390244, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.07317073170731707, 'percent_wrong_to_correct': 0.024390243902439025}
- **drop:P40**: {'n_observations': 170, 'type_flip_rate': 0.1411764705882353, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.07647058823529412, 'percent_correct_to_wrong': 0.10588235294117647, 'percent_wrong_to_correct': 0.041176470588235294}
- **drop:P27**: {'n_observations': 715, 'type_flip_rate': 0.14965034965034965, 'disappearance_rate': 0.2153846153846154, 'percent_downgraded_to_other': 0.03496503496503497, 'percent_correct_to_wrong': 0.0979020979020979, 'percent_wrong_to_correct': 0.019580419580419582}
- **drop:P50**: {'n_observations': 182, 'type_flip_rate': 0.12087912087912088, 'disappearance_rate': 0.37362637362637363, 'percent_downgraded_to_other': 0.07692307692307693, 'percent_correct_to_wrong': 0.054945054945054944, 'percent_wrong_to_correct': 0.0}
- **drop:P19**: {'n_observations': 201, 'type_flip_rate': 0.11940298507462686, 'disappearance_rate': 0.13432835820895522, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0845771144278607, 'percent_wrong_to_correct': 0.024875621890547265}
- **drop:P800**: {'n_observations': 374, 'type_flip_rate': 0.10160427807486631, 'disappearance_rate': 0.25668449197860965, 'percent_downgraded_to_other': 0.0481283422459893, 'percent_correct_to_wrong': 0.05614973262032086, 'percent_wrong_to_correct': 0.0213903743315508}
- **drop:P86**: {'n_observations': 55, 'type_flip_rate': 0.07272727272727272, 'disappearance_rate': 0.03636363636363636, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.07272727272727272, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P69**: {'n_observations': 25, 'type_flip_rate': 0.16, 'disappearance_rate': 0.16, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16, 'percent_wrong_to_correct': 0.08}
- **ambiguous:P161,P495,P57**: {'n_observations': 15, 'type_flip_rate': 0.4, 'disappearance_rate': 0.4666666666666667, 'percent_downgraded_to_other': 0.26666666666666666, 'percent_correct_to_wrong': 0.26666666666666666, 'percent_wrong_to_correct': 0.0}
- **drop:P69**: {'n_observations': 121, 'type_flip_rate': 0.2066115702479339, 'disappearance_rate': 0.2809917355371901, 'percent_downgraded_to_other': 0.05785123966942149, 'percent_correct_to_wrong': 0.1652892561983471, 'percent_wrong_to_correct': 0.04132231404958678}
- **drop:P161**: {'n_observations': 198, 'type_flip_rate': 0.23232323232323232, 'disappearance_rate': 0.30303030303030304, 'percent_downgraded_to_other': 0.015151515151515152, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.005050505050505051}
- **drop:P495**: {'n_observations': 109, 'type_flip_rate': 0.1926605504587156, 'disappearance_rate': 0.1651376146788991, 'percent_downgraded_to_other': 0.01834862385321101, 'percent_correct_to_wrong': 0.05504587155963303, 'percent_wrong_to_correct': 0.009174311926605505}
- **drop:P57**: {'n_observations': 83, 'type_flip_rate': 0.3132530120481928, 'disappearance_rate': 0.1566265060240964, 'percent_downgraded_to_other': 0.07228915662650602, 'percent_correct_to_wrong': 0.060240963855421686, 'percent_wrong_to_correct': 0.012048192771084338}
- **ambiguous:P131,P19,P40**: {'n_observations': 40, 'type_flip_rate': 0.675, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.225, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P361**: {'n_observations': 72, 'type_flip_rate': 0.5972222222222222, 'disappearance_rate': 0.19444444444444445, 'percent_downgraded_to_other': 0.09722222222222222, 'percent_correct_to_wrong': 0.20833333333333334, 'percent_wrong_to_correct': 0.013888888888888888}
- **ambiguous:P17,P1001,P580**: {'n_observations': 18, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.4444444444444444, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **drop:P361**: {'n_observations': 355, 'type_flip_rate': 0.18309859154929578, 'disappearance_rate': 0.36056338028169016, 'percent_downgraded_to_other': 0.04507042253521127, 'percent_correct_to_wrong': 0.056338028169014086, 'percent_wrong_to_correct': 0.011267605633802818}
- **ambiguous:P131,P17,P463**: {'n_observations': 38, 'type_flip_rate': 0.15789473684210525, 'disappearance_rate': 0.13157894736842105, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.10526315789473684, 'percent_wrong_to_correct': 0.10526315789473684}
- **ambiguous:P17,P495,P175**: {'n_observations': 20, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **drop:P1001**: {'n_observations': 127, 'type_flip_rate': 0.10236220472440945, 'disappearance_rate': 0.28346456692913385, 'percent_downgraded_to_other': 0.015748031496062992, 'percent_correct_to_wrong': 0.031496062992125984, 'percent_wrong_to_correct': 0.015748031496062992}
- **drop:P580**: {'n_observations': 157, 'type_flip_rate': 0.15286624203821655, 'disappearance_rate': 0.27388535031847133, 'percent_downgraded_to_other': 0.14012738853503184, 'percent_correct_to_wrong': 0.025477707006369428, 'percent_wrong_to_correct': 0.01910828025477707}
- **ambiguous:P140,P131,P108**: {'n_observations': 13, 'type_flip_rate': 0.3076923076923077, 'disappearance_rate': 0.15384615384615385, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.15384615384615385, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P26,P40,P570**: {'n_observations': 30, 'type_flip_rate': 0.4, 'disappearance_rate': 0.36666666666666664, 'percent_downgraded_to_other': 0.13333333333333333, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P17,P69**: {'n_observations': 21, 'type_flip_rate': 0.19047619047619047, 'disappearance_rate': 0.5714285714285714, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **drop:P108**: {'n_observations': 326, 'type_flip_rate': 0.21779141104294478, 'disappearance_rate': 0.3220858895705521, 'percent_downgraded_to_other': 0.07975460122699386, 'percent_correct_to_wrong': 0.08282208588957055, 'percent_wrong_to_correct': 0.02147239263803681}
- **drop:P463**: {'n_observations': 202, 'type_flip_rate': 0.2524752475247525, 'disappearance_rate': 0.21287128712871287, 'percent_downgraded_to_other': 0.07920792079207921, 'percent_correct_to_wrong': 0.12376237623762376, 'percent_wrong_to_correct': 0.01485148514851485}
- **drop:P140**: {'n_observations': 43, 'type_flip_rate': 0.09302325581395349, 'disappearance_rate': 0.3023255813953488, 'percent_downgraded_to_other': 0.06976744186046512, 'percent_correct_to_wrong': 0.023255813953488372, 'percent_wrong_to_correct': 0.0}
- **drop:P26**: {'n_observations': 110, 'type_flip_rate': 0.2, 'disappearance_rate': 0.22727272727272727, 'percent_downgraded_to_other': 0.12727272727272726, 'percent_correct_to_wrong': 0.16363636363636364, 'percent_wrong_to_correct': 0.02727272727272727}
- **ambiguous:P54,P118,P131**: {'n_observations': 24, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4583333333333333, 'percent_wrong_to_correct': 0.16666666666666666}
- **ambiguous:P178,P127,P131**: {'n_observations': 9, 'type_flip_rate': 0.4444444444444444, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P570**: {'n_observations': 98, 'type_flip_rate': 0.1326530612244898, 'disappearance_rate': 0.29591836734693877, 'percent_downgraded_to_other': 0.08163265306122448, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.01020408163265306}
- **drop:P118**: {'n_observations': 55, 'type_flip_rate': 0.2, 'disappearance_rate': 0.07272727272727272, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.03636363636363636, 'percent_wrong_to_correct': 0.12727272727272726}
- **drop:P54**: {'n_observations': 168, 'type_flip_rate': 0.47023809523809523, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.047619047619047616, 'percent_correct_to_wrong': 0.25595238095238093, 'percent_wrong_to_correct': 0.1130952380952381}
- **drop:P127**: {'n_observations': 69, 'type_flip_rate': 0.14492753623188406, 'disappearance_rate': 0.2028985507246377, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.014492753623188406, 'percent_wrong_to_correct': 0.0}
- **drop:P178**: {'n_observations': 50, 'type_flip_rate': 0.38, 'disappearance_rate': 0.22, 'percent_downgraded_to_other': 0.26, 'percent_correct_to_wrong': 0.02, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P361,P577**: {'n_observations': 13, 'type_flip_rate': 0.38461538461538464, 'disappearance_rate': 0.3076923076923077, 'percent_downgraded_to_other': 0.38461538461538464, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P1441,P140,P40**: {'n_observations': 5, 'type_flip_rate': 0.4, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P1001**: {'n_observations': 41, 'type_flip_rate': 0.21951219512195122, 'disappearance_rate': 0.4146341463414634, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.04878048780487805, 'percent_wrong_to_correct': 0.0}
- **drop:P577**: {'n_observations': 299, 'type_flip_rate': 0.2508361204013378, 'disappearance_rate': 0.22742474916387959, 'percent_downgraded_to_other': 0.17391304347826086, 'percent_correct_to_wrong': 0.12709030100334448, 'percent_wrong_to_correct': 0.016722408026755852}
- **drop:P1441**: {'n_observations': 86, 'type_flip_rate': 0.03488372093023256, 'disappearance_rate': 0.3488372093023256, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.19767441860465115, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P580**: {'n_observations': 89, 'type_flip_rate': 0.4943820224719101, 'disappearance_rate': 0.30337078651685395, 'percent_downgraded_to_other': 0.12359550561797752, 'percent_correct_to_wrong': 0.15730337078651685, 'percent_wrong_to_correct': 0.011235955056179775}
- **ambiguous:P27,P19,P569**: {'n_observations': 16, 'type_flip_rate': 0.5625, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.125, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **drop:P569**: {'n_observations': 38, 'type_flip_rate': 0.15789473684210525, 'disappearance_rate': 0.18421052631578946, 'percent_downgraded_to_other': 0.02631578947368421, 'percent_correct_to_wrong': 0.18421052631578946, 'percent_wrong_to_correct': 0.10526315789473684}
- **ambiguous:P131,P17,P54**: {'n_observations': 57, 'type_flip_rate': 0.38596491228070173, 'disappearance_rate': 0.19298245614035087, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14035087719298245, 'percent_wrong_to_correct': 0.19298245614035087}
- **ambiguous:P17,P131,P463**: {'n_observations': 39, 'type_flip_rate': 0.23076923076923078, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.02564102564102564, 'percent_correct_to_wrong': 0.10256410256410256, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P150**: {'n_observations': 17, 'type_flip_rate': 0.4117647058823529, 'disappearance_rate': 0.4117647058823529, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.23529411764705882, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P264,P577,P800**: {'n_observations': 7, 'type_flip_rate': 0.14285714285714285, 'disappearance_rate': 0.2857142857142857, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2857142857142857, 'percent_wrong_to_correct': 0.14285714285714285}
- **ambiguous:P131,P17,P108**: {'n_observations': 103, 'type_flip_rate': 0.2912621359223301, 'disappearance_rate': 0.3883495145631068, 'percent_downgraded_to_other': 0.17475728155339806, 'percent_correct_to_wrong': 0.07766990291262135, 'percent_wrong_to_correct': 0.02912621359223301}
- **ambiguous:P175,P27,P361**: {'n_observations': 11, 'type_flip_rate': 0.09090909090909091, 'disappearance_rate': 0.45454545454545453, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.18181818181818182, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P206,P17**: {'n_observations': 8, 'type_flip_rate': 0.875, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.75, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P361,P279,P527**: {'n_observations': 18, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.05555555555555555, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P161,P264**: {'n_observations': 26, 'type_flip_rate': 0.34615384615384615, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.038461538461538464, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P131,P580**: {'n_observations': 18, 'type_flip_rate': 0.16666666666666666, 'disappearance_rate': 0.8333333333333334, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.05555555555555555, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P800,P264**: {'n_observations': 28, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.03571428571428571, 'percent_correct_to_wrong': 0.10714285714285714, 'percent_wrong_to_correct': 0.10714285714285714}
- **ambiguous:P175,P577,P800**: {'n_observations': 41, 'type_flip_rate': 0.36585365853658536, 'disappearance_rate': 0.34146341463414637, 'percent_downgraded_to_other': 0.2926829268292683, 'percent_correct_to_wrong': 0.21951219512195122, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P241**: {'n_observations': 20, 'type_flip_rate': 0.3, 'disappearance_rate': 0.35, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.05, 'percent_wrong_to_correct': 0.0}
- **drop:P264**: {'n_observations': 120, 'type_flip_rate': 0.06666666666666667, 'disappearance_rate': 0.45, 'percent_downgraded_to_other': 0.008333333333333333, 'percent_correct_to_wrong': 0.008333333333333333, 'percent_wrong_to_correct': 0.025}
- **ambiguous:P123,P127,P178**: {'n_observations': 13, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P279**: {'n_observations': 26, 'type_flip_rate': 0.07692307692307693, 'disappearance_rate': 0.8461538461538461, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.038461538461538464, 'percent_wrong_to_correct': 0.0}
- **drop:P206**: {'n_observations': 42, 'type_flip_rate': 0.21428571428571427, 'disappearance_rate': 0.23809523809523808, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.023809523809523808, 'percent_wrong_to_correct': 0.047619047619047616}
- **drop:P527**: {'n_observations': 165, 'type_flip_rate': 0.20606060606060606, 'disappearance_rate': 0.41818181818181815, 'percent_downgraded_to_other': 0.09696969696969697, 'percent_correct_to_wrong': 0.08484848484848485, 'percent_wrong_to_correct': 0.006060606060606061}
- **drop:P123**: {'n_observations': 26, 'type_flip_rate': 0.07692307692307693, 'disappearance_rate': 0.038461538461538464, 'percent_downgraded_to_other': 0.34615384615384615, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P241**: {'n_observations': 20, 'type_flip_rate': 0.2, 'disappearance_rate': 0.1, 'percent_downgraded_to_other': 0.45, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P527**: {'n_observations': 28, 'type_flip_rate': 0.17857142857142858, 'disappearance_rate': 0.75, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.17857142857142858, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P131,P17**: {'n_observations': 63, 'type_flip_rate': 0.14285714285714285, 'disappearance_rate': 0.3968253968253968, 'percent_downgraded_to_other': 0.015873015873015872, 'percent_correct_to_wrong': 0.19047619047619047, 'percent_wrong_to_correct': 0.015873015873015872}
- **ambiguous:P131,P27,P17**: {'n_observations': 42, 'type_flip_rate': 0.11904761904761904, 'disappearance_rate': 0.4523809523809524, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.21428571428571427, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P161**: {'n_observations': 9, 'type_flip_rate': 0.1111111111111111, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P361**: {'n_observations': 21, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.19047619047619047, 'percent_downgraded_to_other': 0.09523809523809523, 'percent_correct_to_wrong': 0.047619047619047616, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P54,P17,P131**: {'n_observations': 14, 'type_flip_rate': 0.21428571428571427, 'disappearance_rate': 0.2857142857142857, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.21428571428571427, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P57,P364**: {'n_observations': 35, 'type_flip_rate': 0.08571428571428572, 'disappearance_rate': 0.7714285714285715, 'percent_downgraded_to_other': 0.02857142857142857, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.02857142857142857}
- **ambiguous:P50,P131,P108**: {'n_observations': 14, 'type_flip_rate': 0.2857142857142857, 'disappearance_rate': 0.35714285714285715, 'percent_downgraded_to_other': 0.14285714285714285, 'percent_correct_to_wrong': 0.07142857142857142, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P706**: {'n_observations': 18, 'type_flip_rate': 0.5, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1111111111111111, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P161,P57**: {'n_observations': 7, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.2857142857142857, 'percent_correct_to_wrong': 0.2857142857142857, 'percent_wrong_to_correct': 0.0}
- **drop:P364**: {'n_observations': 35, 'type_flip_rate': 0.3142857142857143, 'disappearance_rate': 0.22857142857142856, 'percent_downgraded_to_other': 0.08571428571428572, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P140,P17**: {'n_observations': 10, 'type_flip_rate': 0.1, 'disappearance_rate': 0.1, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P175,P800**: {'n_observations': 12, 'type_flip_rate': 0.08333333333333333, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.16666666666666666, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **drop:P706**: {'n_observations': 34, 'type_flip_rate': 0.14705882352941177, 'disappearance_rate': 0.08823529411764706, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.029411764705882353}
- **ambiguous:P17,P1344,P710**: {'n_observations': 15, 'type_flip_rate': 0.8, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.26666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P26,P161,P27**: {'n_observations': 5, 'type_flip_rate': 0.2, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P800,P577**: {'n_observations': 36, 'type_flip_rate': 0.16666666666666666, 'disappearance_rate': 0.3055555555555556, 'percent_downgraded_to_other': 0.1111111111111111, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.027777777777777776}
- **ambiguous:P131,P27,P19**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P30,P131,P17**: {'n_observations': 9, 'type_flip_rate': 0.2222222222222222, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P710**: {'n_observations': 99, 'type_flip_rate': 0.2222222222222222, 'disappearance_rate': 0.29292929292929293, 'percent_downgraded_to_other': 0.09090909090909091, 'percent_correct_to_wrong': 0.020202020202020204, 'percent_wrong_to_correct': 0.030303030303030304}
- **ambiguous:P50,P800,P577**: {'n_observations': 6, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P178,P577,P50**: {'n_observations': 14, 'type_flip_rate': 0.5, 'disappearance_rate': 0.07142857142857142, 'percent_downgraded_to_other': 0.6428571428571429, 'percent_correct_to_wrong': 0.07142857142857142, 'percent_wrong_to_correct': 0.0}
- **drop:P30**: {'n_observations': 64, 'type_flip_rate': 0.125, 'disappearance_rate': 0.1875, 'percent_downgraded_to_other': 0.078125, 'percent_correct_to_wrong': 0.046875, 'percent_wrong_to_correct': 0.015625}
- **ambiguous:P30,P463,P69**: {'n_observations': 11, 'type_flip_rate': 0.2727272727272727, 'disappearance_rate': 0.36363636363636365, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.36363636363636365, 'percent_wrong_to_correct': 0.09090909090909091}
- **ambiguous:P161,P495,P1441**: {'n_observations': 36, 'type_flip_rate': 0.7222222222222222, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.027777777777777776}
- **ambiguous:P27,P19,P361**: {'n_observations': 6, 'type_flip_rate': 0.0, 'disappearance_rate': 0.8333333333333334, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P166,P27,P569**: {'n_observations': 5, 'type_flip_rate': 0.4, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.6, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P40,P161**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P361,P30**: {'n_observations': 4, 'type_flip_rate': 0.5, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **drop:P166**: {'n_observations': 31, 'type_flip_rate': 0.2903225806451613, 'disappearance_rate': 0.16129032258064516, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.03225806451612903, 'percent_wrong_to_correct': 0.03225806451612903}
- **ambiguous:P175,P361,P800**: {'n_observations': 13, 'type_flip_rate': 0.15384615384615385, 'disappearance_rate': 0.7692307692307693, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P527,P463,P361**: {'n_observations': 11, 'type_flip_rate': 0.18181818181818182, 'disappearance_rate': 0.7272727272727273, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P50,P800,P175**: {'n_observations': 29, 'type_flip_rate': 0.13793103448275862, 'disappearance_rate': 0.6551724137931034, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.20689655172413793, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P170,P361,P40**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P264,P175,P800**: {'n_observations': 27, 'type_flip_rate': 0.2962962962962963, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.4074074074074074, 'percent_correct_to_wrong': 0.1111111111111111, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P131,P17**: {'n_observations': 15, 'type_flip_rate': 0.2, 'disappearance_rate': 0.5333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.13333333333333333, 'percent_wrong_to_correct': 0.06666666666666667}
- **ambiguous:P54,P463,P27**: {'n_observations': 9, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.1111111111111111, 'percent_correct_to_wrong': 0.4444444444444444, 'percent_wrong_to_correct': 0.1111111111111111}
- **ambiguous:P27,P17,P131**: {'n_observations': 12, 'type_flip_rate': 0.0, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.08333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P800,P527**: {'n_observations': 10, 'type_flip_rate': 0.0, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **drop:P170**: {'n_observations': 10, 'type_flip_rate': 0.3, 'disappearance_rate': 0.1, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P800,P175,P577**: {'n_observations': 9, 'type_flip_rate': 0.1111111111111111, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4444444444444444, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P1412,P17**: {'n_observations': 5, 'type_flip_rate': 0.0, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P403**: {'n_observations': 20, 'type_flip_rate': 0.45, 'disappearance_rate': 0.45, 'percent_downgraded_to_other': 0.1, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **drop:P1412**: {'n_observations': 5, 'type_flip_rate': 0.2, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P570,P17**: {'n_observations': 6, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.16666666666666666, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P206**: {'n_observations': 28, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.5357142857142857, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.17857142857142858, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P361,P150**: {'n_observations': 11, 'type_flip_rate': 0.8181818181818182, 'disappearance_rate': 0.09090909090909091, 'percent_downgraded_to_other': 0.09090909090909091, 'percent_correct_to_wrong': 0.7272727272727273, 'percent_wrong_to_correct': 0.0}
- **drop:P403**: {'n_observations': 20, 'type_flip_rate': 0.35, 'disappearance_rate': 0.05, 'percent_downgraded_to_other': 0.05, 'percent_correct_to_wrong': 0.05, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P140,P131,P361**: {'n_observations': 7, 'type_flip_rate': 0.7142857142857143, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2857142857142857, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P800,P27**: {'n_observations': 12, 'type_flip_rate': 0.0, 'disappearance_rate': 0.6666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.08333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P495,P50,P800**: {'n_observations': 1, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 1.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P571**: {'n_observations': 3, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.3333333333333333, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P1344,P607,P710**: {'n_observations': 14, 'type_flip_rate': 0.21428571428571427, 'disappearance_rate': 0.42857142857142855, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P1441,P50,P674**: {'n_observations': 6, 'type_flip_rate': 0.0, 'disappearance_rate': 0.6666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **drop:P571**: {'n_observations': 11, 'type_flip_rate': 0.18181818181818182, 'disappearance_rate': 0.2727272727272727, 'percent_downgraded_to_other': 0.18181818181818182, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P175,P1344**: {'n_observations': 5, 'type_flip_rate': 0.2, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **drop:P607**: {'n_observations': 53, 'type_flip_rate': 0.18867924528301888, 'disappearance_rate': 0.3018867924528302, 'percent_downgraded_to_other': 0.018867924528301886, 'percent_correct_to_wrong': 0.018867924528301886, 'percent_wrong_to_correct': 0.018867924528301886}
- **ambiguous:P127,P17,P176**: {'n_observations': 7, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P674**: {'n_observations': 25, 'type_flip_rate': 0.0, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P800,P86**: {'n_observations': 24, 'type_flip_rate': 0.9166666666666666, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P40,P50**: {'n_observations': 9, 'type_flip_rate': 0.4444444444444444, 'disappearance_rate': 0.1111111111111111, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P150,P17**: {'n_observations': 34, 'type_flip_rate': 0.2647058823529412, 'disappearance_rate': 0.5882352941176471, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2647058823529412, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P150,P527**: {'n_observations': 17, 'type_flip_rate': 0.8235294117647058, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.058823529411764705, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P800,P175,P361**: {'n_observations': 10, 'type_flip_rate': 0.4, 'disappearance_rate': 0.3, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1, 'percent_wrong_to_correct': 0.0}
- **drop:P176**: {'n_observations': 52, 'type_flip_rate': 0.40384615384615385, 'disappearance_rate': 0.3076923076923077, 'percent_downgraded_to_other': 0.1346153846153846, 'percent_correct_to_wrong': 0.019230769230769232, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P172,P27**: {'n_observations': 15, 'type_flip_rate': 0.26666666666666666, 'disappearance_rate': 0.26666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.06666666666666667, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P17,P569**: {'n_observations': 5, 'type_flip_rate': 0.2, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **drop:P172**: {'n_observations': 32, 'type_flip_rate': 0.0625, 'disappearance_rate': 0.40625, 'percent_downgraded_to_other': 0.09375, 'percent_correct_to_wrong': 0.03125, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P1344,P710,P27**: {'n_observations': 7, 'type_flip_rate': 0.2857142857142857, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.14285714285714285}
- **ambiguous:P161,P108,P19**: {'n_observations': 17, 'type_flip_rate': 0.17647058823529413, 'disappearance_rate': 0.6470588235294118, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.058823529411764705, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P50,P27,P19**: {'n_observations': 9, 'type_flip_rate': 0.0, 'disappearance_rate': 0.7777777777777778, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P57,P577**: {'n_observations': 10, 'type_flip_rate': 0.4, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.8, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P527,P361,P175**: {'n_observations': 13, 'type_flip_rate': 0.46153846153846156, 'disappearance_rate': 0.15384615384615385, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.15384615384615385, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P3373,P27,P1344**: {'n_observations': 8, 'type_flip_rate': 0.5, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P140,P279,P361**: {'n_observations': 8, 'type_flip_rate': 0.125, 'disappearance_rate': 0.75, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P27,P26**: {'n_observations': 15, 'type_flip_rate': 0.26666666666666666, 'disappearance_rate': 0.26666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.13333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P527,P361**: {'n_observations': 16, 'type_flip_rate': 0.5, 'disappearance_rate': 0.1875, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P264,P50**: {'n_observations': 22, 'type_flip_rate': 0.2727272727272727, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P272,P449,P108**: {'n_observations': 7, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.14285714285714285, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P1344,P710,P607**: {'n_observations': 39, 'type_flip_rate': 0.10256410256410256, 'disappearance_rate': 0.38461538461538464, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.02564102564102564}
- **ambiguous:P131,P17,P30**: {'n_observations': 9, 'type_flip_rate': 0.7777777777777778, 'disappearance_rate': 0.2222222222222222, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P27,P131**: {'n_observations': 15, 'type_flip_rate': 0.8, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P800,P570**: {'n_observations': 11, 'type_flip_rate': 0.2727272727272727, 'disappearance_rate': 0.5454545454545454, 'percent_downgraded_to_other': 0.09090909090909091, 'percent_correct_to_wrong': 0.2727272727272727, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P118**: {'n_observations': 5, 'type_flip_rate': 0.4, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.2, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **drop:P272**: {'n_observations': 7, 'type_flip_rate': 0.14285714285714285, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **drop:P449**: {'n_observations': 7, 'type_flip_rate': 0.14285714285714285, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P172**: {'n_observations': 17, 'type_flip_rate': 0.5294117647058824, 'disappearance_rate': 0.17647058823529413, 'percent_downgraded_to_other': 0.17647058823529413, 'percent_correct_to_wrong': 0.058823529411764705, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P27,P17**: {'n_observations': 13, 'type_flip_rate': 0.3076923076923077, 'disappearance_rate': 0.38461538461538464, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.07692307692307693, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P937,P69**: {'n_observations': 12, 'type_flip_rate': 0.4166666666666667, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.5, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P361,P527**: {'n_observations': 7, 'type_flip_rate': 0.2857142857142857, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P30,P706,P108**: {'n_observations': 7, 'type_flip_rate': 0.0, 'disappearance_rate': 0.42857142857142855, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2857142857142857, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P108**: {'n_observations': 8, 'type_flip_rate': 0.5, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.75, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.25}
- **ambiguous:P40,P26,P69**: {'n_observations': 11, 'type_flip_rate': 0.18181818181818182, 'disappearance_rate': 0.45454545454545453, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.36363636363636365, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P361,P527,P155**: {'n_observations': 10, 'type_flip_rate': 0.4, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P54,P108,P27**: {'n_observations': 18, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.6666666666666666, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P31**: {'n_observations': 1, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P155**: {'n_observations': 10, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P50,P27,P69**: {'n_observations': 18, 'type_flip_rate': 0.1111111111111111, 'disappearance_rate': 0.8333333333333334, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **drop:P937**: {'n_observations': 15, 'type_flip_rate': 0.06666666666666667, 'disappearance_rate': 0.06666666666666667, 'percent_downgraded_to_other': 0.06666666666666667, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P26,P1001**: {'n_observations': 10, 'type_flip_rate': 0.4, 'disappearance_rate': 0.3, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P800,P361**: {'n_observations': 22, 'type_flip_rate': 0.22727272727272727, 'disappearance_rate': 0.45454545454545453, 'percent_downgraded_to_other': 0.09090909090909091, 'percent_correct_to_wrong': 0.2727272727272727, 'percent_wrong_to_correct': 0.0}
- **drop:P31**: {'n_observations': 15, 'type_flip_rate': 0.0, 'disappearance_rate': 0.13333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P1001,P131,P937**: {'n_observations': 3, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P400,P577,P123**: {'n_observations': 13, 'type_flip_rate': 0.7692307692307693, 'disappearance_rate': 0.07692307692307693, 'percent_downgraded_to_other': 0.23076923076923078, 'percent_correct_to_wrong': 0.07692307692307693, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P463,P27,P488**: {'n_observations': 10, 'type_flip_rate': 0.4, 'disappearance_rate': 0.3, 'percent_downgraded_to_other': 0.5, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P527,P171**: {'n_observations': 14, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P54,P131**: {'n_observations': 7, 'type_flip_rate': 0.5714285714285714, 'disappearance_rate': 0.14285714285714285, 'percent_downgraded_to_other': 0.14285714285714285, 'percent_correct_to_wrong': 0.42857142857142855, 'percent_wrong_to_correct': 0.14285714285714285}
- **drop:P400**: {'n_observations': 13, 'type_flip_rate': 0.23076923076923078, 'disappearance_rate': 0.6923076923076923, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P131,P463**: {'n_observations': 18, 'type_flip_rate': 0.5, 'disappearance_rate': 0.1111111111111111, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5555555555555556, 'percent_wrong_to_correct': 0.05555555555555555}
- **drop:P171**: {'n_observations': 30, 'type_flip_rate': 0.1, 'disappearance_rate': 0.06666666666666667, 'percent_downgraded_to_other': 0.3333333333333333, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P17,P800**: {'n_observations': 18, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P1001,P131**: {'n_observations': 2, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P488**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.1, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P1441,P674,P131**: {'n_observations': 8, 'type_flip_rate': 0.125, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.125, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P577,P27**: {'n_observations': 17, 'type_flip_rate': 0.29411764705882354, 'disappearance_rate': 0.4117647058823529, 'percent_downgraded_to_other': 0.17647058823529413, 'percent_correct_to_wrong': 0.17647058823529413, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131**: {'n_observations': 5, 'type_flip_rate': 0.6, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.2, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P54,P463,P118**: {'n_observations': 6, 'type_flip_rate': 0.5, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P50,P131,P17**: {'n_observations': 7, 'type_flip_rate': 0.2857142857142857, 'disappearance_rate': 0.7142857142857143, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P463,P27,P102**: {'n_observations': 28, 'type_flip_rate': 0.10714285714285714, 'disappearance_rate': 0.75, 'percent_downgraded_to_other': 0.17857142857142858, 'percent_correct_to_wrong': 0.32142857142857145, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P26,P40,P569**: {'n_observations': 12, 'type_flip_rate': 0.5, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4166666666666667, 'percent_wrong_to_correct': 0.08333333333333333}
- **ambiguous:P131,P27,P495**: {'n_observations': 9, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.4444444444444444, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4444444444444444, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P800,P577**: {'n_observations': 11, 'type_flip_rate': 0.36363636363636365, 'disappearance_rate': 0.18181818181818182, 'percent_downgraded_to_other': 0.18181818181818182, 'percent_correct_to_wrong': 0.2727272727272727, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P50,P800,P27**: {'n_observations': 16, 'type_flip_rate': 0.125, 'disappearance_rate': 0.375, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0625, 'percent_wrong_to_correct': 0.0}
- **drop:P102**: {'n_observations': 28, 'type_flip_rate': 0.25, 'disappearance_rate': 0.17857142857142858, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.07142857142857142}
- **ambiguous:P131,P570,P19**: {'n_observations': 8, 'type_flip_rate': 0.625, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.375, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P131,P17**: {'n_observations': 11, 'type_flip_rate': 0.18181818181818182, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.5454545454545454, 'percent_correct_to_wrong': 0.2727272727272727, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P175,P577**: {'n_observations': 10, 'type_flip_rate': 0.4, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.4, 'percent_correct_to_wrong': 0.6, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P57,P577,P58**: {'n_observations': 5, 'type_flip_rate': 0.6, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P159,P150**: {'n_observations': 11, 'type_flip_rate': 0.09090909090909091, 'disappearance_rate': 0.8181818181818182, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P1441,P26,P495**: {'n_observations': 9, 'type_flip_rate': 0.0, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P570,P108,P19**: {'n_observations': 8, 'type_flip_rate': 0.375, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P1441,P3373,P674**: {'n_observations': 11, 'type_flip_rate': 0.0, 'disappearance_rate': 0.2727272727272727, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P150,P30,P361**: {'n_observations': 10, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 1.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P706,P17**: {'n_observations': 3, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.3333333333333333}
- **drop:P58**: {'n_observations': 5, 'type_flip_rate': 0.6, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P577,P17**: {'n_observations': 16, 'type_flip_rate': 0.3125, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.4375, 'percent_correct_to_wrong': 0.0625, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P463,P580,P571**: {'n_observations': 8, 'type_flip_rate': 0.25, 'disappearance_rate': 0.625, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P264,P175,P577**: {'n_observations': 10, 'type_flip_rate': 0.6, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.5, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P20**: {'n_observations': 10, 'type_flip_rate': 0.3, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.1}
- **ambiguous:P355,P749,P127**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.3, 'percent_downgraded_to_other': 0.1, 'percent_correct_to_wrong': 0.1, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P580,P582,P108**: {'n_observations': 24, 'type_flip_rate': 0.7916666666666666, 'disappearance_rate': 0.08333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P355**: {'n_observations': 10, 'type_flip_rate': 0.1, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1, 'percent_wrong_to_correct': 0.0}
- **drop:P20**: {'n_observations': 10, 'type_flip_rate': 0.3, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.1}
- **drop:P749**: {'n_observations': 10, 'type_flip_rate': 0.1, 'disappearance_rate': 0.3, 'percent_downgraded_to_other': 0.1, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P127,P176,P17**: {'n_observations': 13, 'type_flip_rate': 0.23076923076923078, 'disappearance_rate': 0.6923076923076923, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.07692307692307693, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P706,P206**: {'n_observations': 6, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P582**: {'n_observations': 24, 'type_flip_rate': 0.041666666666666664, 'disappearance_rate': 0.7083333333333334, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P27,P118**: {'n_observations': 10, 'type_flip_rate': 0.1, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P276**: {'n_observations': 2, 'type_flip_rate': 0.5, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P361,P108**: {'n_observations': 23, 'type_flip_rate': 0.21739130434782608, 'disappearance_rate': 0.5652173913043478, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.043478260869565216}
- **drop:P276**: {'n_observations': 2, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P1001**: {'n_observations': 43, 'type_flip_rate': 0.37209302325581395, 'disappearance_rate': 0.3488372093023256, 'percent_downgraded_to_other': 0.046511627906976744, 'percent_correct_to_wrong': 0.11627906976744186, 'percent_wrong_to_correct': 0.023255813953488372}
- **ambiguous:P175,P166,P577**: {'n_observations': 14, 'type_flip_rate': 0.6428571428571429, 'disappearance_rate': 0.21428571428571427, 'percent_downgraded_to_other': 0.7857142857142857, 'percent_correct_to_wrong': 0.07142857142857142, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P150**: {'n_observations': 9, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P127,P178,P1056**: {'n_observations': 1, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P463,P17,P131**: {'n_observations': 5, 'type_flip_rate': 0.4, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P1344,P710,P19**: {'n_observations': 8, 'type_flip_rate': 0.25, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **drop:P1056**: {'n_observations': 1, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P127,P137**: {'n_observations': 5, 'type_flip_rate': 0.0, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P159,P131,P1344**: {'n_observations': 7, 'type_flip_rate': 0.14285714285714285, 'disappearance_rate': 0.42857142857142855, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P1344,P710**: {'n_observations': 12, 'type_flip_rate': 0.25, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.08333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P171,P361,P131**: {'n_observations': 6, 'type_flip_rate': 0.8333333333333334, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P176,P131**: {'n_observations': 19, 'type_flip_rate': 0.631578947368421, 'disappearance_rate': 0.10526315789473684, 'percent_downgraded_to_other': 0.5263157894736842, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P137**: {'n_observations': 16, 'type_flip_rate': 0.125, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0625, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P26**: {'n_observations': 10, 'type_flip_rate': 0.5, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P37,P131**: {'n_observations': 4, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.5, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P463,P131**: {'n_observations': 9, 'type_flip_rate': 0.1111111111111111, 'disappearance_rate': 0.7777777777777778, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P570,P1001**: {'n_observations': 9, 'type_flip_rate': 0.0, 'disappearance_rate': 0.1111111111111111, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1111111111111111, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P1441,P495**: {'n_observations': 11, 'type_flip_rate': 0.0, 'disappearance_rate': 0.6363636363636364, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.09090909090909091, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P57,P27,P577**: {'n_observations': 11, 'type_flip_rate': 0.0, 'disappearance_rate': 0.5454545454545454, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.09090909090909091, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P30,P171**: {'n_observations': 10, 'type_flip_rate': 0.8, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.2, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P495,P361,P527**: {'n_observations': 8, 'type_flip_rate': 0.375, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 1.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P26,P166,P161**: {'n_observations': 8, 'type_flip_rate': 0.625, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.25, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.125}
- **ambiguous:P54,P118,P463**: {'n_observations': 10, 'type_flip_rate': 0.7, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.1}
- **ambiguous:P17,P27,P1001**: {'n_observations': 1, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P1344,P166,P710**: {'n_observations': 4, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P570,P131**: {'n_observations': 16, 'type_flip_rate': 0.3125, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.5625, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P31,P361**: {'n_observations': 14, 'type_flip_rate': 0.0, 'disappearance_rate': 0.7857142857142857, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P361,P137,P127**: {'n_observations': 11, 'type_flip_rate': 0.09090909090909091, 'disappearance_rate': 0.8181818181818182, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2727272727272727, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P30,P17**: {'n_observations': 4, 'type_flip_rate': 0.5, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P40,P131,P570**: {'n_observations': 10, 'type_flip_rate': 0.4, 'disappearance_rate': 0.3, 'percent_downgraded_to_other': 0.2, 'percent_correct_to_wrong': 0.1, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P69,P54**: {'n_observations': 23, 'type_flip_rate': 0.782608695652174, 'disappearance_rate': 0.21739130434782608, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.21739130434782608, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P178,P527,P176**: {'n_observations': 13, 'type_flip_rate': 0.23076923076923078, 'disappearance_rate': 0.6153846153846154, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.07692307692307693, 'percent_wrong_to_correct': 0.0}

## E4 cost-quality

> `recall@k` = (oracle causes recovered) / (total oracle causes)  ·  `hit` = fraction of selected interventions hitting ≥1 cause.

- planner=exhaustive     budget=1    recall@k=1.000  hit=0.46  reuse=11.41  tok_in=10618610  tok_out=25062986
- planner=exhaustive     budget=2    recall@k=1.000  hit=0.46  reuse=11.41  tok_in=10618610  tok_out=25062986
- planner=exhaustive     budget=3    recall@k=1.000  hit=0.46  reuse=11.41  tok_in=10618610  tok_out=25062986
- planner=exhaustive     budget=4    recall@k=1.000  hit=0.46  reuse=11.41  tok_in=10618610  tok_out=25062986
- planner=exhaustive     budget=6    recall@k=1.000  hit=0.46  reuse=11.41  tok_in=10618610  tok_out=25062986
- planner=exhaustive     budget=8    recall@k=1.000  hit=0.46  reuse=11.41  tok_in=10618610  tok_out=25062986
- planner=random         budget=1    recall@k=0.020  hit=0.40  reuse=12.71  tok_in=225986  tok_out=503822
- planner=random         budget=2    recall@k=0.069  hit=0.40  reuse=12.04  tok_in=423374  tok_out=1059669
- planner=random         budget=3    recall@k=0.097  hit=0.44  reuse=11.32  tok_in=688618  tok_out=1698049
- planner=random         budget=4    recall@k=0.114  hit=0.42  reuse=11.39  tok_in=891972  tok_out=2175669
- planner=random         budget=6    recall@k=0.212  hit=0.48  reuse=11.47  tok_in=1563634  tok_out=3765131
- planner=random         budget=8    recall@k=0.256  hit=0.46  reuse=11.43  tok_in=1977247  tok_out=4726362
- planner=span_only      budget=1    recall@k=0.001  hit=0.13  reuse=11.43  tok_in=64482  tok_out=147020
- planner=span_only      budget=2    recall@k=0.001  hit=0.13  reuse=11.43  tok_in=129340  tok_out=285747
- planner=span_only      budget=3    recall@k=0.001  hit=0.13  reuse=11.43  tok_in=193874  tok_out=434360
- planner=span_only      budget=4    recall@k=0.001  hit=0.13  reuse=11.43  tok_in=258418  tok_out=586580
- planner=span_only      budget=6    recall@k=0.002  hit=0.13  reuse=11.43  tok_in=387336  tok_out=872155
- planner=span_only      budget=8    recall@k=0.002  hit=0.13  reuse=11.43  tok_in=516464  tok_out=1183411
- planner=prompt_only    budget=1    recall@k=0.155  hit=1.00  reuse=12.25  tok_in=536045  tok_out=1268796
- planner=prompt_only    budget=2    recall@k=0.157  hit=0.57  reuse=11.60  tok_in=602294  tok_out=1428858
- planner=prompt_only    budget=3    recall@k=0.158  hit=0.42  reuse=11.38  tok_in=668241  tok_out=1578105
- planner=prompt_only    budget=4    recall@k=0.161  hit=0.35  reuse=11.28  tok_in=735383  tok_out=1736986
- planner=prompt_only    budget=6    recall@k=0.316  hit=0.42  reuse=11.38  tok_in=1339945  tok_out=3157997
- planner=prompt_only    budget=8    recall@k=0.404  hit=0.46  reuse=11.44  tok_in=1945015  tok_out=4603551
- planner=schema_only    budget=1    recall@k=0.010  hit=1.00  reuse=12.25  tok_in=633563  tok_out=1316748
- planner=schema_only    budget=2    recall@k=0.024  hit=1.00  reuse=12.25  tok_in=1122224  tok_out=2624048
- planner=schema_only    budget=3    recall@k=0.196  hit=1.00  reuse=12.25  tok_in=1579141  tok_out=4088733
- planner=schema_only    budget=4    recall@k=0.297  hit=1.00  reuse=12.25  tok_in=2121303  tok_out=5482209
- planner=schema_only    budget=6    recall@k=0.322  hit=1.00  reuse=12.25  tok_in=3203309  tok_out=7967648
- planner=schema_only    budget=8    recall@k=0.335  hit=1.00  reuse=12.25  tok_in=4289513  tok_out=10502981
- planner=graphguard  budget=1    recall@k=0.029  hit=1.00  reuse=12.25  tok_in=541313  tok_out=1295830
- planner=graphguard  budget=2    recall@k=0.068  hit=1.00  reuse=12.25  tok_in=1082590  tok_out=2564298
- planner=graphguard  budget=3    recall@k=0.117  hit=1.00  reuse=12.25  tok_in=1624257  tok_out=3867024
- planner=graphguard  budget=4    recall@k=0.136  hit=1.00  reuse=12.25  tok_in=2164844  tok_out=5126255
- planner=graphguard  budget=6    recall@k=0.173  hit=1.00  reuse=12.25  tok_in=3264422  tok_out=7752763
- planner=graphguard  budget=8    recall@k=0.211  hit=1.00  reuse=12.25  tok_in=4359546  tok_out=10352315
- planner=adaptive_graphguard budget=1    recall@k=0.027  hit=0.84  reuse=11.30  tok_in=431864  tok_out=1047347
- planner=adaptive_graphguard budget=2    recall@k=0.069  hit=0.88  reuse=11.52  tok_in=905424  tok_out=2108448
- planner=adaptive_graphguard budget=3    recall@k=0.099  hit=0.86  reuse=11.55  tok_in=1328721  tok_out=3120926
- planner=adaptive_graphguard budget=4    recall@k=0.023  hit=0.14  reuse=11.80  tok_in=234806  tok_out=578286
- planner=adaptive_graphguard budget=6    recall@k=0.063  hit=0.23  reuse=11.34  tok_in=624552  tok_out=1449524
- planner=adaptive_graphguard budget=8    recall@k=0.247  hit=0.43  reuse=11.41  tok_in=1603878  tok_out=3696709

**Cost-quality AUC (higher = better):**
- exhaustive: 1.0
- prompt_only: 0.2386
- schema_only: 0.2354
- random: 0.1468
- graphguard: 0.1373
- adaptive_graphguard: 0.084
- span_only: 0.0014

## Repair (secondary, exploratory)

> F1-improving repair is **not yet supported by current data**; reported for completeness only.

- raw               best F1=0.149 at frac=0.0
- random            best F1=0.149 at frac=0.0
- by_confidence     best F1=0.151 at frac=0.1
- by_risk           best F1=0.149 at frac=0.0
- by_schema_sens    best F1=0.149 at frac=0.0
- by_stability      best F1=0.149 at frac=0.0

## Case studies (one per category when available)

### Case 1 [prompt_induced_wrong]: (Kriegers Flak) -[P361]-> (Denmark)
- risk=2.6, stab=0.0, label=wrong
- top existence cause: tone on prompt_clause 'strict' → edge disappears in 1/1 runs
- top type cause:      remove on prompt_clause 'C1_evidence_only' → relation type flips in 1/1 runs

### Case 2 [schema_forced_flip]: (Kriegers Flak) -[P361]-> (Germany)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: tone on prompt_clause 'strict' → edge disappears in 1/1 runs
- top type cause:      remove on prompt_clause 'C1_evidence_only' → relation type flips in 1/1 runs

### Case 3 [schema_forced_flip]: (Kriegers Flak) -[P361]-> (Sweden)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: tone on prompt_clause 'strict' → edge disappears in 1/1 runs
- top type cause:      remove on prompt_clause 'C1_evidence_only' → relation type flips in 1/1 runs

### Case 4 [prompt_induced_wrong]: (South Sudan) -[OTHER]-> (9 July 2011)
- risk=2.6, stab=0.0, label=wrong
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs
- top type cause:      tone on prompt_clause 'strict' → relation type flips in 1/1 runs

### Case 5 [prompt_induced_wrong]: (Red Bird) -[P19]-> (the United States)
- risk=2.6, stab=0.0, label=wrong
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs
- top type cause:      tone on prompt_clause 'strict' → relation type flips in 1/1 runs

### Case 6 [prompt_induced_wrong]: (the United States) -[P150]-> (Wisconsin)
- risk=2.6, stab=0.0, label=correct
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs

### Case 7 [schema_forced_flip]: (the United States) -[P17]-> (Americans)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs

### Case 8 [schema_forced_flip]: (Ho - Chunk) -[P463]-> (Winnebago)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs
- top type cause:      switch_schema on schema 'drop:P131' → relation type flips in 1/1 runs

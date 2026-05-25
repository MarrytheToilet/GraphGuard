# GraphGuard experiment report

> **Claim.** GraphGuard enables reliability auditing of LLM-extracted graph databases. Current evidence supports audit prioritization; F1 repair remains a secondary, in-progress claim.

## Database summary

- documents: 100
- sentences: 801
- entities: 1905
- gold_edges: 1315
- extraction_events: 1991
- extracted_edges: 16131
- intervention_candidates: 4301
- counterfactual_runs: 1776
- edge_outcomes: 14102
- edge_reliability_scores: 1137
- edge_correctness: 819
- stability_reports: 29

## E0 stability

```json
{
  "docs": [
    {
      "document_id": "docred-validation-000000-Skai_TV",
      "event_ids": [
        "evt-docred-validation-000000-Skai_TV-baf4949d87",
        "evt-docred-validation-000000-Skai_TV-1dbbc90a00",
        "evt-docred-validation-000000-Skai_TV-13e89b7a12",
        "evt-docred-validation-000000-Skai_TV-eb3b593ae1"
      ],
      "metrics": {
        "avg_edge_overlap": 0.7183,
        "type_agreement": 0.8,
        "disappearance_rate": 0.2056,
        "type_flip_rate": 0.1333,
        "new_edge_rate": 0.1333
      }
    },
    {
      "document_id": "docred-validation-000001-Washington_Place__West_Virginia_",
      "event_ids": [
        "evt-docred-validation-000001-Washington_Place__West_Virginia_-765d58e521",
        "evt-docred-validation-000001-Washington_Place__West_Virginia_-ce29a8ee90",
        "evt-docred-validation-000001-Washington_Place__West_Virginia_-3acb9bd6a2",
        "evt-docred-validation-000001-Washington_Place__West_Virginia_-8ef67022c9"
      ],
      "metrics": {
        "avg_edge_overlap": 0.3274,
        "type_agreement": 1.0,
        "disappearance_rate": 0.5532,
        "type_flip_rate": 0.0,
        "new_edge_rate": 0.5208
      }
    },
    {
      "document_id": "docred-validation-000002-IBM_Research___Brazil",
      "event_ids": [
        "evt-docred-validation-000002-IBM_Research___Brazil-d82d235f09",
        "evt-docred-validation-000002-IBM_Research___Brazil-ef53b2b585",
        "evt-docred-validation-000002-IBM_Research___B
```

## E2 error detection (multi-mode)

- correct=151 wrong=103 unmatched=565 ambiguous=0

**Mode `strict`** — positive = wrong + unmatched (assumes DocRED gold is complete) (n_eval=819, prevalence=0.8156)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.933 | 0.764 | 0.98 | 0.99 | 0.99 |
| prompt_sensitivity | 0.873 | 0.652 | 0.88 | 0.93 | 0.93 |
| schema_sensitivity | 0.932 | 0.747 | 0.98 | 0.99 | 0.99 |
| stochastic_variance | 0.784 | 0.500 | 0.68 | 0.73 | 0.78 |
| 1_minus_stability | 0.942 | 0.790 | 0.98 | 0.98 | 0.98 |
| random | 0.837 | 0.524 | 0.90 | 0.87 | 0.87 |
| baseline:confidence_inv | 0.936 | 0.747 | 1.00 | 1.00 | 0.99 |
| baseline:majority_vote_inv | 0.881 | 0.662 | 0.95 | 0.90 | 0.93 |
| baseline:source_prov_inv | 0.784 | 0.500 | 0.68 | 0.73 | 0.78 |
| baseline:subj_obj_cooccur_inv | 0.829 | 0.589 | 0.73 | 0.80 | 0.80 |

**Mode `clean`** — drop unmatched; correct vs wrong only (robust to gold incompleteness) (n_eval=254, prevalence=0.4055)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.674 | 0.745 | 0.92 | 0.88 | 0.67 |
| prompt_sensitivity | 0.515 | 0.624 | 0.62 | 0.68 | 0.65 |
| schema_sensitivity | 0.700 | 0.737 | 0.92 | 0.88 | 0.84 |
| stochastic_variance | 0.394 | 0.500 | 0.46 | 0.32 | 0.41 |
| 1_minus_stability | 0.716 | 0.789 | 0.85 | 0.84 | 0.80 |
| random | 0.389 | 0.485 | 0.23 | 0.28 | 0.37 |
| baseline:confidence_inv | 0.510 | 0.560 | 0.77 | 0.56 | 0.55 |
| baseline:majority_vote_inv | 0.540 | 0.636 | 0.62 | 0.64 | 0.65 |
| baseline:source_prov_inv | 0.394 | 0.500 | 0.46 | 0.32 | 0.41 |
| baseline:subj_obj_cooccur_inv | 0.457 | 0.591 | 0.31 | 0.40 | 0.37 |

**Mode `wrong_only`** — positive = wrong only; unmatched treated as negative (n_eval=819, prevalence=0.1258)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.126 | 0.514 | 0.02 | 0.04 | 0.13 |
| prompt_sensitivity | 0.134 | 0.497 | 0.17 | 0.18 | 0.12 |
| schema_sensitivity | 0.128 | 0.523 | 0.02 | 0.04 | 0.13 |
| stochastic_variance | 0.143 | 0.500 | 0.15 | 0.15 | 0.15 |
| 1_minus_stability | 0.132 | 0.528 | 0.07 | 0.10 | 0.15 |
| random | 0.128 | 0.468 | 0.17 | 0.12 | 0.13 |
| baseline:confidence_inv | 0.089 | 0.338 | 0.00 | 0.06 | 0.04 |
| baseline:majority_vote_inv | 0.135 | 0.501 | 0.17 | 0.11 | 0.15 |
| baseline:source_prov_inv | 0.143 | 0.500 | 0.15 | 0.15 | 0.15 |
| baseline:subj_obj_cooccur_inv | 0.146 | 0.520 | 0.17 | 0.15 | 0.12 |

## E5 audit prioritization (primary)


**Mode `strict`** — positive = wrong + unmatched (n_eval=819, prevalence=0.8156)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 99.0 | 1.00 | 0.98 | 0.99 | 81 | 162 |
| prompt_sensitivity | 92.0 | 0.70 | 0.90 | 0.92 | 76 | 152 |
| schema_sensitivity | 99.0 | 1.00 | 0.98 | 0.99 | 81 | 162 |
| stochastic_variance | 74.0 | 0.50 | 0.76 | 0.74 | 64 | 125 |
| 1_minus_stability | 98.0 | 1.00 | 0.98 | 0.98 | 80 | 160 |
| 1_minus_confidence | 100.0 | 1.00 | 1.00 | 1.00 | 82 | 163 |
| random | 77.0 | 0.90 | 0.74 | 0.77 | 60 | 130 |
| baseline:confidence_inv | 100.0 | 1.00 | 1.00 | 1.00 | 82 | 163 |
| baseline:majority_vote_inv | 91.0 | 0.90 | 0.90 | 0.91 | 73 | 152 |
| baseline:source_prov_inv | 74.0 | 0.50 | 0.76 | 0.74 | 64 | 125 |
| baseline:subj_obj_cooccur_inv | 84.0 | 0.80 | 0.82 | 0.84 | 68 | 128 |

**Mode `clean`** — drop unmatched; correct vs wrong only (n_eval=254, prevalence=0.4055)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 64.0 | 0.90 | 0.66 | 0.64 | 22 | 34 |
| prompt_sensitivity | 52.0 | 0.40 | 0.64 | 0.52 | 16 | 33 |
| schema_sensitivity | 65.0 | 0.90 | 0.84 | 0.65 | 22 | 43 |
| stochastic_variance | 35.0 | 0.40 | 0.38 | 0.35 | 12 | 20 |
| 1_minus_stability | 67.0 | 0.80 | 0.82 | 0.67 | 21 | 41 |
| 1_minus_confidence | 45.0 | 0.70 | 0.54 | 0.45 | 14 | 27 |
| random | 37.0 | 0.40 | 0.40 | 0.37 | 9 | 20 |
| baseline:confidence_inv | 45.0 | 0.70 | 0.54 | 0.45 | 14 | 27 |
| baseline:majority_vote_inv | 52.0 | 0.70 | 0.64 | 0.52 | 15 | 32 |
| baseline:source_prov_inv | 35.0 | 0.40 | 0.38 | 0.35 | 12 | 20 |
| baseline:subj_obj_cooccur_inv | 45.0 | 0.60 | 0.38 | 0.45 | 12 | 20 |

**Mode `wrong_only`** — positive = wrong only; unmatched treated as negative (n_eval=819, prevalence=0.1258)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 8.0 | 0.00 | 0.02 | 0.08 | 3 | 21 |
| prompt_sensitivity | 15.0 | 0.00 | 0.04 | 0.15 | 3 | 20 |
| schema_sensitivity | 4.0 | 0.10 | 0.04 | 0.04 | 4 | 22 |
| stochastic_variance | 16.0 | 0.20 | 0.16 | 0.16 | 15 | 23 |
| 1_minus_stability | 10.0 | 0.20 | 0.08 | 0.10 | 8 | 13 |
| 1_minus_confidence | 5.0 | 0.00 | 0.04 | 0.05 | 5 | 7 |
| random | 9.0 | 0.10 | 0.10 | 0.09 | 9 | 19 |
| baseline:confidence_inv | 5.0 | 0.00 | 0.04 | 0.05 | 5 | 7 |
| baseline:majority_vote_inv | 10.0 | 0.10 | 0.16 | 0.10 | 9 | 24 |
| baseline:source_prov_inv | 16.0 | 0.20 | 0.16 | 0.16 | 15 | 23 |
| baseline:subj_obj_cooccur_inv | 14.0 | 0.30 | 0.16 | 0.14 | 12 | 20 |

## E1 known-cause

```json
{
  "n": 727,
  "top1_acc": 0.8019257221458047,
  "top3_recall": 0.8858321870701513,
  "mrr": 0.8383768913342505,
  "macro_f1": 0.42214059498468404,
  "per_cause_f1": {
    "noop": 0.0,
    "prompt_clause": 0.6951871657754011,
    "schema": 0.8757281553398057,
    "sentence": 0.11764705882352941
  },
  "per_cause_n": {
    "noop": 0,
    "prompt_clause": 228,
    "schema": 472,
    "sentence": 27
  }
}
```

## E3 schema debugging — flip rates per variant

- **ambiguous:P17,P159,P361**: {'n_observations': 10, 'type_flip_rate': 0.4, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **coarse**: {'n_observations': 918, 'type_flip_rate': 0.6884531590413944, 'disappearance_rate': 0.2821350762527233, 'percent_downgraded_to_other': 0.023965141612200435, 'percent_correct_to_wrong': 0.17429193899782136, 'percent_wrong_to_correct': 0.0}
- **desc_added**: {'n_observations': 918, 'type_flip_rate': 0.1655773420479303, 'disappearance_rate': 0.19607843137254902, 'percent_downgraded_to_other': 0.03812636165577342, 'percent_correct_to_wrong': 0.020697167755991286, 'percent_wrong_to_correct': 0.027233115468409588}
- **ambiguous:P176,P361,P17**: {'n_observations': 8, 'type_flip_rate': 0.5, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P150**: {'n_observations': 50, 'type_flip_rate': 0.48, 'disappearance_rate': 0.46, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.08, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P159,P361**: {'n_observations': 15, 'type_flip_rate': 0.13333333333333333, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **desc_removed**: {'n_observations': 918, 'type_flip_rate': 0.25381263616557737, 'disappearance_rate': 0.19281045751633988, 'percent_downgraded_to_other': 0.0392156862745098, 'percent_correct_to_wrong': 0.032679738562091505, 'percent_wrong_to_correct': 0.013071895424836602}
- **drop:P159**: {'n_observations': 79, 'type_flip_rate': 0.25316455696202533, 'disappearance_rate': 0.24050632911392406, 'percent_downgraded_to_other': 0.012658227848101266, 'percent_correct_to_wrong': 0.05063291139240506, 'percent_wrong_to_correct': 0.012658227848101266}
- **ambiguous:P17,P131,P150**: {'n_observations': 99, 'type_flip_rate': 0.43434343434343436, 'disappearance_rate': 0.24242424242424243, 'percent_downgraded_to_other': 0.050505050505050504, 'percent_correct_to_wrong': 0.10101010101010101, 'percent_wrong_to_correct': 0.010101010101010102}
- **drop:P17**: {'n_observations': 483, 'type_flip_rate': 0.20496894409937888, 'disappearance_rate': 0.20082815734989648, 'percent_downgraded_to_other': 0.022774327122153208, 'percent_correct_to_wrong': 0.06832298136645963, 'percent_wrong_to_correct': 0.010351966873706004}
- **drop:P361**: {'n_observations': 118, 'type_flip_rate': 0.2457627118644068, 'disappearance_rate': 0.288135593220339, 'percent_downgraded_to_other': 0.01694915254237288, 'percent_correct_to_wrong': 0.00847457627118644, 'percent_wrong_to_correct': 0.0}
- **hierarchical**: {'n_observations': 918, 'type_flip_rate': 0.20915032679738563, 'disappearance_rate': 0.18518518518518517, 'percent_downgraded_to_other': 0.08061002178649238, 'percent_correct_to_wrong': 0.037037037037037035, 'percent_wrong_to_correct': 0.02505446623093682}
- **ambiguous:P577,P175,P54**: {'n_observations': 15, 'type_flip_rate': 0.4, 'disappearance_rate': 0.26666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.26666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P27**: {'n_observations': 17, 'type_flip_rate': 0.11764705882352941, 'disappearance_rate': 0.6470588235294118, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.23529411764705882, 'percent_wrong_to_correct': 0.0}
- **drop:P131**: {'n_observations': 423, 'type_flip_rate': 0.26004728132387706, 'disappearance_rate': 0.28132387706855794, 'percent_downgraded_to_other': 0.04728132387706856, 'percent_correct_to_wrong': 0.054373522458628844, 'percent_wrong_to_correct': 0.018912529550827423}
- **drop:P108**: {'n_observations': 150, 'type_flip_rate': 0.21333333333333335, 'disappearance_rate': 0.30666666666666664, 'percent_downgraded_to_other': 0.006666666666666667, 'percent_correct_to_wrong': 0.04, 'percent_wrong_to_correct': 0.0}
- **rename**: {'n_observations': 918, 'type_flip_rate': 0.2549019607843137, 'disappearance_rate': 0.20043572984749455, 'percent_downgraded_to_other': 0.011982570806100218, 'percent_correct_to_wrong': 0.03159041394335512, 'percent_wrong_to_correct': 0.0}
- **drop:P150**: {'n_observations': 175, 'type_flip_rate': 0.2342857142857143, 'disappearance_rate': 0.19428571428571428, 'percent_downgraded_to_other': 0.10857142857142857, 'percent_correct_to_wrong': 0.05142857142857143, 'percent_wrong_to_correct': 0.022857142857142857}
- **drop:P176**: {'n_observations': 14, 'type_flip_rate': 0.0, 'disappearance_rate': 0.07142857142857142, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **reorder**: {'n_observations': 918, 'type_flip_rate': 0.22657952069716775, 'disappearance_rate': 0.20697167755991286, 'percent_downgraded_to_other': 0.05010893246187364, 'percent_correct_to_wrong': 0.04030501089324619, 'percent_wrong_to_correct': 0.02832244008714597}
- **with_other**: {'n_observations': 918, 'type_flip_rate': 0.10457516339869281, 'disappearance_rate': 0.10784313725490197, 'percent_downgraded_to_other': 0.04357298474945534, 'percent_correct_to_wrong': 0.008714596949891068, 'percent_wrong_to_correct': 0.002178649237472767}
- **ambiguous:P570,P137,P19**: {'n_observations': 17, 'type_flip_rate': 0.47058823529411764, 'disappearance_rate': 0.058823529411764705, 'percent_downgraded_to_other': 0.23529411764705882, 'percent_correct_to_wrong': 0.23529411764705882, 'percent_wrong_to_correct': 0.0}
- **drop:P175**: {'n_observations': 116, 'type_flip_rate': 0.2413793103448276, 'disappearance_rate': 0.23275862068965517, 'percent_downgraded_to_other': 0.06896551724137931, 'percent_correct_to_wrong': 0.04310344827586207, 'percent_wrong_to_correct': 0.0}
- **drop:P54**: {'n_observations': 43, 'type_flip_rate': 0.23255813953488372, 'disappearance_rate': 0.23255813953488372, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P577**: {'n_observations': 111, 'type_flip_rate': 0.17117117117117117, 'disappearance_rate': 0.2072072072072072, 'percent_downgraded_to_other': 0.05405405405405406, 'percent_correct_to_wrong': 0.05405405405405406, 'percent_wrong_to_correct': 0.018018018018018018}
- **drop:P27**: {'n_observations': 172, 'type_flip_rate': 0.18604651162790697, 'disappearance_rate': 0.27906976744186046, 'percent_downgraded_to_other': 0.01744186046511628, 'percent_correct_to_wrong': 0.11046511627906977, 'percent_wrong_to_correct': 0.0}
- **drop:P137**: {'n_observations': 17, 'type_flip_rate': 0.058823529411764705, 'disappearance_rate': 0.17647058823529413, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P19**: {'n_observations': 62, 'type_flip_rate': 0.16129032258064516, 'disappearance_rate': 0.1935483870967742, 'percent_downgraded_to_other': 0.04838709677419355, 'percent_correct_to_wrong': 0.11290322580645161, 'percent_wrong_to_correct': 0.016129032258064516}
- **ambiguous:P17,P69,P131**: {'n_observations': 27, 'type_flip_rate': 0.07407407407407407, 'disappearance_rate': 0.48148148148148145, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **drop:P570**: {'n_observations': 77, 'type_flip_rate': 0.36363636363636365, 'disappearance_rate': 0.1038961038961039, 'percent_downgraded_to_other': 0.09090909090909091, 'percent_correct_to_wrong': 0.11688311688311688, 'percent_wrong_to_correct': 0.1038961038961039}
- **drop:P69**: {'n_observations': 60, 'type_flip_rate': 0.06666666666666667, 'disappearance_rate': 0.26666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.15, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P194,P131**: {'n_observations': 9, 'type_flip_rate': 0.2222222222222222, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1111111111111111, 'percent_wrong_to_correct': 0.0}
- **drop:P194**: {'n_observations': 9, 'type_flip_rate': 0.1111111111111111, 'disappearance_rate': 0.2222222222222222, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P463,P108**: {'n_observations': 13, 'type_flip_rate': 0.46153846153846156, 'disappearance_rate': 0.5384615384615384, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P161,P50**: {'n_observations': 20, 'type_flip_rate': 0.4, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P463**: {'n_observations': 144, 'type_flip_rate': 0.3611111111111111, 'disappearance_rate': 0.1736111111111111, 'percent_downgraded_to_other': 0.020833333333333332, 'percent_correct_to_wrong': 0.034722222222222224, 'percent_wrong_to_correct': 0.0763888888888889}
- **drop:P161**: {'n_observations': 69, 'type_flip_rate': 0.3188405797101449, 'disappearance_rate': 0.11594202898550725, 'percent_downgraded_to_other': 0.17391304347826086, 'percent_correct_to_wrong': 0.08695652173913043, 'percent_wrong_to_correct': 0.0}
- **drop:P50**: {'n_observations': 26, 'type_flip_rate': 0.19230769230769232, 'disappearance_rate': 0.34615384615384615, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P27,P463**: {'n_observations': 9, 'type_flip_rate': 0.1111111111111111, 'disappearance_rate': 0.4444444444444444, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P54,P27**: {'n_observations': 7, 'type_flip_rate': 0.8571428571428571, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P150**: {'n_observations': 3, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.6666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P361**: {'n_observations': 6, 'type_flip_rate': 0.8333333333333334, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P19**: {'n_observations': 6, 'type_flip_rate': 0.8333333333333334, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P27,P108**: {'n_observations': 9, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P361,P264**: {'n_observations': 12, 'type_flip_rate': 0.5833333333333334, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.08333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P108**: {'n_observations': 26, 'type_flip_rate': 0.23076923076923078, 'disappearance_rate': 0.4230769230769231, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.038461538461538464, 'percent_wrong_to_correct': 0.0}
- **drop:P264**: {'n_observations': 43, 'type_flip_rate': 0.23255813953488372, 'disappearance_rate': 0.27906976744186046, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.023255813953488372}
- **ambiguous:P131,P150,P361**: {'n_observations': 9, 'type_flip_rate': 0.4444444444444444, 'disappearance_rate': 0.4444444444444444, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P19,P131**: {'n_observations': 4, 'type_flip_rate': 0.5, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P19,P108,P569**: {'n_observations': 8, 'type_flip_rate': 0.5, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.375, 'percent_correct_to_wrong': 0.375, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P26,P131,P17**: {'n_observations': 5, 'type_flip_rate': 0.2, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P463,P569,P570**: {'n_observations': 11, 'type_flip_rate': 0.7272727272727273, 'disappearance_rate': 0.18181818181818182, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.18181818181818182, 'percent_wrong_to_correct': 0.09090909090909091}
- **ambiguous:P463,P577,P175**: {'n_observations': 10, 'type_flip_rate': 0.3, 'disappearance_rate': 0.3, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P569**: {'n_observations': 84, 'type_flip_rate': 0.2976190476190476, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.047619047619047616, 'percent_correct_to_wrong': 0.13095238095238096, 'percent_wrong_to_correct': 0.047619047619047616}
- **ambiguous:P161,P27,P495**: {'n_observations': 11, 'type_flip_rate': 0.18181818181818182, 'disappearance_rate': 0.7272727272727273, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.6363636363636364, 'percent_wrong_to_correct': 0.0}
- **drop:P26**: {'n_observations': 23, 'type_flip_rate': 0.2608695652173913, 'disappearance_rate': 0.13043478260869565, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.13043478260869565, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P361**: {'n_observations': 7, 'type_flip_rate': 0.5714285714285714, 'disappearance_rate': 0.42857142857142855, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P570,P19**: {'n_observations': 7, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.2857142857142857, 'percent_downgraded_to_other': 0.2857142857142857, 'percent_correct_to_wrong': 0.42857142857142855, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P159**: {'n_observations': 28, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.03571428571428571, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P159,P108,P131**: {'n_observations': 3, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P463,P30**: {'n_observations': 6, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **drop:P495**: {'n_observations': 68, 'type_flip_rate': 0.29411764705882354, 'disappearance_rate': 0.27941176470588236, 'percent_downgraded_to_other': 0.029411764705882353, 'percent_correct_to_wrong': 0.029411764705882353, 'percent_wrong_to_correct': 0.16176470588235295}
- **drop:P30**: {'n_observations': 6, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P577,P495**: {'n_observations': 11, 'type_flip_rate': 0.2727272727272727, 'disappearance_rate': 0.36363636363636365, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P463,P161,P495**: {'n_observations': 17, 'type_flip_rate': 0.0, 'disappearance_rate': 0.8235294117647058, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.058823529411764705, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P17,P264**: {'n_observations': 10, 'type_flip_rate': 0.1, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P264,P175,P577**: {'n_observations': 8, 'type_flip_rate': 0.125, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P159,P108,P361**: {'n_observations': 7, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.2857142857142857, 'percent_downgraded_to_other': 0.14285714285714285, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P108,P361**: {'n_observations': 6, 'type_flip_rate': 0.8333333333333334, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P127,P355,P17**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P463,P69**: {'n_observations': 8, 'type_flip_rate': 0.75, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **drop:P127**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P1441,P361**: {'n_observations': 8, 'type_flip_rate': 0.875, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P355**: {'n_observations': 10, 'type_flip_rate': 0.0, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P26**: {'n_observations': 3, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 1.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P26,P569**: {'n_observations': 7, 'type_flip_rate': 0.2857142857142857, 'disappearance_rate': 0.42857142857142855, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2857142857142857, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P40,P3373,P17**: {'n_observations': 15, 'type_flip_rate': 0.13333333333333333, 'disappearance_rate': 0.5333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P1441**: {'n_observations': 8, 'type_flip_rate': 0.0, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P69,P108**: {'n_observations': 14, 'type_flip_rate': 0.14285714285714285, 'disappearance_rate': 0.2857142857142857, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P577,P159**: {'n_observations': 10, 'type_flip_rate': 0.7, 'disappearance_rate': 0.1, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P570,P19,P569**: {'n_observations': 9, 'type_flip_rate': 0.2222222222222222, 'disappearance_rate': 0.2222222222222222, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **drop:P3373**: {'n_observations': 15, 'type_flip_rate': 0.13333333333333333, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P40**: {'n_observations': 55, 'type_flip_rate': 0.14545454545454545, 'disappearance_rate': 0.4727272727272727, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P495,P57,P577**: {'n_observations': 7, 'type_flip_rate': 0.14285714285714285, 'disappearance_rate': 0.7142857142857143, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2857142857142857, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P179,P123,P495**: {'n_observations': 4, 'type_flip_rate': 0.75, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P463,P108**: {'n_observations': 7, 'type_flip_rate': 0.14285714285714285, 'disappearance_rate': 0.2857142857142857, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **drop:P123**: {'n_observations': 4, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P150,P131**: {'n_observations': 5, 'type_flip_rate': 0.0, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **drop:P179**: {'n_observations': 4, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P57**: {'n_observations': 15, 'type_flip_rate': 0.13333333333333333, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.13333333333333333, 'percent_correct_to_wrong': 0.06666666666666667, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P463,P131,P740**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.7, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P26,P40,P569**: {'n_observations': 8, 'type_flip_rate': 0.375, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P17,P131**: {'n_observations': 10, 'type_flip_rate': 0.0, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P463,P527**: {'n_observations': 6, 'type_flip_rate': 0.0, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.16666666666666666, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P27,P1412**: {'n_observations': 5, 'type_flip_rate': 0.4, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P463,P175**: {'n_observations': 11, 'type_flip_rate': 0.2727272727272727, 'disappearance_rate': 0.5454545454545454, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.18181818181818182, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P159,P176**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P569,P570,P361**: {'n_observations': 5, 'type_flip_rate': 0.4, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P361,P580**: {'n_observations': 5, 'type_flip_rate': 0.6, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P57,P27,P569**: {'n_observations': 8, 'type_flip_rate': 0.25, 'disappearance_rate': 0.75, 'percent_downgraded_to_other': 0.125, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **drop:P1412**: {'n_observations': 5, 'type_flip_rate': 0.0, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P527**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.16666666666666666, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P740**: {'n_observations': 10, 'type_flip_rate': 0.1, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P580**: {'n_observations': 13, 'type_flip_rate': 0.23076923076923078, 'disappearance_rate': 0.07692307692307693, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P17,P463**: {'n_observations': 8, 'type_flip_rate': 0.125, 'disappearance_rate': 0.375, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P361,P495,P50**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P150,P131,P17**: {'n_observations': 9, 'type_flip_rate': 0.7777777777777778, 'disappearance_rate': 0.1111111111111111, 'percent_downgraded_to_other': 0.1111111111111111, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P577,P131**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.16666666666666666}
- **ambiguous:P175,P131,P264**: {'n_observations': 13, 'type_flip_rate': 0.15384615384615385, 'disappearance_rate': 0.6153846153846154, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P569,P570**: {'n_observations': 16, 'type_flip_rate': 0.4375, 'disappearance_rate': 0.0625, 'percent_downgraded_to_other': 0.5, 'percent_correct_to_wrong': 0.1875, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P463**: {'n_observations': 5, 'type_flip_rate': 0.8, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.2, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P577,P17**: {'n_observations': 12, 'type_flip_rate': 0.9166666666666666, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.08333333333333333, 'percent_wrong_to_correct': 0.08333333333333333}
- **ambiguous:P40,P577,P161**: {'n_observations': 21, 'type_flip_rate': 0.14285714285714285, 'disappearance_rate': 0.5714285714285714, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P463,P108**: {'n_observations': 5, 'type_flip_rate': 0.8, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.2, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P54,P17,P463**: {'n_observations': 10, 'type_flip_rate': 0.0, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P495,P27**: {'n_observations': 12, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P1056,P178**: {'n_observations': 5, 'type_flip_rate': 0.2, 'disappearance_rate': 0.8, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P54,P27,P108**: {'n_observations': 7, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.42857142857142855, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **drop:P1056**: {'n_observations': 5, 'type_flip_rate': 0.4, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.2, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.2}
- **drop:P178**: {'n_observations': 5, 'type_flip_rate': 0.4, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.2, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.2}
- **ambiguous:P27,P570,P569**: {'n_observations': 8, 'type_flip_rate': 0.5, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.375, 'percent_correct_to_wrong': 0.375, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P19,P40,P69**: {'n_observations': 11, 'type_flip_rate': 0.18181818181818182, 'disappearance_rate': 0.5454545454545454, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.09090909090909091, 'percent_wrong_to_correct': 0.09090909090909091}
- **ambiguous:P17,P361,P576**: {'n_observations': 14, 'type_flip_rate': 0.0, 'disappearance_rate': 0.8571428571428571, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P27,P131**: {'n_observations': 11, 'type_flip_rate': 0.36363636363636365, 'disappearance_rate': 0.36363636363636365, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.09090909090909091, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P569,P570,P54**: {'n_observations': 4, 'type_flip_rate': 0.75, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P463,P580**: {'n_observations': 8, 'type_flip_rate': 0.625, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **drop:P576**: {'n_observations': 14, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}

## E4 cost-quality

> `recall@k` = (oracle causes recovered) / (total oracle causes)  ·  `hit` = fraction of selected interventions hitting ≥1 cause.

- planner=exhaustive     budget=1    recall@k=1.000  hit=0.38  reuse=8.56  tok_in=2922752  tok_out=1101569
- planner=exhaustive     budget=2    recall@k=1.000  hit=0.38  reuse=8.56  tok_in=2922752  tok_out=1101569
- planner=exhaustive     budget=3    recall@k=1.000  hit=0.38  reuse=8.56  tok_in=2922752  tok_out=1101569
- planner=exhaustive     budget=4    recall@k=1.000  hit=0.38  reuse=8.56  tok_in=2922752  tok_out=1101569
- planner=exhaustive     budget=6    recall@k=1.000  hit=0.38  reuse=8.56  tok_in=2922752  tok_out=1101569
- planner=exhaustive     budget=8    recall@k=1.000  hit=0.38  reuse=8.56  tok_in=2922752  tok_out=1101569
- planner=random         budget=1    recall@k=0.011  hit=0.30  reuse=9.57  tok_in=62305  tok_out=21637
- planner=random         budget=2    recall@k=0.142  hit=0.42  reuse=8.80  tok_in=152150  tok_out=64160
- planner=random         budget=3    recall@k=0.180  hit=0.41  reuse=8.80  tok_in=222069  tok_out=89682
- planner=random         budget=4    recall@k=0.192  hit=0.36  reuse=8.66  tok_in=262696  tok_out=104484
- planner=random         budget=6    recall@k=0.277  hit=0.43  reuse=8.66  tok_in=474269  tok_out=184898
- planner=random         budget=8    recall@k=0.290  hit=0.39  reuse=8.54  tok_in=566246  tok_out=219961
- planner=span_only      budget=1    recall@k=0.000  hit=0.14  reuse=7.29  tok_in=21740  tok_out=7401
- planner=span_only      budget=2    recall@k=0.000  hit=0.14  reuse=7.29  tok_in=43742  tok_out=15292
- planner=span_only      budget=3    recall@k=0.001  hit=0.14  reuse=7.29  tok_in=65568  tok_out=22335
- planner=span_only      budget=4    recall@k=0.001  hit=0.14  reuse=7.29  tok_in=87533  tok_out=29585
- planner=span_only      budget=6    recall@k=0.002  hit=0.14  reuse=7.29  tok_in=131381  tok_out=44115
- planner=span_only      budget=8    recall@k=0.002  hit=0.14  reuse=7.29  tok_in=175189  tok_out=58668
- planner=prompt_only    budget=1    recall@k=0.125  hit=1.00  reuse=9.27  tok_in=186551  tok_out=72500
- planner=prompt_only    budget=2    recall@k=0.126  hit=0.57  reuse=8.77  tok_in=208993  tok_out=80437
- planner=prompt_only    budget=3    recall@k=0.127  hit=0.43  reuse=8.61  tok_in=231351  tok_out=88428
- planner=prompt_only    budget=4    recall@k=0.130  hit=0.36  reuse=8.52  tok_in=253373  tok_out=96620
- planner=prompt_only    budget=6    recall@k=0.135  hit=0.28  reuse=8.44  tok_in=297795  tok_out=113011
- planner=prompt_only    budget=8    recall@k=0.139  hit=0.25  reuse=8.40  tok_in=342217  tok_out=130307
- planner=schema_only    budget=1    recall@k=0.071  hit=1.00  reuse=9.27  tok_in=218869  tok_out=70318
- planner=schema_only    budget=2    recall@k=0.120  hit=1.00  reuse=9.27  tok_in=389600  tok_out=142159
- planner=schema_only    budget=3    recall@k=0.467  hit=1.00  reuse=9.27  tok_in=550839  tok_out=231771
- planner=schema_only    budget=4    recall@k=0.710  hit=1.00  reuse=9.27  tok_in=739193  tok_out=297328
- planner=schema_only    budget=6    recall@k=0.762  hit=1.00  reuse=9.27  tok_in=1114887  tok_out=433441
- planner=schema_only    budget=8    recall@k=0.797  hit=1.00  reuse=9.27  tok_in=1492308  tok_out=580887
- planner=graphguard  budget=1    recall@k=0.065  hit=1.00  reuse=9.27  tok_in=187947  tok_out=69125
- planner=graphguard  budget=2    recall@k=0.170  hit=1.00  reuse=9.27  tok_in=376014  tok_out=138332
- planner=graphguard  budget=3    recall@k=0.279  hit=1.00  reuse=9.27  tok_in=564097  tok_out=204143
- planner=graphguard  budget=4    recall@k=0.321  hit=1.00  reuse=9.27  tok_in=751846  tok_out=269087
- planner=graphguard  budget=6    recall@k=0.445  hit=1.00  reuse=9.27  tok_in=1130178  tok_out=420802
- planner=graphguard  budget=8    recall@k=0.549  hit=1.00  reuse=9.27  tok_in=1509606  tok_out=569536
- planner=adaptive_graphguard budget=1    recall@k=0.055  hit=0.85  reuse=8.77  tok_in=155769  tok_out=57777
- planner=adaptive_graphguard budget=2    recall@k=0.117  hit=0.85  reuse=8.93  tok_in=313222  tok_out=118324
- planner=adaptive_graphguard budget=3    recall@k=0.186  hit=0.85  reuse=8.95  tok_in=463896  tok_out=175358
- planner=adaptive_graphguard budget=4    recall@k=0.021  hit=0.20  reuse=7.70  tok_in=110564  tok_out=38714
- planner=adaptive_graphguard budget=6    recall@k=0.043  hit=0.20  reuse=8.55  tok_in=172157  tok_out=63570
- planner=adaptive_graphguard budget=8    recall@k=0.101  hit=0.28  reuse=8.43  tok_in=336310  tok_out=120592

**Cost-quality AUC (higher = better):**
- exhaustive: 1.0
- schema_only: 0.5727
- graphguard: 0.3431
- random: 0.2086
- prompt_only: 0.1313
- adaptive_graphguard: 0.0784
- span_only: 0.0012

## Repair (secondary, exploratory)

> F1-improving repair is **not yet supported by current data**; reported for completeness only.

- raw               best F1=0.142 at frac=0.0
- random            best F1=0.142 at frac=0.0
- by_confidence     best F1=0.156 at frac=0.3
- by_risk           best F1=0.152 at frac=0.2
- by_schema_sens    best F1=0.156 at frac=0.3
- by_stability      best F1=0.155 at frac=0.3

## Case studies (one per category when available)

### Case 1 [prompt_induced_wrong]: (Rogaland county) -[P17]-> (Norway)
- risk=2.6, stab=0.0, label=correct
- top existence cause: switch_schema on schema 'ambiguous:P17,P150,P131' → edge disappears in 1/1 runs

### Case 2 [schema_forced_flip]: (Civilian Conservation Corps) -[P159]-> (Masten)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C2_infer_implicit' → edge disappears in 1/1 runs

### Case 3 [schema_forced_flip]: (Old Loggers Path) -[P361]-> (Union Tanning Company)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: switch_schema on schema 'ambiguous:P131,P17,P361' → edge disappears in 1/1 runs

### Case 4 [schema_forced_flip]: (Old Loggers Path) -[P361]-> (Central Pennsylvania Lumber Company)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: switch_schema on schema 'ambiguous:P131,P17,P361' → edge disappears in 1/1 runs

### Case 5 [schema_forced_flip]: (Each Time You Break My Heart) -[P463]-> (United Kingdom)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: switch_schema on schema 'ambiguous:P264,P175,P577' → edge disappears in 1/1 runs
- top type cause:      remove on prompt_clause 'C2_infer_implicit' → relation type flips in 1/1 runs

### Case 6 [schema_forced_flip]: (Each Time You Break My Heart) -[P463]-> (France)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C2_infer_implicit' → edge disappears in 1/1 runs
- top type cause:      switch_schema on schema 'coarse' → relation type flips in 1/1 runs

### Case 7 [schema_forced_flip]: (Confucius Prize) -[P361]-> (International Jury)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: switch_schema on schema 'ambiguous:P159,P108,P361' → edge disappears in 1/1 runs

### Case 8 [schema_forced_flip]: (Bicycles & Tricycles) -[P569]-> (1990s)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C2_infer_implicit' → edge disappears in 1/1 runs

# GraphGuard experiment report

> **Claim.** GraphGuard enables reliability auditing of LLM-extracted graph databases. Current evidence supports audit prioritization; F1 repair remains a secondary, in-progress claim.

## Database summary

- documents: 300
- sentences: 2427
- entities: 5716
- gold_edges: 3717
- extraction_events: 7113
- extracted_edges: 71926
- intervention_candidates: 12944
- counterfactual_runs: 6419
- edge_outcomes: 61558
- edge_reliability_scores: 4136
- edge_correctness: 2839
- stability_reports: 79

## E0 stability

```json
{
  "docs": [
    {
      "document_id": "docred-validation-000000-Skai_TV",
      "event_ids": [
        "evt-docred-validation-000000-Skai_TV-617e89a3ef",
        "evt-docred-validation-000000-Skai_TV-336063a6f4",
        "evt-docred-validation-000000-Skai_TV-3cf9cfa70e",
        "evt-docred-validation-000000-Skai_TV-0acc89d03b",
        "evt-docred-validation-000000-Skai_TV-0cdd5ef1fe"
      ],
      "metrics": {
        "avg_edge_overlap": 0.8714,
        "type_agreement": 1.0,
        "disappearance_rate": 0.0833,
        "type_flip_rate": 0.0,
        "new_edge_rate": 0.05
      }
    },
    {
      "document_id": "docred-validation-000001-Washington_Place__West_Virginia_",
      "event_ids": [
        "evt-docred-validation-000001-Washington_Place__West_Virginia_-d1db147f1d",
        "evt-docred-validation-000001-Washington_Place__West_Virginia_-996cf215c1",
        "evt-docred-validation-000001-Washington_Place__West_Virginia_-91c6156484",
        "evt-docred-validation-000001-Washington_Place__West_Virginia_-7874eea2fb",
        "evt-docred-validation-000001-Washington_Place__West_Virginia_-4820b6dfde"
      ],
      "metrics": {
        "avg_edge_overlap": 0.382,
        "type_agreement": 0.625,
        "disappearance_rate": 0.368,
        "type_flip_rate": 0.268,
        "new_edge_rate": 0.4836
      }
    },
    {
      "document_id": "docred-validation-000002-IBM_Research___Brazil",
      "event_ids": [
        "evt-docred-validation-000002-IBM_Research___Brazil-
```

## E2 error detection (multi-mode)

- correct=637 wrong=293 unmatched=1909 ambiguous=0

**Mode `strict`** — positive = wrong + unmatched (assumes DocRED gold is complete) (n_eval=2839, prevalence=0.7756)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.915 | 0.793 | 0.95 | 0.94 | 0.94 |
| prompt_sensitivity | 0.909 | 0.769 | 0.94 | 0.94 | 0.94 |
| schema_sensitivity | 0.904 | 0.750 | 0.93 | 0.95 | 0.93 |
| stochastic_variance | 0.761 | 0.500 | 0.72 | 0.75 | 0.75 |
| 1_minus_stability | 0.916 | 0.802 | 0.92 | 0.94 | 0.92 |
| random | 0.772 | 0.485 | 0.78 | 0.75 | 0.77 |
| baseline:confidence_inv | 0.911 | 0.755 | 0.96 | 0.97 | 0.97 |
| baseline:majority_vote_inv | 0.909 | 0.789 | 0.92 | 0.93 | 0.93 |
| baseline:source_prov_inv | 0.761 | 0.500 | 0.73 | 0.75 | 0.75 |
| baseline:subj_obj_cooccur_inv | 0.812 | 0.606 | 0.80 | 0.79 | 0.80 |

**Mode `clean`** — drop unmatched; correct vs wrong only (robust to gold incompleteness) (n_eval=930, prevalence=0.3151)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.613 | 0.776 | 0.78 | 0.68 | 0.68 |
| prompt_sensitivity | 0.608 | 0.768 | 0.74 | 0.70 | 0.65 |
| schema_sensitivity | 0.587 | 0.730 | 0.72 | 0.70 | 0.68 |
| stochastic_variance | 0.313 | 0.500 | 0.33 | 0.31 | 0.31 |
| 1_minus_stability | 0.604 | 0.793 | 0.67 | 0.70 | 0.67 |
| random | 0.367 | 0.528 | 0.54 | 0.47 | 0.39 |
| baseline:confidence_inv | 0.575 | 0.727 | 0.72 | 0.74 | 0.61 |
| baseline:majority_vote_inv | 0.590 | 0.792 | 0.59 | 0.62 | 0.65 |
| baseline:source_prov_inv | 0.313 | 0.500 | 0.33 | 0.31 | 0.31 |
| baseline:subj_obj_cooccur_inv | 0.335 | 0.541 | 0.35 | 0.30 | 0.30 |

**Mode `wrong_only`** — positive = wrong only; unmatched treated as negative (n_eval=2839, prevalence=0.1032)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.129 | 0.568 | 0.15 | 0.17 | 0.13 |
| prompt_sensitivity | 0.134 | 0.572 | 0.18 | 0.15 | 0.13 |
| schema_sensitivity | 0.124 | 0.554 | 0.15 | 0.14 | 0.13 |
| stochastic_variance | 0.114 | 0.500 | 0.13 | 0.12 | 0.11 |
| 1_minus_stability | 0.123 | 0.570 | 0.12 | 0.14 | 0.14 |
| random | 0.110 | 0.485 | 0.11 | 0.11 | 0.10 |
| baseline:confidence_inv | 0.106 | 0.520 | 0.09 | 0.07 | 0.10 |
| baseline:majority_vote_inv | 0.123 | 0.577 | 0.13 | 0.14 | 0.13 |
| baseline:source_prov_inv | 0.111 | 0.500 | 0.13 | 0.12 | 0.10 |
| baseline:subj_obj_cooccur_inv | 0.100 | 0.454 | 0.10 | 0.10 | 0.09 |

## E5 audit prioritization (primary)


**Mode `strict`** — positive = wrong + unmatched (n_eval=2839, prevalence=0.7756)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 94.0 | 1.00 | 0.94 | 0.94 | 265 | 532 |
| prompt_sensitivity | 93.0 | 1.00 | 0.96 | 0.93 | 265 | 535 |
| schema_sensitivity | 96.0 | 1.00 | 0.98 | 0.96 | 269 | 531 |
| stochastic_variance | 74.0 | 0.70 | 0.70 | 0.74 | 207 | 425 |
| 1_minus_stability | 92.0 | 1.00 | 0.90 | 0.92 | 266 | 525 |
| 1_minus_confidence | 98.0 | 1.00 | 0.96 | 0.98 | 276 | 551 |
| random | 78.0 | 0.70 | 0.78 | 0.78 | 227 | 452 |
| baseline:confidence_inv | 98.0 | 1.00 | 0.96 | 0.98 | 276 | 551 |
| baseline:majority_vote_inv | 94.0 | 1.00 | 0.90 | 0.94 | 263 | 530 |
| baseline:source_prov_inv | 74.0 | 0.70 | 0.72 | 0.74 | 207 | 425 |
| baseline:subj_obj_cooccur_inv | 80.0 | 0.90 | 0.94 | 0.80 | 223 | 453 |

**Mode `clean`** — drop unmatched; correct vs wrong only (n_eval=930, prevalence=0.3151)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 68.0 | 0.70 | 0.78 | 0.68 | 63 | 125 |
| prompt_sensitivity | 69.0 | 0.80 | 0.76 | 0.69 | 65 | 121 |
| schema_sensitivity | 66.0 | 0.80 | 0.74 | 0.66 | 64 | 126 |
| stochastic_variance | 30.0 | 0.40 | 0.36 | 0.30 | 29 | 56 |
| 1_minus_stability | 65.0 | 0.40 | 0.70 | 0.65 | 65 | 124 |
| 1_minus_confidence | 74.0 | 0.80 | 0.74 | 0.74 | 69 | 112 |
| random | 35.0 | 0.30 | 0.32 | 0.35 | 32 | 61 |
| baseline:confidence_inv | 74.0 | 0.80 | 0.74 | 0.74 | 69 | 112 |
| baseline:majority_vote_inv | 63.0 | 0.50 | 0.62 | 0.63 | 58 | 121 |
| baseline:source_prov_inv | 30.0 | 0.40 | 0.36 | 0.30 | 29 | 56 |
| baseline:subj_obj_cooccur_inv | 29.0 | 0.70 | 0.34 | 0.29 | 28 | 55 |

**Mode `wrong_only`** — positive = wrong only; unmatched treated as negative (n_eval=2839, prevalence=0.1032)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 15.0 | 0.10 | 0.14 | 0.15 | 47 | 75 |
| prompt_sensitivity | 16.0 | 0.00 | 0.22 | 0.16 | 43 | 72 |
| schema_sensitivity | 15.0 | 0.00 | 0.10 | 0.15 | 42 | 74 |
| stochastic_variance | 16.0 | 0.20 | 0.22 | 0.16 | 35 | 57 |
| 1_minus_stability | 9.0 | 0.00 | 0.04 | 0.09 | 41 | 78 |
| 1_minus_confidence | 9.0 | 0.20 | 0.08 | 0.09 | 22 | 56 |
| random | 13.0 | 0.10 | 0.12 | 0.13 | 22 | 57 |
| baseline:confidence_inv | 9.0 | 0.20 | 0.08 | 0.09 | 22 | 56 |
| baseline:majority_vote_inv | 8.0 | 0.20 | 0.10 | 0.08 | 41 | 74 |
| baseline:source_prov_inv | 16.0 | 0.20 | 0.22 | 0.16 | 35 | 57 |
| baseline:subj_obj_cooccur_inv | 9.0 | 0.20 | 0.14 | 0.09 | 28 | 50 |

## E1 known-cause

```json
{
  "n": 2421,
  "top1_acc": 0.5931433292028088,
  "top3_recall": 0.8736059479553904,
  "mrr": 0.7174721189591058,
  "macro_f1": 0.4011640277021591,
  "per_cause_f1": {
    "noop": 0.0,
    "prompt_clause": 0.5369458128078818,
    "schema": 0.6586193889098454,
    "sentence": 0.40909090909090917
  },
  "per_cause_n": {
    "noop": 0,
    "prompt_clause": 671,
    "schema": 1691,
    "sentence": 59
  }
}
```

## E3 schema debugging — flip rates per variant

- **ambiguous:P17,P159,P131**: {'n_observations': 9, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.2222222222222222, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **coarse**: {'n_observations': 3211, 'type_flip_rate': 0.6533790096543133, 'disappearance_rate': 0.300840859545313, 'percent_downgraded_to_other': 0.05948302709436313, 'percent_correct_to_wrong': 0.21488632824665213, 'percent_wrong_to_correct': 0.0}
- **desc_added**: {'n_observations': 3211, 'type_flip_rate': 0.13858611024602926, 'disappearance_rate': 0.23294923699782, 'percent_downgraded_to_other': 0.06446589847399564, 'percent_correct_to_wrong': 0.024291497975708502, 'percent_wrong_to_correct': 0.018685767673621925}
- **desc_removed**: {'n_observations': 3216, 'type_flip_rate': 0.13681592039800994, 'disappearance_rate': 0.24036069651741293, 'percent_downgraded_to_other': 0.06063432835820896, 'percent_correct_to_wrong': 0.03513681592039801, 'percent_wrong_to_correct': 0.017412935323383085}
- **ambiguous:P131,P17,P150**: {'n_observations': 120, 'type_flip_rate': 0.7333333333333333, 'disappearance_rate': 0.175, 'percent_downgraded_to_other': 0.03333333333333333, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P194,P131**: {'n_observations': 13, 'type_flip_rate': 0.3076923076923077, 'disappearance_rate': 0.3076923076923077, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.07692307692307693, 'percent_wrong_to_correct': 0.0}
- **drop:P131**: {'n_observations': 1471, 'type_flip_rate': 0.26784500339904826, 'disappearance_rate': 0.2991162474507138, 'percent_downgraded_to_other': 0.08157715839564922, 'percent_correct_to_wrong': 0.05914343983684568, 'percent_wrong_to_correct': 0.04078857919782461}
- **ambiguous:P17,P131,P150**: {'n_observations': 192, 'type_flip_rate': 0.4427083333333333, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.08854166666666667, 'percent_correct_to_wrong': 0.15625, 'percent_wrong_to_correct': 0.015625}
- **drop:P159**: {'n_observations': 59, 'type_flip_rate': 0.1016949152542373, 'disappearance_rate': 0.2542372881355932, 'percent_downgraded_to_other': 0.0847457627118644, 'percent_correct_to_wrong': 0.06779661016949153, 'percent_wrong_to_correct': 0.0}
- **drop:P17**: {'n_observations': 1601, 'type_flip_rate': 0.18863210493441598, 'disappearance_rate': 0.24359775140537165, 'percent_downgraded_to_other': 0.038101186758276076, 'percent_correct_to_wrong': 0.07058088694565896, 'percent_wrong_to_correct': 0.016864459712679577}
- **ambiguous:P577,P175,P50**: {'n_observations': 19, 'type_flip_rate': 0.7368421052631579, 'disappearance_rate': 0.05263157894736842, 'percent_downgraded_to_other': 0.3157894736842105, 'percent_correct_to_wrong': 0.3157894736842105, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131**: {'n_observations': 4, 'type_flip_rate': 0.75, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.75, 'percent_wrong_to_correct': 0.0}
- **hierarchical**: {'n_observations': 3216, 'type_flip_rate': 0.13837064676616914, 'disappearance_rate': 0.2269900497512438, 'percent_downgraded_to_other': 0.056592039800995024, 'percent_correct_to_wrong': 0.030783582089552237, 'percent_wrong_to_correct': 0.021144278606965175}
- **rename**: {'n_observations': 3216, 'type_flip_rate': 0.17350746268656717, 'disappearance_rate': 0.21082089552238806, 'percent_downgraded_to_other': 0.05690298507462686, 'percent_correct_to_wrong': 0.033893034825870645, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P580**: {'n_observations': 21, 'type_flip_rate': 0.2857142857142857, 'disappearance_rate': 0.6190476190476191, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.19047619047619047, 'percent_wrong_to_correct': 0.0}
- **reorder**: {'n_observations': 3216, 'type_flip_rate': 0.1623134328358209, 'disappearance_rate': 0.23662935323383086, 'percent_downgraded_to_other': 0.048507462686567165, 'percent_correct_to_wrong': 0.029539800995024876, 'percent_wrong_to_correct': 0.026119402985074626}
- **ambiguous:P108,P17,P131**: {'n_observations': 27, 'type_flip_rate': 0.4074074074074074, 'disappearance_rate': 0.37037037037037035, 'percent_downgraded_to_other': 0.14814814814814814, 'percent_correct_to_wrong': 0.037037037037037035, 'percent_wrong_to_correct': 0.0}
- **drop:P150**: {'n_observations': 487, 'type_flip_rate': 0.17453798767967146, 'disappearance_rate': 0.23819301848049282, 'percent_downgraded_to_other': 0.026694045174537988, 'percent_correct_to_wrong': 0.043121149897330596, 'percent_wrong_to_correct': 0.026694045174537988}
- **drop:P175**: {'n_observations': 385, 'type_flip_rate': 0.17922077922077922, 'disappearance_rate': 0.33766233766233766, 'percent_downgraded_to_other': 0.05454545454545454, 'percent_correct_to_wrong': 0.0987012987012987, 'percent_wrong_to_correct': 0.007792207792207792}
- **ambiguous:P176,P361,P577**: {'n_observations': 20, 'type_flip_rate': 0.05, 'disappearance_rate': 0.85, 'percent_downgraded_to_other': 0.15, 'percent_correct_to_wrong': 0.05, 'percent_wrong_to_correct': 0.0}
- **with_other**: {'n_observations': 3216, 'type_flip_rate': 0.13805970149253732, 'disappearance_rate': 0.20180348258706468, 'percent_downgraded_to_other': 0.06623134328358209, 'percent_correct_to_wrong': 0.023009950248756218, 'percent_wrong_to_correct': 0.01896766169154229}
- **ambiguous:P19,P570,P137**: {'n_observations': 24, 'type_flip_rate': 0.4166666666666667, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.20833333333333334, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P577,P361**: {'n_observations': 27, 'type_flip_rate': 0.2222222222222222, 'disappearance_rate': 0.6296296296296297, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **drop:P50**: {'n_observations': 210, 'type_flip_rate': 0.1380952380952381, 'disappearance_rate': 0.37142857142857144, 'percent_downgraded_to_other': 0.09523809523809523, 'percent_correct_to_wrong': 0.06190476190476191, 'percent_wrong_to_correct': 0.004761904761904762}
- **drop:P194**: {'n_observations': 23, 'type_flip_rate': 0.043478260869565216, 'disappearance_rate': 0.5652173913043478, 'percent_downgraded_to_other': 0.21739130434782608, 'percent_correct_to_wrong': 0.043478260869565216, 'percent_wrong_to_correct': 0.0}
- **drop:P577**: {'n_observations': 512, 'type_flip_rate': 0.203125, 'disappearance_rate': 0.306640625, 'percent_downgraded_to_other': 0.140625, 'percent_correct_to_wrong': 0.0703125, 'percent_wrong_to_correct': 0.0078125}
- **ambiguous:P580,P17,P27**: {'n_observations': 34, 'type_flip_rate': 0.08823529411764706, 'disappearance_rate': 0.17647058823529413, 'percent_downgraded_to_other': 0.20588235294117646, 'percent_correct_to_wrong': 0.058823529411764705, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P27**: {'n_observations': 28, 'type_flip_rate': 0.14285714285714285, 'disappearance_rate': 0.5714285714285714, 'percent_downgraded_to_other': 0.17857142857142858, 'percent_correct_to_wrong': 0.10714285714285714, 'percent_wrong_to_correct': 0.0}
- **drop:P108**: {'n_observations': 692, 'type_flip_rate': 0.25578034682080925, 'disappearance_rate': 0.26445086705202314, 'percent_downgraded_to_other': 0.08815028901734104, 'percent_correct_to_wrong': 0.030346820809248554, 'percent_wrong_to_correct': 0.014450867052023121}
- **ambiguous:P17,P69,P150**: {'n_observations': 38, 'type_flip_rate': 0.39473684210526316, 'disappearance_rate': 0.05263157894736842, 'percent_downgraded_to_other': 0.15789473684210525, 'percent_correct_to_wrong': 0.15789473684210525, 'percent_wrong_to_correct': 0.02631578947368421}
- **drop:P137**: {'n_observations': 24, 'type_flip_rate': 0.0, 'disappearance_rate': 0.2916666666666667, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P361**: {'n_observations': 299, 'type_flip_rate': 0.18394648829431437, 'disappearance_rate': 0.33444816053511706, 'percent_downgraded_to_other': 0.030100334448160536, 'percent_correct_to_wrong': 0.043478260869565216, 'percent_wrong_to_correct': 0.0033444816053511705}
- **drop:P19**: {'n_observations': 342, 'type_flip_rate': 0.15204678362573099, 'disappearance_rate': 0.24269005847953215, 'percent_downgraded_to_other': 0.02046783625730994, 'percent_correct_to_wrong': 0.09649122807017543, 'percent_wrong_to_correct': 0.008771929824561403}
- **drop:P176**: {'n_observations': 30, 'type_flip_rate': 0.13333333333333333, 'disappearance_rate': 0.23333333333333334, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P27**: {'n_observations': 687, 'type_flip_rate': 0.14847161572052403, 'disappearance_rate': 0.3231441048034934, 'percent_downgraded_to_other': 0.033478893740902474, 'percent_correct_to_wrong': 0.08733624454148471, 'percent_wrong_to_correct': 0.017467248908296942}
- **drop:P570**: {'n_observations': 264, 'type_flip_rate': 0.16287878787878787, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.01893939393939394, 'percent_correct_to_wrong': 0.13636363636363635, 'percent_wrong_to_correct': 0.041666666666666664}
- **ambiguous:P17,P131,P69**: {'n_observations': 38, 'type_flip_rate': 0.13157894736842105, 'disappearance_rate': 0.2894736842105263, 'percent_downgraded_to_other': 0.13157894736842105, 'percent_correct_to_wrong': 0.15789473684210525, 'percent_wrong_to_correct': 0.05263157894736842}
- **drop:P580**: {'n_observations': 145, 'type_flip_rate': 0.15862068965517243, 'disappearance_rate': 0.3793103448275862, 'percent_downgraded_to_other': 0.027586206896551724, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P69**: {'n_observations': 207, 'type_flip_rate': 0.3140096618357488, 'disappearance_rate': 0.16908212560386474, 'percent_downgraded_to_other': 0.05314009661835749, 'percent_correct_to_wrong': 0.12560386473429952, 'percent_wrong_to_correct': 0.03864734299516908}
- **ambiguous:P131,P150**: {'n_observations': 9, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.8888888888888888, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P54,P17,P27**: {'n_observations': 15, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.26666666666666666, 'percent_downgraded_to_other': 0.13333333333333333, 'percent_correct_to_wrong': 0.4666666666666667, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P19**: {'n_observations': 18, 'type_flip_rate': 0.5555555555555556, 'disappearance_rate': 0.2777777777777778, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P577,P264**: {'n_observations': 14, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.14285714285714285, 'percent_downgraded_to_other': 0.6428571428571429, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P19,P108,P569**: {'n_observations': 17, 'type_flip_rate': 0.6470588235294118, 'disappearance_rate': 0.35294117647058826, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5294117647058824, 'percent_wrong_to_correct': 0.0}
- **drop:P54**: {'n_observations': 101, 'type_flip_rate': 0.297029702970297, 'disappearance_rate': 0.10891089108910891, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.18811881188118812, 'percent_wrong_to_correct': 0.009900990099009901}
- **drop:P264**: {'n_observations': 79, 'type_flip_rate': 0.0759493670886076, 'disappearance_rate': 0.31645569620253167, 'percent_downgraded_to_other': 0.0759493670886076, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P150,P17**: {'n_observations': 36, 'type_flip_rate': 0.2777777777777778, 'disappearance_rate': 0.4444444444444444, 'percent_downgraded_to_other': 0.2777777777777778, 'percent_correct_to_wrong': 0.3055555555555556, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P131,P69**: {'n_observations': 23, 'type_flip_rate': 0.6521739130434783, 'disappearance_rate': 0.17391304347826086, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.043478260869565216}
- **drop:P569**: {'n_observations': 184, 'type_flip_rate': 0.21195652173913043, 'disappearance_rate': 0.13043478260869565, 'percent_downgraded_to_other': 0.05434782608695652, 'percent_correct_to_wrong': 0.15760869565217392, 'percent_wrong_to_correct': 0.021739130434782608}
- **ambiguous:P27,P17,P108**: {'n_observations': 37, 'type_flip_rate': 0.3783783783783784, 'disappearance_rate': 0.6216216216216216, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.05405405405405406, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P108**: {'n_observations': 84, 'type_flip_rate': 0.39285714285714285, 'disappearance_rate': 0.36904761904761907, 'percent_downgraded_to_other': 0.07142857142857142, 'percent_correct_to_wrong': 0.047619047619047616, 'percent_wrong_to_correct': 0.03571428571428571}
- **ambiguous:P108,P569,P570**: {'n_observations': 32, 'type_flip_rate': 0.34375, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0625, 'percent_correct_to_wrong': 0.21875, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P50,P577**: {'n_observations': 18, 'type_flip_rate': 0.8888888888888888, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.16666666666666666, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P26,P17**: {'n_observations': 20, 'type_flip_rate': 0.15, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.15, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P27,P577**: {'n_observations': 12, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.08333333333333333, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **drop:P161**: {'n_observations': 256, 'type_flip_rate': 0.24609375, 'disappearance_rate': 0.296875, 'percent_downgraded_to_other': 0.0234375, 'percent_correct_to_wrong': 0.1328125, 'percent_wrong_to_correct': 0.01171875}
- **drop:P26**: {'n_observations': 133, 'type_flip_rate': 0.18796992481203006, 'disappearance_rate': 0.09022556390977443, 'percent_downgraded_to_other': 0.18045112781954886, 'percent_correct_to_wrong': 0.07518796992481203, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P570,P131**: {'n_observations': 40, 'type_flip_rate': 0.325, 'disappearance_rate': 0.225, 'percent_downgraded_to_other': 0.05, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.1}
- **ambiguous:P17,P463,P30**: {'n_observations': 18, 'type_flip_rate': 0.8888888888888888, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P159**: {'n_observations': 7, 'type_flip_rate': 0.5714285714285714, 'disappearance_rate': 0.2857142857142857, 'percent_downgraded_to_other': 0.7142857142857143, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P30**: {'n_observations': 60, 'type_flip_rate': 0.21666666666666667, 'disappearance_rate': 0.08333333333333333, 'percent_downgraded_to_other': 0.03333333333333333, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.016666666666666666}
- **drop:P463**: {'n_observations': 219, 'type_flip_rate': 0.228310502283105, 'disappearance_rate': 0.319634703196347, 'percent_downgraded_to_other': 0.0502283105022831, 'percent_correct_to_wrong': 0.0593607305936073, 'percent_wrong_to_correct': 0.0182648401826484}
- **ambiguous:P17,P131,P26**: {'n_observations': 3, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.6666666666666666, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P361,P150**: {'n_observations': 9, 'type_flip_rate': 0.7777777777777778, 'disappearance_rate': 0.2222222222222222, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P361**: {'n_observations': 43, 'type_flip_rate': 0.5581395348837209, 'disappearance_rate': 0.32558139534883723, 'percent_downgraded_to_other': 0.023255813953488372, 'percent_correct_to_wrong': 0.13953488372093023, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P264,P577,P175**: {'n_observations': 10, 'type_flip_rate': 0.1, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P3373,P17,P40**: {'n_observations': 12, 'type_flip_rate': 0.25, 'disappearance_rate': 0.4166666666666667, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P150,P1441,P131**: {'n_observations': 8, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P26,P569**: {'n_observations': 9, 'type_flip_rate': 0.4444444444444444, 'disappearance_rate': 0.2222222222222222, 'percent_downgraded_to_other': 0.5555555555555556, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P69,P27,P463**: {'n_observations': 10, 'type_flip_rate': 0.3, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.1, 'percent_correct_to_wrong': 0.1, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P127,P355,P749**: {'n_observations': 2, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P264,P495**: {'n_observations': 8, 'type_flip_rate': 0.0, 'disappearance_rate': 0.875, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P69,P108**: {'n_observations': 13, 'type_flip_rate': 0.3076923076923077, 'disappearance_rate': 0.07692307692307693, 'percent_downgraded_to_other': 0.3076923076923077, 'percent_correct_to_wrong': 0.15384615384615385, 'percent_wrong_to_correct': 0.0}
- **drop:P127**: {'n_observations': 8, 'type_flip_rate': 0.0, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **drop:P355**: {'n_observations': 12, 'type_flip_rate': 0.25, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **drop:P1441**: {'n_observations': 42, 'type_flip_rate': 0.023809523809523808, 'disappearance_rate': 0.30952380952380953, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P749**: {'n_observations': 22, 'type_flip_rate': 0.36363636363636365, 'disappearance_rate': 0.2727272727272727, 'percent_downgraded_to_other': 0.2727272727272727, 'percent_correct_to_wrong': 0.13636363636363635, 'percent_wrong_to_correct': 0.0}
- **drop:P3373**: {'n_observations': 19, 'type_flip_rate': 0.0, 'disappearance_rate': 0.3684210526315789, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P40**: {'n_observations': 98, 'type_flip_rate': 0.20408163265306123, 'disappearance_rate': 0.3163265306122449, 'percent_downgraded_to_other': 0.030612244897959183, 'percent_correct_to_wrong': 0.02040816326530612, 'percent_wrong_to_correct': 0.01020408163265306}
- **ambiguous:P161,P577,P495**: {'n_observations': 31, 'type_flip_rate': 0.6774193548387096, 'disappearance_rate': 0.0967741935483871, 'percent_downgraded_to_other': 0.12903225806451613, 'percent_correct_to_wrong': 0.5161290322580645, 'percent_wrong_to_correct': 0.0}
- **drop:P495**: {'n_observations': 183, 'type_flip_rate': 0.12021857923497267, 'disappearance_rate': 0.2568306010928962, 'percent_downgraded_to_other': 0.09289617486338798, 'percent_correct_to_wrong': 0.10382513661202186, 'percent_wrong_to_correct': 0.00546448087431694}
- **ambiguous:P175,P577,P495**: {'n_observations': 28, 'type_flip_rate': 0.10714285714285714, 'disappearance_rate': 0.5714285714285714, 'percent_downgraded_to_other': 0.03571428571428571, 'percent_correct_to_wrong': 0.2857142857142857, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P31**: {'n_observations': 1, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P131,P161**: {'n_observations': 16, 'type_flip_rate': 0.125, 'disappearance_rate': 0.6875, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0625, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P495,P57,P577**: {'n_observations': 8, 'type_flip_rate': 0.875, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.375, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P50,P570**: {'n_observations': 31, 'type_flip_rate': 0.4838709677419355, 'disappearance_rate': 0.3548387096774194, 'percent_downgraded_to_other': 0.1935483870967742, 'percent_correct_to_wrong': 0.0967741935483871, 'percent_wrong_to_correct': 0.03225806451612903}
- **ambiguous:P17,P150,P131**: {'n_observations': 24, 'type_flip_rate': 0.5, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2916666666666667, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P463,P131,P17**: {'n_observations': 15, 'type_flip_rate': 0.2, 'disappearance_rate': 0.4666666666666667, 'percent_downgraded_to_other': 0.06666666666666667, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P179,P123,P495**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P57**: {'n_observations': 21, 'type_flip_rate': 0.2857142857142857, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.23809523809523808, 'percent_correct_to_wrong': 0.09523809523809523, 'percent_wrong_to_correct': 0.0}
- **drop:P31**: {'n_observations': 1, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P577,P463**: {'n_observations': 19, 'type_flip_rate': 0.47368421052631576, 'disappearance_rate': 0.3157894736842105, 'percent_downgraded_to_other': 0.47368421052631576, 'percent_correct_to_wrong': 0.21052631578947367, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P17,P69**: {'n_observations': 9, 'type_flip_rate': 0.0, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P26,P40,P569**: {'n_observations': 8, 'type_flip_rate': 0.375, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **drop:P123**: {'n_observations': 17, 'type_flip_rate': 0.058823529411764705, 'disappearance_rate': 0.23529411764705882, 'percent_downgraded_to_other': 0.058823529411764705, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P179**: {'n_observations': 16, 'type_flip_rate': 0.0625, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0625, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P159**: {'n_observations': 18, 'type_flip_rate': 0.8333333333333334, 'disappearance_rate': 0.05555555555555555, 'percent_downgraded_to_other': 0.2222222222222222, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P57,P27,P569**: {'n_observations': 3, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.6666666666666666, 'percent_downgraded_to_other': 0.3333333333333333, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P577,P54**: {'n_observations': 12, 'type_flip_rate': 0.0, 'disappearance_rate': 0.9166666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P17,P361**: {'n_observations': 13, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.38461538461538464, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P108,P19**: {'n_observations': 10, 'type_flip_rate': 0.3, 'disappearance_rate': 0.3, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P150,P361**: {'n_observations': 5, 'type_flip_rate': 0.6, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P577**: {'n_observations': 18, 'type_flip_rate': 0.16666666666666666, 'disappearance_rate': 0.4444444444444444, 'percent_downgraded_to_other': 0.05555555555555555, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.1111111111111111}
- **ambiguous:P27,P569,P570**: {'n_observations': 20, 'type_flip_rate': 0.55, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.6, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P17,P131**: {'n_observations': 7, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P175,P264**: {'n_observations': 12, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.08333333333333333, 'percent_downgraded_to_other': 0.5833333333333334, 'percent_correct_to_wrong': 0.08333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P175,P577**: {'n_observations': 7, 'type_flip_rate': 0.7142857142857143, 'disappearance_rate': 0.2857142857142857, 'percent_downgraded_to_other': 0.7142857142857143, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P361**: {'n_observations': 27, 'type_flip_rate': 0.37037037037037035, 'disappearance_rate': 0.2962962962962963, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1111111111111111, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P463,P108**: {'n_observations': 11, 'type_flip_rate': 0.9090909090909091, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.09090909090909091, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P54,P17,P108**: {'n_observations': 15, 'type_flip_rate': 0.4666666666666667, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P495,P108**: {'n_observations': 5, 'type_flip_rate': 0.2, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.2, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P17,P361**: {'n_observations': 21, 'type_flip_rate': 0.38095238095238093, 'disappearance_rate': 0.5238095238095238, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.09523809523809523, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P577,P26**: {'n_observations': 28, 'type_flip_rate': 0.35714285714285715, 'disappearance_rate': 0.42857142857142855, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.07142857142857142, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131**: {'n_observations': 10, 'type_flip_rate': 0.4, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P54,P569,P570**: {'n_observations': 9, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.3333333333333333, 'percent_correct_to_wrong': 0.4444444444444444, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P54,P569**: {'n_observations': 9, 'type_flip_rate': 0.1111111111111111, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P131,P27**: {'n_observations': 19, 'type_flip_rate': 0.0, 'disappearance_rate': 0.6842105263157895, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.05263157894736842, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P17,P580**: {'n_observations': 15, 'type_flip_rate': 0.06666666666666667, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.06666666666666667, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P40,P19,P26**: {'n_observations': 15, 'type_flip_rate': 0.4, 'disappearance_rate': 0.26666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.13333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P361,P576**: {'n_observations': 19, 'type_flip_rate': 0.05263157894736842, 'disappearance_rate': 0.7894736842105263, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P580**: {'n_observations': 18, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.05555555555555555, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P570,P569**: {'n_observations': 9, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P355,P17,P749**: {'n_observations': 10, 'type_flip_rate': 0.3, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P175,P264**: {'n_observations': 6, 'type_flip_rate': 0.16666666666666666, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.16666666666666666, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P30**: {'n_observations': 9, 'type_flip_rate': 0.7777777777777778, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P569,P108**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.3333333333333333, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P1001,P194**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.7, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P463,P108,P527**: {'n_observations': 3, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P69,P108,P19**: {'n_observations': 16, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4375, 'percent_wrong_to_correct': 0.0}
- **drop:P576**: {'n_observations': 26, 'type_flip_rate': 0.19230769230769232, 'disappearance_rate': 0.19230769230769232, 'percent_downgraded_to_other': 0.11538461538461539, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P1001**: {'n_observations': 25, 'type_flip_rate': 0.4, 'disappearance_rate': 0.16, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.12}
- **ambiguous:P17,P69**: {'n_observations': 2, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P159,P463**: {'n_observations': 8, 'type_flip_rate': 0.875, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.625, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P69,P131**: {'n_observations': 9, 'type_flip_rate': 0.4444444444444444, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **drop:P527**: {'n_observations': 181, 'type_flip_rate': 0.23756906077348067, 'disappearance_rate': 0.32044198895027626, 'percent_downgraded_to_other': 0.08287292817679558, 'percent_correct_to_wrong': 0.03314917127071823, 'percent_wrong_to_correct': 0.0055248618784530384}
- **ambiguous:P570,P19,P27**: {'n_observations': 8, 'type_flip_rate': 0.125, 'disappearance_rate': 0.625, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P108**: {'n_observations': 34, 'type_flip_rate': 0.4411764705882353, 'disappearance_rate': 0.2647058823529412, 'percent_downgraded_to_other': 0.14705882352941177, 'percent_correct_to_wrong': 0.058823529411764705, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P108,P361**: {'n_observations': 12, 'type_flip_rate': 0.5833333333333334, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.08333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P19,P463**: {'n_observations': 7, 'type_flip_rate': 0.2857142857142857, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P35,P27,P937**: {'n_observations': 1, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P19,P27,P54**: {'n_observations': 9, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.1111111111111111}
- **ambiguous:P272,P495,P577**: {'n_observations': 6, 'type_flip_rate': 0.16666666666666666, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.3333333333333333, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P176,P131,P17**: {'n_observations': 4, 'type_flip_rate': 0.75, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P102,P27,P17**: {'n_observations': 7, 'type_flip_rate': 0.0, 'disappearance_rate': 0.7142857142857143, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P580,P131,P17**: {'n_observations': 14, 'type_flip_rate': 0.0, 'disappearance_rate': 0.7857142857142857, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P35**: {'n_observations': 1, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P272**: {'n_observations': 6, 'type_flip_rate': 0.16666666666666666, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P166,P175**: {'n_observations': 9, 'type_flip_rate': 0.0, 'disappearance_rate': 0.5555555555555556, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P276,P159**: {'n_observations': 9, 'type_flip_rate': 0.7777777777777778, 'disappearance_rate': 0.2222222222222222, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P102**: {'n_observations': 47, 'type_flip_rate': 0.23404255319148937, 'disappearance_rate': 0.3191489361702128, 'percent_downgraded_to_other': 0.02127659574468085, 'percent_correct_to_wrong': 0.0425531914893617, 'percent_wrong_to_correct': 0.0}
- **drop:P937**: {'n_observations': 1, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P19,P20**: {'n_observations': 12, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.08333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **drop:P166**: {'n_observations': 13, 'type_flip_rate': 0.07692307692307693, 'disappearance_rate': 0.07692307692307693, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P495,P577,P17**: {'n_observations': 6, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.3333333333333333, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P276**: {'n_observations': 11, 'type_flip_rate': 0.0, 'disappearance_rate': 0.09090909090909091, 'percent_downgraded_to_other': 0.36363636363636365, 'percent_correct_to_wrong': 0.09090909090909091, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P166,P108**: {'n_observations': 4, 'type_flip_rate': 0.0, 'disappearance_rate': 0.75, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P20**: {'n_observations': 47, 'type_flip_rate': 0.2553191489361702, 'disappearance_rate': 0.3829787234042553, 'percent_downgraded_to_other': 0.1702127659574468, 'percent_correct_to_wrong': 0.19148936170212766, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P108,P580**: {'n_observations': 9, 'type_flip_rate': 0.4444444444444444, 'disappearance_rate': 0.4444444444444444, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P527,P131,P155**: {'n_observations': 6, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P27,P17**: {'n_observations': 23, 'type_flip_rate': 0.43478260869565216, 'disappearance_rate': 0.30434782608695654, 'percent_downgraded_to_other': 0.17391304347826086, 'percent_correct_to_wrong': 0.043478260869565216, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P50,P577,P361**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.6666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P131,P40**: {'n_observations': 16, 'type_flip_rate': 0.5, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0625}
- **drop:P155**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.16666666666666666, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P495,P50**: {'n_observations': 8, 'type_flip_rate': 0.375, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.625, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P495,P179,P57**: {'n_observations': 10, 'type_flip_rate': 0.3, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P577,P50**: {'n_observations': 13, 'type_flip_rate': 0.15384615384615385, 'disappearance_rate': 0.5384615384615384, 'percent_downgraded_to_other': 0.15384615384615385, 'percent_correct_to_wrong': 0.3076923076923077, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P27,P495**: {'n_observations': 6, 'type_flip_rate': 0.16666666666666666, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.16666666666666666}
- **ambiguous:P361,P108,P749**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P19,P108**: {'n_observations': 19, 'type_flip_rate': 0.5789473684210527, 'disappearance_rate': 0.10526315789473684, 'percent_downgraded_to_other': 0.10526315789473684, 'percent_correct_to_wrong': 0.05263157894736842, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P27,P1344**: {'n_observations': 18, 'type_flip_rate': 0.3888888888888889, 'disappearance_rate': 0.1111111111111111, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.05555555555555555, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P400,P123,P577**: {'n_observations': 11, 'type_flip_rate': 0.2727272727272727, 'disappearance_rate': 0.09090909090909091, 'percent_downgraded_to_other': 0.45454545454545453, 'percent_correct_to_wrong': 0.09090909090909091, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P495,P17,P27**: {'n_observations': 2, 'type_flip_rate': 0.0, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P27,P19**: {'n_observations': 17, 'type_flip_rate': 0.5882352941176471, 'disappearance_rate': 0.23529411764705882, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.17647058823529413, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P577,P108**: {'n_observations': 26, 'type_flip_rate': 0.38461538461538464, 'disappearance_rate': 0.5769230769230769, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P108,P569**: {'n_observations': 12, 'type_flip_rate': 0.5, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **drop:P1344**: {'n_observations': 18, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.05555555555555555, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.05555555555555555}
- **ambiguous:P463,P50,P131**: {'n_observations': 5, 'type_flip_rate': 0.4, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.2}
- **ambiguous:P131,P17,P403**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **drop:P400**: {'n_observations': 11, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.36363636363636365, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P108,P150**: {'n_observations': 10, 'type_flip_rate': 0.0, 'disappearance_rate': 0.8, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P159,P463,P108**: {'n_observations': 5, 'type_flip_rate': 0.6, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.8, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P403**: {'n_observations': 12, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.08333333333333333, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.08333333333333333}
- **ambiguous:P17,P131,P607**: {'n_observations': 11, 'type_flip_rate': 0.2727272727272727, 'disappearance_rate': 0.5454545454545454, 'percent_downgraded_to_other': 0.18181818181818182, 'percent_correct_to_wrong': 0.09090909090909091, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P161,P577**: {'n_observations': 14, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.35714285714285715, 'percent_downgraded_to_other': 0.07142857142857142, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P361,P527**: {'n_observations': 18, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P569,P570,P27**: {'n_observations': 4, 'type_flip_rate': 0.75, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P69,P131**: {'n_observations': 10, 'type_flip_rate': 0.4, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.1}
- **ambiguous:P131,P17,P50**: {'n_observations': 15, 'type_flip_rate': 0.4, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.26666666666666666, 'percent_correct_to_wrong': 0.06666666666666667, 'percent_wrong_to_correct': 0.0}
- **drop:P607**: {'n_observations': 11, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.2727272727272727, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P361,P577,P580**: {'n_observations': 11, 'type_flip_rate': 0.2727272727272727, 'disappearance_rate': 0.7272727272727273, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.09090909090909091, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P27,P131**: {'n_observations': 10, 'type_flip_rate': 0.1, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P710**: {'n_observations': 3, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.6666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P577,P19**: {'n_observations': 13, 'type_flip_rate': 0.07692307692307693, 'disappearance_rate': 0.6153846153846154, 'percent_downgraded_to_other': 0.07692307692307693, 'percent_correct_to_wrong': 0.07692307692307693, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P175,P108**: {'n_observations': 11, 'type_flip_rate': 0.18181818181818182, 'disappearance_rate': 0.6363636363636364, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.18181818181818182, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P1412,P364**: {'n_observations': 15, 'type_flip_rate': 0.4666666666666667, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4666666666666667, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P26,P27**: {'n_observations': 3, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P26,P161,P569**: {'n_observations': 8, 'type_flip_rate': 0.25, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.25, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **drop:P710**: {'n_observations': 3, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P19,P27,P527**: {'n_observations': 15, 'type_flip_rate': 0.4666666666666667, 'disappearance_rate': 0.13333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.13333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P131,P19**: {'n_observations': 5, 'type_flip_rate': 0.2, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.4, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **drop:P1412**: {'n_observations': 15, 'type_flip_rate': 0.06666666666666667, 'disappearance_rate': 0.06666666666666667, 'percent_downgraded_to_other': 0.3333333333333333, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P364**: {'n_observations': 15, 'type_flip_rate': 0.0, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P527,P175,P463**: {'n_observations': 18, 'type_flip_rate': 0.5, 'disappearance_rate': 0.4444444444444444, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P17,P463**: {'n_observations': 10, 'type_flip_rate': 0.5, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P361,P17,P585**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.7, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P131,P50**: {'n_observations': 9, 'type_flip_rate': 0.2222222222222222, 'disappearance_rate': 0.6666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1111111111111111, 'percent_wrong_to_correct': 0.0}
- **drop:P585**: {'n_observations': 12, 'type_flip_rate': 0.08333333333333333, 'disappearance_rate': 0.9166666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P171,P527**: {'n_observations': 14, 'type_flip_rate': 0.5714285714285714, 'disappearance_rate': 0.2857142857142857, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P1441,P674,P108**: {'n_observations': 11, 'type_flip_rate': 0.0, 'disappearance_rate': 0.18181818181818182, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P30,P17**: {'n_observations': 11, 'type_flip_rate': 0.45454545454545453, 'disappearance_rate': 0.36363636363636365, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P674**: {'n_observations': 28, 'type_flip_rate': 0.07142857142857142, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P171**: {'n_observations': 14, 'type_flip_rate': 0.07142857142857142, 'disappearance_rate': 0.07142857142857142, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P40,P131,P17**: {'n_observations': 15, 'type_flip_rate': 0.0, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P570,P19**: {'n_observations': 23, 'type_flip_rate': 0.21739130434782608, 'disappearance_rate': 0.21739130434782608, 'percent_downgraded_to_other': 0.043478260869565216, 'percent_correct_to_wrong': 0.17391304347826086, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P26,P551**: {'n_observations': 24, 'type_flip_rate': 0.25, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.625, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P206**: {'n_observations': 6, 'type_flip_rate': 0.0, 'disappearance_rate': 0.8333333333333334, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P30,P175,P495**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P19,P27,P17**: {'n_observations': 10, 'type_flip_rate': 0.1, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **drop:P551**: {'n_observations': 24, 'type_flip_rate': 0.125, 'disappearance_rate': 0.5833333333333334, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P27,P131**: {'n_observations': 32, 'type_flip_rate': 0.3125, 'disappearance_rate': 0.34375, 'percent_downgraded_to_other': 0.0625, 'percent_correct_to_wrong': 0.03125, 'percent_wrong_to_correct': 0.03125}
- **ambiguous:P175,P161,P463**: {'n_observations': 19, 'type_flip_rate': 0.47368421052631576, 'disappearance_rate': 0.3684210526315789, 'percent_downgraded_to_other': 0.3157894736842105, 'percent_correct_to_wrong': 0.10526315789473684, 'percent_wrong_to_correct': 0.05263157894736842}
- **ambiguous:P17,P27,P50**: {'n_observations': 13, 'type_flip_rate': 0.15384615384615385, 'disappearance_rate': 0.5384615384615384, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.15384615384615385, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P403,P361**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P206**: {'n_observations': 18, 'type_flip_rate': 0.1111111111111111, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P1001,P150,P50**: {'n_observations': 10, 'type_flip_rate': 0.1, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P112,P576**: {'n_observations': 7, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.14285714285714285, 'percent_downgraded_to_other': 0.42857142857142855, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P463,P527,P131**: {'n_observations': 15, 'type_flip_rate': 0.4666666666666667, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P571**: {'n_observations': 18, 'type_flip_rate': 0.16666666666666666, 'disappearance_rate': 0.5555555555555556, 'percent_downgraded_to_other': 0.3888888888888889, 'percent_correct_to_wrong': 0.1111111111111111, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P577,P19**: {'n_observations': 10, 'type_flip_rate': 0.4, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P527,P17,P580**: {'n_observations': 13, 'type_flip_rate': 0.38461538461538464, 'disappearance_rate': 0.38461538461538464, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P527,P19**: {'n_observations': 10, 'type_flip_rate': 0.3, 'disappearance_rate': 0.3, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P37,P131,P150**: {'n_observations': 5, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P361,P27**: {'n_observations': 9, 'type_flip_rate': 0.2222222222222222, 'disappearance_rate': 0.1111111111111111, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1111111111111111, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P264,P175**: {'n_observations': 29, 'type_flip_rate': 0.5517241379310345, 'disappearance_rate': 0.3103448275862069, 'percent_downgraded_to_other': 0.3448275862068966, 'percent_correct_to_wrong': 0.13793103448275862, 'percent_wrong_to_correct': 0.0}
- **drop:P571**: {'n_observations': 33, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.12121212121212122, 'percent_downgraded_to_other': 0.18181818181818182, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.06060606060606061}
- **drop:P37**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.3, 'percent_downgraded_to_other': 0.1, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P112**: {'n_observations': 19, 'type_flip_rate': 0.2631578947368421, 'disappearance_rate': 0.10526315789473684, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P131,P69**: {'n_observations': 21, 'type_flip_rate': 0.23809523809523808, 'disappearance_rate': 0.2857142857142857, 'percent_downgraded_to_other': 0.23809523809523808, 'percent_correct_to_wrong': 0.09523809523809523, 'percent_wrong_to_correct': 0.09523809523809523}
- **ambiguous:P27,P102,P17**: {'n_observations': 9, 'type_flip_rate': 0.2222222222222222, 'disappearance_rate': 0.6666666666666666, 'percent_downgraded_to_other': 0.2222222222222222, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P27,P108**: {'n_observations': 2, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P570,P69,P112**: {'n_observations': 8, 'type_flip_rate': 0.375, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.25, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P161,P27**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.16666666666666666, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P27,P569**: {'n_observations': 9, 'type_flip_rate': 0.2222222222222222, 'disappearance_rate': 0.4444444444444444, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P26,P40,P570**: {'n_observations': 7, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2857142857142857, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P69,P570,P27**: {'n_observations': 10, 'type_flip_rate': 0.1, 'disappearance_rate': 0.3, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P40,P361,P26**: {'n_observations': 8, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P17,P527**: {'n_observations': 7, 'type_flip_rate': 0.0, 'disappearance_rate': 0.5714285714285714, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P495**: {'n_observations': 4, 'type_flip_rate': 0.75, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P463,P19**: {'n_observations': 9, 'type_flip_rate': 0.0, 'disappearance_rate': 0.5555555555555556, 'percent_downgraded_to_other': 0.1111111111111111, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P19,P108**: {'n_observations': 22, 'type_flip_rate': 0.18181818181818182, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.09090909090909091, 'percent_wrong_to_correct': 0.045454545454545456}
- **ambiguous:P161,P495,P577**: {'n_observations': 20, 'type_flip_rate': 0.75, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.15, 'percent_correct_to_wrong': 0.45, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P54,P27,P118**: {'n_observations': 7, 'type_flip_rate': 0.2857142857142857, 'disappearance_rate': 0.14285714285714285, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5714285714285714, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P463,P50,P108**: {'n_observations': 14, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P463,P495**: {'n_observations': 10, 'type_flip_rate': 0.5, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P571,P112**: {'n_observations': 4, 'type_flip_rate': 0.75, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.25, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P108,P527**: {'n_observations': 10, 'type_flip_rate': 0.6, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **drop:P118**: {'n_observations': 7, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P50,P19,P20**: {'n_observations': 13, 'type_flip_rate': 0.5384615384615384, 'disappearance_rate': 0.15384615384615385, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.15384615384615385, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P27,P463**: {'n_observations': 9, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.2222222222222222, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P54,P108,P17**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.2, 'percent_correct_to_wrong': 0.1, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P140,P570,P571**: {'n_observations': 11, 'type_flip_rate': 0.45454545454545453, 'disappearance_rate': 0.18181818181818182, 'percent_downgraded_to_other': 0.36363636363636365, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.09090909090909091}
- **ambiguous:P17,P40,P569**: {'n_observations': 11, 'type_flip_rate': 0.45454545454545453, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.18181818181818182, 'percent_correct_to_wrong': 0.09090909090909091, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P50,P800**: {'n_observations': 10, 'type_flip_rate': 0.0, 'disappearance_rate': 0.8, 'percent_downgraded_to_other': 0.1, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P569,P580,P582**: {'n_observations': 10, 'type_flip_rate': 0.2, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P37,P17,P131**: {'n_observations': 5, 'type_flip_rate': 0.4, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P140**: {'n_observations': 19, 'type_flip_rate': 0.10526315789473684, 'disappearance_rate': 0.5263157894736842, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P527,P150**: {'n_observations': 9, 'type_flip_rate': 0.5555555555555556, 'disappearance_rate': 0.4444444444444444, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1111111111111111, 'percent_wrong_to_correct': 0.0}
- **drop:P800**: {'n_observations': 25, 'type_flip_rate': 0.08, 'disappearance_rate': 0.12, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P527,P178**: {'n_observations': 9, 'type_flip_rate': 0.5555555555555556, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.2222222222222222, 'percent_correct_to_wrong': 0.1111111111111111, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P495,P175**: {'n_observations': 13, 'type_flip_rate': 0.0, 'disappearance_rate': 0.9230769230769231, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.23076923076923078, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P30,P361**: {'n_observations': 11, 'type_flip_rate': 0.6363636363636364, 'disappearance_rate': 0.2727272727272727, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P527**: {'n_observations': 17, 'type_flip_rate': 0.7058823529411765, 'disappearance_rate': 0.17647058823529413, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.058823529411764705, 'percent_wrong_to_correct': 0.0}
- **drop:P582**: {'n_observations': 24, 'type_flip_rate': 0.08333333333333333, 'disappearance_rate': 0.7083333333333334, 'percent_downgraded_to_other': 0.125, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P150,P131,P17**: {'n_observations': 5, 'type_flip_rate': 0.6, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **drop:P178**: {'n_observations': 9, 'type_flip_rate': 0.0, 'disappearance_rate': 0.1111111111111111, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P50,P570,P800**: {'n_observations': 9, 'type_flip_rate': 0.2222222222222222, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.1111111111111111, 'percent_correct_to_wrong': 0.1111111111111111, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P50,P800,P495**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.3333333333333333, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P159,P50,P17**: {'n_observations': 3, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P102,P361**: {'n_observations': 14, 'type_flip_rate': 0.5714285714285714, 'disappearance_rate': 0.21428571428571427, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P582,P131**: {'n_observations': 14, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.42857142857142855, 'percent_downgraded_to_other': 0.07142857142857142, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.07142857142857142}
- **ambiguous:P17,P570,P27**: {'n_observations': 8, 'type_flip_rate': 0.125, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.125, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P17,P1001**: {'n_observations': 5, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.4}
- **ambiguous:P127,P176,P17**: {'n_observations': 6, 'type_flip_rate': 0.16666666666666666, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.3333333333333333, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P54,P569,P27**: {'n_observations': 8, 'type_flip_rate': 0.625, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.625, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P279,P140,P50**: {'n_observations': 2, 'type_flip_rate': 0.5, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P102**: {'n_observations': 4, 'type_flip_rate': 0.5, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.5, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P279**: {'n_observations': 3, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P276,P17,P585**: {'n_observations': 2, 'type_flip_rate': 0.5, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P150,P206**: {'n_observations': 12, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.5833333333333334, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P175,P463**: {'n_observations': 14, 'type_flip_rate': 0.21428571428571427, 'disappearance_rate': 0.7142857142857143, 'percent_downgraded_to_other': 0.21428571428571427, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P527,P1441,P674**: {'n_observations': 17, 'type_flip_rate': 0.0, 'disappearance_rate': 0.7058823529411765, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P241,P108**: {'n_observations': 2, 'type_flip_rate': 0.0, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P241**: {'n_observations': 2, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P19,P20**: {'n_observations': 22, 'type_flip_rate': 0.8636363636363636, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.8636363636363636, 'percent_correct_to_wrong': 0.09090909090909091, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P30,P131**: {'n_observations': 5, 'type_flip_rate': 0.4, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P54,P102**: {'n_observations': 7, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.14285714285714285, 'percent_downgraded_to_other': 0.7142857142857143, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P279,P17**: {'n_observations': 1, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P3373,P19,P27**: {'n_observations': 7, 'type_flip_rate': 0.2857142857142857, 'disappearance_rate': 0.2857142857142857, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2857142857142857, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P50,P102**: {'n_observations': 6, 'type_flip_rate': 0.16666666666666666, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P1441,P40,P140**: {'n_observations': 6, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P19,P27,P570**: {'n_observations': 11, 'type_flip_rate': 0.18181818181818182, 'disappearance_rate': 0.2727272727272727, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2727272727272727, 'percent_wrong_to_correct': 0.09090909090909091}
- **ambiguous:P161,P577,P108**: {'n_observations': 15, 'type_flip_rate': 0.5333333333333333, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}

## E4 cost-quality

> `recall@k` = (oracle causes recovered) / (total oracle causes)  ·  `hit` = fraction of selected interventions hitting ≥1 cause.

- planner=exhaustive     budget=1    recall@k=1.000  hit=0.45  reuse=9.96  tok_in=9844334  tok_out=23172293
- planner=exhaustive     budget=2    recall@k=1.000  hit=0.45  reuse=9.96  tok_in=9844334  tok_out=23172293
- planner=exhaustive     budget=3    recall@k=1.000  hit=0.45  reuse=9.96  tok_in=9844334  tok_out=23172293
- planner=exhaustive     budget=4    recall@k=1.000  hit=0.45  reuse=9.96  tok_in=9844334  tok_out=23172293
- planner=exhaustive     budget=6    recall@k=1.000  hit=0.45  reuse=9.96  tok_in=9844334  tok_out=23172293
- planner=exhaustive     budget=8    recall@k=1.000  hit=0.45  reuse=9.96  tok_in=9844334  tok_out=23172293
- planner=random         budget=1    recall@k=0.012  hit=0.38  reuse=10.49  tok_in=207211  tok_out=454211
- planner=random         budget=2    recall@k=0.062  hit=0.38  reuse=10.50  tok_in=386927  tok_out=944470
- planner=random         budget=3    recall@k=0.092  hit=0.43  reuse=10.09  tok_in=649388  tok_out=1585983
- planner=random         budget=4    recall@k=0.109  hit=0.41  reuse=9.90  tok_in=833675  tok_out=1985047
- planner=random         budget=6    recall@k=0.200  hit=0.48  reuse=9.98  tok_in=1470447  tok_out=3522985
- planner=random         budget=8    recall@k=0.231  hit=0.46  reuse=9.93  tok_in=1868634  tok_out=4458572
- planner=span_only      budget=1    recall@k=0.000  hit=0.13  reuse=9.56  tok_in=56666  tok_out=118761
- planner=span_only      budget=2    recall@k=0.000  hit=0.13  reuse=9.56  tok_in=114119  tok_out=249645
- planner=span_only      budget=3    recall@k=0.001  hit=0.13  reuse=9.56  tok_in=170946  tok_out=378191
- planner=span_only      budget=4    recall@k=0.002  hit=0.13  reuse=9.56  tok_in=227960  tok_out=504306
- planner=span_only      budget=6    recall@k=0.003  hit=0.13  reuse=9.56  tok_in=342062  tok_out=761341
- planner=span_only      budget=8    recall@k=0.004  hit=0.13  reuse=9.56  tok_in=456042  tok_out=1019748
- planner=prompt_only    budget=1    recall@k=0.140  hit=1.00  reuse=10.76  tok_in=514549  tok_out=1250844
- planner=prompt_only    budget=2    recall@k=0.143  hit=0.57  reuse=10.13  tok_in=573015  tok_out=1384339
- planner=prompt_only    budget=3    recall@k=0.144  hit=0.42  reuse=9.92  tok_in=631247  tok_out=1523852
- planner=prompt_only    budget=4    recall@k=0.148  hit=0.35  reuse=9.82  tok_in=699905  tok_out=1680637
- planner=prompt_only    budget=6    recall@k=0.292  hit=0.42  reuse=9.92  tok_in=1275670  tok_out=3062656
- planner=prompt_only    budget=8    recall@k=0.376  hit=0.46  reuse=9.97  tok_in=1849973  tok_out=4364080
- planner=schema_only    budget=1    recall@k=0.009  hit=1.00  reuse=10.78  tok_in=609075  tok_out=1237264
- planner=schema_only    budget=2    recall@k=0.021  hit=1.00  reuse=10.76  tok_in=1076848  tok_out=2481169
- planner=schema_only    budget=3    recall@k=0.196  hit=1.00  reuse=10.76  tok_in=1511624  tok_out=3889072
- planner=schema_only    budget=4    recall@k=0.312  hit=1.00  reuse=10.76  tok_in=2030534  tok_out=5196001
- planner=schema_only    budget=6    recall@k=0.344  hit=1.00  reuse=10.76  tok_in=3066707  tok_out=7609642
- planner=schema_only    budget=8    recall@k=0.361  hit=1.00  reuse=10.76  tok_in=4109424  tok_out=10052922
- planner=graphguard  budget=1    recall@k=0.033  hit=1.00  reuse=10.76  tok_in=518643  tok_out=1235304
- planner=graphguard  budget=2    recall@k=0.079  hit=1.00  reuse=10.76  tok_in=1037549  tok_out=2483706
- planner=graphguard  budget=3    recall@k=0.140  hit=1.00  reuse=10.76  tok_in=1554920  tok_out=3709993
- planner=graphguard  budget=4    recall@k=0.164  hit=1.00  reuse=10.76  tok_in=2074115  tok_out=4908488
- planner=graphguard  budget=6    recall@k=0.207  hit=1.00  reuse=10.76  tok_in=3131571  tok_out=7444066
- planner=graphguard  budget=8    recall@k=0.244  hit=1.00  reuse=10.76  tok_in=4176100  tok_out=9930389
- planner=adaptive_graphguard budget=1    recall@k=0.028  hit=0.86  reuse=10.10  tok_in=424174  tok_out=996661
- planner=adaptive_graphguard budget=2    recall@k=0.071  hit=0.89  reuse=10.16  tok_in=892161  tok_out=2031092
- planner=adaptive_graphguard budget=3    recall@k=0.105  hit=0.88  reuse=10.21  tok_in=1316479  tok_out=3051360
- planner=adaptive_graphguard budget=4    recall@k=0.017  hit=0.14  reuse=9.92  tok_in=216839  tok_out=520499
- planner=adaptive_graphguard budget=6    recall@k=0.060  hit=0.23  reuse=9.52  tok_in=560214  tok_out=1327827
- planner=adaptive_graphguard budget=8    recall@k=0.265  hit=0.43  reuse=9.92  tok_in=1505134  tok_out=3470634

**Cost-quality AUC (higher = better):**
- exhaustive: 1.0
- schema_only: 0.2483
- prompt_only: 0.2199
- graphguard: 0.1629
- random: 0.1363
- adaptive_graphguard: 0.0858
- span_only: 0.0019

## Repair (secondary, exploratory)

> F1-improving repair is **not yet supported by current data**; reported for completeness only.

- raw               best F1=0.195 at frac=0.0
- random            best F1=0.195 at frac=0.0
- by_confidence     best F1=0.209 at frac=0.3
- by_risk           best F1=0.209 at frac=0.5
- by_schema_sens    best F1=0.206 at frac=0.3
- by_stability      best F1=0.207 at frac=0.3

## Case studies (one per category when available)

### Case 1 [prompt_induced_wrong]: (Kalidas Jayaram) -[P26]-> (Ashwathy Kurup)
- risk=2.6, stab=0.0, label=wrong
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs
- top type cause:      switch_schema on schema 'desc_added' → relation type flips in 1/1 runs

### Case 2 [schema_forced_flip]: (Gershonites) -[P150]-> (Manasseh)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs
- top type cause:      remove on prompt_clause 'C2_infer_implicit' → relation type flips in 1/1 runs

### Case 3 [schema_forced_flip]: (Gershonites) -[P150]-> (Issachar)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs
- top type cause:      remove on prompt_clause 'C2_infer_implicit' → relation type flips in 1/1 runs

### Case 4 [schema_forced_flip]: (Gershonites) -[P150]-> (Asher)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs
- top type cause:      remove on prompt_clause 'C2_infer_implicit' → relation type flips in 1/1 runs

### Case 5 [schema_forced_flip]: (Gershonites) -[P150]-> (Naphtali)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs
- top type cause:      remove on prompt_clause 'C2_infer_implicit' → relation type flips in 1/1 runs

### Case 6 [schema_forced_flip]: (Solingen) -[P361]-> (Rhineland)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: tone on prompt_clause 'strict' → edge disappears in 1/1 runs
- top type cause:      remove on prompt_clause 'C1_evidence_only' → relation type flips in 1/1 runs

### Case 7 [schema_forced_flip]: (Ashwathy Kurup) -[P19]-> (Chennai)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C1_evidence_only' → edge disappears in 1/1 runs
- top type cause:      remove on prompt_clause 'C3_use_schema' → relation type flips in 1/1 runs

### Case 8 [schema_forced_flip]: (Ashwathy Kurup) -[P161]-> (1987)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C2_infer_implicit' → edge disappears in 1/1 runs
- top type cause:      remove on prompt_clause 'C1_evidence_only' → relation type flips in 1/1 runs

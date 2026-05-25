# GraphGuard experiment report

> **Claim.** GraphGuard enables reliability auditing of LLM-extracted graph databases. Current evidence supports audit prioritization; F1 repair remains a secondary, in-progress claim.

## Database summary

- documents: 100
- sentences: 801
- entities: 1905
- gold_edges: 1315
- extraction_events: 2040
- extracted_edges: 13478
- intervention_candidates: 4299
- counterfactual_runs: 1820
- edge_outcomes: 11964
- edge_reliability_scores: 969
- edge_correctness: 689
- stability_reports: 30

## E0 stability

```json
{
  "docs": [
    {
      "document_id": "docred-validation-000000-Skai_TV",
      "event_ids": [
        "evt-docred-validation-000000-Skai_TV-962150163e",
        "evt-docred-validation-000000-Skai_TV-5d83faffa8",
        "evt-docred-validation-000000-Skai_TV-5915d600ce",
        "evt-docred-validation-000000-Skai_TV-8921bf1184"
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
      "document_id": "docred-validation-000001-Washington_Place__West_Virginia_",
      "event_ids": [
        "evt-docred-validation-000001-Washington_Place__West_Virginia_-9e44d7c4fa",
        "evt-docred-validation-000001-Washington_Place__West_Virginia_-d6872501ed",
        "evt-docred-validation-000001-Washington_Place__West_Virginia_-90785477a4",
        "evt-docred-validation-000001-Washington_Place__West_Virginia_-1825e90d4b"
      ],
      "metrics": {
        "avg_edge_overlap": 0.3551,
        "type_agreement": 1.0,
        "disappearance_rate": 0.4661,
        "type_flip_rate": 0.1227,
        "new_edge_rate": 0.4652
      }
    },
    {
      "document_id": "docred-validation-000002-IBM_Research___Brazil",
      "event_ids": [
        "evt-docred-validation-000002-IBM_Research___Brazil-171652a4b9",
        "evt-docred-validation-000002-IBM_Research___Brazil-66bdae95e9",
        "evt-docred-validation-000002-IBM_Research___Brazil-fd7
```

## E2 error detection (multi-mode)

- correct=235 wrong=56 unmatched=398 ambiguous=0

**Mode `strict`** — positive = wrong + unmatched (assumes DocRED gold is complete) (n_eval=689, prevalence=0.6589)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.798 | 0.652 | 0.97 | 0.94 | 0.82 |
| prompt_sensitivity | 0.718 | 0.593 | 0.62 | 0.80 | 0.82 |
| schema_sensitivity | 0.797 | 0.660 | 0.94 | 0.93 | 0.87 |
| stochastic_variance | 0.654 | 0.500 | 0.59 | 0.61 | 0.61 |
| 1_minus_stability | 0.814 | 0.667 | 1.00 | 0.96 | 0.90 |
| random | 0.647 | 0.491 | 0.59 | 0.62 | 0.68 |
| baseline:confidence_inv | 0.775 | 0.624 | 0.91 | 0.86 | 0.86 |
| baseline:majority_vote_inv | 0.728 | 0.592 | 0.76 | 0.72 | 0.79 |
| baseline:source_prov_inv | 0.654 | 0.500 | 0.59 | 0.61 | 0.61 |
| baseline:subj_obj_cooccur_inv | 0.674 | 0.531 | 0.59 | 0.64 | 0.65 |

**Mode `clean`** — drop unmatched; correct vs wrong only (robust to gold incompleteness) (n_eval=291, prevalence=0.1924)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.305 | 0.583 | 0.47 | 0.28 | 0.26 |
| prompt_sensitivity | 0.232 | 0.555 | 0.13 | 0.24 | 0.24 |
| schema_sensitivity | 0.283 | 0.581 | 0.40 | 0.34 | 0.26 |
| stochastic_variance | 0.222 | 0.500 | 0.27 | 0.21 | 0.17 |
| 1_minus_stability | 0.344 | 0.597 | 0.53 | 0.41 | 0.29 |
| random | 0.212 | 0.462 | 0.20 | 0.21 | 0.16 |
| baseline:confidence_inv | 0.279 | 0.549 | 0.33 | 0.34 | 0.26 |
| baseline:majority_vote_inv | 0.239 | 0.562 | 0.20 | 0.28 | 0.26 |
| baseline:source_prov_inv | 0.222 | 0.500 | 0.27 | 0.21 | 0.17 |
| baseline:subj_obj_cooccur_inv | 0.246 | 0.540 | 0.27 | 0.24 | 0.24 |

**Mode `wrong_only`** — positive = wrong only; unmatched treated as negative (n_eval=689, prevalence=0.0813)

| signal | AUC-PR | ROC-AUC | P@5% | P@10% | P@20% |
|---|---|---|---|---|---|
| risk | 0.084 | 0.478 | 0.06 | 0.07 | 0.06 |
| prompt_sensitivity | 0.084 | 0.491 | 0.09 | 0.07 | 0.07 |
| schema_sensitivity | 0.081 | 0.472 | 0.03 | 0.07 | 0.07 |
| stochastic_variance | 0.101 | 0.500 | 0.12 | 0.10 | 0.08 |
| 1_minus_stability | 0.082 | 0.485 | 0.03 | 0.10 | 0.06 |
| random | 0.094 | 0.527 | 0.12 | 0.10 | 0.10 |
| baseline:confidence_inv | 0.087 | 0.468 | 0.09 | 0.09 | 0.08 |
| baseline:majority_vote_inv | 0.086 | 0.499 | 0.09 | 0.09 | 0.07 |
| baseline:source_prov_inv | 0.101 | 0.500 | 0.12 | 0.10 | 0.08 |
| baseline:subj_obj_cooccur_inv | 0.114 | 0.521 | 0.15 | 0.13 | 0.12 |

## E5 audit prioritization (primary)


**Mode `strict`** — positive = wrong + unmatched (n_eval=689, prevalence=0.6589)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 91.0 | 1.00 | 0.96 | 0.91 | 65 | 113 |
| prompt_sensitivity | 78.0 | 0.70 | 0.68 | 0.78 | 51 | 112 |
| schema_sensitivity | 91.0 | 0.90 | 0.92 | 0.91 | 63 | 120 |
| stochastic_variance | 62.0 | 0.30 | 0.60 | 0.62 | 47 | 84 |
| 1_minus_stability | 90.0 | 1.00 | 0.98 | 0.90 | 66 | 124 |
| 1_minus_confidence | 82.0 | 0.70 | 0.84 | 0.82 | 57 | 117 |
| random | 69.0 | 0.90 | 0.78 | 0.69 | 52 | 99 |
| baseline:confidence_inv | 83.0 | 0.90 | 0.88 | 0.83 | 58 | 119 |
| baseline:majority_vote_inv | 75.0 | 0.70 | 0.66 | 0.75 | 50 | 109 |
| baseline:source_prov_inv | 62.0 | 0.30 | 0.60 | 0.62 | 47 | 84 |
| baseline:subj_obj_cooccur_inv | 62.0 | 0.40 | 0.66 | 0.62 | 46 | 90 |

**Mode `clean`** — drop unmatched; correct vs wrong only (n_eval=291, prevalence=0.1924)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 26.0 | 0.50 | 0.28 | 0.26 | 8 | 15 |
| prompt_sensitivity | 24.0 | 0.20 | 0.22 | 0.24 | 7 | 15 |
| schema_sensitivity | 27.0 | 0.50 | 0.28 | 0.27 | 11 | 15 |
| stochastic_variance | 18.0 | 0.10 | 0.18 | 0.18 | 8 | 10 |
| 1_minus_stability | 25.0 | 0.70 | 0.34 | 0.25 | 12 | 17 |
| 1_minus_confidence | 24.0 | 0.30 | 0.28 | 0.24 | 10 | 15 |
| random | 16.0 | 0.20 | 0.22 | 0.16 | 5 | 12 |
| baseline:confidence_inv | 24.0 | 0.40 | 0.28 | 0.24 | 10 | 15 |
| baseline:majority_vote_inv | 24.0 | 0.30 | 0.28 | 0.24 | 9 | 15 |
| baseline:source_prov_inv | 18.0 | 0.10 | 0.18 | 0.18 | 8 | 10 |
| baseline:subj_obj_cooccur_inv | 23.0 | 0.40 | 0.24 | 0.23 | 8 | 15 |

**Mode `wrong_only`** — positive = wrong only; unmatched treated as negative (n_eval=689, prevalence=0.0813)

| signal | errs/100 | hit@10 | hit@50 | hit@100 | caught@10% | caught@20% |
|---|---|---|---|---|---|---|
| risk | 8.0 | 0.10 | 0.10 | 0.08 | 5 | 8 |
| prompt_sensitivity | 7.0 | 0.00 | 0.12 | 0.07 | 6 | 8 |
| schema_sensitivity | 5.0 | 0.10 | 0.08 | 0.05 | 5 | 10 |
| stochastic_variance | 9.0 | 0.10 | 0.16 | 0.09 | 8 | 13 |
| 1_minus_stability | 8.0 | 0.10 | 0.08 | 0.08 | 7 | 8 |
| 1_minus_confidence | 8.0 | 0.10 | 0.08 | 0.08 | 6 | 11 |
| random | 8.0 | 0.00 | 0.08 | 0.08 | 5 | 13 |
| baseline:confidence_inv | 8.0 | 0.20 | 0.08 | 0.08 | 6 | 11 |
| baseline:majority_vote_inv | 9.0 | 0.20 | 0.10 | 0.09 | 8 | 10 |
| baseline:source_prov_inv | 9.0 | 0.10 | 0.16 | 0.09 | 8 | 13 |
| baseline:subj_obj_cooccur_inv | 13.0 | 0.10 | 0.14 | 0.13 | 9 | 17 |

## E1 known-cause

```json
{
  "n": 618,
  "top1_acc": 0.8624595469255664,
  "top3_recall": 0.8996763754045307,
  "mrr": 0.8783710895361382,
  "macro_f1": 0.48365713540628014,
  "per_cause_f1": {
    "noop": 0.0,
    "prompt_clause": 0.8013698630136985,
    "schema": 0.9227323628219484,
    "sentence": 0.2105263157894737
  },
  "per_cause_n": {
    "noop": 0,
    "prompt_clause": 157,
    "schema": 438,
    "sentence": 23
  }
}
```

## E3 schema debugging — flip rates per variant

- **ambiguous:P17,P159,P361**: {'n_observations': 8, 'type_flip_rate': 0.5, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **coarse**: {'n_observations': 763, 'type_flip_rate': 0.7116644823066841, 'disappearance_rate': 0.2817824377457405, 'percent_downgraded_to_other': 0.001310615989515072, 'percent_correct_to_wrong': 0.32634338138925295, 'percent_wrong_to_correct': 0.0}
- **desc_added**: {'n_observations': 763, 'type_flip_rate': 0.047182175622542594, 'disappearance_rate': 0.1651376146788991, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.022280471821756225, 'percent_wrong_to_correct': 0.00655307994757536}
- **ambiguous:P131,P17,P150**: {'n_observations': 44, 'type_flip_rate': 0.5, 'disappearance_rate': 0.3409090909090909, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.22727272727272727, 'percent_wrong_to_correct': 0.0}
- **desc_removed**: {'n_observations': 763, 'type_flip_rate': 0.07863695937090433, 'disappearance_rate': 0.1743119266055046, 'percent_downgraded_to_other': 0.002621231979030144, 'percent_correct_to_wrong': 0.03800786369593709, 'percent_wrong_to_correct': 0.007863695937090432}
- **drop:P159**: {'n_observations': 26, 'type_flip_rate': 0.3076923076923077, 'disappearance_rate': 0.15384615384615385, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.11538461538461539, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P175,P264**: {'n_observations': 11, 'type_flip_rate': 0.18181818181818182, 'disappearance_rate': 0.45454545454545453, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.36363636363636365, 'percent_wrong_to_correct': 0.0}
- **drop:P17**: {'n_observations': 422, 'type_flip_rate': 0.16587677725118483, 'disappearance_rate': 0.1966824644549763, 'percent_downgraded_to_other': 0.004739336492890996, 'percent_correct_to_wrong': 0.14218009478672985, 'percent_wrong_to_correct': 0.0071090047393364926}
- **drop:P361**: {'n_observations': 82, 'type_flip_rate': 0.2682926829268293, 'disappearance_rate': 0.1951219512195122, 'percent_downgraded_to_other': 0.024390243902439025, 'percent_correct_to_wrong': 0.13414634146341464, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P176,P17,P527**: {'n_observations': 9, 'type_flip_rate': 0.2222222222222222, 'disappearance_rate': 0.4444444444444444, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **drop:P131**: {'n_observations': 294, 'type_flip_rate': 0.23129251700680273, 'disappearance_rate': 0.30612244897959184, 'percent_downgraded_to_other': 0.013605442176870748, 'percent_correct_to_wrong': 0.10884353741496598, 'percent_wrong_to_correct': 0.01020408163265306}
- **drop:P150**: {'n_observations': 173, 'type_flip_rate': 0.05202312138728324, 'disappearance_rate': 0.23121387283236994, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.017341040462427744, 'percent_wrong_to_correct': 0.011560693641618497}
- **hierarchical**: {'n_observations': 763, 'type_flip_rate': 0.057667103538663174, 'disappearance_rate': 0.15334207077326342, 'percent_downgraded_to_other': 0.005242463958060288, 'percent_correct_to_wrong': 0.019659239842726082, 'percent_wrong_to_correct': 0.005242463958060288}
- **rename**: {'n_observations': 754, 'type_flip_rate': 0.08090185676392574, 'disappearance_rate': 0.17771883289124668, 'percent_downgraded_to_other': 0.001326259946949602, 'percent_correct_to_wrong': 0.04509283819628647, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P19,P570,P137**: {'n_observations': 13, 'type_flip_rate': 0.38461538461538464, 'disappearance_rate': 0.07692307692307693, 'percent_downgraded_to_other': 0.15384615384615385, 'percent_correct_to_wrong': 0.3076923076923077, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P108,P159**: {'n_observations': 13, 'type_flip_rate': 0.6153846153846154, 'disappearance_rate': 0.23076923076923078, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P175**: {'n_observations': 93, 'type_flip_rate': 0.16129032258064516, 'disappearance_rate': 0.13978494623655913, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.08602150537634409, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P150**: {'n_observations': 67, 'type_flip_rate': 0.3880597014925373, 'disappearance_rate': 0.34328358208955223, 'percent_downgraded_to_other': 0.11940298507462686, 'percent_correct_to_wrong': 0.31343283582089554, 'percent_wrong_to_correct': 0.0}
- **reorder**: {'n_observations': 763, 'type_flip_rate': 0.09043250327653997, 'disappearance_rate': 0.15334207077326342, 'percent_downgraded_to_other': 0.003931847968545216, 'percent_correct_to_wrong': 0.03407601572739188, 'percent_wrong_to_correct': 0.011795543905635648}
- **drop:P264**: {'n_observations': 39, 'type_flip_rate': 0.0, 'disappearance_rate': 0.1282051282051282, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **with_other**: {'n_observations': 763, 'type_flip_rate': 0.045871559633027525, 'disappearance_rate': 0.1363040629095675, 'percent_downgraded_to_other': 0.001310615989515072, 'percent_correct_to_wrong': 0.01834862385321101, 'percent_wrong_to_correct': 0.005242463958060288}
- **drop:P577**: {'n_observations': 123, 'type_flip_rate': 0.032520325203252036, 'disappearance_rate': 0.2845528455284553, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.056910569105691054, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P108**: {'n_observations': 27, 'type_flip_rate': 0.2962962962962963, 'disappearance_rate': 0.6666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **drop:P176**: {'n_observations': 9, 'type_flip_rate': 0.0, 'disappearance_rate': 0.5555555555555556, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P137**: {'n_observations': 13, 'type_flip_rate': 0.0, 'disappearance_rate': 0.15384615384615385, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P108**: {'n_observations': 161, 'type_flip_rate': 0.16770186335403728, 'disappearance_rate': 0.2360248447204969, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.043478260869565216, 'percent_wrong_to_correct': 0.012422360248447204}
- **drop:P527**: {'n_observations': 66, 'type_flip_rate': 0.09090909090909091, 'disappearance_rate': 0.5151515151515151, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P19**: {'n_observations': 49, 'type_flip_rate': 0.10204081632653061, 'disappearance_rate': 0.16326530612244897, 'percent_downgraded_to_other': 0.02040816326530612, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **drop:P570**: {'n_observations': 68, 'type_flip_rate': 0.14705882352941177, 'disappearance_rate': 0.14705882352941177, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14705882352941177, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P69,P150**: {'n_observations': 23, 'type_flip_rate': 0.0, 'disappearance_rate': 0.34782608695652173, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2608695652173913, 'percent_wrong_to_correct': 0.0}
- **drop:P69**: {'n_observations': 66, 'type_flip_rate': 0.045454545454545456, 'disappearance_rate': 0.3787878787878788, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.19696969696969696, 'percent_wrong_to_correct': 0.015151515151515152}
- **ambiguous:P175,P577,P361**: {'n_observations': 9, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.2222222222222222, 'percent_downgraded_to_other': 0.3333333333333333, 'percent_correct_to_wrong': 0.4444444444444444, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P361**: {'n_observations': 6, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P194**: {'n_observations': 11, 'type_flip_rate': 0.2727272727272727, 'disappearance_rate': 0.2727272727272727, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.18181818181818182, 'percent_wrong_to_correct': 0.0}
- **drop:P194**: {'n_observations': 11, 'type_flip_rate': 0.0, 'disappearance_rate': 0.09090909090909091, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P150,P1336**: {'n_observations': 4, 'type_flip_rate': 0.5, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P1336**: {'n_observations': 4, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P54,P27,P569**: {'n_observations': 6, 'type_flip_rate': 0.8333333333333334, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.16666666666666666, 'percent_correct_to_wrong': 0.8333333333333334, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P19**: {'n_observations': 5, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P527,P131**: {'n_observations': 11, 'type_flip_rate': 0.45454545454545453, 'disappearance_rate': 0.36363636363636365, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P264,P577**: {'n_observations': 14, 'type_flip_rate': 0.42857142857142855, 'disappearance_rate': 0.07142857142857142, 'percent_downgraded_to_other': 0.14285714285714285, 'percent_correct_to_wrong': 0.07142857142857142, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P150**: {'n_observations': 3, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.6666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P27,P463**: {'n_observations': 6, 'type_flip_rate': 0.0, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P17,P108**: {'n_observations': 13, 'type_flip_rate': 0.0, 'disappearance_rate': 0.9230769230769231, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.23076923076923078, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P69**: {'n_observations': 16, 'type_flip_rate': 0.125, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3125, 'percent_wrong_to_correct': 0.0}
- **drop:P27**: {'n_observations': 147, 'type_flip_rate': 0.12244897959183673, 'disappearance_rate': 0.19047619047619047, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.14285714285714285, 'percent_wrong_to_correct': 0.0}
- **drop:P54**: {'n_observations': 24, 'type_flip_rate': 0.375, 'disappearance_rate': 0.08333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **drop:P569**: {'n_observations': 93, 'type_flip_rate': 0.03225806451612903, 'disappearance_rate': 0.26881720430107525, 'percent_downgraded_to_other': 0.010752688172043012, 'percent_correct_to_wrong': 0.17204301075268819, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P108,P69**: {'n_observations': 8, 'type_flip_rate': 0.25, 'disappearance_rate': 0.375, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P463**: {'n_observations': 40, 'type_flip_rate': 0.15, 'disappearance_rate': 0.175, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.075, 'percent_wrong_to_correct': 0.025}
- **ambiguous:P19,P108,P569**: {'n_observations': 5, 'type_flip_rate': 0.6, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.6, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P150,P108**: {'n_observations': 8, 'type_flip_rate': 0.625, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P19,P108**: {'n_observations': 4, 'type_flip_rate': 0.25, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P26,P40**: {'n_observations': 9, 'type_flip_rate': 0.1111111111111111, 'disappearance_rate': 0.4444444444444444, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P27,P569**: {'n_observations': 13, 'type_flip_rate': 0.5384615384615384, 'disappearance_rate': 0.15384615384615385, 'percent_downgraded_to_other': 0.07692307692307693, 'percent_correct_to_wrong': 0.07692307692307693, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P577,P50**: {'n_observations': 8, 'type_flip_rate': 0.5, 'disappearance_rate': 0.375, 'percent_downgraded_to_other': 0.25, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P27,P495**: {'n_observations': 9, 'type_flip_rate': 0.7777777777777778, 'disappearance_rate': 0.1111111111111111, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.7777777777777778, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P570,P19**: {'n_observations': 5, 'type_flip_rate': 0.0, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.6, 'percent_wrong_to_correct': 0.0}
- **drop:P161**: {'n_observations': 37, 'type_flip_rate': 0.16216216216216217, 'disappearance_rate': 0.4864864864864865, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16216216216216217, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P159**: {'n_observations': 3, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **drop:P50**: {'n_observations': 31, 'type_flip_rate': 0.06451612903225806, 'disappearance_rate': 0.2903225806451613, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.03225806451612903, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P463,P30**: {'n_observations': 8, 'type_flip_rate': 0.625, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **drop:P26**: {'n_observations': 25, 'type_flip_rate': 0.0, 'disappearance_rate': 0.24, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.16, 'percent_wrong_to_correct': 0.0}
- **drop:P495**: {'n_observations': 46, 'type_flip_rate': 0.043478260869565216, 'disappearance_rate': 0.17391304347826086, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.043478260869565216, 'percent_wrong_to_correct': 0.0}
- **drop:P40**: {'n_observations': 30, 'type_flip_rate': 0.1, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.1, 'percent_correct_to_wrong': 0.03333333333333333, 'percent_wrong_to_correct': 0.0}
- **drop:P30**: {'n_observations': 8, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P577,P527**: {'n_observations': 14, 'type_flip_rate': 0.35714285714285715, 'disappearance_rate': 0.42857142857142855, 'percent_downgraded_to_other': 0.35714285714285715, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P264,P577,P175**: {'n_observations': 7, 'type_flip_rate': 0.14285714285714285, 'disappearance_rate': 0.14285714285714285, 'percent_downgraded_to_other': 0.14285714285714285, 'percent_correct_to_wrong': 0.2857142857142857, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P361,P150**: {'n_observations': 3, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.6666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P108,P131,P361**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P50,P17,P264**: {'n_observations': 7, 'type_flip_rate': 0.0, 'disappearance_rate': 0.42857142857142855, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P127,P361,P355**: {'n_observations': 5, 'type_flip_rate': 0.2, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P495,P577**: {'n_observations': 18, 'type_flip_rate': 0.7222222222222222, 'disappearance_rate': 0.1111111111111111, 'percent_downgraded_to_other': 0.05555555555555555, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P569,P570**: {'n_observations': 23, 'type_flip_rate': 0.7391304347826086, 'disappearance_rate': 0.08695652173913043, 'percent_downgraded_to_other': 0.08695652173913043, 'percent_correct_to_wrong': 0.6086956521739131, 'percent_wrong_to_correct': 0.0}
- **drop:P127**: {'n_observations': 5, 'type_flip_rate': 0.0, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P355**: {'n_observations': 5, 'type_flip_rate': 0.0, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P26,P569**: {'n_observations': 6, 'type_flip_rate': 0.16666666666666666, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P3373,P40,P17**: {'n_observations': 7, 'type_flip_rate': 0.2857142857142857, 'disappearance_rate': 0.14285714285714285, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P527,P1441,P361**: {'n_observations': 15, 'type_flip_rate': 0.06666666666666667, 'disappearance_rate': 0.8666666666666667, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P26**: {'n_observations': 4, 'type_flip_rate': 0.75, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P69,P108**: {'n_observations': 10, 'type_flip_rate': 0.1, 'disappearance_rate': 0.3, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P159,P131**: {'n_observations': 2, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P577,P17**: {'n_observations': 15, 'type_flip_rate': 0.26666666666666666, 'disappearance_rate': 0.4666666666666667, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.06666666666666667, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P50,P570,P108**: {'n_observations': 9, 'type_flip_rate': 0.1111111111111111, 'disappearance_rate': 0.5555555555555556, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1111111111111111, 'percent_wrong_to_correct': 0.0}
- **drop:P1441**: {'n_observations': 15, 'type_flip_rate': 0.0, 'disappearance_rate': 0.9333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P361,P31**: {'n_observations': 7, 'type_flip_rate': 0.14285714285714285, 'disappearance_rate': 0.8571428571428571, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.42857142857142855, 'percent_wrong_to_correct': 0.0}
- **drop:P3373**: {'n_observations': 7, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P31**: {'n_observations': 7, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P495,P57,P577**: {'n_observations': 5, 'type_flip_rate': 0.2, 'disappearance_rate': 0.6, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P108,P131**: {'n_observations': 4, 'type_flip_rate': 0.5, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.5, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P179,P123,P527**: {'n_observations': 8, 'type_flip_rate': 0.0, 'disappearance_rate': 0.625, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P150,P131**: {'n_observations': 6, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **drop:P57**: {'n_observations': 9, 'type_flip_rate': 0.1111111111111111, 'disappearance_rate': 0.1111111111111111, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1111111111111111, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P17,P740**: {'n_observations': 4, 'type_flip_rate': 0.75, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P17,P69**: {'n_observations': 9, 'type_flip_rate': 0.1111111111111111, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P26,P40,P569**: {'n_observations': 6, 'type_flip_rate': 0.16666666666666666, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.3333333333333333, 'percent_wrong_to_correct': 0.0}
- **drop:P123**: {'n_observations': 8, 'type_flip_rate': 0.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P463,P527**: {'n_observations': 5, 'type_flip_rate': 0.0, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **drop:P179**: {'n_observations': 8, 'type_flip_rate': 0.0, 'disappearance_rate': 0.625, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P495,P1412**: {'n_observations': 7, 'type_flip_rate': 0.2857142857142857, 'disappearance_rate': 0.7142857142857143, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2857142857142857, 'percent_wrong_to_correct': 0.0}
- **drop:P740**: {'n_observations': 4, 'type_flip_rate': 0.25, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P463,P131**: {'n_observations': 8, 'type_flip_rate': 0.875, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.125}
- **ambiguous:P108,P569,P570**: {'n_observations': 7, 'type_flip_rate': 0.5714285714285714, 'disappearance_rate': 0.42857142857142855, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2857142857142857, 'percent_wrong_to_correct': 0.0}
- **drop:P1412**: {'n_observations': 7, 'type_flip_rate': 0.0, 'disappearance_rate': 0.2857142857142857, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P161,P57,P569**: {'n_observations': 4, 'type_flip_rate': 0.25, 'disappearance_rate': 0.75, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P27,P361**: {'n_observations': 5, 'type_flip_rate': 0.0, 'disappearance_rate': 1.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P463,P175**: {'n_observations': 8, 'type_flip_rate': 0.125, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P17,P131**: {'n_observations': 10, 'type_flip_rate': 0.0, 'disappearance_rate': 0.3, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P150,P17,P131**: {'n_observations': 8, 'type_flip_rate': 0.25, 'disappearance_rate': 0.75, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.125, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P495,P50,P527**: {'n_observations': 4, 'type_flip_rate': 0.5, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.25, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P175,P17,P27**: {'n_observations': 2, 'type_flip_rate': 1.0, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P463**: {'n_observations': 5, 'type_flip_rate': 0.6, 'disappearance_rate': 0.4, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131,P577**: {'n_observations': 8, 'type_flip_rate': 0.375, 'disappearance_rate': 0.125, 'percent_downgraded_to_other': 0.25, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P54,P17,P108**: {'n_observations': 9, 'type_flip_rate': 0.8888888888888888, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.4444444444444444, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P577,P161,P364**: {'n_observations': 6, 'type_flip_rate': 0.0, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P108,P17**: {'n_observations': 4, 'type_flip_rate': 0.75, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.25, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P495,P50**: {'n_observations': 3, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.3333333333333333, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.6666666666666666, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P131,P150,P361**: {'n_observations': 7, 'type_flip_rate': 0.5714285714285714, 'disappearance_rate': 0.2857142857142857, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P54,P569**: {'n_observations': 4, 'type_flip_rate': 0.5, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P570,P569**: {'n_observations': 6, 'type_flip_rate': 0.6666666666666666, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **drop:P364**: {'n_observations': 6, 'type_flip_rate': 0.0, 'disappearance_rate': 0.16666666666666666, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P19,P40,P569**: {'n_observations': 8, 'type_flip_rate': 0.375, 'disappearance_rate': 0.25, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.375, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P576,P361**: {'n_observations': 11, 'type_flip_rate': 0.9090909090909091, 'disappearance_rate': 0.09090909090909091, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.7272727272727273, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P54,P569,P570**: {'n_observations': 5, 'type_flip_rate': 0.6, 'disappearance_rate': 0.2, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.2, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P108,P19**: {'n_observations': 9, 'type_flip_rate': 0.4444444444444444, 'disappearance_rate': 0.2222222222222222, 'percent_downgraded_to_other': 0.2222222222222222, 'percent_correct_to_wrong': 0.2222222222222222, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P17,P131**: {'n_observations': 2, 'type_flip_rate': 0.5, 'disappearance_rate': 0.5, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.5, 'percent_wrong_to_correct': 0.0}
- **ambiguous:P27,P580,P108**: {'n_observations': 9, 'type_flip_rate': 0.3333333333333333, 'disappearance_rate': 0.5555555555555556, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.1111111111111111, 'percent_wrong_to_correct': 0.0}
- **drop:P576**: {'n_observations': 11, 'type_flip_rate': 0.09090909090909091, 'disappearance_rate': 0.0, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}
- **drop:P580**: {'n_observations': 9, 'type_flip_rate': 0.0, 'disappearance_rate': 0.5555555555555556, 'percent_downgraded_to_other': 0.0, 'percent_correct_to_wrong': 0.0, 'percent_wrong_to_correct': 0.0}

## E4 cost-quality

> `recall@k` = (oracle causes recovered) / (total oracle causes)  ·  `hit` = fraction of selected interventions hitting ≥1 cause.

- planner=exhaustive     budget=1    recall@k=1.000  hit=0.38  reuse=7.10  tok_in=2747936  tok_out=614109
- planner=exhaustive     budget=2    recall@k=1.000  hit=0.38  reuse=7.10  tok_in=2747936  tok_out=614109
- planner=exhaustive     budget=3    recall@k=1.000  hit=0.38  reuse=7.10  tok_in=2747936  tok_out=614109
- planner=exhaustive     budget=4    recall@k=1.000  hit=0.38  reuse=7.10  tok_in=2747936  tok_out=614109
- planner=exhaustive     budget=6    recall@k=1.000  hit=0.38  reuse=7.10  tok_in=2747936  tok_out=614109
- planner=exhaustive     budget=8    recall@k=1.000  hit=0.38  reuse=7.10  tok_in=2747936  tok_out=614109
- planner=random         budget=1    recall@k=0.009  hit=0.31  reuse=7.35  tok_in=58909  tok_out=11105
- planner=random         budget=2    recall@k=0.163  hit=0.42  reuse=7.39  tok_in=140946  tok_out=35907
- planner=random         budget=3    recall@k=0.195  hit=0.41  reuse=7.39  tok_in=207762  tok_out=50423
- planner=random         budget=4    recall@k=0.200  hit=0.37  reuse=7.29  tok_in=246655  tok_out=58723
- planner=random         budget=6    recall@k=0.278  hit=0.44  reuse=7.24  tok_in=444904  tok_out=103246
- planner=random         budget=8    recall@k=0.292  hit=0.40  reuse=7.08  tok_in=534537  tok_out=122620
- planner=span_only      budget=1    recall@k=0.000  hit=0.15  reuse=6.20  tok_in=21331  tok_out=4142
- planner=span_only      budget=2    recall@k=0.000  hit=0.15  reuse=6.20  tok_in=42959  tok_out=8442
- planner=span_only      budget=3    recall@k=0.001  hit=0.15  reuse=6.20  tok_in=64396  tok_out=12340
- planner=span_only      budget=4    recall@k=0.002  hit=0.15  reuse=6.20  tok_in=85889  tok_out=16611
- planner=span_only      budget=6    recall@k=0.003  hit=0.15  reuse=6.20  tok_in=128856  tok_out=25179
- planner=span_only      budget=8    recall@k=0.005  hit=0.15  reuse=6.20  tok_in=170518  tok_out=34194
- planner=prompt_only    budget=1    recall@k=0.097  hit=1.00  reuse=7.63  tok_in=173791  tok_out=37181
- planner=prompt_only    budget=2    recall@k=0.097  hit=0.57  reuse=7.26  tok_in=195860  tok_out=42259
- planner=prompt_only    budget=3    recall@k=0.098  hit=0.43  reuse=7.14  tok_in=217839  tok_out=46915
- planner=prompt_only    budget=4    recall@k=0.101  hit=0.36  reuse=7.08  tok_in=239458  tok_out=51626
- planner=prompt_only    budget=6    recall@k=0.111  hit=0.29  reuse=7.01  tok_in=283161  tok_out=61528
- planner=prompt_only    budget=8    recall@k=0.114  hit=0.26  reuse=6.98  tok_in=326804  tok_out=71801
- planner=schema_only    budget=1    recall@k=0.037  hit=1.00  reuse=7.63  tok_in=206741  tok_out=40181
- planner=schema_only    budget=2    recall@k=0.059  hit=1.00  reuse=7.63  tok_in=364372  tok_out=80519
- planner=schema_only    budget=3    recall@k=0.474  hit=1.00  reuse=7.63  tok_in=511603  tok_out=131910
- planner=schema_only    budget=4    recall@k=0.699  hit=1.00  reuse=7.63  tok_in=686736  tok_out=168966
- planner=schema_only    budget=6    recall@k=0.777  hit=1.00  reuse=7.63  tok_in=1036887  tok_out=239735
- planner=schema_only    budget=8    recall@k=0.826  hit=1.00  reuse=7.63  tok_in=1388665  tok_out=317906
- planner=graphguard  budget=1    recall@k=0.077  hit=1.00  reuse=7.63  tok_in=175067  tok_out=35776
- planner=graphguard  budget=2    recall@k=0.175  hit=1.00  reuse=7.63  tok_in=350017  tok_out=72196
- planner=graphguard  budget=3    recall@k=0.298  hit=1.00  reuse=7.63  tok_in=525193  tok_out=109604
- planner=graphguard  budget=4    recall@k=0.347  hit=1.00  reuse=7.63  tok_in=700239  tok_out=144399
- planner=graphguard  budget=6    recall@k=0.460  hit=1.00  reuse=7.63  tok_in=1054773  tok_out=227421
- planner=graphguard  budget=8    recall@k=0.537  hit=1.00  reuse=7.63  tok_in=1409883  tok_out=309886
- planner=adaptive_graphguard budget=1    recall@k=0.043  hit=0.82  reuse=6.95  tok_in=139122  tok_out=28223
- planner=adaptive_graphguard budget=2    recall@k=0.101  hit=0.82  reuse=6.98  tok_in=277867  tok_out=57769
- planner=adaptive_graphguard budget=3    recall@k=0.146  hit=0.82  reuse=7.01  tok_in=411973  tok_out=86571
- planner=adaptive_graphguard budget=4    recall@k=0.016  hit=0.21  reuse=7.16  tok_in=104248  tok_out=23211
- planner=adaptive_graphguard budget=6    recall@k=0.060  hit=0.21  reuse=7.34  tok_in=165775  tok_out=37762
- planner=adaptive_graphguard budget=8    recall@k=0.107  hit=0.28  reuse=7.01  tok_in=321005  tok_out=67561

**Cost-quality AUC (higher = better):**
- exhaustive: 1.0
- schema_only: 0.5686
- graphguard: 0.3555
- random: 0.2157
- prompt_only: 0.1046
- adaptive_graphguard: 0.0742
- span_only: 0.0022

## Repair (secondary, exploratory)

> F1-improving repair is **not yet supported by current data**; reported for completeness only.

- raw               best F1=0.235 at frac=0.0
- random            best F1=0.235 at frac=0.0
- by_confidence     best F1=0.235 at frac=0.0
- by_risk           best F1=0.239 at frac=0.1
- by_schema_sens    best F1=0.237 at frac=0.1
- by_stability      best F1=0.235 at frac=0.0

## Case studies (one per category when available)

### Case 1 [prompt_induced_wrong]: (Queen of Housewives) -[P108]-> (MBC)
- risk=2.6, stab=0.0, label=wrong
- top existence cause: remove on prompt_clause 'C2_infer_implicit' → edge disappears in 1/1 runs
- top type cause:      switch_schema on schema 'coarse' → relation type flips in 1/1 runs

### Case 2 [schema_forced_flip]: (The Seeker) -[P495]-> (French)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: switch_schema on schema 'coarse' → edge disappears in 1/1 runs

### Case 3 [schema_forced_flip]: (The Seeker) -[P577]-> (2007)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: switch_schema on schema 'ambiguous:P175,P577,P50' → edge disappears in 1/1 runs
- top type cause:      switch_schema on schema 'coarse' → relation type flips in 1/1 runs

### Case 4 [schema_forced_flip]: (Central) -[OTHER]-> (South America)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C2_infer_implicit' → edge disappears in 1/1 runs

### Case 5 [schema_forced_flip]: (Wellywood) -[P131]-> (Miramar)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: switch_schema on schema 'ambiguous:P17,P159,P131' → edge disappears in 1/1 runs

### Case 6 [schema_forced_flip]: (America's Sweetheart) -[P131]-> (France)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C2_infer_implicit' → edge disappears in 1/1 runs
- top type cause:      switch_schema on schema 'coarse' → relation type flips in 1/1 runs

### Case 7 [schema_forced_flip]: (Liffey Viaduct) -[P577]-> (1891)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C2_infer_implicit' → edge disappears in 1/1 runs
- top type cause:      switch_schema on schema 'desc_removed' → relation type flips in 1/1 runs

### Case 8 [schema_forced_flip]: (Gershonites) -[P527]-> (Golan)
- risk=2.6, stab=0.0, label=unmatched
- top existence cause: remove on prompt_clause 'C2_infer_implicit' → edge disappears in 1/1 runs
- top type cause:      switch_schema on schema 'coarse' → relation type flips in 1/1 runs

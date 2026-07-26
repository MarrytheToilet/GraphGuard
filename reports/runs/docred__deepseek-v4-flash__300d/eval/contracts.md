# Drift contract report

**0 satisfied · 10 violated · 1 inconclusive** (of 11 contracts)

| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |
|---|---|---|---|---:|---:|---:|---:|
| K1 | Schema rename/reorder invariance (strict) | invariance | **VIOLATED** | 676 | 0.97 | 0.344 | 0.524 / 0.850 |
| K1b | Schema description-add invariance | invariance | **VIOLATED** | 337 | 0.93 | 0.357 | 0.479 / 0.800 |
| K1c | Schema semantic-shading bounded drift | bounded_drift | **VIOLATED** | 676 | 0.72 | 0.359 | 0.259 / 0.500 |
| K2 | Prompt presentation invariance | invariance | **VIOLATED** | 534 | 0.92 | 0.384 | 0.464 / 0.800 |
| K3 | Evidence/entity-alias reorder invariance | invariance | **VIOLATED** | 78 | 0.64 | 0.590 | 0.439 / 0.720 |
| K4 | Multi-hop join robustness (Q3) | bounded_drift | **VIOLATED** | 2301 | 0.92 | 0.219 | 0.543 / 0.700 |
| K4b | Shortest-path robustness (Q5) | bounded_drift | **VIOLATED** | 872 | 0.82 | 0.259 | 0.600 / 0.700 |
| K4c | Degree-aggregation robustness (Q6) | bounded_drift | **VIOLATED** | 2301 | 0.55 | 0.685 | 0.271 / 0.500 |
| K4d | GraphRAG-retrieval robustness (Q7) | bounded_drift | **VIOLATED** | 2301 | 0.88 | 0.374 | 0.390 / 0.700 |
| K5 | Model swap recall stability | bounded_drift | **INCONCLUSIVE** | 0 | 0.00 | 0.000 | 0.000 / 0.000 |
| K6 | Decoding-resample stability | invariance | **VIOLATED** | 78 | 0.91 | 0.488 | 0.410 / 0.683 |

## Per-contract details

### K1 — Schema rename/reorder invariance (strict)  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'rename'", "'reorder'"]}`
- pairs: n=676, fail=656, violation_rate=0.970
- metric: mean=0.344, median=0.314
- by family:
    - `schema` n=676, viol=0.97, mean_metric=0.344
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.75
    - τ=0.7: 0.91
    - τ=0.8: 0.95
    - τ=0.9: 0.98
- top violation examples:
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000018-Quokka` op=`switch_schema` family=`schema` metric=0.000

### K1b — Schema description-add invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'desc_added'"]}`
- pairs: n=337, fail=315, violation_rate=0.935
- metric: mean=0.357, median=0.333
- by family:
    - `schema` n=337, viol=0.93, mean_metric=0.357
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.74
    - τ=0.7: 0.90
    - τ=0.8: 0.93
    - τ=0.9: 0.98
- top violation examples:
    - doc=`docred-validation-000039-Pointr` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000039-Pointr` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000061-Metropolitan_statistical_area` op=`switch_schema` family=`schema` metric=0.000

### K1c — Schema semantic-shading bounded drift  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'description_substring_in': ["'desc_removed'", "'hierarchical'"]}`
- pairs: n=676, fail=485, violation_rate=0.717
- metric: mean=0.359, median=0.333
- by family:
    - `schema` n=676, viol=0.72, mean_metric=0.359
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.72
    - τ=0.7: 0.89
    - τ=0.8: 0.94
    - τ=0.9: 0.98
- top violation examples:
    - doc=`docred-validation-000024-Beibu_Gulf_Economic_Rim` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000024-Beibu_Gulf_Economic_Rim` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000033-Queen_of_Housewives` op=`switch_schema` family=`schema` metric=0.000

### K2 — Prompt presentation invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['prompt'], 'semantic_class_in': ['presentation']}`
- pairs: n=534, fail=489, violation_rate=0.916
- metric: mean=0.384, median=0.353
- by family:
    - `prompt` n=534, viol=0.92, mean_metric=0.384
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.69
    - τ=0.7: 0.88
    - τ=0.8: 0.92
    - τ=0.9: 0.96
- top violation examples:
    - doc=`docred-validation-000002-IBM_Research___Brazil` op=`role_swap` family=`prompt` metric=0.000
    - doc=`docred-validation-000002-IBM_Research___Brazil` op=`tone` family=`prompt` metric=0.000
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`tone` family=`prompt` metric=0.000

### K3 — Evidence/entity-alias reorder invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['entity_alias', 'evidence'], 'semantic_class_in': ['presentation']}`
- pairs: n=78, fail=50, violation_rate=0.641
- metric: mean=0.590, median=0.529
- by family:
    - `entity_alias` n=39, viol=0.33, mean_metric=0.788
    - `evidence` n=39, viol=0.95, mean_metric=0.393
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.47
    - τ=0.7: 0.64
    - τ=0.8: 0.64
    - τ=0.9: 0.64
- top violation examples:
    - doc=`docred-validation-000013-Palestinian_National_Theatre` op=`para_swap` family=`evidence` metric=0.000
    - doc=`docred-validation-000029-Addy_Lee` op=`para_swap` family=`evidence` metric=0.000
    - doc=`docred-validation-000035-Grand_Wing_Servo-Tech` op=`para_swap` family=`evidence` metric=0.062

### K4 — Multi-hop join robustness (Q3)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=2301, fail=2115, violation_rate=0.919
- metric: mean=0.219, median=0.121
- by family:
    - `entity_alias` n=39, viol=0.33, mean_metric=0.724
    - `evidence` n=39, viol=0.92, mean_metric=0.240
    - `prompt` n=534, viol=0.89, mean_metric=0.242
    - `schema` n=1689, viol=0.94, mean_metric=0.200
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.86
    - τ=0.7: 0.92
    - τ=0.8: 0.94
    - τ=0.9: 0.94
- top violation examples:
    - doc=`docred-validation-000000-Skai_TV` op=`role_swap` family=`prompt` metric=0.000
    - doc=`docred-validation-000000-Skai_TV` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000000-Skai_TV` op=`switch_schema` family=`schema` metric=0.000

### K4b — Shortest-path robustness (Q5)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=872, fail=711, violation_rate=0.815
- metric: mean=0.259, median=0.000
- by family:
    - `entity_alias` n=15, viol=0.40, mean_metric=0.624
    - `evidence` n=15, viol=0.87, mean_metric=0.183
    - `prompt` n=203, viol=0.86, mean_metric=0.219
    - `schema` n=639, viol=0.81, mean_metric=0.265
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.72
    - τ=0.7: 0.82
    - τ=0.8: 0.83
    - τ=0.9: 0.85
- top violation examples:
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`tone` family=`prompt` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000

### K4c — Degree-aggregation robustness (Q6)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=2301, fail=1268, violation_rate=0.551
- metric: mean=0.685, median=0.667
- by family:
    - `entity_alias` n=39, viol=0.18, mean_metric=0.910
    - `evidence` n=39, viol=0.62, mean_metric=0.654
    - `prompt` n=534, viol=0.53, mean_metric=0.696
    - `schema` n=1689, viol=0.57, mean_metric=0.677
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.25
    - τ=0.7: 0.55
    - τ=0.8: 0.55
    - τ=0.9: 0.55
- top violation examples:
    - doc=`docred-validation-000002-IBM_Research___Brazil` op=`tone` family=`prompt` metric=0.000
    - doc=`docred-validation-000006-Ned_McEvoy` op=`tone` family=`prompt` metric=0.000
    - doc=`docred-validation-000018-Quokka` op=`role_swap` family=`prompt` metric=0.000

### K4d — GraphRAG-retrieval robustness (Q7)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=2301, fail=2031, violation_rate=0.883
- metric: mean=0.374, median=0.333
- by family:
    - `entity_alias` n=39, viol=0.33, mean_metric=0.788
    - `evidence` n=39, viol=0.95, mean_metric=0.404
    - `prompt` n=534, viol=0.88, mean_metric=0.392
    - `schema` n=1689, viol=0.89, mean_metric=0.357
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.70
    - τ=0.7: 0.88
    - τ=0.8: 0.92
    - τ=0.9: 0.96
- top violation examples:
    - doc=`docred-validation-000002-IBM_Research___Brazil` op=`role_swap` family=`prompt` metric=0.000
    - doc=`docred-validation-000002-IBM_Research___Brazil` op=`tone` family=`prompt` metric=0.000
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`tone` family=`prompt` metric=0.000

### K5 — Model swap recall stability  · *INCONCLUSIVE*

- kind: `bounded_drift` · direction: `max` · threshold: `0.2` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['model']}`
- pairs: n=0, fail=0, violation_rate=0.000
- metric: mean=0.000, median=0.000
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.00
    - τ=0.7: 0.00
    - τ=0.8: 0.00
    - τ=0.9: 0.00

### K6 — Decoding-resample stability  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['stochastic']}`
- pairs: n=78, fail=71, violation_rate=0.910
- metric: mean=0.488, median=0.471
- by family:
    - `stochastic` n=78, viol=0.91, mean_metric=0.488
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.54
    - τ=0.7: 0.77
    - τ=0.8: 0.86
    - τ=0.9: 0.92
- top violation examples:
    - doc=`docred-validation-000020-Memogate__Pakistan_` op=`repeat` family=`stochastic` metric=0.000
    - doc=`docred-validation-000013-Palestinian_National_Theatre` op=`repeat` family=`stochastic` metric=0.071
    - doc=`docred-validation-000024-Beibu_Gulf_Economic_Rim` op=`repeat` family=`stochastic` metric=0.083

# Drift contract report

**0 satisfied · 7 violated · 1 inconclusive** (of 8 contracts)

| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |
|---|---|---|---|---:|---:|---:|---:|
| K1 | Schema rename/reorder invariance (strict) | invariance | **VIOLATED** | 676 | 0.97 | 0.340 | 0.527 / 0.850 |
| K1b | Schema description-add invariance | invariance | **VIOLATED** | 337 | 0.93 | 0.353 | 0.483 / 0.800 |
| K1c | Schema semantic-shading bounded drift | bounded_drift | **VIOLATED** | 676 | 0.72 | 0.354 | 0.263 / 0.500 |
| K2 | Prompt presentation invariance | invariance | **VIOLATED** | 534 | 0.92 | 0.379 | 0.470 / 0.800 |
| K3 | Evidence/entity-alias reorder invariance | invariance | **VIOLATED** | 78 | 0.64 | 0.586 | 0.446 / 0.800 |
| K4 | Multi-hop join robustness (Q3) | bounded_drift | **VIOLATED** | 2301 | 0.89 | 0.194 | 0.382 / 0.500 |
| K5 | Model swap recall stability | bounded_drift | **INCONCLUSIVE** | 0 | 0.00 | 0.000 | 0.000 / 0.000 |
| K6 | Stochastic repeatability | invariance | **VIOLATED** | 78 | 0.92 | 0.488 | 0.454 / 0.733 |

## Per-contract details

### K1 — Schema rename/reorder invariance (strict)  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'rename'", "'reorder'"]}`
- pairs: n=676, fail=657, violation_rate=0.972
- metric: mean=0.340, median=0.308
- by family:
    - `schema` n=676, viol=0.97, mean_metric=0.340
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.76
    - τ=0.7: 0.91
    - τ=0.8: 0.95
    - τ=0.9: 0.98
- top violation examples:
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000018-Quokka` op=`switch_schema` family=`schema` metric=0.000

### K1b — Schema description-add invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'desc_added'"]}`
- pairs: n=337, fail=315, violation_rate=0.935
- metric: mean=0.353, median=0.333
- by family:
    - `schema` n=337, viol=0.93, mean_metric=0.353
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.75
    - τ=0.7: 0.90
    - τ=0.8: 0.93
    - τ=0.9: 0.98
- top violation examples:
    - doc=`docred-validation-000039-Pointr` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000039-Pointr` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000061-Metropolitan_statistical_area` op=`switch_schema` family=`schema` metric=0.000

### K1c — Schema semantic-shading bounded drift  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'cause_family_in': ['schema'], 'description_substring_in': ["'desc_removed'", "'hierarchical'"]}`
- pairs: n=676, fail=489, violation_rate=0.723
- metric: mean=0.354, median=0.333
- by family:
    - `schema` n=676, viol=0.72, mean_metric=0.354
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

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['prompt'], 'semantic_class_in': ['presentation']}`
- pairs: n=534, fail=489, violation_rate=0.916
- metric: mean=0.379, median=0.333
- by family:
    - `prompt` n=534, viol=0.92, mean_metric=0.379
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.70
    - τ=0.7: 0.88
    - τ=0.8: 0.92
    - τ=0.9: 0.96
- top violation examples:
    - doc=`docred-validation-000002-IBM_Research___Brazil` op=`role_swap` family=`prompt` metric=0.000
    - doc=`docred-validation-000002-IBM_Research___Brazil` op=`tone` family=`prompt` metric=0.000
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`tone` family=`prompt` metric=0.000

### K3 — Evidence/entity-alias reorder invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['entity_alias', 'evidence'], 'semantic_class_in': ['presentation']}`
- pairs: n=78, fail=50, violation_rate=0.641
- metric: mean=0.586, median=0.529
- by family:
    - `entity_alias` n=39, viol=0.33, mean_metric=0.788
    - `evidence` n=39, viol=0.95, mean_metric=0.384
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.47
    - τ=0.7: 0.64
    - τ=0.8: 0.64
    - τ=0.9: 0.64
- top violation examples:
    - doc=`docred-validation-000013-Palestinian_National_Theatre` op=`para_swap` family=`evidence` metric=0.000
    - doc=`docred-validation-000016-Johan_Gottlieb_Gahn` op=`para_swap` family=`evidence` metric=0.000
    - doc=`docred-validation-000029-Addy_Lee` op=`para_swap` family=`evidence` metric=0.000

### K4 — Multi-hop join robustness (Q3)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=2301, fail=2037, violation_rate=0.885
- metric: mean=0.194, median=0.104
- by family:
    - `entity_alias` n=39, viol=0.33, mean_metric=0.718
    - `evidence` n=39, viol=0.92, mean_metric=0.186
    - `prompt` n=534, viol=0.85, mean_metric=0.220
    - `schema` n=1689, viol=0.91, mean_metric=0.174
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.89
    - τ=0.7: 0.93
    - τ=0.8: 0.95
    - τ=0.9: 0.95
- top violation examples:
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`role_swap` family=`prompt` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`role_swap` family=`prompt` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`role_swap` family=`prompt` metric=0.000

### K5 — Model swap recall stability  · *INCONCLUSIVE*

- kind: `bounded_drift` · direction: `min` · threshold: `0.4`
- scope: `{'operator_prefix': 'model:'}`
- pairs: n=0, fail=0, violation_rate=0.000
- metric: mean=0.000, median=0.000
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.00
    - τ=0.7: 0.00
    - τ=0.8: 0.00
    - τ=0.9: 0.00

### K6 — Stochastic repeatability  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.9`
- scope: `{'cause_family_in': ['stochastic']}`
- pairs: n=78, fail=72, violation_rate=0.923
- metric: mean=0.488, median=0.471
- by family:
    - `stochastic` n=78, viol=0.92, mean_metric=0.488
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.54
    - τ=0.7: 0.77
    - τ=0.8: 0.86
    - τ=0.9: 0.92
- top violation examples:
    - doc=`docred-validation-000020-Memogate__Pakistan_` op=`repeat` family=`stochastic` metric=0.000
    - doc=`docred-validation-000013-Palestinian_National_Theatre` op=`repeat` family=`stochastic` metric=0.071
    - doc=`docred-validation-000024-Beibu_Gulf_Economic_Rim` op=`repeat` family=`stochastic` metric=0.083

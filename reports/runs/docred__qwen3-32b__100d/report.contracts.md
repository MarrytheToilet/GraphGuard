# Drift contract report

**0 satisfied · 7 violated · 1 inconclusive** (of 8 contracts)

| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |
|---|---|---|---|---:|---:|---:|---:|
| K1 | Schema rename/reorder invariance (strict) | invariance | **VIOLATED** | 226 | 0.97 | 0.293 | 0.575 / 0.850 |
| K1b | Schema description-add invariance | invariance | **VIOLATED** | 113 | 0.88 | 0.411 | 0.463 / 0.800 |
| K1c | Schema semantic-shading bounded drift | bounded_drift | **VIOLATED** | 226 | 0.76 | 0.337 | 0.292 / 0.500 |
| K2 | Prompt presentation invariance | invariance | **VIOLATED** | 84 | 0.67 | 0.580 | 0.396 / 0.800 |
| K3 | Evidence/entity-alias reorder invariance | invariance | **VIOLATED** | 28 | 0.64 | 0.558 | 0.478 / 0.800 |
| K4 | Multi-hop join robustness (Q3) | bounded_drift | **VIOLATED** | 677 | 0.84 | 0.229 | 0.396 / 0.500 |
| K5 | Model swap recall stability | bounded_drift | **INCONCLUSIVE** | 0 | 0.00 | 0.000 | 0.000 / 0.000 |
| K6 | Stochastic repeatability | invariance | **VIOLATED** | 28 | 0.79 | 0.607 | 0.400 / 0.775 |

## Per-contract details

### K1 — Schema rename/reorder invariance (strict)  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'rename'", "'reorder'"]}`
- pairs: n=226, fail=220, violation_rate=0.973
- metric: mean=0.293, median=0.250
- by family:
    - `schema` n=226, viol=0.97, mean_metric=0.293
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.79
    - τ=0.7: 0.96
    - τ=0.8: 0.97
    - τ=0.9: 0.98
- top violation examples:
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`switch_schema` family=`schema` metric=0.000

### K1b — Schema description-add invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'desc_added'"]}`
- pairs: n=113, fail=99, violation_rate=0.876
- metric: mean=0.411, median=0.364
- by family:
    - `schema` n=113, viol=0.88, mean_metric=0.411
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.62
    - τ=0.7: 0.83
    - τ=0.8: 0.88
    - τ=0.9: 0.92
- top violation examples:
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000011-Delaware_General_Assembly` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000012-Allen_County__Ohio` op=`switch_schema` family=`schema` metric=0.000

### K1c — Schema semantic-shading bounded drift  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'cause_family_in': ['schema'], 'description_substring_in': ["'desc_removed'", "'hierarchical'"]}`
- pairs: n=226, fail=171, violation_rate=0.757
- metric: mean=0.337, median=0.270
- by family:
    - `schema` n=226, viol=0.76, mean_metric=0.337
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.76
    - τ=0.7: 0.88
    - τ=0.8: 0.91
    - τ=0.9: 0.94
- top violation examples:
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`switch_schema` family=`schema` metric=0.000

### K2 — Prompt presentation invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['prompt'], 'semantic_class_in': ['presentation']}`
- pairs: n=84, fail=56, violation_rate=0.667
- metric: mean=0.580, median=0.571
- by family:
    - `prompt` n=84, viol=0.67, mean_metric=0.580
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.38
    - τ=0.7: 0.58
    - τ=0.8: 0.67
    - τ=0.9: 0.82
- top violation examples:
    - doc=`docred-validation-000011-Delaware_General_Assembly` op=`role_swap` family=`prompt` metric=0.000
    - doc=`docred-validation-000011-Delaware_General_Assembly` op=`role_swap` family=`prompt` metric=0.000
    - doc=`docred-validation-000011-Delaware_General_Assembly` op=`tone` family=`prompt` metric=0.000

### K3 — Evidence/entity-alias reorder invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['entity_alias', 'evidence'], 'semantic_class_in': ['presentation']}`
- pairs: n=28, fail=18, violation_rate=0.643
- metric: mean=0.558, median=0.500
- by family:
    - `entity_alias` n=14, viol=0.36, mean_metric=0.748
    - `evidence` n=14, viol=0.93, mean_metric=0.368
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.46
    - τ=0.7: 0.61
    - τ=0.8: 0.64
    - τ=0.9: 0.68
- top violation examples:
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`entity_alias` family=`entity_alias` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`para_swap` family=`evidence` metric=0.000
    - doc=`docred-validation-000003-Lookin_Ass` op=`para_swap` family=`evidence` metric=0.000

### K4 — Multi-hop join robustness (Q3)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=677, fail=567, violation_rate=0.838
- metric: mean=0.229, median=0.094
- by family:
    - `entity_alias` n=14, viol=0.36, mean_metric=0.690
    - `evidence` n=14, viol=0.93, mean_metric=0.195
    - `prompt` n=84, viol=0.63, mean_metric=0.425
    - `schema` n=565, viol=0.88, mean_metric=0.190
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.84
    - τ=0.7: 0.88
    - τ=0.8: 0.89
    - τ=0.9: 0.89
- top violation examples:
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000

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
- pairs: n=28, fail=22, violation_rate=0.786
- metric: mean=0.607, median=0.667
- by family:
    - `stochastic` n=28, viol=0.79, mean_metric=0.607
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.39
    - τ=0.7: 0.54
    - τ=0.8: 0.68
    - τ=0.9: 0.79
- top violation examples:
    - doc=`docred-validation-000011-Delaware_General_Assembly` op=`repeat` family=`stochastic` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`repeat` family=`stochastic` metric=0.118
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`repeat` family=`stochastic` metric=0.125

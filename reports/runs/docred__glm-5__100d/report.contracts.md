# Drift contract report

**0 satisfied · 7 violated · 1 inconclusive** (of 8 contracts)

| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |
|---|---|---|---|---:|---:|---:|---:|
| K1 | Schema rename/reorder invariance (strict) | invariance | **VIOLATED** | 28 | 0.75 | 0.627 | 0.348 / 0.750 |
| K1b | Schema description-add invariance | invariance | **VIOLATED** | 18 | 0.61 | 0.686 | 0.283 / 0.514 |
| K1c | Schema semantic-shading bounded drift | bounded_drift | **VIOLATED** | 32 | 0.28 | 0.594 | 0.240 / 0.423 |
| K2 | Prompt presentation invariance | invariance | **VIOLATED** | 58 | 0.71 | 0.672 | 0.233 / 0.500 |
| K3 | Evidence/entity-alias reorder invariance | invariance | **VIOLATED** | 19 | 0.42 | 0.746 | 0.404 / 0.729 |
| K4 | Multi-hop join robustness (Q3) | bounded_drift | **VIOLATED** | 155 | 0.53 | 0.503 | 0.303 / 0.500 |
| K5 | Model swap recall stability | bounded_drift | **INCONCLUSIVE** | 0 | 0.00 | 0.000 | 0.000 / 0.000 |
| K6 | Stochastic repeatability | invariance | **VIOLATED** | 18 | 0.83 | 0.594 | 0.387 / 0.820 |

## Per-contract details

### K1 — Schema rename/reorder invariance (strict)  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'rename'", "'reorder'"]}`
- pairs: n=28, fail=21, violation_rate=0.750
- metric: mean=0.627, median=0.677
- by family:
    - `schema` n=28, viol=0.75, mean_metric=0.627
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.32
    - τ=0.7: 0.54
    - τ=0.8: 0.68
    - τ=0.9: 0.75
- top violation examples:
    - doc=`docred-validation-000006-Ned_McEvoy` op=`switch_schema` family=`schema` metric=0.100
    - doc=`docred-validation-000006-Ned_McEvoy` op=`switch_schema` family=`schema` metric=0.100
    - doc=`docred-validation-000003-Lookin_Ass` op=`switch_schema` family=`schema` metric=0.200

### K1b — Schema description-add invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'desc_added'"]}`
- pairs: n=18, fail=11, violation_rate=0.611
- metric: mean=0.686, median=0.686
- by family:
    - `schema` n=18, viol=0.61, mean_metric=0.686
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.22
    - τ=0.7: 0.50
    - τ=0.8: 0.61
    - τ=0.9: 0.72
- top violation examples:
    - doc=`docred-validation-000006-Ned_McEvoy` op=`switch_schema` family=`schema` metric=0.100
    - doc=`docred-validation-000003-Lookin_Ass` op=`switch_schema` family=`schema` metric=0.286
    - doc=`docred-validation-000003-Lookin_Ass` op=`switch_schema` family=`schema` metric=0.400

### K1c — Schema semantic-shading bounded drift  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'cause_family_in': ['schema'], 'description_substring_in': ["'desc_removed'", "'hierarchical'"]}`
- pairs: n=32, fail=9, violation_rate=0.281
- metric: mean=0.594, median=0.600
- by family:
    - `schema` n=32, viol=0.28, mean_metric=0.594
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.28
    - τ=0.7: 0.69
    - τ=0.8: 0.72
    - τ=0.9: 0.88
- top violation examples:
    - doc=`docred-validation-000006-Ned_McEvoy` op=`switch_schema` family=`schema` metric=0.071
    - doc=`docred-validation-000006-Ned_McEvoy` op=`switch_schema` family=`schema` metric=0.077
    - doc=`docred-validation-000003-Lookin_Ass` op=`switch_schema` family=`schema` metric=0.200

### K2 — Prompt presentation invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['prompt'], 'semantic_class_in': ['presentation']}`
- pairs: n=58, fail=41, violation_rate=0.707
- metric: mean=0.672, median=0.667
- by family:
    - `prompt` n=58, viol=0.71, mean_metric=0.672
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.14
    - τ=0.7: 0.59
    - τ=0.8: 0.71
    - τ=0.9: 0.84
- top violation examples:
    - doc=`docred-validation-000006-Ned_McEvoy` op=`tone` family=`prompt` metric=0.083
    - doc=`docred-validation-000003-Lookin_Ass` op=`tone` family=`prompt` metric=0.125
    - doc=`docred-validation-000003-Lookin_Ass` op=`role_swap` family=`prompt` metric=0.300

### K3 — Evidence/entity-alias reorder invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['entity_alias', 'evidence'], 'semantic_class_in': ['presentation']}`
- pairs: n=19, fail=8, violation_rate=0.421
- metric: mean=0.746, median=1.000
- by family:
    - `entity_alias` n=12, viol=0.25, mean_metric=0.841
    - `evidence` n=7, viol=0.71, mean_metric=0.582
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.26
    - τ=0.7: 0.37
    - τ=0.8: 0.42
    - τ=0.9: 0.42
- top violation examples:
    - doc=`docred-validation-000003-Lookin_Ass` op=`entity_alias` family=`entity_alias` metric=0.000
    - doc=`docred-validation-000006-Ned_McEvoy` op=`para_swap` family=`evidence` metric=0.071
    - doc=`docred-validation-000003-Lookin_Ass` op=`para_swap` family=`evidence` metric=0.200

### K4 — Multi-hop join robustness (Q3)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=155, fail=82, violation_rate=0.529
- metric: mean=0.503, median=0.421
- by family:
    - `entity_alias` n=12, viol=0.25, mean_metric=0.808
    - `evidence` n=7, viol=0.71, mean_metric=0.410
    - `prompt` n=58, viol=0.47, mean_metric=0.521
    - `schema` n=78, viol=0.60, mean_metric=0.452
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.53
    - τ=0.7: 0.63
    - τ=0.8: 0.68
    - τ=0.9: 0.76
- top violation examples:
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000003-Lookin_Ass` op=`role_swap` family=`prompt` metric=0.000

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
- pairs: n=18, fail=15, violation_rate=0.833
- metric: mean=0.594, median=0.636
- by family:
    - `stochastic` n=18, viol=0.83, mean_metric=0.594
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.33
    - τ=0.7: 0.61
    - τ=0.8: 0.72
    - τ=0.9: 0.83
- top violation examples:
    - doc=`docred-validation-000010-More__The_Sisters_of_Mercy_song_` op=`repeat` family=`stochastic` metric=0.048
    - doc=`docred-validation-000010-More__The_Sisters_of_Mercy_song_` op=`repeat` family=`stochastic` metric=0.080
    - doc=`docred-validation-000012-Allen_County__Ohio` op=`repeat` family=`stochastic` metric=0.250

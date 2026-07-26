# Drift contract report

**0 satisfied · 10 violated · 1 inconclusive** (of 11 contracts)

| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |
|---|---|---|---|---:|---:|---:|---:|
| K1 | Schema rename/reorder invariance (strict) | invariance | **VIOLATED** | 28 | 0.75 | 0.627 | 0.348 / 0.750 |
| K1b | Schema description-add invariance | invariance | **VIOLATED** | 18 | 0.61 | 0.686 | 0.283 / 0.514 |
| K1c | Schema semantic-shading bounded drift | bounded_drift | **VIOLATED** | 32 | 0.28 | 0.594 | 0.240 / 0.423 |
| K2 | Prompt presentation invariance | invariance | **VIOLATED** | 58 | 0.71 | 0.672 | 0.233 / 0.500 |
| K3 | Evidence/entity-alias reorder invariance | invariance | **VIOLATED** | 19 | 0.42 | 0.746 | 0.404 / 0.729 |
| K4 | Diagnostic fan-out join robustness (D3) | bounded_drift | **VIOLATED** | 155 | 0.56 | 0.585 | 0.413 / 0.700 |
| K4b | Shortest-path robustness (Q5) | bounded_drift | **VIOLATED** | 126 | 0.37 | 0.663 | 0.586 / 0.700 |
| K4c | Degree-aggregation robustness (Q6) | bounded_drift | **VIOLATED** | 155 | 0.51 | 0.721 | 0.247 / 0.500 |
| K4d | GraphRAG-retrieval robustness (Q7) | bounded_drift | **VIOLATED** | 155 | 0.52 | 0.671 | 0.233 / 0.700 |
| K5 | Model swap recall stability | bounded_drift | **INCONCLUSIVE** | 0 | 0.00 | 0.000 | 0.000 / 0.000 |
| K6 | Decoding-resample stability | invariance | **VIOLATED** | 18 | 0.83 | 0.594 | 0.337 / 0.770 |

## Per-contract details

### K1 — Schema rename/reorder invariance (strict)  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85` · alpha: `0.2` · min_pairs: `1`
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

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
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

- kind: `bounded_drift` · direction: `min` · threshold: `0.5` · alpha: `0.2` · min_pairs: `1`
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

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
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

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
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

### K4 — Diagnostic fan-out join robustness (D3)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=155, fail=87, violation_rate=0.561
- metric: mean=0.585, median=0.600
- by family:
    - `entity_alias` n=12, viol=0.25, mean_metric=0.812
    - `evidence` n=7, viol=0.57, mean_metric=0.582
    - `prompt` n=58, viol=0.55, mean_metric=0.611
    - `schema` n=78, viol=0.62, mean_metric=0.530
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.41
    - τ=0.7: 0.56
    - τ=0.8: 0.60
    - τ=0.9: 0.63
- top violation examples:
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000003-Lookin_Ass` op=`role_swap` family=`prompt` metric=0.000

### K4b — Shortest-path robustness (Q5)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=126, fail=46, violation_rate=0.365
- metric: mean=0.663, median=1.000
- by family:
    - `entity_alias` n=10, viol=0.20, mean_metric=0.800
    - `evidence` n=6, viol=0.50, mean_metric=0.500
    - `prompt` n=47, viol=0.32, mean_metric=0.704
    - `schema` n=63, viol=0.41, mean_metric=0.627
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.33
    - τ=0.7: 0.37
    - τ=0.8: 0.37
    - τ=0.9: 0.44
- top violation examples:
    - doc=`docred-validation-000003-Lookin_Ass` op=`tone` family=`prompt` metric=0.000
    - doc=`docred-validation-000003-Lookin_Ass` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000003-Lookin_Ass` op=`switch_schema` family=`schema` metric=0.000

### K4c — Degree-aggregation robustness (Q6)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=155, fail=79, violation_rate=0.510
- metric: mean=0.721, median=0.667
- by family:
    - `entity_alias` n=12, viol=0.17, mean_metric=0.871
    - `evidence` n=7, viol=0.71, mean_metric=0.576
    - `prompt` n=58, viol=0.55, mean_metric=0.678
    - `schema` n=78, viol=0.51, mean_metric=0.743
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.22
    - τ=0.7: 0.51
    - τ=0.8: 0.51
    - τ=0.9: 0.51
- top violation examples:
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`tone` family=`prompt` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`role_swap` family=`prompt` metric=0.200
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`role_swap` family=`prompt` metric=0.200

### K4d — GraphRAG-retrieval robustness (Q7)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=155, fail=81, violation_rate=0.523
- metric: mean=0.671, median=0.667
- by family:
    - `entity_alias` n=12, viol=0.25, mean_metric=0.844
    - `evidence` n=7, viol=0.57, mean_metric=0.579
    - `prompt` n=58, viol=0.52, mean_metric=0.702
    - `schema` n=78, viol=0.56, mean_metric=0.631
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.21
    - τ=0.7: 0.52
    - τ=0.8: 0.61
    - τ=0.9: 0.77
- top violation examples:
    - doc=`docred-validation-000003-Lookin_Ass` op=`entity_alias` family=`entity_alias` metric=0.000
    - doc=`docred-validation-000006-Ned_McEvoy` op=`tone` family=`prompt` metric=0.000
    - doc=`docred-validation-000006-Ned_McEvoy` op=`switch_schema` family=`schema` metric=0.000

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

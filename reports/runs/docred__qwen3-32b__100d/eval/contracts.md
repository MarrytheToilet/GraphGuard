# Drift contract report

**0 satisfied · 10 violated · 1 inconclusive** (of 11 contracts)

| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |
|---|---|---|---|---:|---:|---:|---:|
| K1 | Schema rename/reorder invariance (strict) | invariance | **VIOLATED** | 226 | 0.97 | 0.302 | 0.565 / 0.850 |
| K1b | Schema description-add invariance | invariance | **VIOLATED** | 113 | 0.88 | 0.417 | 0.456 / 0.800 |
| K1c | Schema semantic-shading bounded drift | bounded_drift | **VIOLATED** | 226 | 0.73 | 0.354 | 0.288 / 0.500 |
| K2 | Prompt presentation invariance | invariance | **VIOLATED** | 84 | 0.67 | 0.581 | 0.394 / 0.800 |
| K3 | Evidence/entity-alias reorder invariance | invariance | **VIOLATED** | 28 | 0.64 | 0.572 | 0.456 / 0.800 |
| K4 | Diagnostic fan-out join robustness (D3) | bounded_drift | **VIOLATED** | 677 | 0.86 | 0.260 | 0.552 / 0.700 |
| K4b | Shortest-path robustness (Q5) | bounded_drift | **VIOLATED** | 243 | 0.65 | 0.414 | 0.596 / 0.700 |
| K4c | Degree-aggregation robustness (Q6) | bounded_drift | **VIOLATED** | 677 | 0.39 | 0.793 | 0.232 / 0.500 |
| K4d | GraphRAG-retrieval robustness (Q7) | bounded_drift | **VIOLATED** | 677 | 0.83 | 0.394 | 0.410 / 0.700 |
| K5 | Model swap recall stability | bounded_drift | **INCONCLUSIVE** | 0 | 0.00 | 0.000 | 0.000 / 0.000 |
| K6 | Decoding-resample stability | invariance | **VIOLATED** | 28 | 0.75 | 0.625 | 0.344 / 0.628 |

## Per-contract details

### K1 — Schema rename/reorder invariance (strict)  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'rename'", "'reorder'"]}`
- pairs: n=226, fail=220, violation_rate=0.973
- metric: mean=0.302, median=0.267
- by family:
    - `schema` n=226, viol=0.97, mean_metric=0.302
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.78
    - τ=0.7: 0.96
    - τ=0.8: 0.97
    - τ=0.9: 0.98
- top violation examples:
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000011-Delaware_General_Assembly` op=`switch_schema` family=`schema` metric=0.000

### K1b — Schema description-add invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'desc_added'"]}`
- pairs: n=113, fail=99, violation_rate=0.876
- metric: mean=0.417, median=0.375
- by family:
    - `schema` n=113, viol=0.88, mean_metric=0.417
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.61
    - τ=0.7: 0.83
    - τ=0.8: 0.88
    - τ=0.9: 0.92
- top violation examples:
    - doc=`docred-validation-000011-Delaware_General_Assembly` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000012-Allen_County__Ohio` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000012-Allen_County__Ohio` op=`switch_schema` family=`schema` metric=0.000

### K1c — Schema semantic-shading bounded drift  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'description_substring_in': ["'desc_removed'", "'hierarchical'"]}`
- pairs: n=226, fail=165, violation_rate=0.730
- metric: mean=0.354, median=0.286
- by family:
    - `schema` n=226, viol=0.73, mean_metric=0.354
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.73
    - τ=0.7: 0.87
    - τ=0.8: 0.90
    - τ=0.9: 0.93
- top violation examples:
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000006-Ned_McEvoy` op=`switch_schema` family=`schema` metric=0.000

### K2 — Prompt presentation invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['prompt'], 'semantic_class_in': ['presentation']}`
- pairs: n=84, fail=56, violation_rate=0.667
- metric: mean=0.581, median=0.571
- by family:
    - `prompt` n=84, viol=0.67, mean_metric=0.581
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.37
    - τ=0.7: 0.58
    - τ=0.8: 0.67
    - τ=0.9: 0.82
- top violation examples:
    - doc=`docred-validation-000011-Delaware_General_Assembly` op=`role_swap` family=`prompt` metric=0.000
    - doc=`docred-validation-000011-Delaware_General_Assembly` op=`role_swap` family=`prompt` metric=0.000
    - doc=`docred-validation-000011-Delaware_General_Assembly` op=`tone` family=`prompt` metric=0.000

### K3 — Evidence/entity-alias reorder invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['entity_alias', 'evidence'], 'semantic_class_in': ['presentation']}`
- pairs: n=28, fail=18, violation_rate=0.643
- metric: mean=0.572, median=0.550
- by family:
    - `entity_alias` n=14, viol=0.36, mean_metric=0.760
    - `evidence` n=14, viol=0.93, mean_metric=0.384
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.39
    - τ=0.7: 0.61
    - τ=0.8: 0.64
    - τ=0.9: 0.68
- top violation examples:
    - doc=`docred-validation-000003-Lookin_Ass` op=`para_swap` family=`evidence` metric=0.000
    - doc=`docred-validation-000013-Palestinian_National_Theatre` op=`para_swap` family=`evidence` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`entity_alias` family=`entity_alias` metric=0.062

### K4 — Diagnostic fan-out join robustness (D3)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=677, fail=584, violation_rate=0.863
- metric: mean=0.260, median=0.125
- by family:
    - `entity_alias` n=14, viol=0.36, mean_metric=0.698
    - `evidence` n=14, viol=0.93, mean_metric=0.269
    - `prompt` n=84, viol=0.70, mean_metric=0.458
    - `schema` n=565, viol=0.90, mean_metric=0.219
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.81
    - τ=0.7: 0.86
    - τ=0.8: 0.88
    - τ=0.9: 0.88
- top violation examples:
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000

### K4b — Shortest-path robustness (Q5)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=243, fail=157, violation_rate=0.646
- metric: mean=0.414, median=0.167
- by family:
    - `entity_alias` n=6, viol=0.17, mean_metric=0.833
    - `evidence` n=6, viol=0.83, mean_metric=0.167
    - `prompt` n=36, viol=0.42, mean_metric=0.660
    - `schema` n=195, viol=0.70, mean_metric=0.363
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.56
    - τ=0.7: 0.65
    - τ=0.8: 0.67
    - τ=0.9: 0.68
- top violation examples:
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`switch_schema` family=`schema` metric=0.000

### K4c — Degree-aggregation robustness (Q6)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=677, fail=263, violation_rate=0.388
- metric: mean=0.793, median=1.000
- by family:
    - `entity_alias` n=14, viol=0.14, mean_metric=0.940
    - `evidence` n=14, viol=0.50, mean_metric=0.717
    - `prompt` n=84, viol=0.26, mean_metric=0.869
    - `schema` n=565, viol=0.41, mean_metric=0.780
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.12
    - τ=0.7: 0.39
    - τ=0.8: 0.39
    - τ=0.9: 0.39
- top violation examples:
    - doc=`docred-validation-000061-Metropolitan_statistical_area` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000061-Metropolitan_statistical_area` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`tone` family=`prompt` metric=0.200

### K4d — GraphRAG-retrieval robustness (Q7)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=677, fail=560, violation_rate=0.827
- metric: mean=0.394, median=0.333
- by family:
    - `entity_alias` n=14, viol=0.36, mean_metric=0.761
    - `evidence` n=14, viol=0.86, mean_metric=0.390
    - `prompt` n=84, viol=0.56, mean_metric=0.592
    - `schema` n=565, viol=0.88, mean_metric=0.355
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.66
    - τ=0.7: 0.83
    - τ=0.8: 0.87
    - τ=0.9: 0.92
- top violation examples:
    - doc=`docred-validation-000003-Lookin_Ass` op=`para_swap` family=`evidence` metric=0.000
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`switch_schema` family=`schema` metric=0.000

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
- pairs: n=28, fail=21, violation_rate=0.750
- metric: mean=0.625, median=0.667
- by family:
    - `stochastic` n=28, viol=0.75, mean_metric=0.625
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.39
    - τ=0.7: 0.54
    - τ=0.8: 0.68
    - τ=0.9: 0.79
- top violation examples:
    - doc=`docred-validation-000011-Delaware_General_Assembly` op=`repeat` family=`stochastic` metric=0.000
    - doc=`docred-validation-000011-Delaware_General_Assembly` op=`repeat` family=`stochastic` metric=0.222
    - doc=`docred-validation-000010-More__The_Sisters_of_Mercy_song_` op=`repeat` family=`stochastic` metric=0.235

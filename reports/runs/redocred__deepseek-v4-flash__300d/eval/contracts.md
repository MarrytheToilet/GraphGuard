# Drift contract report

**0 satisfied · 10 violated · 1 inconclusive** (of 11 contracts)

| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |
|---|---|---|---|---:|---:|---:|---:|
| K1 | Schema rename/reorder invariance (strict) | invariance | **VIOLATED** | 680 | 0.99 | 0.322 | 0.536 / 0.850 |
| K1b | Schema description-add invariance | invariance | **VIOLATED** | 340 | 0.98 | 0.337 | 0.473 / 0.800 |
| K1c | Schema semantic-shading bounded drift | bounded_drift | **VIOLATED** | 680 | 0.78 | 0.319 | 0.273 / 0.500 |
| K2 | Prompt presentation invariance | invariance | **VIOLATED** | 540 | 0.95 | 0.361 | 0.465 / 0.800 |
| K3 | Evidence/entity-alias reorder invariance | invariance | **VIOLATED** | 80 | 0.61 | 0.572 | 0.490 / 0.800 |
| K4 | Diagnostic fan-out join robustness (D3) | bounded_drift | **VIOLATED** | 2320 | 0.93 | 0.216 | 0.540 / 0.700 |
| K4b | Shortest-path robustness (Q5) | bounded_drift | **VIOLATED** | 1025 | 0.82 | 0.256 | 0.604 / 0.700 |
| K4c | Degree-aggregation robustness (Q6) | bounded_drift | **VIOLATED** | 2320 | 0.60 | 0.646 | 0.289 / 0.700 |
| K4d | GraphRAG-retrieval robustness (Q7) | bounded_drift | **VIOLATED** | 2320 | 0.91 | 0.347 | 0.401 / 0.700 |
| K5 | Model swap recall stability | bounded_drift | **INCONCLUSIVE** | 0 | 0.00 | 0.000 | 0.000 / 0.000 |
| K6 | Decoding-resample stability | invariance | **VIOLATED** | 80 | 0.95 | 0.463 | 0.411 / 0.739 |

## Per-contract details

### K1 — Schema rename/reorder invariance (strict)  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'rename'", "'reorder'"]}`
- pairs: n=680, fail=671, violation_rate=0.987
- metric: mean=0.322, median=0.300
- by family:
    - `schema` n=680, viol=0.99, mean_metric=0.322
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.78
    - τ=0.7: 0.95
    - τ=0.8: 0.98
    - τ=0.9: 0.99
- top violation examples:
    - doc=`redocred-validation-000006-Soccer_Academy` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000006-Soccer_Academy` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000021-South_Gondar_Zone` op=`switch_schema` family=`schema` metric=0.000

### K1b — Schema description-add invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'desc_added'"]}`
- pairs: n=340, fail=334, violation_rate=0.982
- metric: mean=0.337, median=0.313
- by family:
    - `schema` n=340, viol=0.98, mean_metric=0.337
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.74
    - τ=0.7: 0.95
    - τ=0.8: 0.98
    - τ=0.9: 0.99
- top violation examples:
    - doc=`redocred-validation-000006-Soccer_Academy` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000035-Won-yong` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000036-Ramada__shelter_` op=`switch_schema` family=`schema` metric=0.000

### K1c — Schema semantic-shading bounded drift  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'description_substring_in': ["'desc_removed'", "'hierarchical'"]}`
- pairs: n=680, fail=531, violation_rate=0.781
- metric: mean=0.319, median=0.278
- by family:
    - `schema` n=680, viol=0.78, mean_metric=0.319
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.78
    - τ=0.7: 0.94
    - τ=0.8: 0.96
    - τ=0.9: 0.98
- top violation examples:
    - doc=`redocred-validation-000006-Soccer_Academy` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000006-Soccer_Academy` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000019-Railroad_Revival_Tour` op=`switch_schema` family=`schema` metric=0.000

### K2 — Prompt presentation invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['prompt'], 'semantic_class_in': ['presentation']}`
- pairs: n=540, fail=515, violation_rate=0.954
- metric: mean=0.361, median=0.333
- by family:
    - `prompt` n=540, viol=0.95, mean_metric=0.361
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.71
    - τ=0.7: 0.90
    - τ=0.8: 0.95
    - τ=0.9: 0.98
- top violation examples:
    - doc=`redocred-validation-000006-Soccer_Academy` op=`tone` family=`prompt` metric=0.000
    - doc=`redocred-validation-000019-Railroad_Revival_Tour` op=`tone` family=`prompt` metric=0.000
    - doc=`redocred-validation-000019-Railroad_Revival_Tour` op=`tone` family=`prompt` metric=0.000

### K3 — Evidence/entity-alias reorder invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['entity_alias', 'evidence'], 'semantic_class_in': ['presentation']}`
- pairs: n=80, fail=49, violation_rate=0.613
- metric: mean=0.572, median=0.500
- by family:
    - `entity_alias` n=40, viol=0.28, mean_metric=0.822
    - `evidence` n=40, viol=0.95, mean_metric=0.323
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.47
    - τ=0.7: 0.60
    - τ=0.8: 0.61
    - τ=0.9: 0.64
- top violation examples:
    - doc=`redocred-validation-000006-Soccer_Academy` op=`para_swap` family=`evidence` metric=0.000
    - doc=`redocred-validation-000016-Henrik_Angell` op=`para_swap` family=`evidence` metric=0.000
    - doc=`redocred-validation-000021-South_Gondar_Zone` op=`para_swap` family=`evidence` metric=0.000

### K4 — Diagnostic fan-out join robustness (D3)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=2320, fail=2157, violation_rate=0.930
- metric: mean=0.216, median=0.125
- by family:
    - `entity_alias` n=40, viol=0.28, mean_metric=0.785
    - `evidence` n=40, viol=0.95, mean_metric=0.182
    - `prompt` n=540, viol=0.93, mean_metric=0.230
    - `schema` n=1700, viol=0.94, mean_metric=0.198
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.88
    - τ=0.7: 0.93
    - τ=0.8: 0.94
    - τ=0.9: 0.94
- top violation examples:
    - doc=`redocred-validation-000002-Mess_of_Blues__Jeff_Healey_album_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000002-Mess_of_Blues__Jeff_Healey_album_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000002-Mess_of_Blues__Jeff_Healey_album_` op=`switch_schema` family=`schema` metric=0.000

### K4b — Shortest-path robustness (Q5)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=1025, fail=839, violation_rate=0.819
- metric: mean=0.256, median=0.000
- by family:
    - `entity_alias` n=16, viol=0.31, mean_metric=0.698
    - `evidence` n=16, viol=0.94, mean_metric=0.168
    - `prompt` n=232, viol=0.84, mean_metric=0.237
    - `schema` n=761, viol=0.82, mean_metric=0.254
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.72
    - τ=0.7: 0.82
    - τ=0.8: 0.82
    - τ=0.9: 0.84
- top violation examples:
    - doc=`redocred-validation-000001-Ross_Alger` op=`role_swap` family=`prompt` metric=0.000
    - doc=`redocred-validation-000001-Ross_Alger` op=`role_swap` family=`prompt` metric=0.000
    - doc=`redocred-validation-000001-Ross_Alger` op=`role_swap` family=`prompt` metric=0.000

### K4c — Degree-aggregation robustness (Q6)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=2320, fail=1395, violation_rate=0.601
- metric: mean=0.646, median=0.500
- by family:
    - `entity_alias` n=40, viol=0.20, mean_metric=0.890
    - `evidence` n=40, viol=0.65, mean_metric=0.591
    - `prompt` n=540, viol=0.59, mean_metric=0.654
    - `schema` n=1700, viol=0.61, mean_metric=0.638
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.29
    - τ=0.7: 0.60
    - τ=0.8: 0.60
    - τ=0.9: 0.60
- top violation examples:
    - doc=`redocred-validation-000019-Railroad_Revival_Tour` op=`tone` family=`prompt` metric=0.000
    - doc=`redocred-validation-000019-Railroad_Revival_Tour` op=`tone` family=`prompt` metric=0.000
    - doc=`redocred-validation-000019-Railroad_Revival_Tour` op=`switch_schema` family=`schema` metric=0.000

### K4d — GraphRAG-retrieval robustness (Q7)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=2320, fail=2118, violation_rate=0.913
- metric: mean=0.347, median=0.308
- by family:
    - `entity_alias` n=40, viol=0.28, mean_metric=0.814
    - `evidence` n=40, viol=0.88, mean_metric=0.355
    - `prompt` n=540, viol=0.90, mean_metric=0.370
    - `schema` n=1700, viol=0.93, mean_metric=0.329
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.74
    - τ=0.7: 0.91
    - τ=0.8: 0.95
    - τ=0.9: 0.97
- top violation examples:
    - doc=`redocred-validation-000006-Soccer_Academy` op=`para_swap` family=`evidence` metric=0.000
    - doc=`redocred-validation-000006-Soccer_Academy` op=`tone` family=`prompt` metric=0.000
    - doc=`redocred-validation-000006-Soccer_Academy` op=`switch_schema` family=`schema` metric=0.000

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
- pairs: n=80, fail=76, violation_rate=0.950
- metric: mean=0.463, median=0.458
- by family:
    - `stochastic` n=80, viol=0.95, mean_metric=0.463
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.55
    - τ=0.7: 0.80
    - τ=0.8: 0.93
    - τ=0.9: 0.96
- top violation examples:
    - doc=`redocred-validation-000030-Joseph_in_Islam` op=`repeat` family=`stochastic` metric=0.057
    - doc=`redocred-validation-000027-Nexus_Q` op=`repeat` family=`stochastic` metric=0.067
    - doc=`redocred-validation-000004-ELAM__Latin_American_School_of_Medicine_` op=`repeat` family=`stochastic` metric=0.087

# Drift contract report

**0 satisfied · 7 violated · 1 inconclusive** (of 8 contracts)

| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |
|---|---|---|---|---:|---:|---:|---:|
| K1 | Schema rename/reorder invariance (strict) | invariance | **VIOLATED** | 680 | 0.99 | 0.317 | 0.541 / 0.850 |
| K1b | Schema description-add invariance | invariance | **VIOLATED** | 340 | 0.99 | 0.331 | 0.478 / 0.800 |
| K1c | Schema semantic-shading bounded drift | bounded_drift | **VIOLATED** | 680 | 0.79 | 0.315 | 0.273 / 0.500 |
| K2 | Prompt presentation invariance | invariance | **VIOLATED** | 540 | 0.96 | 0.358 | 0.467 / 0.800 |
| K3 | Evidence/entity-alias reorder invariance | invariance | **VIOLATED** | 80 | 0.61 | 0.570 | 0.494 / 0.800 |
| K4 | Multi-hop join robustness (Q3) | bounded_drift | **VIOLATED** | 2320 | 0.92 | 0.174 | 0.386 / 0.500 |
| K5 | Model swap recall stability | bounded_drift | **INCONCLUSIVE** | 0 | 0.00 | 0.000 | 0.000 / 0.000 |
| K6 | Stochastic repeatability | invariance | **VIOLATED** | 80 | 0.96 | 0.462 | 0.458 / 0.789 |

## Per-contract details

### K1 — Schema rename/reorder invariance (strict)  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'rename'", "'reorder'"]}`
- pairs: n=680, fail=671, violation_rate=0.987
- metric: mean=0.317, median=0.294
- by family:
    - `schema` n=680, viol=0.99, mean_metric=0.317
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.79
    - τ=0.7: 0.95
    - τ=0.8: 0.98
    - τ=0.9: 0.99
- top violation examples:
    - doc=`redocred-validation-000006-Soccer_Academy` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000006-Soccer_Academy` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000021-South_Gondar_Zone` op=`switch_schema` family=`schema` metric=0.000

### K1b — Schema description-add invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'desc_added'"]}`
- pairs: n=340, fail=335, violation_rate=0.985
- metric: mean=0.331, median=0.302
- by family:
    - `schema` n=340, viol=0.99, mean_metric=0.331
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.75
    - τ=0.7: 0.95
    - τ=0.8: 0.99
    - τ=0.9: 0.99
- top violation examples:
    - doc=`redocred-validation-000006-Soccer_Academy` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000035-Won-yong` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000036-Ramada__shelter_` op=`switch_schema` family=`schema` metric=0.000

### K1c — Schema semantic-shading bounded drift  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'cause_family_in': ['schema'], 'description_substring_in': ["'desc_removed'", "'hierarchical'"]}`
- pairs: n=680, fail=537, violation_rate=0.790
- metric: mean=0.315, median=0.275
- by family:
    - `schema` n=680, viol=0.79, mean_metric=0.315
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.79
    - τ=0.7: 0.94
    - τ=0.8: 0.96
    - τ=0.9: 0.98
- top violation examples:
    - doc=`redocred-validation-000006-Soccer_Academy` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000006-Soccer_Academy` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000019-Railroad_Revival_Tour` op=`switch_schema` family=`schema` metric=0.000

### K2 — Prompt presentation invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['prompt'], 'semantic_class_in': ['presentation']}`
- pairs: n=540, fail=516, violation_rate=0.956
- metric: mean=0.358, median=0.333
- by family:
    - `prompt` n=540, viol=0.96, mean_metric=0.358
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.72
    - τ=0.7: 0.91
    - τ=0.8: 0.96
    - τ=0.9: 0.98
- top violation examples:
    - doc=`redocred-validation-000006-Soccer_Academy` op=`tone` family=`prompt` metric=0.000
    - doc=`redocred-validation-000019-Railroad_Revival_Tour` op=`tone` family=`prompt` metric=0.000
    - doc=`redocred-validation-000019-Railroad_Revival_Tour` op=`tone` family=`prompt` metric=0.000

### K3 — Evidence/entity-alias reorder invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['entity_alias', 'evidence'], 'semantic_class_in': ['presentation']}`
- pairs: n=80, fail=49, violation_rate=0.613
- metric: mean=0.570, median=0.500
- by family:
    - `entity_alias` n=40, viol=0.28, mean_metric=0.821
    - `evidence` n=40, viol=0.95, mean_metric=0.320
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.47
    - τ=0.7: 0.60
    - τ=0.8: 0.61
    - τ=0.9: 0.64
- top violation examples:
    - doc=`redocred-validation-000006-Soccer_Academy` op=`para_swap` family=`evidence` metric=0.000
    - doc=`redocred-validation-000016-Henrik_Angell` op=`para_swap` family=`evidence` metric=0.000
    - doc=`redocred-validation-000021-South_Gondar_Zone` op=`para_swap` family=`evidence` metric=0.000

### K4 — Multi-hop join robustness (Q3)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=2320, fail=2128, violation_rate=0.917
- metric: mean=0.174, median=0.091
- by family:
    - `entity_alias` n=40, viol=0.28, mean_metric=0.774
    - `evidence` n=40, viol=0.97, mean_metric=0.113
    - `prompt` n=540, viol=0.92, mean_metric=0.185
    - `schema` n=1700, viol=0.93, mean_metric=0.158
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.92
    - τ=0.7: 0.94
    - τ=0.8: 0.95
    - τ=0.9: 0.95
- top violation examples:
    - doc=`redocred-validation-000002-Mess_of_Blues__Jeff_Healey_album_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000002-Mess_of_Blues__Jeff_Healey_album_` op=`switch_schema` family=`schema` metric=0.000
    - doc=`redocred-validation-000002-Mess_of_Blues__Jeff_Healey_album_` op=`switch_schema` family=`schema` metric=0.000

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
- pairs: n=80, fail=77, violation_rate=0.963
- metric: mean=0.462, median=0.458
- by family:
    - `stochastic` n=80, viol=0.96, mean_metric=0.462
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.55
    - τ=0.7: 0.80
    - τ=0.8: 0.93
    - τ=0.9: 0.96
- top violation examples:
    - doc=`redocred-validation-000030-Joseph_in_Islam` op=`repeat` family=`stochastic` metric=0.057
    - doc=`redocred-validation-000027-Nexus_Q` op=`repeat` family=`stochastic` metric=0.067
    - doc=`redocred-validation-000004-ELAM__Latin_American_School_of_Medicine_` op=`repeat` family=`stochastic` metric=0.087

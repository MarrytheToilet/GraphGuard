# Drift contract report

**0 satisfied · 7 violated · 1 inconclusive** (of 8 contracts)

| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |
|---|---|---|---|---:|---:|---:|---:|
| K1 | Schema rename/reorder invariance (strict) | invariance | **VIOLATED** | 229 | 0.81 | 0.537 | 0.414 / 0.783 |
| K1b | Schema description-add invariance | invariance | **VIOLATED** | 115 | 0.64 | 0.616 | 0.361 / 0.733 |
| K1c | Schema semantic-shading bounded drift | bounded_drift | **VIOLATED** | 230 | 0.40 | 0.576 | 0.229 / 0.500 |
| K2 | Prompt presentation invariance | invariance | **VIOLATED** | 90 | 0.64 | 0.639 | 0.320 / 0.675 |
| K3 | Evidence/entity-alias reorder invariance | invariance | **VIOLATED** | 30 | 0.60 | 0.671 | 0.338 / 0.586 |
| K4 | Multi-hop join robustness (Q3) | bounded_drift | **VIOLATED** | 694 | 0.54 | 0.475 | 0.332 / 0.500 |
| K5 | Model swap recall stability | bounded_drift | **INCONCLUSIVE** | 0 | 0.00 | 0.000 | 0.000 / 0.000 |
| K6 | Stochastic repeatability | invariance | **VIOLATED** | 29 | 0.90 | 0.611 | 0.334 / 0.614 |

## Per-contract details

### K1 — Schema rename/reorder invariance (strict)  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'rename'", "'reorder'"]}`
- pairs: n=229, fail=185, violation_rate=0.808
- metric: mean=0.537, median=0.500
- by family:
    - `schema` n=229, viol=0.81, mean_metric=0.537
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.43
    - τ=0.7: 0.68
    - τ=0.8: 0.76
    - τ=0.9: 0.86
- top violation examples:
    - doc=`docred-validation-000024-Beibu_Gulf_Economic_Rim` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000047-Chachalaca` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000050-Gershonites` op=`switch_schema` family=`schema` metric=0.000

### K1b — Schema description-add invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'desc_added'"]}`
- pairs: n=115, fail=74, violation_rate=0.643
- metric: mean=0.616, median=0.667
- by family:
    - `schema` n=115, viol=0.64, mean_metric=0.616
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.35
    - τ=0.7: 0.53
    - τ=0.8: 0.64
    - τ=0.9: 0.77
- top violation examples:
    - doc=`docred-validation-000050-Gershonites` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000058-Wellywood` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000061-Metropolitan_statistical_area` op=`switch_schema` family=`schema` metric=0.000

### K1c — Schema semantic-shading bounded drift  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'cause_family_in': ['schema'], 'description_substring_in': ["'desc_removed'", "'hierarchical'"]}`
- pairs: n=230, fail=93, violation_rate=0.404
- metric: mean=0.576, median=0.571
- by family:
    - `schema` n=230, viol=0.40, mean_metric=0.576
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.40
    - τ=0.7: 0.60
    - τ=0.8: 0.68
    - τ=0.9: 0.83
- top violation examples:
    - doc=`docred-validation-000013-Palestinian_National_Theatre` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000050-Gershonites` op=`switch_schema` family=`schema` metric=0.000
    - doc=`docred-validation-000058-Wellywood` op=`switch_schema` family=`schema` metric=0.000

### K2 — Prompt presentation invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['prompt'], 'semantic_class_in': ['presentation']}`
- pairs: n=90, fail=58, violation_rate=0.644
- metric: mean=0.639, median=0.667
- by family:
    - `prompt` n=90, viol=0.64, mean_metric=0.639
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.31
    - τ=0.7: 0.56
    - τ=0.8: 0.64
    - τ=0.9: 0.80
- top violation examples:
    - doc=`docred-validation-000013-Palestinian_National_Theatre` op=`role_swap` family=`prompt` metric=0.100
    - doc=`docred-validation-000010-More__The_Sisters_of_Mercy_song_` op=`role_swap` family=`prompt` metric=0.111
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`tone` family=`prompt` metric=0.115

### K3 — Evidence/entity-alias reorder invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['entity_alias', 'evidence'], 'semantic_class_in': ['presentation']}`
- pairs: n=30, fail=18, violation_rate=0.600
- metric: mean=0.671, median=0.667
- by family:
    - `entity_alias` n=15, viol=0.33, mean_metric=0.835
    - `evidence` n=15, viol=0.87, mean_metric=0.506
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.33
    - τ=0.7: 0.53
    - τ=0.8: 0.60
    - τ=0.9: 0.63
- top violation examples:
    - doc=`docred-validation-000013-Palestinian_National_Theatre` op=`para_swap` family=`evidence` metric=0.143
    - doc=`docred-validation-000010-More__The_Sisters_of_Mercy_song_` op=`para_swap` family=`evidence` metric=0.214
    - doc=`docred-validation-000005-Samsung_Galaxy_S_series` op=`para_swap` family=`evidence` metric=0.231

### K4 — Multi-hop join robustness (Q3)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=694, fail=374, violation_rate=0.539
- metric: mean=0.475, median=0.429
- by family:
    - `entity_alias` n=15, viol=0.20, mean_metric=0.814
    - `evidence` n=15, viol=0.80, mean_metric=0.309
    - `prompt` n=90, viol=0.53, mean_metric=0.476
    - `schema` n=574, viol=0.54, mean_metric=0.471
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.54
    - τ=0.7: 0.68
    - τ=0.8: 0.73
    - τ=0.9: 0.76
- top violation examples:
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`role_swap` family=`prompt` metric=0.000
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
- pairs: n=29, fail=26, violation_rate=0.897
- metric: mean=0.611, median=0.600
- by family:
    - `stochastic` n=29, viol=0.90, mean_metric=0.611
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.34
    - τ=0.7: 0.66
    - τ=0.8: 0.72
    - τ=0.9: 0.90
- top violation examples:
    - doc=`docred-validation-000001-Washington_Place__West_Virginia_` op=`repeat` family=`stochastic` metric=0.250
    - doc=`docred-validation-000008-Urgut` op=`repeat` family=`stochastic` metric=0.286
    - doc=`docred-validation-000012-Allen_County__Ohio` op=`repeat` family=`stochastic` metric=0.286

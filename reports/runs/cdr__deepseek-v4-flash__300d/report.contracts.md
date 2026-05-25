# Drift contract report

**1 satisfied · 6 violated · 1 inconclusive** (of 8 contracts)

| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |
|---|---|---|---|---:|---:|---:|---:|
| K1 | Schema rename/reorder invariance (strict) | invariance | **VIOLATED** | 680 | 0.49 | 0.735 | 0.390 / 0.850 |
| K1b | Schema description-add invariance | invariance | **VIOLATED** | 338 | 0.46 | 0.720 | 0.399 / 0.800 |
| K1c | Schema semantic-shading bounded drift | bounded_drift | **VIOLATED** | 680 | 0.21 | 0.731 | 0.260 / 0.500 |
| K2 | Prompt presentation invariance | invariance | **VIOLATED** | 1737 | 0.47 | 0.725 | 0.371 / 0.800 |
| K3 | Evidence/entity-alias reorder invariance | invariance | **VIOLATED** | 80 | 0.20 | 0.881 | 0.374 / 0.600 |
| K4 | Multi-hop join robustness (Q3) | bounded_drift | **SATISFIED** | 3515 | 0.07 | 0.927 | 0.498 / 0.500 |
| K5 | Model swap recall stability | bounded_drift | **INCONCLUSIVE** | 0 | 0.00 | 0.000 | 0.000 / 0.000 |
| K6 | Stochastic repeatability | invariance | **VIOLATED** | 80 | 0.30 | 0.829 | 0.470 / 0.900 |

## Per-contract details

### K1 — Schema rename/reorder invariance (strict)  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'rename'", "'reorder'"]}`
- pairs: n=680, fail=331, violation_rate=0.487
- metric: mean=0.735, median=0.900
- by family:
    - `schema` n=680, viol=0.49, mean_metric=0.735
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.19
    - τ=0.7: 0.42
    - τ=0.8: 0.45
    - τ=0.9: 0.50
- top violation examples:
    - doc=`cdr-validation-000023-15867025` op=`switch_schema` family=`schema` metric=0.000
    - doc=`cdr-validation-000023-15867025` op=`switch_schema` family=`schema` metric=0.000
    - doc=`cdr-validation-000023-15867025` op=`switch_schema` family=`schema` metric=0.000

### K1b — Schema description-add invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'desc_added'"]}`
- pairs: n=338, fail=154, violation_rate=0.456
- metric: mean=0.720, median=1.000
- by family:
    - `schema` n=338, viol=0.46, mean_metric=0.720
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.22
    - τ=0.7: 0.40
    - τ=0.8: 0.46
    - τ=0.9: 0.49
- top violation examples:
    - doc=`cdr-validation-000010-1545575` op=`switch_schema` family=`schema` metric=0.000
    - doc=`cdr-validation-000010-1545575` op=`switch_schema` family=`schema` metric=0.000
    - doc=`cdr-validation-000023-15867025` op=`switch_schema` family=`schema` metric=0.000

### K1c — Schema semantic-shading bounded drift  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'cause_family_in': ['schema'], 'description_substring_in': ["'desc_removed'", "'hierarchical'"]}`
- pairs: n=680, fail=144, violation_rate=0.212
- metric: mean=0.731, median=1.000
- by family:
    - `schema` n=680, viol=0.21, mean_metric=0.731
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.21
    - τ=0.7: 0.42
    - τ=0.8: 0.45
    - τ=0.9: 0.49
- top violation examples:
    - doc=`cdr-validation-000023-15867025` op=`switch_schema` family=`schema` metric=0.000
    - doc=`cdr-validation-000023-15867025` op=`switch_schema` family=`schema` metric=0.000
    - doc=`cdr-validation-000023-15867025` op=`switch_schema` family=`schema` metric=0.000

### K2 — Prompt presentation invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['prompt'], 'semantic_class_in': ['presentation']}`
- pairs: n=1737, fail=811, violation_rate=0.467
- metric: mean=0.725, median=0.833
- by family:
    - `prompt` n=1737, viol=0.47, mean_metric=0.725
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.20
    - τ=0.7: 0.42
    - τ=0.8: 0.47
    - τ=0.9: 0.52
- top violation examples:
    - doc=`cdr-validation-000003-6293644` op=`role_swap` family=`prompt` metric=0.000
    - doc=`cdr-validation-000003-6293644` op=`role_swap` family=`prompt` metric=0.000
    - doc=`cdr-validation-000003-6293644` op=`tone` family=`prompt` metric=0.000

### K3 — Evidence/entity-alias reorder invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['entity_alias', 'evidence'], 'semantic_class_in': ['presentation']}`
- pairs: n=80, fail=16, violation_rate=0.200
- metric: mean=0.881, median=1.000
- by family:
    - `entity_alias` n=40, viol=0.00, mean_metric=1.000
    - `evidence` n=40, viol=0.40, mean_metric=0.761
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.09
    - τ=0.7: 0.17
    - τ=0.8: 0.20
    - τ=0.9: 0.23
- top violation examples:
    - doc=`cdr-validation-000023-15867025` op=`para_swap` family=`evidence` metric=0.000
    - doc=`cdr-validation-000034-7651879` op=`para_swap` family=`evidence` metric=0.200
    - doc=`cdr-validation-000015-20705401` op=`para_swap` family=`evidence` metric=0.222

### K4 — Multi-hop join robustness (Q3)  · *SATISFIED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=3515, fail=255, violation_rate=0.073
- metric: mean=0.927, median=1.000
- by family:
    - `entity_alias` n=40, viol=0.00, mean_metric=1.000
    - `evidence` n=40, viol=0.07, mean_metric=0.925
    - `prompt` n=1737, viol=0.07, mean_metric=0.927
    - `schema` n=1698, viol=0.07, mean_metric=0.926
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.07
    - τ=0.7: 0.07
    - τ=0.8: 0.07
    - τ=0.9: 0.07
- top violation examples:
    - doc=`cdr-validation-000001-6504332` op=`switch_schema` family=`schema` metric=0.000
    - doc=`cdr-validation-000001-6504332` op=`switch_schema` family=`schema` metric=0.000
    - doc=`cdr-validation-000013-591536` op=`switch_schema` family=`schema` metric=0.000

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
- pairs: n=80, fail=24, violation_rate=0.300
- metric: mean=0.829, median=1.000
- by family:
    - `stochastic` n=80, viol=0.30, mean_metric=0.829
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.16
    - τ=0.7: 0.24
    - τ=0.8: 0.25
    - τ=0.9: 0.30
- top violation examples:
    - doc=`cdr-validation-000003-6293644` op=`repeat` family=`stochastic` metric=0.000
    - doc=`cdr-validation-000023-15867025` op=`repeat` family=`stochastic` metric=0.000
    - doc=`cdr-validation-000023-15867025` op=`repeat` family=`stochastic` metric=0.000

# Drift contract report

**2 satisfied · 8 violated · 1 inconclusive** (of 11 contracts)

| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |
|---|---|---|---|---:|---:|---:|---:|
| K1 | Schema rename/reorder invariance (strict) | invariance | **VIOLATED** | 680 | 0.49 | 0.736 | 0.388 / 0.850 |
| K1b | Schema description-add invariance | invariance | **VIOLATED** | 338 | 0.46 | 0.721 | 0.397 / 0.800 |
| K1c | Schema semantic-shading bounded drift | bounded_drift | **VIOLATED** | 680 | 0.21 | 0.733 | 0.260 / 0.500 |
| K2 | Prompt presentation invariance | invariance | **VIOLATED** | 1737 | 0.46 | 0.728 | 0.369 / 0.800 |
| K3 | Evidence/entity-alias reorder invariance | invariance | **SATISFIED** | 80 | 0.20 | 0.883 | 0.364 / 0.600 |
| K4 | Diagnostic fan-out join robustness (D3) | bounded_drift | **SATISFIED** | 3515 | 0.07 | 0.927 | 0.694 / 0.700 |
| K4b | Shortest-path robustness (Q5) | bounded_drift | **VIOLATED** | 139 | 0.69 | 0.336 | 0.657 / 0.700 |
| K4c | Degree-aggregation robustness (Q6) | bounded_drift | **VIOLATED** | 3485 | 0.23 | 0.875 | 0.233 / 0.700 |
| K4d | GraphRAG-retrieval robustness (Q7) | bounded_drift | **VIOLATED** | 3485 | 0.40 | 0.733 | 0.323 / 0.700 |
| K5 | Model swap recall stability | bounded_drift | **INCONCLUSIVE** | 0 | 0.00 | 0.000 | 0.000 / 0.000 |
| K6 | Decoding-resample stability | invariance | **VIOLATED** | 80 | 0.30 | 0.829 | 0.420 / 0.850 |

## Per-contract details

### K1 — Schema rename/reorder invariance (strict)  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'rename'", "'reorder'"]}`
- pairs: n=680, fail=331, violation_rate=0.487
- metric: mean=0.736, median=0.900
- by family:
    - `schema` n=680, viol=0.49, mean_metric=0.736
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

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'desc_added'"]}`
- pairs: n=338, fail=154, violation_rate=0.456
- metric: mean=0.721, median=1.000
- by family:
    - `schema` n=338, viol=0.46, mean_metric=0.721
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

- kind: `bounded_drift` · direction: `min` · threshold: `0.5` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'description_substring_in': ["'desc_removed'", "'hierarchical'"]}`
- pairs: n=680, fail=143, violation_rate=0.210
- metric: mean=0.733, median=1.000
- by family:
    - `schema` n=680, viol=0.21, mean_metric=0.733
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.21
    - τ=0.7: 0.41
    - τ=0.8: 0.45
    - τ=0.9: 0.49
- top violation examples:
    - doc=`cdr-validation-000023-15867025` op=`switch_schema` family=`schema` metric=0.000
    - doc=`cdr-validation-000023-15867025` op=`switch_schema` family=`schema` metric=0.000
    - doc=`cdr-validation-000023-15867025` op=`switch_schema` family=`schema` metric=0.000

### K2 — Prompt presentation invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['prompt'], 'semantic_class_in': ['presentation']}`
- pairs: n=1737, fail=804, violation_rate=0.463
- metric: mean=0.728, median=0.833
- by family:
    - `prompt` n=1737, viol=0.46, mean_metric=0.728
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.20
    - τ=0.7: 0.42
    - τ=0.8: 0.46
    - τ=0.9: 0.51
- top violation examples:
    - doc=`cdr-validation-000003-6293644` op=`role_swap` family=`prompt` metric=0.000
    - doc=`cdr-validation-000003-6293644` op=`role_swap` family=`prompt` metric=0.000
    - doc=`cdr-validation-000003-6293644` op=`tone` family=`prompt` metric=0.000

### K3 — Evidence/entity-alias reorder invariance  · *SATISFIED*

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['entity_alias', 'evidence'], 'semantic_class_in': ['presentation']}`
- pairs: n=80, fail=16, violation_rate=0.200
- metric: mean=0.883, median=1.000
- by family:
    - `entity_alias` n=40, viol=0.00, mean_metric=1.000
    - `evidence` n=40, viol=0.40, mean_metric=0.765
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.07
    - τ=0.7: 0.17
    - τ=0.8: 0.20
    - τ=0.9: 0.23
- top violation examples:
    - doc=`cdr-validation-000023-15867025` op=`para_swap` family=`evidence` metric=0.000
    - doc=`cdr-validation-000034-7651879` op=`para_swap` family=`evidence` metric=0.200
    - doc=`cdr-validation-000015-20705401` op=`para_swap` family=`evidence` metric=0.222

### K4 — Diagnostic fan-out join robustness (D3)  · *SATISFIED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=3515, fail=257, violation_rate=0.073
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

### K4b — Shortest-path robustness (Q5)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=139, fail=96, violation_rate=0.691
- metric: mean=0.336, median=0.000
- by family:
    - `entity_alias` n=3, viol=0.00, mean_metric=1.000
    - `evidence` n=3, viol=1.00, mean_metric=0.000
    - `prompt` n=68, viol=0.69, mean_metric=0.338
    - `schema` n=65, viol=0.71, mean_metric=0.319
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.65
    - τ=0.7: 0.69
    - τ=0.8: 0.70
    - τ=0.9: 0.71
- top violation examples:
    - doc=`cdr-validation-000006-3115150` op=`role_swap` family=`prompt` metric=0.000
    - doc=`cdr-validation-000006-3115150` op=`role_swap` family=`prompt` metric=0.000
    - doc=`cdr-validation-000006-3115150` op=`role_swap` family=`prompt` metric=0.000

### K4c — Degree-aggregation robustness (Q6)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=3485, fail=818, violation_rate=0.235
- metric: mean=0.875, median=1.000
- by family:
    - `entity_alias` n=40, viol=0.00, mean_metric=1.000
    - `evidence` n=40, viol=0.23, mean_metric=0.887
    - `prompt` n=1722, viol=0.25, mean_metric=0.867
    - `schema` n=1683, viol=0.22, mean_metric=0.880
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.06
    - τ=0.7: 0.23
    - τ=0.8: 0.23
    - τ=0.9: 0.23
- top violation examples:
    - doc=`cdr-validation-000010-1545575` op=`switch_schema` family=`schema` metric=0.000
    - doc=`cdr-validation-000010-1545575` op=`switch_schema` family=`schema` metric=0.000
    - doc=`cdr-validation-000019-16192988` op=`role_swap` family=`prompt` metric=0.000

### K4d — GraphRAG-retrieval robustness (Q7)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=3485, fail=1405, violation_rate=0.403
- metric: mean=0.733, median=1.000
- by family:
    - `entity_alias` n=40, viol=0.00, mean_metric=1.000
    - `evidence` n=40, viol=0.33, mean_metric=0.784
    - `prompt` n=1722, viol=0.42, mean_metric=0.725
    - `schema` n=1683, viol=0.40, mean_metric=0.733
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.20
    - τ=0.7: 0.40
    - τ=0.8: 0.44
    - τ=0.9: 0.48
- top violation examples:
    - doc=`cdr-validation-000003-6293644` op=`role_swap` family=`prompt` metric=0.000
    - doc=`cdr-validation-000003-6293644` op=`role_swap` family=`prompt` metric=0.000
    - doc=`cdr-validation-000003-6293644` op=`tone` family=`prompt` metric=0.000

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

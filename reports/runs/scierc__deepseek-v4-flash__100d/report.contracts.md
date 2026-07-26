# Drift contract report

**0 satisfied · 10 violated · 1 inconclusive** (of 11 contracts)

| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |
|---|---|---|---|---:|---:|---:|---:|
| K1 | Schema rename/reorder invariance (strict) | invariance | **VIOLATED** | 612 | 0.97 | 0.308 | 0.563 / 0.808 |
| K1b | Schema description-add invariance | invariance | **VIOLATED** | 302 | 0.97 | 0.334 | 0.487 / 0.741 |
| K1c | Schema semantic-shading bounded drift | bounded_drift | **VIOLATED** | 606 | 0.79 | 0.308 | 0.284 / 0.500 |
| K2 | Prompt presentation invariance | invariance | **VIOLATED** | 887 | 0.98 | 0.282 | 0.532 / 0.772 |
| K3 | Evidence/entity-alias reorder invariance | invariance | **VIOLATED** | 236 | 0.82 | 0.398 | 0.535 / 0.800 |
| K4 | Multi-hop join robustness (Q3) | bounded_drift | **VIOLATED** | 2643 | 0.64 | 0.394 | 0.644 / 0.700 |
| K4b | Shortest-path robustness (Q5) | bounded_drift | **VIOLATED** | 2072 | 0.75 | 0.337 | 0.568 / 0.700 |
| K4c | Degree-aggregation robustness (Q6) | bounded_drift | **VIOLATED** | 2620 | 0.73 | 0.572 | 0.289 / 0.500 |
| K4d | GraphRAG-retrieval robustness (Q7) | bounded_drift | **VIOLATED** | 2620 | 0.88 | 0.332 | 0.450 / 0.700 |
| K5 | Model swap recall stability | bounded_drift | **INCONCLUSIVE** | 0 | 0.00 | 0.000 | 0.000 / 0.000 |
| K6 | Decoding-resample stability | invariance | **VIOLATED** | 238 | 0.89 | 0.420 | 0.497 / 0.767 |

## Per-contract details

### K1 — Schema rename/reorder invariance (strict)  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'rename'", "'reorder'"]}`
- pairs: n=612, fail=594, violation_rate=0.971
- metric: mean=0.308, median=0.250
- by family:
    - `schema` n=612, viol=0.97, mean_metric=0.308
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.79
    - τ=0.7: 0.94
    - τ=0.8: 0.96
    - τ=0.9: 0.97
- top violation examples:
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000

### K1b — Schema description-add invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'desc_added'"]}`
- pairs: n=302, fail=292, violation_rate=0.967
- metric: mean=0.334, median=0.273
- by family:
    - `schema` n=302, viol=0.97, mean_metric=0.334
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.75
    - τ=0.7: 0.95
    - τ=0.8: 0.97
    - τ=0.9: 0.98
- top violation examples:
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000

### K1c — Schema semantic-shading bounded drift  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['schema'], 'description_substring_in': ["'desc_removed'", "'hierarchical'"]}`
- pairs: n=606, fail=478, violation_rate=0.789
- metric: mean=0.308, median=0.268
- by family:
    - `schema` n=606, viol=0.79, mean_metric=0.308
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.79
    - τ=0.7: 0.93
    - τ=0.8: 0.97
    - τ=0.9: 0.98
- top violation examples:
    - doc=`scierc-dev-000003-C88-1066` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000003-C88-1066` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000003-C88-1066` op=`switch_schema` family=`schema` metric=0.000

### K2 — Prompt presentation invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['prompt'], 'semantic_class_in': ['presentation']}`
- pairs: n=887, fail=869, violation_rate=0.980
- metric: mean=0.282, median=0.250
- by family:
    - `prompt` n=887, viol=0.98, mean_metric=0.282
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.85
    - τ=0.7: 0.97
    - τ=0.8: 0.98
    - τ=0.9: 0.99
- top violation examples:
    - doc=`scierc-dev-000003-C88-1066` op=`role_swap` family=`prompt` metric=0.000
    - doc=`scierc-dev-000003-C88-1066` op=`role_swap` family=`prompt` metric=0.000
    - doc=`scierc-dev-000005-ICCV_2009_47_abs` op=`tone` family=`prompt` metric=0.000

### K3 — Evidence/entity-alias reorder invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8` · alpha: `0.2` · min_pairs: `1`
- scope: `{'cause_family_in': ['entity_alias', 'evidence'], 'semantic_class_in': ['presentation']}`
- pairs: n=236, fail=193, violation_rate=0.818
- metric: mean=0.398, median=0.304
- by family:
    - `entity_alias` n=118, viol=0.66, mean_metric=0.521
    - `evidence` n=118, viol=0.97, mean_metric=0.274
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.73
    - τ=0.7: 0.81
    - τ=0.8: 0.82
    - τ=0.9: 0.82
- top violation examples:
    - doc=`scierc-dev-000003-C88-1066` op=`entity_alias` family=`entity_alias` metric=0.000
    - doc=`scierc-dev-000003-C88-1066` op=`para_swap` family=`evidence` metric=0.000
    - doc=`scierc-dev-000003-C88-1066` op=`entity_alias` family=`entity_alias` metric=0.000

### K4 — Multi-hop join robustness (Q3)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=2643, fail=1694, violation_rate=0.641
- metric: mean=0.394, median=0.000
- by family:
    - `entity_alias` n=118, viol=0.39, mean_metric=0.640
    - `evidence` n=118, viol=0.58, mean_metric=0.454
    - `prompt` n=887, viol=0.67, mean_metric=0.361
    - `schema` n=1520, viol=0.65, mean_metric=0.389
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.62
    - τ=0.7: 0.64
    - τ=0.8: 0.64
    - τ=0.9: 0.65
- top violation examples:
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`role_swap` family=`prompt` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`role_swap` family=`prompt` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000

### K4b — Shortest-path robustness (Q5)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=2072, fail=1562, violation_rate=0.754
- metric: mean=0.337, median=0.167
- by family:
    - `entity_alias` n=92, viol=0.48, mean_metric=0.589
    - `evidence` n=92, viol=0.88, mean_metric=0.197
    - `prompt` n=698, viol=0.80, mean_metric=0.306
    - `schema` n=1190, viol=0.74, mean_metric=0.346
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.66
    - τ=0.7: 0.75
    - τ=0.8: 0.77
    - τ=0.9: 0.80
- top violation examples:
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`role_swap` family=`prompt` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`tone` family=`prompt` metric=0.000

### K4c — Degree-aggregation robustness (Q6)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=2620, fail=1907, violation_rate=0.728
- metric: mean=0.572, median=0.500
- by family:
    - `entity_alias` n=116, viol=0.51, mean_metric=0.683
    - `evidence` n=116, viol=0.76, mean_metric=0.533
    - `prompt` n=876, viol=0.77, mean_metric=0.555
    - `schema` n=1512, viol=0.72, mean_metric=0.576
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.24
    - τ=0.7: 0.73
    - τ=0.8: 0.73
    - τ=0.9: 0.73
- top violation examples:
    - doc=`scierc-dev-000002-P84-1047` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000002-P84-1047` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000002-P84-1047` op=`switch_schema` family=`schema` metric=0.000

### K4d — GraphRAG-retrieval robustness (Q7)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.7` · alpha: `0.2` · min_pairs: `1`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=2620, fail=2311, violation_rate=0.882
- metric: mean=0.332, median=0.273
- by family:
    - `entity_alias` n=116, viol=0.66, mean_metric=0.510
    - `evidence` n=116, viol=0.94, mean_metric=0.279
    - `prompt` n=876, viol=0.91, mean_metric=0.306
    - `schema` n=1512, viol=0.88, mean_metric=0.337
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.73
    - τ=0.7: 0.88
    - τ=0.8: 0.90
    - τ=0.9: 0.91
- top violation examples:
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000

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
- pairs: n=238, fail=213, violation_rate=0.895
- metric: mean=0.420, median=0.369
- by family:
    - `stochastic` n=238, viol=0.89, mean_metric=0.420
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.64
    - τ=0.7: 0.85
    - τ=0.8: 0.89
    - τ=0.9: 0.90
- top violation examples:
    - doc=`scierc-dev-000007-H05-1041` op=`repeat` family=`stochastic` metric=0.000
    - doc=`scierc-dev-000007-H05-1041` op=`repeat` family=`stochastic` metric=0.000
    - doc=`scierc-dev-000024-L08-1260` op=`repeat` family=`stochastic` metric=0.000

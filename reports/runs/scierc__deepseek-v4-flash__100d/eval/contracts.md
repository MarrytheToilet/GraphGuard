# Drift contract report

**0 satisfied · 7 violated · 1 inconclusive** (of 8 contracts)

| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |
|---|---|---|---|---:|---:|---:|---:|
| K1 | Schema rename/reorder invariance (strict) | invariance | **VIOLATED** | 612 | 0.97 | 0.304 | 0.566 / 0.850 |
| K1b | Schema description-add invariance | invariance | **VIOLATED** | 302 | 0.97 | 0.331 | 0.488 / 0.744 |
| K1c | Schema semantic-shading bounded drift | bounded_drift | **VIOLATED** | 606 | 0.80 | 0.304 | 0.284 / 0.500 |
| K2 | Prompt presentation invariance | invariance | **VIOLATED** | 887 | 0.98 | 0.277 | 0.537 / 0.800 |
| K3 | Evidence/entity-alias reorder invariance | invariance | **VIOLATED** | 236 | 0.82 | 0.394 | 0.540 / 0.800 |
| K4 | Multi-hop join robustness (Q3) | bounded_drift | **VIOLATED** | 2643 | 0.62 | 0.387 | 0.466 / 0.500 |
| K5 | Model swap recall stability | bounded_drift | **INCONCLUSIVE** | 0 | 0.00 | 0.000 | 0.000 / 0.000 |
| K6 | Stochastic repeatability | invariance | **VIOLATED** | 238 | 0.90 | 0.418 | 0.544 / 0.817 |

## Per-contract details

### K1 — Schema rename/reorder invariance (strict)  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'rename'", "'reorder'"]}`
- pairs: n=612, fail=594, violation_rate=0.971
- metric: mean=0.304, median=0.250
- by family:
    - `schema` n=612, viol=0.97, mean_metric=0.304
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.80
    - τ=0.7: 0.94
    - τ=0.8: 0.96
    - τ=0.9: 0.97
- top violation examples:
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000

### K1b — Schema description-add invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'desc_added'"]}`
- pairs: n=302, fail=293, violation_rate=0.970
- metric: mean=0.331, median=0.273
- by family:
    - `schema` n=302, viol=0.97, mean_metric=0.331
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.76
    - τ=0.7: 0.96
    - τ=0.8: 0.97
    - τ=0.9: 0.98
- top violation examples:
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000

### K1c — Schema semantic-shading bounded drift  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'cause_family_in': ['schema'], 'description_substring_in': ["'desc_removed'", "'hierarchical'"]}`
- pairs: n=606, fail=484, violation_rate=0.799
- metric: mean=0.304, median=0.250
- by family:
    - `schema` n=606, viol=0.80, mean_metric=0.304
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.80
    - τ=0.7: 0.93
    - τ=0.8: 0.97
    - τ=0.9: 0.98
- top violation examples:
    - doc=`scierc-dev-000003-C88-1066` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000003-C88-1066` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000003-C88-1066` op=`switch_schema` family=`schema` metric=0.000

### K2 — Prompt presentation invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['prompt'], 'semantic_class_in': ['presentation']}`
- pairs: n=887, fail=869, violation_rate=0.980
- metric: mean=0.277, median=0.250
- by family:
    - `prompt` n=887, viol=0.98, mean_metric=0.277
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.86
    - τ=0.7: 0.97
    - τ=0.8: 0.98
    - τ=0.9: 0.99
- top violation examples:
    - doc=`scierc-dev-000003-C88-1066` op=`role_swap` family=`prompt` metric=0.000
    - doc=`scierc-dev-000003-C88-1066` op=`role_swap` family=`prompt` metric=0.000
    - doc=`scierc-dev-000004-C04-1116` op=`role_swap` family=`prompt` metric=0.000

### K3 — Evidence/entity-alias reorder invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['entity_alias', 'evidence'], 'semantic_class_in': ['presentation']}`
- pairs: n=236, fail=193, violation_rate=0.818
- metric: mean=0.394, median=0.286
- by family:
    - `entity_alias` n=118, viol=0.66, mean_metric=0.519
    - `evidence` n=118, viol=0.97, mean_metric=0.269
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

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=2643, fail=1648, violation_rate=0.624
- metric: mean=0.387, median=0.000
- by family:
    - `entity_alias` n=118, viol=0.39, mean_metric=0.625
    - `evidence` n=118, viol=0.57, mean_metric=0.436
    - `prompt` n=887, viol=0.64, mean_metric=0.357
    - `schema` n=1520, viol=0.63, mean_metric=0.382
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.62
    - τ=0.7: 0.65
    - τ=0.8: 0.65
    - τ=0.9: 0.65
- top violation examples:
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`role_swap` family=`prompt` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`role_swap` family=`prompt` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000

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
- pairs: n=238, fail=215, violation_rate=0.903
- metric: mean=0.418, median=0.369
- by family:
    - `stochastic` n=238, viol=0.90, mean_metric=0.418
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.64
    - τ=0.7: 0.85
    - τ=0.8: 0.89
    - τ=0.9: 0.90
- top violation examples:
    - doc=`scierc-dev-000007-H05-1041` op=`repeat` family=`stochastic` metric=0.000
    - doc=`scierc-dev-000007-H05-1041` op=`repeat` family=`stochastic` metric=0.000
    - doc=`scierc-dev-000024-L08-1260` op=`repeat` family=`stochastic` metric=0.000

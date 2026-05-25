# Drift contract report

**0 satisfied · 7 violated · 1 inconclusive** (of 8 contracts)

| ID | Contract | Kind | Verdict | n | Viol-rate | Mean metric | Severity (μ / p95) |
|---|---|---|---|---:|---:|---:|---:|
| K1 | Schema rename/reorder invariance (strict) | invariance | **VIOLATED** | 392 | 0.98 | 0.267 | 0.597 / 0.850 |
| K1b | Schema description-add invariance | invariance | **VIOLATED** | 192 | 0.99 | 0.283 | 0.524 / 0.750 |
| K1c | Schema semantic-shading bounded drift | bounded_drift | **VIOLATED** | 386 | 0.85 | 0.267 | 0.300 / 0.500 |
| K2 | Prompt presentation invariance | invariance | **VIOLATED** | 766 | 0.98 | 0.269 | 0.544 / 0.800 |
| K3 | Evidence/entity-alias reorder invariance | invariance | **VIOLATED** | 196 | 0.78 | 0.416 | 0.547 / 0.800 |
| K4 | Multi-hop join robustness (Q3) | bounded_drift | **VIOLATED** | 1932 | 0.63 | 0.377 | 0.472 / 0.500 |
| K5 | Model swap recall stability | bounded_drift | **INCONCLUSIVE** | 0 | 0.00 | 0.000 | 0.000 / 0.000 |
| K6 | Stochastic repeatability | invariance | **VIOLATED** | 198 | 0.92 | 0.399 | 0.554 / 0.817 |

## Per-contract details

### K1 — Schema rename/reorder invariance (strict)  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.85`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'rename'", "'reorder'"]}`
- pairs: n=392, fail=385, violation_rate=0.982
- metric: mean=0.267, median=0.222
- by family:
    - `schema` n=392, viol=0.98, mean_metric=0.267
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.84
    - τ=0.7: 0.97
    - τ=0.8: 0.98
    - τ=0.9: 0.98
- top violation examples:
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000

### K1b — Schema description-add invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['schema'], 'semantic_class_in': ['presentation'], 'description_substring_in': ["'desc_added'"]}`
- pairs: n=192, fail=190, violation_rate=0.990
- metric: mean=0.283, median=0.250
- by family:
    - `schema` n=192, viol=0.99, mean_metric=0.283
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.85
    - τ=0.7: 0.99
    - τ=0.8: 0.99
    - τ=0.9: 0.99
- top violation examples:
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000000-ICCV_2003_158_abs` op=`switch_schema` family=`schema` metric=0.000

### K1c — Schema semantic-shading bounded drift  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'cause_family_in': ['schema'], 'description_substring_in': ["'desc_removed'", "'hierarchical'"]}`
- pairs: n=386, fail=329, violation_rate=0.852
- metric: mean=0.267, median=0.212
- by family:
    - `schema` n=386, viol=0.85, mean_metric=0.267
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.85
    - τ=0.7: 0.95
    - τ=0.8: 0.97
    - τ=0.9: 0.98
- top violation examples:
    - doc=`scierc-dev-000003-C88-1066` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000003-C88-1066` op=`switch_schema` family=`schema` metric=0.000
    - doc=`scierc-dev-000003-C88-1066` op=`switch_schema` family=`schema` metric=0.000

### K2 — Prompt presentation invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['prompt'], 'semantic_class_in': ['presentation']}`
- pairs: n=766, fail=752, violation_rate=0.982
- metric: mean=0.269, median=0.250
- by family:
    - `prompt` n=766, viol=0.98, mean_metric=0.269
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.87
    - τ=0.7: 0.98
    - τ=0.8: 0.98
    - τ=0.9: 0.99
- top violation examples:
    - doc=`scierc-dev-000003-C88-1066` op=`role_swap` family=`prompt` metric=0.000
    - doc=`scierc-dev-000003-C88-1066` op=`role_swap` family=`prompt` metric=0.000
    - doc=`scierc-dev-000004-C04-1116` op=`role_swap` family=`prompt` metric=0.000

### K3 — Evidence/entity-alias reorder invariance  · *VIOLATED*

- kind: `invariance` · direction: `min` · threshold: `0.8`
- scope: `{'cause_family_in': ['entity_alias', 'evidence'], 'semantic_class_in': ['presentation']}`
- pairs: n=196, fail=153, violation_rate=0.781
- metric: mean=0.416, median=0.304
- by family:
    - `entity_alias` n=98, viol=0.59, mean_metric=0.563
    - `evidence` n=98, viol=0.97, mean_metric=0.269
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.71
    - τ=0.7: 0.78
    - τ=0.8: 0.78
    - τ=0.9: 0.79
- top violation examples:
    - doc=`scierc-dev-000003-C88-1066` op=`entity_alias` family=`entity_alias` metric=0.000
    - doc=`scierc-dev-000003-C88-1066` op=`para_swap` family=`evidence` metric=0.000
    - doc=`scierc-dev-000003-C88-1066` op=`entity_alias` family=`entity_alias` metric=0.000

### K4 — Multi-hop join robustness (Q3)  · *VIOLATED*

- kind: `bounded_drift` · direction: `min` · threshold: `0.5`
- scope: `{'semantic_class_in': ['presentation']}`
- pairs: n=1932, fail=1223, violation_rate=0.633
- metric: mean=0.377, median=0.000
- by family:
    - `entity_alias` n=98, viol=0.34, mean_metric=0.676
    - `evidence` n=98, viol=0.57, mean_metric=0.433
    - `prompt` n=766, viol=0.66, mean_metric=0.344
    - `schema` n=970, viol=0.65, mean_metric=0.368
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.63
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
- pairs: n=198, fail=182, violation_rate=0.919
- metric: mean=0.399, median=0.333
- by family:
    - `stochastic` n=198, viol=0.92, mean_metric=0.399
- threshold sensitivity (violation_rate at alt thresholds):
    - τ=0.5: 0.66
    - τ=0.7: 0.87
    - τ=0.8: 0.91
    - τ=0.9: 0.92
- top violation examples:
    - doc=`scierc-dev-000007-H05-1041` op=`repeat` family=`stochastic` metric=0.000
    - doc=`scierc-dev-000007-H05-1041` op=`repeat` family=`stochastic` metric=0.000
    - doc=`scierc-dev-000024-L08-1260` op=`repeat` family=`stochastic` metric=0.000

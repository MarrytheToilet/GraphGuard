# K5 across model sizes (Qwen3 family)

Shared documents: **99**. tau = 0.2, alpha = 0.2, B = 2000.

| pair | recall A | recall B | mean |dR| | frac>tau | 95% CI | drift | verdict |
|---|---:|---:|---:|---:|---|---:|:---:|
| Qwen3-8B vs Qwen3-14B | 0.107 | 0.122 | 0.081 | 0.09 | [0.04, 0.15] | 0.85 | **SATISFIED** |
| Qwen3-8B vs Qwen3-32B | 0.107 | 0.140 | 0.083 | 0.08 | [0.03, 0.14] | 0.86 | **SATISFIED** |
| Qwen3-8B vs DeepSeek-V4-Flash | 0.107 | 0.206 | 0.107 | 0.12 | [0.06, 0.19] | 0.83 | **SATISFIED** |
| Qwen3-14B vs Qwen3-32B | 0.122 | 0.140 | 0.049 | 0.05 | [0.01, 0.10] | 0.79 | **SATISFIED** |
| Qwen3-14B vs DeepSeek-V4-Flash | 0.122 | 0.206 | 0.115 | 0.13 | [0.07, 0.20] | 0.80 | **INCONCLUSIVE** |
| Qwen3-32B vs DeepSeek-V4-Flash | 0.140 | 0.206 | 0.103 | 0.14 | [0.08, 0.21] | 0.75 | **INCONCLUSIVE** |

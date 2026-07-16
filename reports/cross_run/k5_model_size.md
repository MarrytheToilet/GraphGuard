# K5 across model sizes (Qwen3 family)

Shared documents: **99**. tau = 0.2, alpha = 0.2, B = 2000.

| pair | recall A | recall B | mean |dR| | frac>tau | 95% CI | drift | verdict |
|---|---:|---:|---:|---:|---|---:|:---:|
| Qwen3-8B vs Qwen3-14B | 0.102 | 0.119 | 0.083 | 0.09 | [0.04, 0.15] | 0.86 | **SATISFIED** |
| Qwen3-8B vs Qwen3-32B | 0.102 | 0.138 | 0.085 | 0.09 | [0.04, 0.15] | 0.87 | **SATISFIED** |
| Qwen3-8B vs DeepSeek-V4-Flash | 0.102 | 0.206 | 0.111 | 0.15 | [0.08, 0.22] | 0.84 | **INCONCLUSIVE** |
| Qwen3-14B vs Qwen3-32B | 0.119 | 0.138 | 0.050 | 0.05 | [0.01, 0.10] | 0.80 | **SATISFIED** |
| Qwen3-14B vs DeepSeek-V4-Flash | 0.119 | 0.206 | 0.119 | 0.15 | [0.08, 0.22] | 0.81 | **INCONCLUSIVE** |
| Qwen3-32B vs DeepSeek-V4-Flash | 0.138 | 0.206 | 0.105 | 0.15 | [0.08, 0.22] | 0.76 | **INCONCLUSIVE** |

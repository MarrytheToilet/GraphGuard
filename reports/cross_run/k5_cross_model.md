# K5 cross-model recall stability

Shared documents (V3 ∩ Qwen3 ∩ Kimi): **98**.  τ = 0.2, α = 0.2.  Bootstrap 95% CIs use B=2000 percentile resamples.

| pair | mean recall A | mean recall B | mean \|Δrecall\| | fraction \|Δ\|>τ | 95% CI | verdict |
|---|---:|---:|---:|---:|---|:---:|
| DeepSeek-V4-Flash (v5 primary, 300 docs) vs Qwen3-32B (legacy, 100 docs) | 0.208 | 0.139 | 0.106 | 0.15 | [0.09, 0.22] | **INCONCLUSIVE** |
| DeepSeek-V4-Flash (v5 primary, 300 docs) vs Kimi-K2 (legacy, 100 docs) | 0.208 | 0.203 | 0.083 | 0.10 | [0.05, 0.16] | **SATISFIED** |
| DeepSeek-V4-Flash (v5 primary, 300 docs) vs GLM-5 (v5 partial, 100 docs) | 0.208 | 0.261 | 0.110 | 0.15 | [0.08, 0.22] | **INCONCLUSIVE** |
| Qwen3-32B (legacy, 100 docs) vs Kimi-K2 (legacy, 100 docs) | 0.139 | 0.203 | 0.079 | 0.13 | [0.07, 0.20] | **INCONCLUSIVE** |

# K5 cross-model recall stability

Shared documents (V3 ∩ Qwen3 ∩ Kimi): **98**.  τ = 0.2, α = 0.2.  Bootstrap 95% CIs use B=2000 percentile resamples.

| pair | mean recall A | mean recall B | mean \|Δrecall\| | fraction \|Δ\|>τ | 95% CI | verdict |
|---|---:|---:|---:|---:|---|:---:|
| DeepSeek-V4-Flash (v5 primary, 300 docs) vs Qwen3-32B (legacy, 100 docs) | 0.208 | 0.141 | 0.104 | 0.14 | [0.08, 0.21] | **INCONCLUSIVE** |
| DeepSeek-V4-Flash (v5 primary, 300 docs) vs Kimi-K2 (legacy, 100 docs) | 0.208 | 0.204 | 0.084 | 0.10 | [0.05, 0.16] | **SATISFIED** |
| DeepSeek-V4-Flash (v5 primary, 300 docs) vs GLM-5 (v5 partial, 100 docs) | 0.208 | 0.259 | 0.108 | 0.15 | [0.08, 0.22] | **INCONCLUSIVE** |
| Qwen3-32B (legacy, 100 docs) vs Kimi-K2 (legacy, 100 docs) | 0.141 | 0.204 | 0.078 | 0.11 | [0.05, 0.18] | **SATISFIED** |

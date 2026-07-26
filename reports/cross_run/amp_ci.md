# Canonical diagnostic amplification

Document-cluster bootstrap 95% CIs from the complete v2 pair populations (B=1000, seed=0; mean of per-pair ratios).

| run | query | n | docs | Amp mean | 95% CI | Amp(ratio-of-means) |
|---|---|---:|---:|---:|---|---:|
| docred__deepseek-v4-flash__300d | D1 edge identity | 6419 | 299 | 0.901 | [0.892, 0.908] | 0.929 |
| docred__deepseek-v4-flash__300d | D2 two-hop endpoints | 6419 | 299 | 0.740 | [0.673, 0.802] | 0.747 |
| docred__deepseek-v4-flash__300d | D3 fan-out join | 6419 | 299 | 1.146 | [1.119, 1.173] | 1.118 |
| docred__deepseek-v4-flash__300d | D4 top degree | 6419 | 299 | 0.602 | [0.574, 0.629] | 0.602 |
| docred__deepseek-v4-flash__300d | D5 short connectivity | 6419 | 299 | 0.787 | [0.767, 0.807] | 0.791 |
| redocred__deepseek-v4-flash__300d | D1 edge identity | 6614 | 300 | 0.910 | [0.903, 0.915] | 0.931 |
| redocred__deepseek-v4-flash__300d | D2 two-hop endpoints | 6614 | 300 | 0.800 | [0.745, 0.852] | 0.790 |
| redocred__deepseek-v4-flash__300d | D3 fan-out join | 6614 | 300 | 1.150 | [1.126, 1.176] | 1.116 |
| redocred__deepseek-v4-flash__300d | D4 top degree | 6614 | 300 | 0.606 | [0.576, 0.636] | 0.604 |
| redocred__deepseek-v4-flash__300d | D5 short connectivity | 6614 | 300 | 0.790 | [0.770, 0.810] | 0.791 |
| scierc__deepseek-v4-flash__100d | D1 edge identity | 6336 | 100 | 0.898 | [0.885, 0.908] | 0.933 |
| scierc__deepseek-v4-flash__100d | D2 two-hop endpoints | 6336 | 100 | 1.008 | [0.956, 1.060] | 1.013 |
| scierc__deepseek-v4-flash__100d | D3 fan-out join | 6336 | 100 | 0.816 | [0.706, 0.930] | 0.809 |
| scierc__deepseek-v4-flash__100d | D4 top degree | 6336 | 100 | 0.505 | [0.454, 0.552] | 0.503 |
| scierc__deepseek-v4-flash__100d | D5 short connectivity | 6336 | 100 | 0.697 | [0.637, 0.747] | 0.709 |
| cdr__deepseek-v4-flash__300d | D1 edge identity | 6351 | 300 | 0.471 | [0.431, 0.510] | 0.858 |
| cdr__deepseek-v4-flash__300d | D2 two-hop endpoints | 6351 | 300 | 0.109 | [0.072, 0.152] | 0.177 |
| cdr__deepseek-v4-flash__300d | D3 fan-out join | 6351 | 300 | 0.124 | [0.084, 0.171] | 0.186 |
| cdr__deepseek-v4-flash__300d | D4 top degree | 6351 | 300 | 0.300 | [0.266, 0.332] | 0.487 |
| cdr__deepseek-v4-flash__300d | D5 short connectivity | 6351 | 300 | 0.477 | [0.432, 0.518] | 0.779 |
| docred__glm-5__100d | D1 edge identity | 431 | 13 | 0.746 | [0.652, 0.852] | 0.890 |
| docred__glm-5__100d | D2 two-hop endpoints | 431 | 13 | 0.949 | [0.619, 1.276] | 1.048 |
| docred__glm-5__100d | D3 fan-out join | 431 | 13 | 0.983 | [0.783, 1.195] | 1.128 |
| docred__glm-5__100d | D4 top degree | 431 | 13 | 0.534 | [0.364, 0.719] | 0.557 |
| docred__glm-5__100d | D5 short connectivity | 431 | 13 | 0.633 | [0.474, 0.772] | 0.704 |
| docred__kimi-k2__100d | D1 edge identity | 1820 | 100 | 0.785 | [0.743, 0.819] | 0.905 |
| docred__kimi-k2__100d | D2 two-hop endpoints | 1820 | 100 | 0.688 | [0.529, 0.847] | 0.738 |
| docred__kimi-k2__100d | D3 fan-out join | 1820 | 100 | 1.039 | [0.962, 1.120] | 1.089 |
| docred__kimi-k2__100d | D4 top degree | 1820 | 100 | 0.572 | [0.498, 0.648] | 0.591 |
| docred__kimi-k2__100d | D5 short connectivity | 1820 | 100 | 0.720 | [0.665, 0.777] | 0.770 |
| docred__qwen3-32b__100d | D1 edge identity | 1776 | 99 | 0.850 | [0.829, 0.871] | 0.924 |
| docred__qwen3-32b__100d | D2 two-hop endpoints | 1776 | 99 | 0.516 | [0.411, 0.616] | 0.556 |
| docred__qwen3-32b__100d | D3 fan-out join | 1776 | 99 | 1.103 | [1.034, 1.161] | 1.122 |
| docred__qwen3-32b__100d | D4 top degree | 1776 | 99 | 0.523 | [0.468, 0.582] | 0.518 |
| docred__qwen3-32b__100d | D5 short connectivity | 1776 | 99 | 0.707 | [0.665, 0.750] | 0.732 |

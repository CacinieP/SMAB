# 书生-A1.5 vs MiniCPM-V 4.7 35B-A3B 批次 summary（2026-11-16）

| 模型 | 数据集 | 通道 | overall 均值±σ | perfect(pass^1) | 单遍分数 |
|---|---|---|---|---|---|
| Sage-A1.5-Q4_K_M (thinking on) | core | native | **98.6% ± 0.0** | 96.4% | 98.6% / 98.6% / 98.6% |
| Sage-A1.5-Q4_K_M (thinking on) | core | json | **96.7% ± 0.1** | 89.3% | 96.6% / 96.6% / 96.8% |
| Sage-A1.5-Q4_K_M (thinking on) | extra | native | **90.8% ± 0.0** | 69.2% | 90.8% / 90.8% / 90.8% |
| Sage-A1.5-Q4_K_M (thinking on) | extra | json | **96.1% ± 0.0** | 84.6% | 96.2% / 96.2% / 96.2% |
| Sage-A1.5-Q4_K_M (thinking off) | core | native | **88.9% ± 0.0** | 85.7% | 88.9% / 88.9% / 88.9% |
| Sage-A1.5-Q4_K_M (thinking off) | core | json | **95.1% ± 0.4** | 92.9% | 95.6% / 94.8% / 94.8% |
| Sage-A1.5-Q4_K_M (thinking off) | extra | native | **81.4% ± 0.0** | 69.2% | 81.4% / 81.4% / 81.4% |
| Sage-A1.5-Q4_K_M (thinking off) | extra | json | **83.4% ± 1.1** | 59.0% | 81.8% / 84.0% / 84.4% |
| MiniCPM-V-4.7-35B-A3B-Q4_K_M | core | native | **95.6% ± 0.0** | 89.3% | 95.6% / 95.6% / 95.6% |
| MiniCPM-V-4.7-35B-A3B-Q4_K_M | core | json | **91.3% ± 0.0** | 82.1% | 91.3% / 91.3% / 91.3% |
| MiniCPM-V-4.7-35B-A3B-Q4_K_M | extra | native | **91.7% ± 0.0** | 69.2% | 91.7% / 91.7% / 91.7% |
| MiniCPM-V-4.7-35B-A3B-Q4_K_M | extra | json | **82.0% ± 0.0** | 69.2% | 82.0% / 82.0% / 82.0% |

## 敏感性（Sage 原生形态，core × native，单遍）

| max_tokens | overall | perfect | avg_completion | tok/s |
|---|---:|---:|---:|---:|
| 512 | 98.6% | 96.4% | 280 | 110.1 |
| 2048 | 98.6% | 96.4% | 283 | 116.1 |

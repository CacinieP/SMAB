# SMAB 本地端点评测汇总

- 基准：[CacinieP/SMAB](https://github.com/CacinieP/SMAB) `small-model-agent-bench` 0.2.0，commit `c654074`（2026-11-03）
- 数据集：`datasets/core.jsonl`，28 episodes（core 17 / ood 11，zh 18 / en 10），七维加权 case overall
- 解码：temperature 0（greedy）、max-tokens 512、timeout 180s、schema-variant original
- 主协议 A（基线）：**json prompt-only** —— schema 注入 system prompt，`--extra-body '{"response_format":null}'`，服务端不做约束解码
- 变体 B：**json + 约束解码** —— `--extra-body '{"response_format":{"type":"json_object"}}'`，由 llama.cpp grammar 保证输出是 JSON 对象（仅 llama.cpp 端点）
- 变体 C：**native** —— llama.cpp `--jinja` 原生 `tools`/`tool_calls`（仅 probe 显示支持的端点）
- 串行执行：同一时刻只跑一个 `smab run`，避免 Metal/MNN 争用污染延迟
- 有效性门槛：`case_count == 28` 且 `adapter_error == 0`；不满足的 run 不进主表（见第 9 节）
- 本地端点协议与 2026-10-26 ModelBest API 历史 run（**native**）不同，两组分数不可直接横比

结果目录：`/Users/cacinie/Documents/deepseek-harness/default-workspace/mnn-pocket-smab/runs`

## 1. 总览

| name | model | port | 协议 | overall | perfect | cases | protocol_error | 平均请求延迟 ms | tokens 总量 |
|---|---|---|---|---|---|---|---|---|---|
| pocket03b-mnn-int4 | `MNN-Pocket-0.3B-int4` | :8090 | json | 29.2% | 0.0% | 28 | 16 (57.1%) | 646 | 26,527 |
| minicpm5-1b-q8 | `MiniCPM5-1B-Q8_0` | :8091 | json | 35.3% | 3.6% | 28 | 13 (46.4%) | 640 | 8,534 |
| minicpm5-1b-q8 | `MiniCPM5-1B-Q8_0` | :8091 | json-constrained | 34.7% | 3.6% | 28 | 10 (35.7%) | 420 | 7,925 |
| minicpm5-1b-q8 | `MiniCPM5-1B-Q8_0` | :8091 | native | 83.8% | 60.7% | 28 | 0 (0.0%) | 899 | 35,123 |
| minicpm5-2b-q8 | `MiniCPM5-2B-Q8_0` | :8092 | json | 44.5% | 7.1% | 28 | 21 (75.0%) | 957 | 13,548 |
| minicpm5-2b-q8 | `MiniCPM5-2B-Q8_0` | :8092 | json-constrained | 78.9% | 53.6% | 28 | 0 (0.0%) | 862 | 21,078 |
| minicpm5-2b-q8 | `MiniCPM5-2B-Q8_0` | :8092 | native | 94.6% | 85.7% | 28 | 0 (0.0%) | 1198 | 30,741 |
| minicpmv47-1b-q8 | `MiniCPM-V-4.7-1B-Q8_0` | :8093 | json | 35.8% | 3.6% | 28 | 9 (32.1%) | 575 | 15,225 |
| minicpmv47-1b-q8 | `MiniCPM-V-4.7-1B-Q8_0` | :8093 | json-constrained | 40.9% | 10.7% | 28 | 0 (0.0%) | 596 | 17,939 |
| minicpmv47-1b-q8 | `MiniCPM-V-4.7-1B-Q8_0` | :8093 | native | 86.4% | 75.0% | 28 | 0 (0.0%) | 787 | 36,282 |
| pocket03b-gguf-q8 | `MNN-Pocket-0.3B-GGUF-Q8_0` | :8094 | json | 30.1% | 0.0% | 28 | 20 (71.4%) | 283 | 23,296 |
| pocket03b-gguf-q8 | `MNN-Pocket-0.3B-GGUF-Q8_0` | :8094 | json-constrained | 28.1% | 0.0% | 28 | 18 (64.3%) | 326 | 31,819 |
| qwen35-08b-q8 | `Qwen3.5-0.8B-Q8_0` | :8101 | json | 32.5% | 3.6% | 28 | 13 (46.4%) | 704 | 31,758 |
| qwen35-08b-q8 | `Qwen3.5-0.8B-Q8_0` | :8101 | json-constrained | 29.7% | 3.6% | 28 | 12 (42.9%) | 679 | 34,622 |
| qwen35-08b-q8 | `Qwen3.5-0.8B-Q8_0` | :8101 | native | 83.8% | 71.4% | 28 | 0 (0.0%) | 669 | 47,678 |
| qwen35-2b-q8 | `Qwen3.5-2B-Q8_0` | :8102 | json | 74.4% | 14.3% | 28 | 17 (60.7%) | 788 | 18,445 |
| qwen35-2b-q8 | `Qwen3.5-2B-Q8_0` | :8102 | json-constrained | 77.0% | 25.0% | 28 | 13 (46.4%) | 800 | 18,822 |
| qwen35-2b-q8 | `Qwen3.5-2B-Q8_0` | :8102 | native | 89.9% | 78.6% | 28 | 0 (0.0%) | 1242 | 45,572 |
| lfm25-230m-q8 | `LFM2.5-230M-Q8_0` | :8103 | json | 29.3% | 0.0% | 28 | 28 (100.0%) | 144 | 8,827 |
| lfm25-230m-q8 | `LFM2.5-230M-Q8_0` | :8103 | json-constrained | 33.5% | 0.0% | 28 | 9 (32.1%) | 175 | 63,807 |
| lfm25-230m-q8 | `LFM2.5-230M-Q8_0` | :8103 | native | 65.9% | 46.4% | 28 | 0 (0.0%) | 132 | 14,009 |
| lfm25-12b-q8 | `LFM2.5-1.2B-Instruct-Q8_0` | :8104 | json | 37.3% | 7.1% | 28 | 5 (17.9%) | 775 | 9,265 |
| lfm25-12b-q8 | `LFM2.5-1.2B-Instruct-Q8_0` | :8104 | json-constrained | 39.9% | 10.7% | 28 | 0 (0.0%) | 632 | 9,136 |
| lfm25-12b-q8 | `LFM2.5-1.2B-Instruct-Q8_0` | :8104 | native | 81.0% | 53.6% | 28 | 0 (0.0%) | 669 | 20,577 |
| lfm25-26b-q8 | `LFM2.5-2.6B-Q8_0` | :8105 | json | 29.3% | 0.0% | 28 | 28 (100.0%) | 5856 | 10,836 |
| lfm25-26b-q8 | `LFM2.5-2.6B-Q8_0` | :8105 | json-constrained | 29.3% | 0.0% | 28 | 28 (100.0%) | 4503 | 11,016 |
| lfm25-26b-q8 | `LFM2.5-2.6B-Q8_0` | :8105 | native | 91.6% | 78.6% | 28 | 0 (0.0%) | 4322 | 34,116 |
| lfm25-350m-q8 | `LFM2.5-350M-Q8_0` | :8106 | json | 30.3% | 3.6% | 28 | 26 (92.9%) | 260 | 8,779 |
| lfm25-350m-q8 | `LFM2.5-350M-Q8_0` | :8106 | json-constrained | 43.1% | 10.7% | 28 | 0 (0.0%) | 175 | 38,689 |
| lfm25-350m-q8 | `LFM2.5-350M-Q8_0` | :8106 | native | 72.6% | 46.4% | 28 | 0 (0.0%) | 208 | 16,852 |
| qwen35-08b-f16 | `Qwen3.5-0.8B-BF16` | :8111 | json | 31.0% | 0.0% | 28 | 20 (71.4%) | 2056 | 27,578 |
| qwen35-08b-f16 | `Qwen3.5-0.8B-BF16` | :8111 | json-constrained | 29.7% | 3.6% | 28 | 17 (60.7%) | 1619 | 35,841 |
| qwen35-08b-f16 | `Qwen3.5-0.8B-BF16` | :8111 | native | 81.5% | 67.9% | 28 | 0 (0.0%) | 1654 | 48,187 |
| qwen35-2b-f16 | `Qwen3.5-2B-BF16` | :8112 | json | 72.6% | 10.7% | 28 | 17 (60.7%) | 1306 | 18,138 |
| qwen35-2b-f16 | `Qwen3.5-2B-BF16` | :8112 | json-constrained | 75.8% | 25.0% | 28 | 12 (42.9%) | 1495 | 18,539 |
| qwen35-2b-f16 | `Qwen3.5-2B-BF16` | :8112 | native | 89.9% | 78.6% | 28 | 0 (0.0%) | 2234 | 45,645 |
| lfm25-230m-f16 | `LFM2.5-230M-F16` | :8113 | json | 29.3% | 0.0% | 28 | 28 (100.0%) | 296 | 8,826 |
| lfm25-230m-f16 | `LFM2.5-230M-F16` | :8113 | json-constrained | 38.9% | 0.0% | 28 | 10 (35.7%) | 288 | 51,261 |
| lfm25-230m-f16 | `LFM2.5-230M-F16` | :8113 | native | 70.0% | 53.6% | 28 | 0 (0.0%) | 191 | 14,247 |
| lfm25-12b-f16 | `LFM2.5-1.2B-Instruct-F16` | :8114 | json | 37.3% | 7.1% | 28 | 5 (17.9%) | 899 | 9,242 |
| lfm25-12b-f16 | `LFM2.5-1.2B-Instruct-F16` | :8114 | json-constrained | 39.9% | 10.7% | 28 | 0 (0.0%) | 652 | 9,116 |
| lfm25-12b-f16 | `LFM2.5-1.2B-Instruct-F16` | :8114 | native | 81.2% | 53.6% | 28 | 0 (0.0%) | 886 | 20,173 |
| lfm25-26b-f16 | `LFM2.5-2.6B-F16` | :8115 | json | 29.3% | 0.0% | 28 | 28 (100.0%) | 7773 | 10,831 |
| lfm25-26b-f16 | `LFM2.5-2.6B-F16` | :8115 | json-constrained | 29.3% | 0.0% | 28 | 28 (100.0%) | 11332 | 10,952 |
| lfm25-26b-f16 | `LFM2.5-2.6B-F16` | :8115 | native | 93.5% | 82.1% | 28 | 0 (0.0%) | 9351 | 28,800 |
| minicpm5-1b-f16 | `MiniCPM5-1B-F16` | :8116 | json | 35.8% | 7.1% | 28 | 11 (39.3%) | 760 | 8,096 |
| minicpm5-1b-f16 | `MiniCPM5-1B-F16` | :8116 | json-constrained | 36.2% | 7.1% | 28 | 6 (21.4%) | 557 | 7,902 |
| minicpm5-1b-f16 | `MiniCPM5-1B-F16` | :8116 | native | 84.7% | 60.7% | 28 | 0 (0.0%) | 1385 | 35,925 |
| minicpm5-2b-f16 | `MiniCPM5-2B-F16` | :8117 | json | 43.7% | 7.1% | 28 | 20 (71.4%) | 1841 | 13,531 |
| minicpm5-2b-f16 | `MiniCPM5-2B-F16` | :8117 | json-constrained | 80.3% | 53.6% | 28 | 0 (0.0%) | 1473 | 20,697 |
| minicpm5-2b-f16 | `MiniCPM5-2B-F16` | :8117 | native | 96.7% | 89.3% | 28 | 0 (0.0%) | 2005 | 31,435 |
| mnnpocket-03b-f16 | `MNN-Pocket-0.3B-F16` | :8118 | json | 30.4% | 0.0% | 28 | 19 (67.9%) | 396 | 22,743 |
| mnnpocket-03b-f16 | `MNN-Pocket-0.3B-F16` | :8118 | json-constrained | 28.4% | 0.0% | 28 | 17 (60.7%) | 411 | 30,326 |
| minicpmv47-1b-f16 | `MiniCPM-V-4.7-1B-F16` | :8119 | json | 35.1% | 3.6% | 28 | 10 (35.7%) | 876 | 9,770 |
| minicpmv47-1b-f16 | `MiniCPM-V-4.7-1B-F16` | :8119 | json-constrained | 40.9% | 10.7% | 28 | 0 (0.0%) | 855 | 17,949 |
| minicpmv47-1b-f16 | `MiniCPM-V-4.7-1B-F16` | :8119 | native | 83.8% | 75.0% | 28 | 0 (0.0%) | 1289 | 52,821 |
| lfm25-350m-f16 | `LFM2.5-350M-F16` | :8120 | json | 29.9% | 3.6% | 28 | 27 (96.4%) | 258 | 8,789 |
| lfm25-350m-f16 | `LFM2.5-350M-F16` | :8120 | json-constrained | 41.5% | 7.1% | 28 | 0 (0.0%) | 311 | 47,322 |
| lfm25-350m-f16 | `LFM2.5-350M-F16` | :8120 | native | 73.5% | 46.4% | 28 | 0 (0.0%) | 287 | 16,793 |

> **Pocket-0.3B 的 native 通道**：8090（MNN shim 无 tool parser）与 8094（0.3B 只输出裸 JSON，不包 `<tool_call>`，llama-serve 实测 0/2）probe 均为 `native_tool_calling=no`，因此 **native 不支持/未测**，不以 0 分计入主表。

### 关键发现（TL;DR）

- **覆盖**：21 个本地端点、59 个有效 run（全部 case_count=28、adapter_error=0），外加 8090 的 `--repeats 3` 稳定性复测与 4 个 2026-10-26 ModelBest API 历史 native run 对照。
- **MiniCPM5-1B-Q8_0**：json prompt-only 35.3% → 约束解码 34.7% （-0.6pp）→ native 83.8% （+48.5pp，perfect 60.7%）。
- **MiniCPM5-2B-Q8_0**：json prompt-only 44.5% → 约束解码 78.9% （+34.4pp）→ native 94.6% （+50.0pp，perfect 85.7%）。
- **MiniCPM-V-4.7-1B-Q8_0**：json prompt-only 35.8% → 约束解码 40.9% （+5.1pp）→ native 86.4% （+50.6pp，perfect 75.0%）。
- **MNN-Pocket-0.3B（同模型两运行时）**：MNN INT4 29.2% vs llama.cpp GGUF Q8_0 30.1%（+0.9pp）；两个端点 protocol_error 16/28 与 20/28，失败模式同为顶层键漂移。
- **协议是第一自变量**：三个能走 native 的模型上，native 比 json prompt-only 高 48.5–50.6pp；约束解码只在 MiniCPM5-2B 上大幅生效（语法修复），对 1B/0.3B 几乎无效（失败在键名/语义而非 JSON 合法性）。
- **与历史 API**：MiniCPM5-2B 本地 native 94.6%/85.7% vs API 96.9%/92.9%（−2.3pp，部署栈差异）；V4.7-1B 本地 86.4%/75.0% 反而高于 API 79.2%/64.3%（+7.2pp），说明部署栈可造成同权重 7pp 级差异。
- **延迟/吞吐仅作参考**：评测期间 loadavg 一度 3.5–7.5（并发下载/其他运行时基准），分数为 greedy 不受影响。

> 2026 最新 ≤3B 模型的 **Q8_0 vs F16/BF16 双精度横评**见 **第 11 节**（8101–8120），与原 5 端点使用完全相同的协议与解码设置。

- **双精度结论（§11）**：10 个 2026 模型上，同模型 Q8_0 → F16/BF16 的 native overall 变化 均值 +0.6pp、最大绝对差 4.1pp（约束通道最大 5.4pp、prompt-only ≤1.8pp）；而协议通道（prompt-only → native）差 **+40~62pp**。
- **精度不是分水岭**：F16 的质量收益可忽略，代价却是 decode 慢 1.2–3.5×、磁盘 1.8–1.9×（服务端实测，见第 4 节注）。
- **LFM2.5 家族（230M/1.2B/2.6B/350M）**在 json prompt-only 下几乎全灭（26–28/28 protocol_error，全部输出其专属 `<|tool_call_start|>` 语法），json 约束也救不了（2.6B 仍 28/28）；native 通道正常（66–94%）。**协议偏好 ≠ 端点缺陷**。
- **Qwen3.5-2B 是唯一 prompt-only 也较强的模型**（74.4%，F16 72.6%）；Qwen3.5-0.8B 仍需 native（83.8% vs 32.5%）。
- **0.3B 三个精度点（MNN INT4 29.2 / GGUF Q8 30.1 / F16 30.4）**几乎不变，低分来自顶层键漂移，换运行时/精度都救不了。

### 稳定性复测（--repeats 3，Lead 独立复测）

- `MNN-Pocket-0.3B-int4` / json 协议 / 28 例 / 重复 3 次（seed 固定）：overall_mean = **30.1%**，std = 0.82pp，perfect-case rate = 0.0%
- pass^k：pass^1 = 0.0%，pass^2 = 0.0%，pass^3 = 0.0%
- 与主表单次结果（29.2%）相差 0.9pp，在 1σ 内 → 单次 temperature-0 结果可复现，低分不是采样噪声。
- 原始聚合文件：`runs/appendix-pocket03b-mnn-int4-json-r3.json`

## 2. 七维分数

| name | 协议 | relevance | selection | arguments | planning | state_tracking | recovery | stopping | overall |
|---|---|---|---|---|---|---|---|---|---|
| pocket03b-mnn-int4 | json | 50.0% | 0.0% | 4.3% | 0.0% | 13.3% | 0.0% | 65.7% | 29.2% |
| minicpm5-1b-q8 | json | 66.7% | 0.0% | 0.0% | 0.0% | 20.0% | 0.0% | 83.7% | 35.3% |
| minicpm5-1b-q8 | json-constrained | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 85.6% | 34.7% |
| minicpm5-1b-q8 | native | 66.7% | 93.4% | 89.9% | 77.8% | 60.0% | 64.6% | 91.7% | 83.8% |
| minicpm5-2b-q8 | json | 66.7% | 21.6% | 17.4% | 53.7% | 33.3% | 25.0% | 73.0% | 44.5% |
| minicpm5-2b-q8 | json-constrained | 83.3% | 70.4% | 78.3% | 100.0% | 33.3% | 93.8% | 96.0% | 78.9% |
| minicpm5-2b-q8 | native | 100.0% | 92.9% | 92.8% | 100.0% | 93.3% | 93.8% | 96.4% | 94.6% |
| minicpmv47-1b-q8 | json | 33.3% | 2.6% | 7.2% | 13.0% | 20.0% | 6.2% | 81.7% | 35.8% |
| minicpmv47-1b-q8 | json-constrained | 66.7% | 2.9% | 8.7% | 11.1% | 20.0% | 0.0% | 91.2% | 40.9% |
| minicpmv47-1b-q8 | native | 50.0% | 92.9% | 92.8% | 87.0% | 73.3% | 56.2% | 94.6% | 86.4% |
| pocket03b-gguf-q8 | json | 50.0% | 0.0% | 8.0% | 11.1% | 6.7% | 12.5% | 64.8% | 30.1% |
| pocket03b-gguf-q8 | json-constrained | 50.0% | 0.0% | 8.0% | 11.1% | 6.7% | 12.5% | 60.0% | 28.1% |
| qwen35-08b-q8 | json | 50.0% | 1.6% | 17.4% | 11.1% | 6.7% | 25.0% | 65.7% | 32.5% |
| qwen35-08b-q8 | json-constrained | 33.3% | 1.6% | 17.4% | 16.7% | 6.7% | 25.0% | 62.1% | 29.7% |
| qwen35-08b-q8 | native | 66.7% | 88.1% | 86.2% | 83.3% | 66.7% | 58.3% | 86.2% | 83.8% |
| qwen35-2b-q8 | json | 83.3% | 86.9% | 77.5% | 61.1% | 53.3% | 37.5% | 78.3% | 74.4% |
| qwen35-2b-q8 | json-constrained | 83.3% | 86.9% | 79.7% | 72.2% | 53.3% | 37.5% | 82.7% | 77.0% |
| qwen35-2b-q8 | native | 50.0% | 93.4% | 98.6% | 100.0% | 93.3% | 100.0% | 87.5% | 89.9% |
| lfm25-230m-q8 | json | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 66.4% | 29.3% |
| lfm25-230m-q8 | json-constrained | 33.3% | 20.2% | 37.7% | 20.4% | 6.7% | 8.3% | 48.7% | 33.5% |
| lfm25-230m-q8 | native | 66.7% | 56.0% | 56.5% | 22.2% | 26.7% | 6.2% | 97.9% | 65.9% |
| lfm25-12b-q8 | json | 66.7% | 0.0% | 2.2% | 5.6% | 6.7% | 6.2% | 92.9% | 37.3% |
| lfm25-12b-q8 | json-constrained | 66.7% | 0.0% | 2.2% | 5.6% | 13.3% | 6.2% | 98.4% | 39.9% |
| lfm25-12b-q8 | native | 50.0% | 88.8% | 83.0% | 79.6% | 63.3% | 56.2% | 91.1% | 81.0% |
| lfm25-26b-q8 | json | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 66.4% | 29.3% |
| lfm25-26b-q8 | json-constrained | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 66.4% | 29.3% |
| lfm25-26b-q8 | native | 83.3% | 93.9% | 95.7% | 94.4% | 86.7% | 81.2% | 90.5% | 91.6% |
| lfm25-350m-q8 | json | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 68.8% | 30.3% |
| lfm25-350m-q8 | json-constrained | 50.0% | 20.6% | 34.8% | 27.8% | 6.7% | 14.6% | 79.2% | 43.1% |
| lfm25-350m-q8 | native | 50.0% | 68.7% | 72.5% | 40.7% | 43.3% | 20.8% | 95.2% | 72.6% |
| qwen35-08b-f16 | json | 50.0% | 1.6% | 17.4% | 11.1% | 6.7% | 25.0% | 60.0% | 31.0% |
| qwen35-08b-f16 | json-constrained | 33.3% | 4.4% | 21.7% | 22.2% | 6.7% | 25.0% | 56.1% | 29.7% |
| qwen35-08b-f16 | native | 66.7% | 88.1% | 86.2% | 83.3% | 60.0% | 58.3% | 85.6% | 81.5% |
| qwen35-2b-f16 | json | 83.3% | 86.9% | 73.2% | 61.1% | 53.3% | 37.5% | 78.3% | 72.6% |
| qwen35-2b-f16 | json-constrained | 83.3% | 86.9% | 75.4% | 72.2% | 53.3% | 37.5% | 83.9% | 75.8% |
| qwen35-2b-f16 | native | 50.0% | 93.4% | 98.6% | 100.0% | 93.3% | 100.0% | 87.5% | 89.9% |
| lfm25-230m-f16 | json | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 66.4% | 29.3% |
| lfm25-230m-f16 | json-constrained | 50.0% | 21.8% | 37.7% | 20.4% | 13.3% | 8.3% | 58.5% | 38.9% |
| lfm25-230m-f16 | native | 66.7% | 63.1% | 60.9% | 22.2% | 40.0% | 6.2% | 98.8% | 70.0% |
| lfm25-12b-f16 | json | 66.7% | 0.0% | 2.2% | 5.6% | 6.7% | 6.2% | 92.9% | 37.3% |
| lfm25-12b-f16 | json-constrained | 66.7% | 0.0% | 2.2% | 5.6% | 13.3% | 6.2% | 98.4% | 39.9% |
| lfm25-12b-f16 | native | 50.0% | 90.0% | 83.0% | 79.6% | 63.3% | 56.2% | 91.1% | 81.2% |
| lfm25-26b-f16 | json | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 66.4% | 29.3% |
| lfm25-26b-f16 | json-constrained | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 66.4% | 29.3% |
| lfm25-26b-f16 | native | 100.0% | 95.7% | 95.7% | 94.4% | 86.7% | 81.2% | 92.9% | 93.5% |
| minicpm5-1b-f16 | json | 66.7% | 0.0% | 0.0% | 0.0% | 20.0% | 0.0% | 84.9% | 35.8% |
| minicpm5-1b-f16 | json-constrained | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 90.4% | 36.2% |
| minicpm5-1b-f16 | native | 66.7% | 92.0% | 90.6% | 79.6% | 66.7% | 45.8% | 91.7% | 84.7% |
| minicpm5-2b-f16 | json | 66.7% | 21.6% | 17.4% | 53.7% | 26.7% | 25.0% | 74.2% | 43.7% |
| minicpm5-2b-f16 | json-constrained | 100.0% | 70.4% | 78.3% | 100.0% | 33.3% | 87.5% | 97.2% | 80.3% |
| minicpm5-2b-f16 | native | 100.0% | 92.9% | 95.7% | 100.0% | 100.0% | 100.0% | 96.4% | 96.7% |
| mnnpocket-03b-f16 | json | 50.0% | 0.0% | 8.0% | 11.1% | 6.7% | 12.5% | 66.0% | 30.4% |
| mnnpocket-03b-f16 | json-constrained | 50.0% | 0.0% | 8.0% | 11.1% | 6.7% | 12.5% | 61.2% | 28.4% |
| minicpmv47-1b-f16 | json | 33.3% | 0.0% | 4.3% | 5.6% | 20.0% | 6.2% | 84.6% | 35.1% |
| minicpmv47-1b-f16 | json-constrained | 66.7% | 2.9% | 8.7% | 11.1% | 20.0% | 0.0% | 91.2% | 40.9% |
| minicpmv47-1b-f16 | native | 50.0% | 92.9% | 94.2% | 92.6% | 66.7% | 62.5% | 85.1% | 83.8% |
| lfm25-350m-f16 | json | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 67.6% | 29.9% |
| lfm25-350m-f16 | json-constrained | 50.0% | 15.1% | 37.0% | 33.3% | 6.7% | 31.2% | 72.0% | 41.5% |
| lfm25-350m-f16 | native | 50.0% | 71.4% | 73.6% | 46.3% | 43.3% | 20.8% | 95.2% | 73.5% |

## 3. core / OOD 与 by_horizon

| name | 协议 | core | OOD | h=0 | h=1 | h=2 | h=3+ |
|---|---|---|---|---|---|---|---|
| pocket03b-mnn-int4 | json | 31.3% | 25.9% | 56.6% | 31.3% | 13.8% | 12.2% |
| minicpm5-1b-q8 | json | 34.7% | 36.3% | 90.3% | 30.0% | 20.1% | 18.3% |
| minicpm5-1b-q8 | json-constrained | 34.7% | 34.8% | 84.7% | 30.9% | 19.1% | 18.3% |
| minicpm5-1b-q8 | native | 86.6% | 79.4% | 77.8% | 92.0% | 69.3% | 85.2% |
| minicpm5-2b-q8 | json | 43.8% | 45.6% | 84.7% | 29.7% | 52.7% | 47.2% |
| minicpm5-2b-q8 | json-constrained | 75.6% | 84.1% | 72.2% | 74.8% | 93.1% | 73.6% |
| minicpm5-2b-q8 | native | 93.1% | 96.8% | 100.0% | 92.2% | 95.0% | 100.0% |
| minicpmv47-1b-q8 | json | 34.8% | 37.4% | 62.5% | 37.0% | 21.0% | 25.3% |
| minicpmv47-1b-q8 | json-constrained | 40.4% | 41.6% | 91.7% | 37.0% | 26.6% | 18.3% |
| minicpmv47-1b-q8 | native | 89.0% | 82.3% | 50.7% | 97.0% | 89.3% | 68.0% |
| pocket03b-gguf-q8 | json | 31.1% | 28.6% | 56.6% | 30.7% | 18.9% | 12.2% |
| pocket03b-gguf-q8 | json-constrained | 29.9% | 25.3% | 56.6% | 28.5% | 15.7% | 12.2% |
| qwen35-08b-q8 | json | 28.7% | 38.3% | 62.5% | 31.0% | 23.6% | 15.0% |
| qwen35-08b-q8 | json-constrained | 24.5% | 37.8% | 44.5% | 31.0% | 22.9% | 15.0% |
| qwen35-08b-q8 | native | 86.9% | 78.8% | 63.9% | 94.8% | 66.7% | 100.0% |
| qwen35-2b-q8 | json | 71.7% | 78.7% | 69.1% | 83.8% | 64.8% | 48.0% |
| qwen35-2b-q8 | json-constrained | 75.4% | 79.4% | 69.1% | 85.1% | 72.3% | 48.0% |
| qwen35-2b-q8 | native | 96.8% | 79.1% | 59.0% | 95.3% | 94.3% | 95.2% |
| lfm25-230m-q8 | json | 28.2% | 30.9% | 87.2% | 22.8% | 15.1% | 12.2% |
| lfm25-230m-q8 | json-constrained | 32.5% | 35.0% | 27.4% | 42.8% | 23.2% | 12.4% |
| lfm25-230m-q8 | native | 70.7% | 58.5% | 80.6% | 80.7% | 30.9% | 48.0% |
| lfm25-12b-q8 | json | 37.3% | 37.3% | 87.5% | 32.1% | 25.2% | 18.3% |
| lfm25-12b-q8 | json-constrained | 39.0% | 41.4% | 91.7% | 35.4% | 26.2% | 18.3% |
| lfm25-12b-q8 | native | 84.9% | 75.1% | 59.0% | 93.1% | 68.7% | 78.2% |
| lfm25-26b-q8 | json | 28.2% | 30.9% | 87.2% | 22.8% | 15.1% | 12.2% |
| lfm25-26b-q8 | json-constrained | 28.2% | 30.9% | 87.2% | 22.8% | 15.1% | 12.2% |
| lfm25-26b-q8 | native | 94.9% | 86.7% | 80.5% | 96.2% | 87.2% | 95.2% |
| lfm25-350m-q8 | json | 29.9% | 30.9% | 91.3% | 23.5% | 15.1% | 12.2% |
| lfm25-350m-q8 | json-constrained | 40.3% | 47.5% | 53.5% | 47.0% | 35.9% | 18.3% |
| lfm25-350m-q8 | native | 78.4% | 63.7% | 77.8% | 87.1% | 48.1% | 39.7% |
| qwen35-08b-f16 | json | 27.4% | 36.6% | 62.2% | 29.5% | 21.7% | 12.2% |
| qwen35-08b-f16 | json-constrained | 22.5% | 40.9% | 44.5% | 29.5% | 26.7% | 12.2% |
| qwen35-08b-f16 | native | 86.9% | 73.0% | 47.9% | 94.8% | 66.7% | 100.0% |
| qwen35-2b-f16 | json | 68.7% | 78.7% | 69.1% | 80.5% | 64.8% | 48.0% |
| qwen35-2b-f16 | json-constrained | 73.4% | 79.4% | 69.1% | 82.9% | 72.3% | 48.0% |
| qwen35-2b-f16 | native | 96.8% | 79.1% | 59.0% | 95.3% | 94.3% | 95.2% |
| lfm25-230m-f16 | json | 28.2% | 30.9% | 87.2% | 22.8% | 15.1% | 12.2% |
| lfm25-230m-f16 | json-constrained | 39.8% | 37.5% | 49.6% | 45.1% | 27.0% | 12.4% |
| lfm25-230m-f16 | native | 75.5% | 61.5% | 88.9% | 86.1% | 30.9% | 48.0% |
| lfm25-12b-f16 | json | 37.3% | 37.3% | 87.5% | 32.1% | 25.2% | 18.3% |
| lfm25-12b-f16 | json-constrained | 39.0% | 41.4% | 91.7% | 35.4% | 26.2% | 18.3% |
| lfm25-12b-f16 | native | 84.9% | 75.5% | 59.0% | 93.3% | 68.7% | 78.2% |
| lfm25-26b-f16 | json | 28.2% | 30.9% | 87.2% | 22.8% | 15.1% | 12.2% |
| lfm25-26b-f16 | json-constrained | 28.2% | 30.9% | 87.2% | 22.8% | 15.1% | 12.2% |
| lfm25-26b-f16 | native | 97.4% | 87.6% | 88.9% | 96.4% | 88.2% | 100.0% |
| minicpm5-1b-f16 | json | 36.0% | 35.7% | 93.1% | 30.7% | 19.1% | 18.3% |
| minicpm5-1b-f16 | json-constrained | 36.6% | 35.4% | 87.5% | 32.4% | 20.1% | 18.3% |
| minicpm5-1b-f16 | native | 88.2% | 79.4% | 77.8% | 92.0% | 76.4% | 73.4% |
| minicpm5-2b-f16 | json | 42.5% | 45.6% | 79.2% | 29.7% | 52.7% | 47.2% |
| minicpm5-2b-f16 | json-constrained | 78.2% | 83.6% | 83.3% | 74.8% | 92.4% | 73.6% |
| minicpm5-2b-f16 | native | 95.1% | 99.1% | 100.0% | 94.4% | 98.6% | 100.0% |
| mnnpocket-03b-f16 | json | 31.1% | 29.2% | 56.6% | 30.7% | 19.8% | 12.2% |
| mnnpocket-03b-f16 | json-constrained | 29.2% | 27.2% | 56.6% | 28.5% | 16.7% | 12.2% |
| minicpmv47-1b-f16 | json | 34.0% | 37.0% | 62.5% | 36.7% | 21.0% | 18.3% |
| minicpmv47-1b-f16 | json-constrained | 40.4% | 41.6% | 91.7% | 37.0% | 26.6% | 18.3% |
| minicpmv47-1b-f16 | native | 89.0% | 75.6% | 36.8% | 97.0% | 86.7% | 68.0% |
| lfm25-350m-f16 | json | 29.2% | 30.9% | 91.3% | 22.8% | 15.1% | 12.2% |
| lfm25-350m-f16 | json-constrained | 37.6% | 47.5% | 53.5% | 43.1% | 37.8% | 18.3% |
| lfm25-350m-f16 | native | 78.5% | 65.7% | 77.8% | 87.2% | 51.2% | 39.7% |

## 4. 资源与吞吐（延迟 / token / 输出速率）

| name | 协议 | 请求数 | 平均请求延迟 ms | P95 请求 ms | 平均 case 墙钟 ms | 输出 tok/s | loadavg(开始) | prompt tok | completion tok | total tok | tok/case |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pocket03b-mnn-int4 | json | 56 | 646 | 7081 | 1293 | 73.4 | — | 23,871 | 2,656 | 26,527 | 947 |
| minicpm5-1b-q8 | json | 28 | 640 | 912 | 640 | 78.5 | 8.0 | 7,127 | 1,407 | 8,534 | 305 |
| minicpm5-1b-q8 | json-constrained | 28 | 420 | 786 | 420 | 67.9 | 8.0 | 7,127 | 798 | 7,925 | 283 |
| minicpm5-1b-q8 | native | 68 | 899 | 5966 | 2184 | 58.6 | 8.0 | 31,537 | 3,586 | 35,123 | 1254 |
| minicpm5-2b-q8 | json | 40 | 957 | 3975 | 1367 | 30.0 | 3.6 | 12,401 | 1,147 | 13,548 | 484 |
| minicpm5-2b-q8 | json-constrained | 59 | 862 | 3949 | 1818 | 29.4 | 3.6 | 19,581 | 1,497 | 21,078 | 753 |
| minicpm5-2b-q8 | native | 67 | 1198 | 5899 | 2868 | 27.9 | 3.6 | 28,504 | 2,237 | 30,741 | 1098 |
| minicpmv47-1b-q8 | json | 39 | 575 | 1632 | 801 | 70.4 | 5.8 | 13,646 | 1,579 | 15,225 | 544 |
| minicpmv47-1b-q8 | json-constrained | 42 | 596 | 4269 | 894 | 61.5 | 5.8 | 16,402 | 1,537 | 17,939 | 641 |
| minicpmv47-1b-q8 | native | 64 | 787 | 2966 | 1798 | 75.6 | 5.8 | 32,476 | 3,806 | 36,282 | 1296 |
| pocket03b-gguf-q8 | json | 53 | 283 | 2071 | 536 | 180.6 | 6.1 | 20,588 | 2,708 | 23,296 | 832 |
| pocket03b-gguf-q8 | json-constrained | 64 | 326 | 2553 | 746 | 152.4 | 6.1 | 28,636 | 3,183 | 31,819 | 1136 |
| qwen35-08b-q8 | json | 63 | 704 | 5843 | 1585 | 70.2 | 3.8 | 28,645 | 3,113 | 31,758 | 1134 |
| qwen35-08b-q8 | json-constrained | 71 | 679 | 6375 | 1721 | 64.6 | 3.8 | 31,509 | 3,113 | 34,622 | 1236 |
| qwen35-08b-q8 | native | 78 | 669 | 5142 | 1863 | 68.4 | 3.8 | 44,110 | 3,568 | 47,678 | 1703 |
| qwen35-2b-q8 | json | 54 | 788 | 2780 | 1520 | 32.7 | 3.5 | 17,055 | 1,390 | 18,445 | 659 |
| qwen35-2b-q8 | json-constrained | 55 | 800 | 2973 | 1572 | 31.4 | 3.5 | 17,439 | 1,383 | 18,822 | 672 |
| qwen35-2b-q8 | native | 77 | 1242 | 8518 | 3416 | 35.9 | 3.5 | 42,141 | 3,431 | 45,572 | 1628 |
| lfm25-230m-q8 | json | 28 | 144 | 259 | 144 | 191.2 | 5.2 | 8,055 | 772 | 8,827 | 315 |
| lfm25-230m-q8 | json-constrained | 110 | 175 | 1381 | 689 | 247.6 | 5.2 | 59,037 | 4,770 | 63,807 | 2279 |
| lfm25-230m-q8 | native | 46 | 132 | 371 | 217 | 235.9 | 5.2 | 12,574 | 1,435 | 14,009 | 500 |
| lfm25-12b-q8 | json | 29 | 775 | 1814 | 803 | 37.0 | 5.7 | 8,434 | 831 | 9,265 | 331 |
| lfm25-12b-q8 | json-constrained | 29 | 632 | 1706 | 655 | 38.2 | 5.7 | 8,435 | 701 | 9,136 | 326 |
| lfm25-12b-q8 | native | 67 | 669 | 2979 | 1603 | 48.9 | 5.7 | 18,384 | 2,193 | 20,577 | 735 |
| lfm25-26b-q8 | json | 28 | 5856 | 12149 | 5856 | 22.7 | 12.2 | 7,116 | 3,720 | 10,836 | 387 |
| lfm25-26b-q8 | json-constrained | 28 | 4503 | 13643 | 4503 | 30.9 | 12.2 | 7,116 | 3,900 | 11,016 | 393 |
| lfm25-26b-q8 | native | 77 | 4322 | 37934 | 11886 | 31.5 | 12.2 | 23,636 | 10,480 | 34,116 | 1218 |
| lfm25-350m-q8 | json | 28 | 260 | 347 | 260 | 99.6 | 11.0 | 8,055 | 724 | 8,779 | 314 |
| lfm25-350m-q8 | json-constrained | 70 | 175 | 2002 | 437 | 188.1 | 11.0 | 36,391 | 2,298 | 38,689 | 1382 |
| lfm25-350m-q8 | native | 57 | 208 | 787 | 424 | 151.9 | 11.0 | 15,052 | 1,800 | 16,852 | 602 |
| qwen35-08b-f16 | json | 57 | 2056 | 24630 | 4187 | 23.8 | 8.2 | 24,788 | 2,790 | 27,578 | 985 |
| qwen35-08b-f16 | json-constrained | 71 | 1619 | 13587 | 4107 | 27.6 | 8.2 | 32,662 | 3,179 | 35,841 | 1280 |
| qwen35-08b-f16 | native | 78 | 1654 | 13152 | 4607 | 29.8 | 8.2 | 44,338 | 3,849 | 48,187 | 1721 |
| qwen35-2b-f16 | json | 53 | 1306 | 4443 | 2473 | 20.0 | 5.0 | 16,752 | 1,386 | 18,138 | 648 |
| qwen35-2b-f16 | json-constrained | 54 | 1495 | 4939 | 2884 | 17.2 | 5.0 | 17,149 | 1,390 | 18,539 | 662 |
| qwen35-2b-f16 | native | 77 | 2234 | 16202 | 6145 | 20.2 | 5.0 | 42,164 | 3,481 | 45,645 | 1630 |
| lfm25-230m-f16 | json | 28 | 296 | 630 | 296 | 93.0 | 5.9 | 8,055 | 771 | 8,826 | 315 |
| lfm25-230m-f16 | json-constrained | 89 | 288 | 2002 | 915 | 165.0 | 5.9 | 47,036 | 4,225 | 51,261 | 1831 |
| lfm25-230m-f16 | native | 47 | 191 | 549 | 321 | 162.5 | 5.9 | 12,789 | 1,458 | 14,247 | 509 |
| lfm25-12b-f16 | json | 29 | 899 | 2260 | 932 | 30.9 | 3.2 | 8,435 | 807 | 9,242 | 330 |
| lfm25-12b-f16 | json-constrained | 29 | 652 | 1295 | 676 | 35.9 | 3.2 | 8,436 | 680 | 9,116 | 326 |
| lfm25-12b-f16 | native | 66 | 886 | 3438 | 2090 | 36.7 | 3.2 | 18,026 | 2,147 | 20,173 | 720 |
| lfm25-26b-f16 | json | 28 | 7773 | 22265 | 7774 | 17.1 | 3.9 | 7,116 | 3,715 | 10,831 | 387 |
| lfm25-26b-f16 | json-constrained | 28 | 11332 | 25101 | 11339 | 12.1 | 3.9 | 7,116 | 3,836 | 10,952 | 391 |
| lfm25-26b-f16 | native | 67 | 9351 | 68636 | 22380 | 15.6 | 3.9 | 19,029 | 9,771 | 28,800 | 1029 |
| minicpm5-1b-f16 | json | 28 | 760 | 1595 | 761 | 45.5 | 5.0 | 7,127 | 969 | 8,096 | 289 |
| minicpm5-1b-f16 | json-constrained | 28 | 557 | 922 | 557 | 49.7 | 5.0 | 7,127 | 775 | 7,902 | 282 |
| minicpm5-1b-f16 | native | 68 | 1385 | 12839 | 3364 | 48.1 | 5.0 | 31,393 | 4,532 | 35,925 | 1283 |
| minicpm5-2b-f16 | json | 40 | 1841 | 7453 | 2631 | 15.2 | 7.0 | 12,409 | 1,122 | 13,531 | 483 |
| minicpm5-2b-f16 | json-constrained | 58 | 1473 | 7056 | 3052 | 17.3 | 7.0 | 19,222 | 1,475 | 20,697 | 739 |
| minicpm5-2b-f16 | native | 68 | 2005 | 11045 | 4872 | 16.7 | 7.0 | 29,160 | 2,275 | 31,435 | 1123 |
| mnnpocket-03b-f16 | json | 52 | 396 | 2970 | 736 | 124.6 | 9.5 | 20,174 | 2,569 | 22,743 | 812 |
| mnnpocket-03b-f16 | json-constrained | 64 | 411 | 3788 | 940 | 114.5 | 9.5 | 27,313 | 3,013 | 30,326 | 1083 |
| minicpmv47-1b-f16 | json | 32 | 876 | 2377 | 1002 | 45.3 | 4.7 | 8,500 | 1,270 | 9,770 | 349 |
| minicpmv47-1b-f16 | json-constrained | 42 | 855 | 6180 | 1282 | 43.1 | 4.7 | 16,403 | 1,546 | 17,949 | 641 |
| minicpmv47-1b-f16 | native | 80 | 1289 | 11696 | 3685 | 51.7 | 4.7 | 47,489 | 5,332 | 52,821 | 1886 |
| lfm25-350m-f16 | json | 28 | 258 | 439 | 258 | 101.6 | 3.5 | 8,055 | 734 | 8,789 | 314 |
| lfm25-350m-f16 | json-constrained | 82 | 311 | 3513 | 912 | 111.6 | 3.5 | 44,472 | 2,850 | 47,322 | 1690 |
| lfm25-350m-f16 | native | 57 | 287 | 1714 | 585 | 113.5 | 3.5 | 14,935 | 1,858 | 16,793 | 600 |

> **延迟/tok-s 数据仅作参考**：评测期间有并发模型下载/加载与其他运行时的基准（loadavg 见上表，一度 3.5-7.5），
> Metal/MNN/CPU 争用会拉低吞吐；分数为 greedy 确定性输出，不受负载影响。
> 输出 tok/s = completion_tokens 总量 / 客户端累计请求延迟，含网络与调度开销，是端到端速率而非服务端 decode 速率。

## 5. protocol_error / stop_reasons（低分的协议层解释）

| name | 协议 | protocol_error cases | error turns | stop_reasons |
|---|---|---|---|---|
| pocket03b-mnn-int4 | json | 16/28 (57.1%) | 16 | completed=8, max_turns=4, protocol_error=16 |
| minicpm5-1b-q8 | json | 13/28 (46.4%) | 13 | completed=15, protocol_error=13 |
| minicpm5-1b-q8 | json-constrained | 10/28 (35.7%) | 10 | completed=18, protocol_error=10 |
| minicpm5-1b-q8 | native | 0/28 (0.0%) | 0 | completed=27, max_turns=1 |
| minicpm5-2b-q8 | json | 21/28 (75.0%) | 21 | completed=7, protocol_error=21 |
| minicpm5-2b-q8 | json-constrained | 0/28 (0.0%) | 0 | completed=28 |
| minicpm5-2b-q8 | native | 0/28 (0.0%) | 0 | completed=28 |
| minicpmv47-1b-q8 | json | 9/28 (32.1%) | 9 | completed=18, max_turns=1, protocol_error=9 |
| minicpmv47-1b-q8 | json-constrained | 0/28 (0.0%) | 0 | completed=26, max_turns=2 |
| minicpmv47-1b-q8 | native | 0/28 (0.0%) | 0 | completed=28 |
| pocket03b-gguf-q8 | json | 20/28 (71.4%) | 20 | completed=5, max_turns=3, protocol_error=20 |
| pocket03b-gguf-q8 | json-constrained | 18/28 (64.3%) | 18 | completed=5, max_turns=5, protocol_error=18 |
| qwen35-08b-q8 | json | 13/28 (46.4%) | 13 | completed=10, max_turns=5, protocol_error=13 |
| qwen35-08b-q8 | json-constrained | 12/28 (42.9%) | 12 | completed=10, max_turns=6, protocol_error=12 |
| qwen35-08b-q8 | native | 0/28 (0.0%) | 0 | completed=25, max_turns=3 |
| qwen35-2b-q8 | json | 17/28 (60.7%) | 17 | completed=11, protocol_error=17 |
| qwen35-2b-q8 | json-constrained | 13/28 (46.4%) | 13 | completed=15, protocol_error=13 |
| qwen35-2b-q8 | native | 0/28 (0.0%) | 0 | completed=26, max_turns=2 |
| lfm25-230m-q8 | json | 28/28 (100.0%) | 28 | protocol_error=28 |
| lfm25-230m-q8 | json-constrained | 9/28 (32.1%) | 9 | completed=8, max_turns=11, protocol_error=9 |
| lfm25-230m-q8 | native | 0/28 (0.0%) | 0 | completed=28 |
| lfm25-12b-q8 | json | 5/28 (17.9%) | 5 | completed=23, protocol_error=5 |
| lfm25-12b-q8 | json-constrained | 0/28 (0.0%) | 0 | completed=28 |
| lfm25-12b-q8 | native | 0/28 (0.0%) | 0 | completed=28 |
| lfm25-26b-q8 | json | 28/28 (100.0%) | 28 | protocol_error=28 |
| lfm25-26b-q8 | json-constrained | 28/28 (100.0%) | 28 | protocol_error=28 |
| lfm25-26b-q8 | native | 0/28 (0.0%) | 0 | completed=27, max_turns=1 |
| lfm25-350m-q8 | json | 26/28 (92.9%) | 26 | completed=2, protocol_error=26 |
| lfm25-350m-q8 | json-constrained | 0/28 (0.0%) | 0 | completed=23, max_turns=5 |
| lfm25-350m-q8 | native | 0/28 (0.0%) | 0 | completed=28 |
| qwen35-08b-f16 | json | 20/28 (71.4%) | 20 | completed=4, max_turns=4, protocol_error=20 |
| qwen35-08b-f16 | json-constrained | 17/28 (60.7%) | 17 | completed=5, max_turns=6, protocol_error=17 |
| qwen35-08b-f16 | native | 0/28 (0.0%) | 0 | completed=25, max_turns=3 |
| qwen35-2b-f16 | json | 17/28 (60.7%) | 17 | completed=11, protocol_error=17 |
| qwen35-2b-f16 | json-constrained | 12/28 (42.9%) | 12 | completed=16, protocol_error=12 |
| qwen35-2b-f16 | native | 0/28 (0.0%) | 0 | completed=26, max_turns=2 |
| lfm25-230m-f16 | json | 28/28 (100.0%) | 28 | protocol_error=28 |
| lfm25-230m-f16 | json-constrained | 10/28 (35.7%) | 10 | completed=10, max_turns=8, protocol_error=10 |
| lfm25-230m-f16 | native | 0/28 (0.0%) | 0 | completed=28 |
| lfm25-12b-f16 | json | 5/28 (17.9%) | 5 | completed=23, protocol_error=5 |
| lfm25-12b-f16 | json-constrained | 0/28 (0.0%) | 0 | completed=28 |
| lfm25-12b-f16 | native | 0/28 (0.0%) | 0 | completed=28 |
| lfm25-26b-f16 | json | 28/28 (100.0%) | 28 | protocol_error=28 |
| lfm25-26b-f16 | json-constrained | 28/28 (100.0%) | 28 | protocol_error=28 |
| lfm25-26b-f16 | native | 0/28 (0.0%) | 0 | completed=28 |
| minicpm5-1b-f16 | json | 11/28 (39.3%) | 11 | completed=17, protocol_error=11 |
| minicpm5-1b-f16 | json-constrained | 6/28 (21.4%) | 6 | completed=22, protocol_error=6 |
| minicpm5-1b-f16 | native | 0/28 (0.0%) | 0 | completed=27, max_turns=1 |
| minicpm5-2b-f16 | json | 20/28 (71.4%) | 20 | completed=8, protocol_error=20 |
| minicpm5-2b-f16 | json-constrained | 0/28 (0.0%) | 0 | completed=28 |
| minicpm5-2b-f16 | native | 0/28 (0.0%) | 0 | completed=28 |
| mnnpocket-03b-f16 | json | 19/28 (67.9%) | 19 | completed=6, max_turns=3, protocol_error=19 |
| mnnpocket-03b-f16 | json-constrained | 17/28 (60.7%) | 17 | completed=6, max_turns=5, protocol_error=17 |
| minicpmv47-1b-f16 | json | 10/28 (35.7%) | 10 | completed=18, protocol_error=10 |
| minicpmv47-1b-f16 | json-constrained | 0/28 (0.0%) | 0 | completed=26, max_turns=2 |
| minicpmv47-1b-f16 | native | 0/28 (0.0%) | 0 | completed=25, max_turns=3 |
| lfm25-350m-f16 | json | 27/28 (96.4%) | 27 | completed=1, protocol_error=27 |
| lfm25-350m-f16 | json-constrained | 0/28 (0.0%) | 0 | completed=21, max_turns=7 |
| lfm25-350m-f16 | native | 0/28 (0.0%) | 0 | completed=28 |

protocol_error 触发 case：
- `pocket03b-mnn-int4`（json）：rel_001, rel_002, rel_003, rel_004, rel_005, sel_001, sel_002, sel_004, arg_002, arg_004, plan_001, plan_002, plan_003, plan_004, recover_003, stop_003
- `minicpm5-1b-q8`（json）：rel_001, rel_004, rel_005, rel_006, sel_001, sel_003, arg_001, arg_004, state_002, recover_004, stop_002, stop_003, stop_004
- `minicpm5-1b-q8`（json-constrained）：rel_001, rel_005, sel_001, sel_003, arg_001, arg_004, recover_002, recover_004, stop_002, stop_003
- `minicpm5-2b-q8`（json）：rel_001, rel_002, rel_004, rel_005, sel_002, sel_003, sel_004, arg_001, arg_002, arg_004, plan_001, plan_004, state_001, state_002, recover_001, recover_002, recover_003, recover_004, stop_001, stop_003, stop_004
- `minicpmv47-1b-q8`（json）：rel_001, rel_005, sel_001, sel_003, arg_001, plan_001, plan_003, state_002, stop_003
- `pocket03b-gguf-q8`（json）：rel_001, rel_002, rel_003, rel_004, rel_005, sel_001, sel_002, sel_004, arg_001, arg_002, arg_003, arg_004, plan_002, plan_003, plan_004, state_002, recover_002, recover_003, stop_002, stop_003
- `pocket03b-gguf-q8`（json-constrained）：rel_001, rel_002, rel_003, rel_004, rel_005, sel_001, sel_002, sel_004, arg_001, arg_003, arg_004, plan_002, plan_003, plan_004, recover_001, recover_003, stop_002, stop_003
- `qwen35-08b-q8`（json）：rel_001, rel_002, sel_002, sel_004, arg_001, arg_004, plan_002, plan_003, state_002, recover_001, recover_004, stop_002, stop_003
- `qwen35-08b-q8`（json-constrained）：rel_002, rel_005, sel_002, sel_004, arg_001, arg_004, plan_002, plan_003, recover_001, recover_004, stop_002, stop_003
- `qwen35-2b-q8`（json）：rel_002, rel_003, rel_004, sel_001, sel_002, sel_003, sel_004, arg_001, arg_002, arg_003, arg_004, plan_001, plan_003, state_001, recover_001, recover_004, stop_003
- `qwen35-2b-q8`（json-constrained）：rel_002, rel_003, rel_004, sel_001, sel_002, sel_003, arg_001, arg_002, arg_004, state_001, recover_001, recover_004, stop_003
- `lfm25-230m-q8`（json）：rel_001, rel_002, rel_003, rel_004, rel_005, rel_006, sel_001, sel_002, sel_003, sel_004, arg_001, arg_002, arg_003, arg_004, plan_001, plan_002, plan_003, plan_004, state_001, state_002, recover_001, recover_002, recover_003, recover_004, stop_001, stop_002, stop_003, stop_004
- `lfm25-230m-q8`（json-constrained）：rel_003, rel_004, sel_003, sel_004, arg_002, arg_003, arg_004, plan_004, recover_003
- `lfm25-12b-q8`（json）：rel_001, rel_004, plan_004, state_001, stop_004
- `lfm25-26b-q8`（json）：rel_001, rel_002, rel_003, rel_004, rel_005, rel_006, sel_001, sel_002, sel_003, sel_004, arg_001, arg_002, arg_003, arg_004, plan_001, plan_002, plan_003, plan_004, state_001, state_002, recover_001, recover_002, recover_003, recover_004, stop_001, stop_002, stop_003, stop_004
- `lfm25-26b-q8`（json-constrained）：rel_001, rel_002, rel_003, rel_004, rel_005, rel_006, sel_001, sel_002, sel_003, sel_004, arg_001, arg_002, arg_003, arg_004, plan_001, plan_002, plan_003, plan_004, state_001, state_002, recover_001, recover_002, recover_003, recover_004, stop_001, stop_002, stop_003, stop_004
- `lfm25-350m-q8`（json）：rel_002, rel_003, rel_004, rel_005, rel_006, sel_001, sel_002, sel_003, sel_004, arg_001, arg_002, arg_003, arg_004, plan_001, plan_002, plan_003, plan_004, state_002, recover_001, recover_002, recover_003, recover_004, stop_001, stop_002, stop_003, stop_004
- `qwen35-08b-f16`（json）：rel_001, rel_002, rel_003, rel_005, sel_001, sel_002, sel_004, arg_001, arg_004, plan_001, plan_002, plan_003, plan_004, state_001, state_002, recover_001, recover_003, recover_004, stop_002, stop_003
- `qwen35-08b-f16`（json-constrained）：rel_002, rel_005, sel_001, sel_002, sel_004, arg_001, arg_004, plan_001, plan_002, plan_003, state_001, state_002, recover_001, recover_003, recover_004, stop_002, stop_003
- `qwen35-2b-f16`（json）：rel_002, rel_003, rel_004, sel_001, sel_002, sel_003, sel_004, arg_001, arg_002, arg_003, arg_004, plan_001, plan_003, state_001, recover_001, recover_004, stop_003
- `qwen35-2b-f16`（json-constrained）：rel_002, rel_003, rel_004, sel_001, sel_002, sel_003, arg_002, arg_004, state_001, recover_001, recover_004, stop_003
- `lfm25-230m-f16`（json）：rel_001, rel_002, rel_003, rel_004, rel_005, rel_006, sel_001, sel_002, sel_003, sel_004, arg_001, arg_002, arg_003, arg_004, plan_001, plan_002, plan_003, plan_004, state_001, state_002, recover_001, recover_002, recover_003, recover_004, stop_001, stop_002, stop_003, stop_004
- `lfm25-230m-f16`（json-constrained）：rel_003, rel_004, rel_005, sel_003, sel_004, arg_002, arg_003, arg_004, recover_003, stop_002
- `lfm25-12b-f16`（json）：rel_001, rel_004, plan_004, state_001, stop_004
- `lfm25-26b-f16`（json）：rel_001, rel_002, rel_003, rel_004, rel_005, rel_006, sel_001, sel_002, sel_003, sel_004, arg_001, arg_002, arg_003, arg_004, plan_001, plan_002, plan_003, plan_004, state_001, state_002, recover_001, recover_002, recover_003, recover_004, stop_001, stop_002, stop_003, stop_004
- `lfm25-26b-f16`（json-constrained）：rel_001, rel_002, rel_003, rel_004, rel_005, rel_006, sel_001, sel_002, sel_003, sel_004, arg_001, arg_002, arg_003, arg_004, plan_001, plan_002, plan_003, plan_004, state_001, state_002, recover_001, recover_002, recover_003, recover_004, stop_001, stop_002, stop_003, stop_004
- `minicpm5-1b-f16`（json）：rel_001, rel_004, rel_006, sel_003, arg_001, arg_004, plan_004, recover_004, stop_002, stop_003, stop_004
- `minicpm5-1b-f16`（json-constrained）：rel_001, arg_001, arg_004, recover_004, stop_002, stop_003
- `minicpm5-2b-f16`（json）：rel_001, rel_002, rel_004, sel_002, sel_003, sel_004, arg_001, arg_002, arg_004, plan_001, plan_004, state_001, state_002, recover_001, recover_002, recover_003, recover_004, stop_001, stop_003, stop_004
- `mnnpocket-03b-f16`（json）：rel_001, rel_002, rel_003, rel_004, rel_005, sel_001, sel_002, sel_004, arg_001, arg_002, arg_003, arg_004, plan_002, plan_003, plan_004, state_002, recover_003, stop_002, stop_003
- `mnnpocket-03b-f16`（json-constrained）：rel_001, rel_002, rel_003, rel_004, rel_005, sel_001, sel_002, sel_004, arg_001, arg_003, arg_004, plan_002, plan_003, plan_004, recover_003, stop_002, stop_003
- `minicpmv47-1b-f16`（json）：rel_001, rel_005, sel_001, sel_003, arg_001, plan_001, plan_003, state_002, stop_003, stop_004
- `lfm25-350m-f16`（json）：rel_002, rel_003, rel_004, rel_005, rel_006, sel_001, sel_002, sel_003, sel_004, arg_001, arg_002, arg_003, arg_004, plan_001, plan_002, plan_003, plan_004, state_001, state_002, recover_001, recover_002, recover_003, recover_004, stop_001, stop_002, stop_003, stop_004

protocol_error 典型报文（模型输出合法 JSON 但顶层既无 `tool_calls` 也无 `final`）：
- `pocket03b-mnn-int4`（json）×15: `JSON object contains neither final nor valid tool_calls`
- `pocket03b-mnn-int4`（json）×1: `response contains no valid JSON object`
- `minicpm5-1b-q8`（json）×10: `JSON object contains neither final nor valid tool_calls`
- `minicpm5-1b-q8`（json）×3: `response contains no valid JSON object`
- `minicpm5-1b-q8`（json-constrained）×10: `JSON object contains neither final nor valid tool_calls`
- `minicpm5-2b-q8`（json）×16: `JSON object contains neither final nor valid tool_calls`
- `minicpm5-2b-q8`（json）×5: `response contains no valid JSON object`
- `minicpmv47-1b-q8`（json）×5: `JSON object contains neither final nor valid tool_calls`
- `minicpmv47-1b-q8`（json）×4: `response contains no valid JSON object`
- `pocket03b-gguf-q8`（json）×18: `JSON object contains neither final nor valid tool_calls`
- `pocket03b-gguf-q8`（json）×2: `response contains no valid JSON object`
- `pocket03b-gguf-q8`（json-constrained）×17: `JSON object contains neither final nor valid tool_calls`
- `pocket03b-gguf-q8`（json-constrained）×1: `response contains no valid JSON object`
- `qwen35-08b-q8`（json）×10: `JSON object contains neither final nor valid tool_calls`
- `qwen35-08b-q8`（json）×3: `response contains no valid JSON object`
- `qwen35-08b-q8`（json-constrained）×11: `JSON object contains neither final nor valid tool_calls`
- `qwen35-08b-q8`（json-constrained）×1: `response contains no valid JSON object`
- `qwen35-2b-q8`（json）×10: `JSON object contains neither final nor valid tool_calls`
- `qwen35-2b-q8`（json）×7: `response contains no valid JSON object`
- `qwen35-2b-q8`（json-constrained）×13: `JSON object contains neither final nor valid tool_calls`
- `lfm25-230m-q8`（json）×28: `response contains no valid JSON object`
- `lfm25-230m-q8`（json-constrained）×8: `JSON object contains neither final nor valid tool_calls`
- `lfm25-230m-q8`（json-constrained）×1: `empty response`
- `lfm25-12b-q8`（json）×4: `JSON object contains neither final nor valid tool_calls`
- `lfm25-12b-q8`（json）×1: `response contains no valid JSON object`
- `lfm25-26b-q8`（json）×27: `response contains no valid JSON object`
- `lfm25-26b-q8`（json）×1: `JSON object contains neither final nor valid tool_calls`
- `lfm25-26b-q8`（json-constrained）×27: `JSON object contains neither final nor valid tool_calls`
- `lfm25-26b-q8`（json-constrained）×1: `response contains no valid JSON object`
- `lfm25-350m-q8`（json）×26: `response contains no valid JSON object`
- `qwen35-08b-f16`（json）×18: `JSON object contains neither final nor valid tool_calls`
- `qwen35-08b-f16`（json）×2: `response contains no valid JSON object`
- `qwen35-08b-f16`（json-constrained）×16: `JSON object contains neither final nor valid tool_calls`
- `qwen35-08b-f16`（json-constrained）×1: `response contains no valid JSON object`
- `qwen35-2b-f16`（json）×10: `JSON object contains neither final nor valid tool_calls`
- `qwen35-2b-f16`（json）×7: `response contains no valid JSON object`
- `qwen35-2b-f16`（json-constrained）×12: `JSON object contains neither final nor valid tool_calls`
- `lfm25-230m-f16`（json）×28: `response contains no valid JSON object`
- `lfm25-230m-f16`（json-constrained）×9: `JSON object contains neither final nor valid tool_calls`
- `lfm25-230m-f16`（json-constrained）×1: `empty response`
- `lfm25-12b-f16`（json）×4: `JSON object contains neither final nor valid tool_calls`
- `lfm25-12b-f16`（json）×1: `response contains no valid JSON object`
- `lfm25-26b-f16`（json）×27: `response contains no valid JSON object`
- `lfm25-26b-f16`（json）×1: `JSON object contains neither final nor valid tool_calls`
- `lfm25-26b-f16`（json-constrained）×28: `JSON object contains neither final nor valid tool_calls`
- `minicpm5-1b-f16`（json）×9: `JSON object contains neither final nor valid tool_calls`
- `minicpm5-1b-f16`（json）×2: `response contains no valid JSON object`
- `minicpm5-1b-f16`（json-constrained）×6: `JSON object contains neither final nor valid tool_calls`
- `minicpm5-2b-f16`（json）×15: `JSON object contains neither final nor valid tool_calls`
- `minicpm5-2b-f16`（json）×5: `response contains no valid JSON object`
- `mnnpocket-03b-f16`（json）×17: `JSON object contains neither final nor valid tool_calls`
- `mnnpocket-03b-f16`（json）×2: `response contains no valid JSON object`
- `mnnpocket-03b-f16`（json-constrained）×16: `JSON object contains neither final nor valid tool_calls`
- `mnnpocket-03b-f16`（json-constrained）×1: `response contains no valid JSON object`
- `minicpmv47-1b-f16`（json）×5: `response contains no valid JSON object`
- `minicpmv47-1b-f16`（json）×5: `JSON object contains neither final nor valid tool_calls`
- `lfm25-350m-f16`（json）×27: `response contains no valid JSON object`

协议失败的典型原始输出（前 2 例，`\n` 表示真实换行）：
- `pocket03b-mnn-int4`（json）`rel_001`: `{\n  "explanation": "缓存命中率是指程序在访问数据时，当数据量较大时，能够快速返回结果，避免重复计算。"\n}`
- `pocket03b-mnn-int4`（json）`rel_002`: `{\n  "answer": "订单 A-1049 现在到哪了？"\n}`
- `minicpm5-1b-q8`（json）`rel_001`: `{"answer": "缓存命中率是指数据在缓存中存在且未被修改时，能够快速返回的结果比例，它通过减少重复计算来提升系统性能。"}`
- `minicpm5-1b-q8`（json）`rel_004`: `I need to check the current weather in London for the specified date to determine if an umbrella is needed.\n\n{"final":"answer": "I cannot `
- `minicpm5-1b-q8`（json-constrained）`rel_001`: `{"answer": "缓存命中率是指数据在缓存中存在且未被修改时，能够快速返回的结果比例，它通过减少重复计算来提升系统性能。"}`
- `minicpm5-1b-q8`（json-constrained）`rel_005`: `{"answer": "请提供具体的日期，我将为您查询深圳的天气。"}`
- `minicpm5-2b-q8`（json）`rel_001`: `{"final":"answer":"缓存命中率是指请求能直接从缓存中获取数据而无需访问原始数据的比例。提高缓存命中率可以减少对后端系统的压力，提升响应速度。"}`
- `minicpm5-2b-q8`（json）`rel_002`: `{"tool_calls":[{"name":"get_order_status","arguments":{"order_id":"A-1049"}}}]}`
- `minicpmv47-1b-q8`（json）`rel_001`: `缓存命中率是指缓存中存储的数据被实际访问的次数与总数据量的比例。它反映了缓存系统的数据利用效率。`
- `minicpmv47-1b-q8`（json）`rel_005`: `{"error": "unknown_or_unconfigured_tool"}`
- `pocket03b-gguf-q8`（json）`rel_001`: `{\n  "explanation": "缓存命中率是指当数据频繁访问时，系统能快速返回结果的比例，它通过预先存储的值来减少重复计算，从而提升响应速度。"\n}`
- `pocket03b-gguf-q8`（json）`rel_002`: `{\n  "answer": "无法确定"\n}`
- `pocket03b-gguf-q8`（json-constrained）`rel_001`: `{\n  "explanation": "缓存命中率是指当数据频繁访问时，系统能快速返回结果的比例，它通过预先存储的值来减少重复计算，从而提升响应速度。"\n}`
- `pocket03b-gguf-q8`（json-constrained）`rel_002`: `{\n  "answer": "无法确定"\n}`
- `qwen35-08b-q8`（json）`rel_001`: `{"tool_calls":[{"name":"search_documents","arguments":{...}}]}`
- `qwen35-08b-q8`（json）`rel_002`: `{\n  "error": "无法查找订单 A-1049 的状态。请提供订单 ID 或尝试搜索其他订单。",\n  "error": "无法查找订单 A-1049 的状态。请提供订单 ID 或尝试搜索其他订单。",\n  "error": "无法查找订单 A-1049 的状态。请`
- `qwen35-08b-q8`（json-constrained）`rel_002`: `{\n  "error": "无法查找订单 A-1049 的状态。请提供订单 ID 或尝试搜索其他订单。",\n  "error": "无法查找订单 A-1049 的状态。请提供订单 ID 或尝试搜索其他订单。",\n  "error": "无法查找订单 A-1049 的状态。请`
- `qwen35-08b-q8`（json-constrained）`rel_005`: `{"error":"unknown_or_unconfigured_tool"}`
- `qwen35-2b-q8`（json）`rel_002`: `您的订单 A-1049 目前处于 **IN_TRANSIT**（运输中）状态，预计送达日期为 **2026-08-31**。`
- `qwen35-2b-q8`（json）`rel_003`: `{"tool_calls":[]}`
- `qwen35-2b-q8`（json-constrained）`rel_002`: `{"status":"IN_TRANSIT","eta":"2026-08-31"}`
- `qwen35-2b-q8`（json-constrained）`rel_003`: `{"tool_calls":[]}`
- `lfm25-230m-q8`（json）`rel_001`: `<|tool_call_start|>[search_documents(query="缓存命中率")]<|tool_call_end|>`
- `lfm25-230m-q8`（json）`rel_002`: `<|tool_call_start|>[get_order_status(order_id="A-1049")]<|tool_call_end|>`
- `lfm25-230m-q8`（json-constrained）`rel_003`: `{"answer": "I'm sorry, but I can't send emails directly. However, I can help you draft the email content for your supplier request."}`
- `lfm25-230m-q8`（json-constrained）`rel_004`: `{"tool_calls": ["get_weather", "get_climate_normals"]}`
- `lfm25-12b-q8`（json）`rel_001`: `缓存命中率是指系统在访问数据时，缓存中找到数据的比例。它反映了缓存的有效性和性能优化程度。`
- `lfm25-12b-q8`（json）`rel_004`: `<|tool_call_start|>[{"name": "get_weather", "arguments": {"city": "London", "date": "2026-09-03"}}]<|tool_call_end|>I am retrieving the weat`
- `lfm25-26b-q8`（json）`rel_001`: `缓存命中率是指在请求数据时，缓存中能直接找到所需数据（命中）的比例，表示系统利用缓存的有效性。它通常以百分比形式表示，数值越高说明缓存的利用率越高，系统响应越快。`
- `lfm25-26b-q8`（json）`rel_002`: `<|tool_call_start|>[get_order_status(order_id='A-1049')]<|tool_call_end|>`
- `lfm25-26b-q8`（json-constrained）`rel_001`: `{"answer": "缓存命中率是指在缓存中命中（即请求的数据已在缓存中）的比例，表示系统从缓存中获取数据的成功率。它反映了缓存的有效性，命中率越高，说明缓存利用率越高，系统性能越好。"}`
- `lfm25-26b-q8`（json-constrained）`rel_002`: `{"name": "get_order_status", "arguments": {"order_id": "A-1049"}}`
- `lfm25-350m-q8`（json）`rel_002`: `<|tool_call_start|>[get_order_status(order_id="A-1049")]<|tool_call_end|>`
- `lfm25-350m-q8`（json）`rel_003`: `<|tool_call_start|>[send_email(to="supplier@example.com", subject="催货通知", body="Dear Supplier, This is a reminder about the upcoming deliver`
- `qwen35-08b-f16`（json）`rel_001`: `{"tool_calls":[{"name":"search_documents","arguments":{...}}]}`
- `qwen35-08b-f16`（json）`rel_002`: `{\n  "error": "无法查找订单 A-1049 的状态。请提供订单 ID 或尝试搜索其他订单。",\n  "error_message": "无法查找订单 A-1049 的状态。请提供订单 ID 或尝试搜索其他订单。"\n}`
- `qwen35-08b-f16`（json-constrained）`rel_002`: `{\n  "error": "无法查找订单 A-1049 的状态。请提供订单 ID 或尝试搜索其他订单。",\n  "error_message": "无法查找订单 A-1049 的状态。请提供订单 ID 或尝试搜索其他订单。"\n}`
- `qwen35-08b-f16`（json-constrained）`rel_005`: `{"error":"unknown_or_unconfigured_tool"}`
- `qwen35-2b-f16`（json）`rel_002`: `您的订单 A-1049 目前处于 **IN_TRANSIT**（运输中）状态，预计送达日期为 **2026-08-31**。`
- `qwen35-2b-f16`（json）`rel_003`: `{"tool_calls":[]}`
- `qwen35-2b-f16`（json-constrained）`rel_002`: `{"ok":true,"result":{"status":"IN_TRANSIT","eta":"2026-08-31"}}`
- `qwen35-2b-f16`（json-constrained）`rel_003`: `{"tool_calls":[]}`
- `lfm25-230m-f16`（json）`rel_001`: `<|tool_call_start|>[search_documents(query="缓存命中率")]<|tool_call_end|>`
- `lfm25-230m-f16`（json）`rel_002`: `<|tool_call_start|>[get_order_status(order_id="A-1049")]<|tool_call_end|>`
- `lfm25-230m-f16`（json-constrained）`rel_003`: `{"name": "send_email", "arguments": {"to": "supplier@example.com", "subject": "Urgent: Urgent Order", "body": "Dear Supplier, I am writing t`
- `lfm25-230m-f16`（json-constrained）`rel_004`: `{"tool_calls": ["get_weather", "get_climate_normals"]}`
- `lfm25-12b-f16`（json）`rel_001`: `缓存命中率是指系统在请求数据时，数据是否已缓存的比例。它反映了缓存系统的效率和性能。`
- `lfm25-12b-f16`（json）`rel_004`: `<|tool_call_start|>[{"name": "get_weather", "arguments": {"city": "London", "date": "2026-09-03"}}]<|tool_call_end|>I am retrieving the weat`
- `lfm25-26b-f16`（json）`rel_001`: `缓存命中率是指在缓存中查找数据时，命中缓存（即直接从缓存中获取数据）的比例，通常用百分比表示。它反映了缓存的有效性，命中率越高，说明缓存越有效地减少了重复访问原始数据的时间。`
- `lfm25-26b-f16`（json）`rel_002`: `<|tool_call_start|>[get_order_status(order_id='A-1049')]<|tool_call_end|>`
- `lfm25-26b-f16`（json-constrained）`rel_001`: `{"answer": "缓存命中率是指在缓存中找到所需数据而无需从主存或外部存储获取数据的比例。它反映了缓存的有效性，命中率越高，系统性能越好，因为数据能更快地被提供给用户或应用程序。"}`
- `lfm25-26b-f16`（json-constrained）`rel_002`: `{"name": "get_order_status", "arguments": {"order_id": "A-1049"}}`
- `minicpm5-1b-f16`（json）`rel_001`: `{"answer": "缓存命中率是指数据在缓存中存在且未被修改时，能够快速返回的结果比例，它通过减少重复计算来提升系统性能。"}`
- `minicpm5-1b-f16`（json）`rel_004`: `I need to check the current weather in London for the specified date to determine if an umbrella is needed.\n\n'''json\n{\n  "city": "London`
- `minicpm5-1b-f16`（json-constrained）`rel_001`: `{"answer": "缓存命中率是指数据在缓存中存在且未被修改时，能够快速返回的结果比例，它通过减少重复计算来提升系统性能。"}`
- `minicpm5-1b-f16`（json-constrained）`arg_001`: `{"result": "user asked for flights on 2026-09-10 from Beijing to Shanghai for 2 adults. I will call the search_flights function with the giv`
- `minicpm5-2b-f16`（json）`rel_001`: `{"final":"answer":"缓存命中率是指请求能直接从缓存中获取数据而无需访问原始数据的比例。提高缓存命中率可以减少对后端系统的压力，提升响应速度。"}`
- `minicpm5-2b-f16`（json）`rel_002`: `{"tool_calls":[{"name":"get_order_status","arguments":{"order_id":"A-1049"}}}]}`
- `mnnpocket-03b-f16`（json）`rel_001`: `{\n  "explanation": "缓存命中率是指当数据频繁访问时，系统能快速返回结果的比例，它通过预先存储的值来减少重复计算，从而提升响应速度。"\n}`
- `mnnpocket-03b-f16`（json）`rel_002`: `{\n  "answer": "无法确定"\n}`
- `mnnpocket-03b-f16`（json-constrained）`rel_001`: `{\n  "explanation": "缓存命中率是指当数据频繁访问时，系统能快速返回结果的比例，它通过预先存储的值来减少重复计算，从而提升响应速度。"\n}`
- `mnnpocket-03b-f16`（json-constrained）`rel_002`: `{\n  "answer": "无法确定"\n}`
- `minicpmv47-1b-f16`（json）`rel_001`: `缓存命中率是指缓存中存储的数据被实际访问的次数与总数据量的比例。它反映了缓存系统的数据利用效率。`
- `minicpmv47-1b-f16`（json）`rel_005`: `{"error": "unknown_or_unconfigured_tool"}`
- `lfm25-350m-f16`（json）`rel_002`: `<|tool_call_start|>[get_order_status(order_id="A-1049")]<|tool_call_end|>`
- `lfm25-350m-f16`（json）`rel_003`: `<|tool_call_start|>[send_email(to="supplier@example.com", subject="催货通知", body="Dear Supplier, This is a reminder about the upcoming deliver`

失败模式归纳：

- **0.3B 两个端点（8090 MNN INT4 / 8094 GGUF Q8_0）**：输出合法 JSON，但顶层键漂移成 `explanation`/`answer`/`task` 等 → 校不出 `tool_calls`/`final`。
  这是纯语义/指令遵循缺陷；`response_format=json_object` 只保证 JSON 合法，不保证键名，所以 8094 的约束变体（20→18 例）几乎没救。
- **MiniCPM5-2B json prompt-only**：输出尝试写 `final`/`tool_calls`，但 JSON 结构坏（嵌套引号未转义 `{"final":"answer":"..."}`、多余右花括号），21 例协议错误。
  加上 grammar 约束后 21→0，overall +34.4pp —— 该模型的语法容量问题是可修复的，剩余差距才是策略/多轮结构问题。

## 6. prompt-only vs 约束解码对照（同模型、同维度）

> A = json prompt-only（`response_format: null`）；B = json + `response_format: {"type":"json_object"}`（服务端 grammar 约束）。
> 差值 = B − A，单位 pp。MNN 8090 的 shim 不实现 grammar 约束，只有 prompt-only 一列。

| name | A json overall | B json+约束 overall | Δ(B−A) | C native overall | Δ(C−A) | Δ(C−B) | protocol_error A→B→C |
|---|---|---|---|---|---|---|---|
| minicpm5-1b-q8 | 35.3% | 34.7% | -0.6pp | 83.8% | +48.5pp | +49.1pp | 13 → 10 → 0 |
| minicpm5-2b-q8 | 44.5% | 78.9% | +34.4pp | 94.6% | +50.0pp | +15.7pp | 21 → 0 → 0 |
| minicpmv47-1b-q8 | 35.8% | 40.9% | +5.1pp | 86.4% | +50.6pp | +45.5pp | 9 → 0 → 0 |
| pocket03b-gguf-q8 | 30.1% | 28.1% | -2.0pp | 不支持/未测 | — | — | 20 → 18 → n/a |
| qwen35-08b-q8 | 32.5% | 29.7% | -2.8pp | 83.8% | +51.2pp | +54.0pp | 13 → 12 → 0 |
| qwen35-2b-q8 | 74.4% | 77.0% | +2.6pp | 89.9% | +15.5pp | +12.9pp | 17 → 13 → 0 |
| lfm25-230m-q8 | 29.3% | 33.5% | +4.2pp | 65.9% | +36.6pp | +32.4pp | 28 → 9 → 0 |
| lfm25-12b-q8 | 37.3% | 39.9% | +2.6pp | 81.0% | +43.8pp | +41.2pp | 5 → 0 → 0 |
| lfm25-26b-q8 | 29.3% | 29.3% | +0.0pp | 91.6% | +62.4pp | +62.4pp | 28 → 28 → 0 |
| lfm25-350m-q8 | 30.3% | 43.1% | +12.8pp | 72.6% | +42.4pp | +29.5pp | 26 → 0 → 0 |
| qwen35-08b-f16 | 31.0% | 29.7% | -1.3pp | 81.5% | +50.5pp | +51.8pp | 20 → 17 → 0 |
| qwen35-2b-f16 | 72.6% | 75.8% | +3.2pp | 89.9% | +17.2pp | +14.1pp | 17 → 12 → 0 |
| lfm25-230m-f16 | 29.3% | 38.9% | +9.6pp | 70.0% | +40.7pp | +31.1pp | 28 → 10 → 0 |
| lfm25-12b-f16 | 37.3% | 39.9% | +2.6pp | 81.2% | +43.9pp | +41.3pp | 5 → 0 → 0 |
| lfm25-26b-f16 | 29.3% | 29.3% | +0.0pp | 93.5% | +64.3pp | +64.3pp | 28 → 28 → 0 |
| minicpm5-1b-f16 | 35.8% | 36.2% | +0.3pp | 84.7% | +48.9pp | +48.6pp | 11 → 6 → 0 |
| minicpm5-2b-f16 | 43.7% | 80.3% | +36.6pp | 96.7% | +52.9pp | +16.3pp | 20 → 0 → 0 |
| mnnpocket-03b-f16 | 30.4% | 28.4% | -2.0pp | 不支持/未测 | — | — | 19 → 17 → n/a |
| minicpmv47-1b-f16 | 35.1% | 40.9% | +5.7pp | 83.8% | +48.6pp | +42.9pp | 10 → 0 → 0 |
| lfm25-350m-f16 | 29.9% | 41.5% | +11.6pp | 73.5% | +43.6pp | +32.0pp | 27 → 0 → 0 |

| name | relevance | selection | arguments | planning | state_tracking | recovery | stopping |
|---|---|---|---|---|---|---|---|
| minicpm5-1b-q8 | 66.7% → 66.7% → 66.7% | 0.0% → 0.0% → 93.4% | 0.0% → 0.0% → 89.9% | 0.0% → 0.0% → 77.8% | 20.0% → 13.3% → 60.0% | 0.0% → 0.0% → 64.6% | 83.7% → 85.6% → 91.7% |
| minicpm5-2b-q8 | 66.7% → 83.3% → 100.0% | 21.6% → 70.4% → 92.9% | 17.4% → 78.3% → 92.8% | 53.7% → 100.0% → 100.0% | 33.3% → 33.3% → 93.3% | 25.0% → 93.8% → 93.8% | 73.0% → 96.0% → 96.4% |
| minicpmv47-1b-q8 | 33.3% → 66.7% → 50.0% | 2.6% → 2.9% → 92.9% | 7.2% → 8.7% → 92.8% | 13.0% → 11.1% → 87.0% | 20.0% → 20.0% → 73.3% | 6.2% → 0.0% → 56.2% | 81.7% → 91.2% → 94.6% |
| pocket03b-gguf-q8 | 50.0% → 50.0% → n/a | 0.0% → 0.0% → n/a | 8.0% → 8.0% → n/a | 11.1% → 11.1% → n/a | 6.7% → 6.7% → n/a | 12.5% → 12.5% → n/a | 64.8% → 60.0% → n/a |
| qwen35-08b-q8 | 50.0% → 33.3% → 66.7% | 1.6% → 1.6% → 88.1% | 17.4% → 17.4% → 86.2% | 11.1% → 16.7% → 83.3% | 6.7% → 6.7% → 66.7% | 25.0% → 25.0% → 58.3% | 65.7% → 62.1% → 86.2% |
| qwen35-2b-q8 | 83.3% → 83.3% → 50.0% | 86.9% → 86.9% → 93.4% | 77.5% → 79.7% → 98.6% | 61.1% → 72.2% → 100.0% | 53.3% → 53.3% → 93.3% | 37.5% → 37.5% → 100.0% | 78.3% → 82.7% → 87.5% |
| lfm25-230m-q8 | 66.7% → 33.3% → 66.7% | 0.0% → 20.2% → 56.0% | 0.0% → 37.7% → 56.5% | 0.0% → 20.4% → 22.2% | 13.3% → 6.7% → 26.7% | 0.0% → 8.3% → 6.2% | 66.4% → 48.7% → 97.9% |
| lfm25-12b-q8 | 66.7% → 66.7% → 50.0% | 0.0% → 0.0% → 88.8% | 2.2% → 2.2% → 83.0% | 5.6% → 5.6% → 79.6% | 6.7% → 13.3% → 63.3% | 6.2% → 6.2% → 56.2% | 92.9% → 98.4% → 91.1% |
| lfm25-26b-q8 | 66.7% → 66.7% → 83.3% | 0.0% → 0.0% → 93.9% | 0.0% → 0.0% → 95.7% | 0.0% → 0.0% → 94.4% | 13.3% → 13.3% → 86.7% | 0.0% → 0.0% → 81.2% | 66.4% → 66.4% → 90.5% |
| lfm25-350m-q8 | 66.7% → 50.0% → 50.0% | 0.0% → 20.6% → 68.7% | 0.0% → 34.8% → 72.5% | 0.0% → 27.8% → 40.7% | 13.3% → 6.7% → 43.3% | 0.0% → 14.6% → 20.8% | 68.8% → 79.2% → 95.2% |
| qwen35-08b-f16 | 50.0% → 33.3% → 66.7% | 1.6% → 4.4% → 88.1% | 17.4% → 21.7% → 86.2% | 11.1% → 22.2% → 83.3% | 6.7% → 6.7% → 60.0% | 25.0% → 25.0% → 58.3% | 60.0% → 56.1% → 85.6% |
| qwen35-2b-f16 | 83.3% → 83.3% → 50.0% | 86.9% → 86.9% → 93.4% | 73.2% → 75.4% → 98.6% | 61.1% → 72.2% → 100.0% | 53.3% → 53.3% → 93.3% | 37.5% → 37.5% → 100.0% | 78.3% → 83.9% → 87.5% |
| lfm25-230m-f16 | 66.7% → 50.0% → 66.7% | 0.0% → 21.8% → 63.1% | 0.0% → 37.7% → 60.9% | 0.0% → 20.4% → 22.2% | 13.3% → 13.3% → 40.0% | 0.0% → 8.3% → 6.2% | 66.4% → 58.5% → 98.8% |
| lfm25-12b-f16 | 66.7% → 66.7% → 50.0% | 0.0% → 0.0% → 90.0% | 2.2% → 2.2% → 83.0% | 5.6% → 5.6% → 79.6% | 6.7% → 13.3% → 63.3% | 6.2% → 6.2% → 56.2% | 92.9% → 98.4% → 91.1% |
| lfm25-26b-f16 | 66.7% → 66.7% → 100.0% | 0.0% → 0.0% → 95.7% | 0.0% → 0.0% → 95.7% | 0.0% → 0.0% → 94.4% | 13.3% → 13.3% → 86.7% | 0.0% → 0.0% → 81.2% | 66.4% → 66.4% → 92.9% |
| minicpm5-1b-f16 | 66.7% → 66.7% → 66.7% | 0.0% → 0.0% → 92.0% | 0.0% → 0.0% → 90.6% | 0.0% → 0.0% → 79.6% | 20.0% → 13.3% → 66.7% | 0.0% → 0.0% → 45.8% | 84.9% → 90.4% → 91.7% |
| minicpm5-2b-f16 | 66.7% → 100.0% → 100.0% | 21.6% → 70.4% → 92.9% | 17.4% → 78.3% → 95.7% | 53.7% → 100.0% → 100.0% | 26.7% → 33.3% → 100.0% | 25.0% → 87.5% → 100.0% | 74.2% → 97.2% → 96.4% |
| mnnpocket-03b-f16 | 50.0% → 50.0% → n/a | 0.0% → 0.0% → n/a | 8.0% → 8.0% → n/a | 11.1% → 11.1% → n/a | 6.7% → 6.7% → n/a | 12.5% → 12.5% → n/a | 66.0% → 61.2% → n/a |
| minicpmv47-1b-f16 | 33.3% → 66.7% → 50.0% | 0.0% → 2.9% → 92.9% | 4.3% → 8.7% → 94.2% | 5.6% → 11.1% → 92.6% | 20.0% → 20.0% → 66.7% | 6.2% → 0.0% → 62.5% | 84.6% → 91.2% → 85.1% |
| lfm25-350m-f16 | 66.7% → 50.0% → 50.0% | 0.0% → 15.1% → 71.4% | 0.0% → 37.0% → 73.6% | 0.0% → 33.3% → 46.3% | 13.3% → 6.7% → 43.3% | 0.0% → 31.2% → 20.8% | 67.6% → 72.0% → 95.2% |

**约束解码到底救什么（按模型分）**：

- **MiniCPM5-2B**：典型语法修复。prompt-only 时会尝试写 `final`/`tool_calls`，但 JSON 结构坏（嵌套引号未转义、多余右花括号）→ 21 例协议错误；`json_object` 约束后 21→0、overall +34.4pp。语法容量问题可修复，剩余差距（78.9% vs native 94.6%）才是文本协议/多轮结构问题。
- **MiniCPM5-1B**：13→10 例协议错误，overall −0.6pp。失败主因不是 JSON 非法，而是**键名漂移**（`{"answer":...}` 而非 `tool_calls`/`final`）和思考文本前缀；grammar 只保证"是合法 JSON"，保证不了"是 SMAB 约定的 JSON"。
- **MiniCPM-V-4.7-1B**：9→0 例协议错误、overall +5.1pp，但 native 高出 45.5pp。prompt-only 时它直接输出自然语言或 chat-template 风格的 `<tool_call>` XML；约束把输出压成合法 JSON，但键名/语义仍错。
- **MNN-Pocket-0.3B（8094）**：20→18，无收益（同上，键漂移非语法问题）。
- 结论：**约束解码的收益取决于失败是否落在语法层**；对 1B/0.3B，主要瓶颈在协议遵循与语义，不在 JSON 合法性。native 通道对 1B/2B/V4.7 都是 +48.5/+50.0/+50.6pp（相对 prompt-only json），说明文本 JSON 协议本身是小模型最大的部署瓶颈。

**同模型跨运行时对照（MNN-Pocket-0.3B，相同 json prompt-only 协议）**：

- MNN 3.6.2 / INT4 W4A16（:8090）overall 29.2%、perfect 0.0%、protocol_error 16/28、平均请求延迟 646ms、输出 73.4 tok/s
- llama.cpp / GGUF Q8_0（:8094）overall 30.1%、perfect 0.0%、protocol_error 20/28、平均请求延迟 283ms、输出 180.6 tok/s
- overall 差 **+1.0pp**（Q8_0 − INT4）：同模型换运行时/量化在 SMAB 上几乎无差，两个端点低分都来自同一失败模式（顶层键漂移），说明 0.3B 的瓶颈是模型能力而非部署栈；
- 吞吐差异明显（Q8_0 输出 181 vs INT4 73 tok/s），但受并发负载影响，仅作参考。

## 7. 端点能力探测（smab probe）

> 详细延迟/吞吐见第 4 节；本节只列能力矩阵（决定走 native 还是 json 通道），每个端点一行。

| name | native tools | json_object | ok | unsupported | error |
|---|---|---|---|---|---|
| pocket03b-mnn-int4 | no | no | 3 | 7 | 2 |
| minicpm5-1b-q8 | yes | yes | 8 | 3 | 1 |
| minicpm5-2b-q8 | yes | yes | 8 | 4 | 0 |
| minicpmv47-1b-q8 | yes | yes | 8 | 4 | 0 |
| pocket03b-gguf-q8 | no | no | 5 | 5 | 2 |
| qwen35-08b-q8 | yes | yes | 8 | 4 | 0 |
| qwen35-2b-q8 | yes | yes | 8 | 4 | 0 |
| lfm25-230m-q8 | yes | yes | 7 | 5 | 0 |
| lfm25-12b-q8 | yes | yes | 7 | 4 | 1 |
| lfm25-26b-q8 | yes | yes | 8 | 4 | 0 |
| lfm25-350m-q8 | yes | yes | 8 | 4 | 0 |
| qwen35-08b-f16 | yes | yes | 8 | 4 | 0 |
| qwen35-2b-f16 | yes | yes | 8 | 4 | 0 |
| lfm25-230m-f16 | yes | yes | 7 | 5 | 0 |
| lfm25-12b-f16 | yes | yes | 7 | 4 | 1 |
| lfm25-26b-f16 | yes | yes | 8 | 4 | 0 |
| minicpm5-1b-f16 | yes | yes | 8 | 4 | 0 |
| minicpm5-2b-f16 | yes | yes | 8 | 4 | 0 |
| mnnpocket-03b-f16 | no | no | 5 | 5 | 2 |
| minicpmv47-1b-f16 | yes | yes | 8 | 4 | 0 |
| lfm25-350m-f16 | yes | yes | 8 | 4 | 0 |

`native tools` 为 no 的 8090（MNN shim 无 tool parser）与 8094（0.3B 裸 JSON）只跑 json 协议，native 记为不支持/未测；8091/8092/8093 补跑 native，用于分离协议通道差异。json_object 的 probe 结论为 "error/unsupported" 多因控制组本身已返回 JSON 或 shim 不实现约束，不代表请求失败（各端点实测 200）。

## 8. 历史 ModelBest API 对照（协议不同，仅作参考）

> 以下为 2026-10-26 用 ModelBest API 跑的 **native** 协议 run（同一 `datasets/core.jsonl` 28 例），
> 与本次本地 **json** 协议不可直接横比：FRAMEWORK_ADAPTATION.md 已记录同一权重切换协议可差 8-14pp
> （MiniCPM5-2B：native 96.9% → json 83.1%）。此表只用于说明历史水位与端点/量化差异的量级。
> 原始文件来自历史工作副本 `/Users/cacinie/.zcode/workspace/draft-920f6705-a1a9-4e14-937f-734fa00bd06d/smab/runs`（未复制进本仓库 runs/）。

| model | 协议 | overall | perfect | cases | 平均请求延迟 ms | 来源 |
|---|---|---|---|---|---|---|
| MiniCPM5-2B | native | 96.9% | 92.9% | 28 | 1152 | 参考副本 `modelbest-MiniCPM5-2B-2026-10-26.json` |
| MiniCPM-V-4.7-1B | native | 79.2% | 64.3% | 28 | 1378 | 参考副本 `modelbest-MiniCPM-V-4.7-1B-2026-10-26.json` |
| MiniCPM-V-4.6 | native | 82.4% | 64.3% | 28 | 1192 | 参考副本 `modelbest-MiniCPM-V-4.6-2026-10-26.json` |
| MiniCPM-V-4.5 | native | 70.5% | 57.1% | 28 | 1367 | 参考副本 `modelbest-MiniCPM-V-4.5-2026-10-26.json` |

| model | relevance | selection | arguments | planning | state_tracking | recovery | stopping |
|---|---|---|---|---|---|---|---|
| MiniCPM5-2B | 100.0% | 92.1% | 96.4% | 100.0% | 100.0% | 100.0% | 97.6% |
| MiniCPM-V-4.7-1B | 50.0% | 87.6% | 90.2% | 87.0% | 60.0% | 45.8% | 78.0% |
| MiniCPM-V-4.6 | 33.3% | 84.9% | 90.9% | 100.0% | 80.0% | 75.0% | 83.9% |
| MiniCPM-V-4.5 | 66.7% | 50.0% | 60.9% | 72.2% | 60.0% | 75.0% | 93.0% |

**同模型差异归因（MiniCPM5-2B：本地 native 94.6% vs API 历史 native 96.9%）**：
数据集（core 28 例）、温度 0、schema variant 完全一致；差异来自部署栈——本地是 llama.cpp
（b1-a08ab75）+ Q8_0 量化 + `enable_thinking: false`，API 侧权重精度/模板/parser 不可见。
小 2.3pp overall（perfect 差 7.2pp）属部署栈差异，不能解释为模型能力差异，也不应改写成分数构造差异。

### 本地 native vs API 历史 native（同协议、同数据集）

> 本地 = llama.cpp + Q8_0（本次，thinking 默认关）；API = 2026-10-26 ModelBest 托管（权重精度/模板不可见）。

| model | 本地 native overall | API native overall | Δoverall | 本地 perfect | API perfect | Δperfect |
|---|---|---|---|---|---|---|
| MiniCPM5-2B | 94.6% | 96.9% | -2.3pp | 85.7% | 92.9% | -7.1pp |
| MiniCPM-V-4.7-1B | 86.4% | 79.2% | +7.2pp | 75.0% | 64.3% | +10.7pp |

- MiniCPM5-2B：本地 94.6% vs API 96.9%（−2.3pp），归因 Q8_0 量化 + llama.cpp 模板/parser + thinking off；同协议同数据集，差距小且方向合理。
- MiniCPM-V-4.7-1B：本地 86.4% vs API 79.2%（+7.2pp，perfect +10.7pp）。API 侧不可见配置（V4.7 倾向 thinking/长输出，历史 run 有 5 例 max_turns）更可能解释差异；这只说明**部署栈可造成同权重 7pp 级差异**，不能得出"Q8 优于托管 bf16"的结论。

## 9. 阻塞、无效 run 与异常

- 无接口错误、无阻塞端点；protocol_error 明细见第 5 节（属模型能力指标，非基础设施异常）

## 10. 复现命令

```bash
./smab/run_all.sh --status      # 端点就绪状态
./smab/run_all.sh               # 全部端点（先就绪先跑，单 run 串行；含 probe/json/native/constrained）
./smab/run_all.sh 8092 --force  # 重跑单个端点
smab/.venv/bin/python smab/summarize.py   # 重新生成本汇总
```

端点配置变更记录：8092 在 2026-11-06 首次跑（13:53–13:56）后由 llama-serve 关闭 thinking 并重启，
首跑结果归档在 `runs/archive/pre-stable-*`，主表使用重启后复测结果（配置与 8091/8093/8094 一致）。

## 11. 2026 ≤3B 双精度横评（Q8_0 vs F16/BF16）

> 范围：2026 年发布的 10 个 ≤3B 模型 × 两种精度（Q8_0 / F16·BF16），共 20 个端点；SMAB core 28 例、temperature 0、schema original，协议与首轮一致。
> Q8 端点：8101–8106（MiniCPM5-1B/2B、V4.7-1B、MNN-Pocket 的 Q8 沿用首轮 8091–8094 结果）；F16/BF16 端点：8111–8120。
> F16 大模型（2B/2.6B 级、约 5GB 权重）在 16GB 机器上逐个起停，轮询到就绪即跑；「未就绪」不计失败（`not_ready` 见第 9 节）。
> 三通道：**A** json prompt-only（`response_format: null`）、**B** json+约束解码（`response_format.json_object`）、**C** native（llama.cpp `--jinja`）；`—` 表示该通道未测/不支持。

### 11.1 三通道 × 精度总览（overall / perfect；Δ = F16 − Q8）

| model | Q8 A | F16 A | ΔA | Q8 B | F16 B | ΔB | Q8 C | F16 C | ΔC |
|---|---|---|---|---|---|---|---|---|---|
| Qwen3.5-0.8B | 32.5% / 3.6% | 31.0% / 0.0% | -1.5pp | 29.7% / 3.6% | 29.7% / 3.6% | -0.0pp | 83.8% / 71.4% | 81.5% / 67.9% | -2.3pp |
| Qwen3.5-2B | 74.4% / 14.3% | 72.6% / 10.7% | -1.8pp | 77.0% / 25.0% | 75.8% / 25.0% | -1.2pp | 89.9% / 78.6% | 89.9% / 78.6% | +0.0pp |
| LFM2.5-230M | 29.3% / 0.0% | 29.3% / 0.0% | +0.0pp | 33.5% / 0.0% | 38.9% / 0.0% | +5.4pp | 65.9% / 46.4% | 70.0% / 53.6% | +4.1pp |
| LFM2.5-1.2B | 37.3% / 7.1% | 37.3% / 7.1% | +0.0pp | 39.9% / 10.7% | 39.9% / 10.7% | +0.0pp | 81.0% / 53.6% | 81.2% / 53.6% | +0.1pp |
| LFM2.5-2.6B | 29.3% / 0.0% | 29.3% / 0.0% | +0.0pp | 29.3% / 0.0% | 29.3% / 0.0% | +0.0pp | 91.6% / 78.6% | 93.5% / 82.1% | +1.9pp |
| LFM2.5-350M | 30.3% / 3.6% | 29.9% / 3.6% | -0.4pp | 43.1% / 10.7% | 41.5% / 7.1% | -1.6pp | 72.6% / 46.4% | 73.5% / 46.4% | +0.8pp |
| MiniCPM5-1B | 35.3% / 3.6% | 35.8% / 7.1% | +0.5pp | 34.7% / 3.6% | 36.2% / 7.1% | +1.4pp | 83.8% / 60.7% | 84.7% / 60.7% | +0.9pp |
| MiniCPM5-2B | 44.5% / 7.1% | 43.7% / 7.1% | -0.8pp | 78.9% / 53.6% | 80.3% / 53.6% | +1.4pp | 94.6% / 85.7% | 96.7% / 89.3% | +2.1pp |
| MNN-Pocket-0.3B | 30.1% / 0.0% | 30.4% / 0.0% | +0.2pp | 28.1% / 0.0% | 28.4% / 0.0% | +0.2pp | — | — | — |
| MiniCPM-V-4.7-1B | 35.8% / 3.6% | 35.1% / 3.6% | -0.7pp | 40.9% / 10.7% | 40.9% / 10.7% | +0.0pp | 86.4% / 75.0% | 83.8% / 75.0% | -2.6pp |

**同模型 Q8 → F16 差值（Δoverall，按协议通道）**

- **Qwen3.5-0.8B**：A prompt-only -1.5pp，B 约束解码 -0.0pp，C native -2.3pp
- **Qwen3.5-2B**：A prompt-only -1.8pp，B 约束解码 -1.2pp，C native +0.0pp
- **LFM2.5-230M**：A prompt-only +0.0pp，B 约束解码 +5.4pp，C native +4.1pp
- **LFM2.5-1.2B**：A prompt-only +0.0pp，B 约束解码 +0.0pp，C native +0.1pp
- **LFM2.5-2.6B**：A prompt-only +0.0pp，B 约束解码 +0.0pp，C native +1.9pp
- **LFM2.5-350M**：A prompt-only -0.4pp，B 约束解码 -1.6pp，C native +0.8pp
- **MiniCPM5-1B**：A prompt-only +0.5pp，B 约束解码 +1.4pp，C native +0.9pp；Q8 沿用首轮 8091 结果
- **MiniCPM5-2B**：A prompt-only -0.8pp，B 约束解码 +1.4pp，C native +2.1pp；Q8 沿用首轮 8092 结果
- **MNN-Pocket-0.3B**：A prompt-only +0.2pp，B 约束解码 +0.2pp，C native —；Q8 用 8094；另有 MNN INT4 运行时 8090（仅 json）
- **MiniCPM-V-4.7-1B**：A prompt-only -0.7pp，B 约束解码 +0.0pp，C native -2.6pp；纯文本评测；Q8 沿用首轮 8093 结果

**横评结论（自动计算）**

- 同模型 Q8 → F16 的 native overall 差值：9 对，均值 +0.6pp，最大绝对差 4.1pp。
- prompt-only 通道差值：10 对，均值 -0.4pp，最大绝对差 1.8pp。
- 约束解码通道差值：10 对，均值 +0.6pp，最大绝对差 5.4pp。
- **结论**：精度（Q8_0 vs F16/BF16）对 SMAB 分数影响在噪声量级；真正的分水岭是**协议通道**（native vs 文本 JSON）与**模型对既定协议的遵循**（LFM 专属语法、0.3B 键漂移）。

### 11.2 七维分数（每模型 × 精度 × 通道一行）

| model | 精度 | 协议 | relevance | selection | arguments | planning | state_tracking | recovery | stopping |
|---|---|---|---|---|---|---|---|---|---|
| Qwen3.5-0.8B | Q8_0 | native | 66.7% | 88.1% | 86.2% | 83.3% | 66.7% | 58.3% | 86.2% |
| Qwen3.5-0.8B | Q8_0 | json-constrained | 33.3% | 1.6% | 17.4% | 16.7% | 6.7% | 25.0% | 62.1% |
| Qwen3.5-0.8B | Q8_0 | json | 50.0% | 1.6% | 17.4% | 11.1% | 6.7% | 25.0% | 65.7% |
| Qwen3.5-0.8B | F16 | native | 66.7% | 88.1% | 86.2% | 83.3% | 60.0% | 58.3% | 85.6% |
| Qwen3.5-0.8B | F16 | json-constrained | 33.3% | 4.4% | 21.7% | 22.2% | 6.7% | 25.0% | 56.1% |
| Qwen3.5-0.8B | F16 | json | 50.0% | 1.6% | 17.4% | 11.1% | 6.7% | 25.0% | 60.0% |
| Qwen3.5-2B | Q8_0 | native | 50.0% | 93.4% | 98.6% | 100.0% | 93.3% | 100.0% | 87.5% |
| Qwen3.5-2B | Q8_0 | json-constrained | 83.3% | 86.9% | 79.7% | 72.2% | 53.3% | 37.5% | 82.7% |
| Qwen3.5-2B | Q8_0 | json | 83.3% | 86.9% | 77.5% | 61.1% | 53.3% | 37.5% | 78.3% |
| Qwen3.5-2B | F16 | native | 50.0% | 93.4% | 98.6% | 100.0% | 93.3% | 100.0% | 87.5% |
| Qwen3.5-2B | F16 | json-constrained | 83.3% | 86.9% | 75.4% | 72.2% | 53.3% | 37.5% | 83.9% |
| Qwen3.5-2B | F16 | json | 83.3% | 86.9% | 73.2% | 61.1% | 53.3% | 37.5% | 78.3% |
| LFM2.5-230M | Q8_0 | native | 66.7% | 56.0% | 56.5% | 22.2% | 26.7% | 6.2% | 97.9% |
| LFM2.5-230M | Q8_0 | json-constrained | 33.3% | 20.2% | 37.7% | 20.4% | 6.7% | 8.3% | 48.7% |
| LFM2.5-230M | Q8_0 | json | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 66.4% |
| LFM2.5-230M | F16 | native | 66.7% | 63.1% | 60.9% | 22.2% | 40.0% | 6.2% | 98.8% |
| LFM2.5-230M | F16 | json-constrained | 50.0% | 21.8% | 37.7% | 20.4% | 13.3% | 8.3% | 58.5% |
| LFM2.5-230M | F16 | json | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 66.4% |
| LFM2.5-1.2B | Q8_0 | native | 50.0% | 88.8% | 83.0% | 79.6% | 63.3% | 56.2% | 91.1% |
| LFM2.5-1.2B | Q8_0 | json-constrained | 66.7% | 0.0% | 2.2% | 5.6% | 13.3% | 6.2% | 98.4% |
| LFM2.5-1.2B | Q8_0 | json | 66.7% | 0.0% | 2.2% | 5.6% | 6.7% | 6.2% | 92.9% |
| LFM2.5-1.2B | F16 | native | 50.0% | 90.0% | 83.0% | 79.6% | 63.3% | 56.2% | 91.1% |
| LFM2.5-1.2B | F16 | json-constrained | 66.7% | 0.0% | 2.2% | 5.6% | 13.3% | 6.2% | 98.4% |
| LFM2.5-1.2B | F16 | json | 66.7% | 0.0% | 2.2% | 5.6% | 6.7% | 6.2% | 92.9% |
| LFM2.5-2.6B | Q8_0 | native | 83.3% | 93.9% | 95.7% | 94.4% | 86.7% | 81.2% | 90.5% |
| LFM2.5-2.6B | Q8_0 | json-constrained | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 66.4% |
| LFM2.5-2.6B | Q8_0 | json | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 66.4% |
| LFM2.5-2.6B | F16 | native | 100.0% | 95.7% | 95.7% | 94.4% | 86.7% | 81.2% | 92.9% |
| LFM2.5-2.6B | F16 | json-constrained | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 66.4% |
| LFM2.5-2.6B | F16 | json | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 66.4% |
| LFM2.5-350M | Q8_0 | native | 50.0% | 68.7% | 72.5% | 40.7% | 43.3% | 20.8% | 95.2% |
| LFM2.5-350M | Q8_0 | json-constrained | 50.0% | 20.6% | 34.8% | 27.8% | 6.7% | 14.6% | 79.2% |
| LFM2.5-350M | Q8_0 | json | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 68.8% |
| LFM2.5-350M | F16 | native | 50.0% | 71.4% | 73.6% | 46.3% | 43.3% | 20.8% | 95.2% |
| LFM2.5-350M | F16 | json-constrained | 50.0% | 15.1% | 37.0% | 33.3% | 6.7% | 31.2% | 72.0% |
| LFM2.5-350M | F16 | json | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 67.6% |
| MiniCPM5-1B | Q8_0 | native | 66.7% | 93.4% | 89.9% | 77.8% | 60.0% | 64.6% | 91.7% |
| MiniCPM5-1B | Q8_0 | json-constrained | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 85.6% |
| MiniCPM5-1B | Q8_0 | json | 66.7% | 0.0% | 0.0% | 0.0% | 20.0% | 0.0% | 83.7% |
| MiniCPM5-1B | F16 | native | 66.7% | 92.0% | 90.6% | 79.6% | 66.7% | 45.8% | 91.7% |
| MiniCPM5-1B | F16 | json-constrained | 66.7% | 0.0% | 0.0% | 0.0% | 13.3% | 0.0% | 90.4% |
| MiniCPM5-1B | F16 | json | 66.7% | 0.0% | 0.0% | 0.0% | 20.0% | 0.0% | 84.9% |
| MiniCPM5-2B | Q8_0 | native | 100.0% | 92.9% | 92.8% | 100.0% | 93.3% | 93.8% | 96.4% |
| MiniCPM5-2B | Q8_0 | json-constrained | 83.3% | 70.4% | 78.3% | 100.0% | 33.3% | 93.8% | 96.0% |
| MiniCPM5-2B | Q8_0 | json | 66.7% | 21.6% | 17.4% | 53.7% | 33.3% | 25.0% | 73.0% |
| MiniCPM5-2B | F16 | native | 100.0% | 92.9% | 95.7% | 100.0% | 100.0% | 100.0% | 96.4% |
| MiniCPM5-2B | F16 | json-constrained | 100.0% | 70.4% | 78.3% | 100.0% | 33.3% | 87.5% | 97.2% |
| MiniCPM5-2B | F16 | json | 66.7% | 21.6% | 17.4% | 53.7% | 26.7% | 25.0% | 74.2% |
| MNN-Pocket-0.3B | Q8_0 | json-constrained | 50.0% | 0.0% | 8.0% | 11.1% | 6.7% | 12.5% | 60.0% |
| MNN-Pocket-0.3B | Q8_0 | json | 50.0% | 0.0% | 8.0% | 11.1% | 6.7% | 12.5% | 64.8% |
| MNN-Pocket-0.3B | F16 | json-constrained | 50.0% | 0.0% | 8.0% | 11.1% | 6.7% | 12.5% | 61.2% |
| MNN-Pocket-0.3B | F16 | json | 50.0% | 0.0% | 8.0% | 11.1% | 6.7% | 12.5% | 66.0% |
| MiniCPM-V-4.7-1B | Q8_0 | native | 50.0% | 92.9% | 92.8% | 87.0% | 73.3% | 56.2% | 94.6% |
| MiniCPM-V-4.7-1B | Q8_0 | json-constrained | 66.7% | 2.9% | 8.7% | 11.1% | 20.0% | 0.0% | 91.2% |
| MiniCPM-V-4.7-1B | Q8_0 | json | 33.3% | 2.6% | 7.2% | 13.0% | 20.0% | 6.2% | 81.7% |
| MiniCPM-V-4.7-1B | F16 | native | 50.0% | 92.9% | 94.2% | 92.6% | 66.7% | 62.5% | 85.1% |
| MiniCPM-V-4.7-1B | F16 | json-constrained | 66.7% | 2.9% | 8.7% | 11.1% | 20.0% | 0.0% | 91.2% |
| MiniCPM-V-4.7-1B | F16 | json | 33.3% | 0.0% | 4.3% | 5.6% | 20.0% | 6.2% | 84.6% |

### 11.3 core / OOD 与 by_horizon

| model | 精度 | 协议 | core | OOD | h=0 | h=1 | h=2 | h=3+ |
|---|---|---|---|---|---|---|---|---|
| Qwen3.5-0.8B | Q8_0 | native | 86.9% | 78.8% | 63.9% | 94.8% | 66.7% | 100.0% |
| Qwen3.5-0.8B | Q8_0 | json-constrained | 24.5% | 37.8% | 44.5% | 31.0% | 22.9% | 15.0% |
| Qwen3.5-0.8B | Q8_0 | json | 28.7% | 38.3% | 62.5% | 31.0% | 23.6% | 15.0% |
| Qwen3.5-0.8B | F16 | native | 86.9% | 73.0% | 47.9% | 94.8% | 66.7% | 100.0% |
| Qwen3.5-0.8B | F16 | json-constrained | 22.5% | 40.9% | 44.5% | 29.5% | 26.7% | 12.2% |
| Qwen3.5-0.8B | F16 | json | 27.4% | 36.6% | 62.2% | 29.5% | 21.7% | 12.2% |
| Qwen3.5-2B | Q8_0 | native | 96.8% | 79.1% | 59.0% | 95.3% | 94.3% | 95.2% |
| Qwen3.5-2B | Q8_0 | json-constrained | 75.4% | 79.4% | 69.1% | 85.1% | 72.3% | 48.0% |
| Qwen3.5-2B | Q8_0 | json | 71.7% | 78.7% | 69.1% | 83.8% | 64.8% | 48.0% |
| Qwen3.5-2B | F16 | native | 96.8% | 79.1% | 59.0% | 95.3% | 94.3% | 95.2% |
| Qwen3.5-2B | F16 | json-constrained | 73.4% | 79.4% | 69.1% | 82.9% | 72.3% | 48.0% |
| Qwen3.5-2B | F16 | json | 68.7% | 78.7% | 69.1% | 80.5% | 64.8% | 48.0% |
| LFM2.5-230M | Q8_0 | native | 70.7% | 58.5% | 80.6% | 80.7% | 30.9% | 48.0% |
| LFM2.5-230M | Q8_0 | json-constrained | 32.5% | 35.0% | 27.4% | 42.8% | 23.2% | 12.4% |
| LFM2.5-230M | Q8_0 | json | 28.2% | 30.9% | 87.2% | 22.8% | 15.1% | 12.2% |
| LFM2.5-230M | F16 | native | 75.5% | 61.5% | 88.9% | 86.1% | 30.9% | 48.0% |
| LFM2.5-230M | F16 | json-constrained | 39.8% | 37.5% | 49.6% | 45.1% | 27.0% | 12.4% |
| LFM2.5-230M | F16 | json | 28.2% | 30.9% | 87.2% | 22.8% | 15.1% | 12.2% |
| LFM2.5-1.2B | Q8_0 | native | 84.9% | 75.1% | 59.0% | 93.1% | 68.7% | 78.2% |
| LFM2.5-1.2B | Q8_0 | json-constrained | 39.0% | 41.4% | 91.7% | 35.4% | 26.2% | 18.3% |
| LFM2.5-1.2B | Q8_0 | json | 37.3% | 37.3% | 87.5% | 32.1% | 25.2% | 18.3% |
| LFM2.5-1.2B | F16 | native | 84.9% | 75.5% | 59.0% | 93.3% | 68.7% | 78.2% |
| LFM2.5-1.2B | F16 | json-constrained | 39.0% | 41.4% | 91.7% | 35.4% | 26.2% | 18.3% |
| LFM2.5-1.2B | F16 | json | 37.3% | 37.3% | 87.5% | 32.1% | 25.2% | 18.3% |
| LFM2.5-2.6B | Q8_0 | native | 94.9% | 86.7% | 80.5% | 96.2% | 87.2% | 95.2% |
| LFM2.5-2.6B | Q8_0 | json-constrained | 28.2% | 30.9% | 87.2% | 22.8% | 15.1% | 12.2% |
| LFM2.5-2.6B | Q8_0 | json | 28.2% | 30.9% | 87.2% | 22.8% | 15.1% | 12.2% |
| LFM2.5-2.6B | F16 | native | 97.4% | 87.6% | 88.9% | 96.4% | 88.2% | 100.0% |
| LFM2.5-2.6B | F16 | json-constrained | 28.2% | 30.9% | 87.2% | 22.8% | 15.1% | 12.2% |
| LFM2.5-2.6B | F16 | json | 28.2% | 30.9% | 87.2% | 22.8% | 15.1% | 12.2% |
| LFM2.5-350M | Q8_0 | native | 78.4% | 63.7% | 77.8% | 87.1% | 48.1% | 39.7% |
| LFM2.5-350M | Q8_0 | json-constrained | 40.3% | 47.5% | 53.5% | 47.0% | 35.9% | 18.3% |
| LFM2.5-350M | Q8_0 | json | 29.9% | 30.9% | 91.3% | 23.5% | 15.1% | 12.2% |
| LFM2.5-350M | F16 | native | 78.5% | 65.7% | 77.8% | 87.2% | 51.2% | 39.7% |
| LFM2.5-350M | F16 | json-constrained | 37.6% | 47.5% | 53.5% | 43.1% | 37.8% | 18.3% |
| LFM2.5-350M | F16 | json | 29.2% | 30.9% | 91.3% | 22.8% | 15.1% | 12.2% |
| MiniCPM5-1B | Q8_0 | native | 86.6% | 79.4% | 77.8% | 92.0% | 69.3% | 85.2% |
| MiniCPM5-1B | Q8_0 | json-constrained | 34.7% | 34.8% | 84.7% | 30.9% | 19.1% | 18.3% |
| MiniCPM5-1B | Q8_0 | json | 34.7% | 36.3% | 90.3% | 30.0% | 20.1% | 18.3% |
| MiniCPM5-1B | F16 | native | 88.2% | 79.4% | 77.8% | 92.0% | 76.4% | 73.4% |
| MiniCPM5-1B | F16 | json-constrained | 36.6% | 35.4% | 87.5% | 32.4% | 20.1% | 18.3% |
| MiniCPM5-1B | F16 | json | 36.0% | 35.7% | 93.1% | 30.7% | 19.1% | 18.3% |
| MiniCPM5-2B | Q8_0 | native | 93.1% | 96.8% | 100.0% | 92.2% | 95.0% | 100.0% |
| MiniCPM5-2B | Q8_0 | json-constrained | 75.6% | 84.1% | 72.2% | 74.8% | 93.1% | 73.6% |
| MiniCPM5-2B | Q8_0 | json | 43.8% | 45.6% | 84.7% | 29.7% | 52.7% | 47.2% |
| MiniCPM5-2B | F16 | native | 95.1% | 99.1% | 100.0% | 94.4% | 98.6% | 100.0% |
| MiniCPM5-2B | F16 | json-constrained | 78.2% | 83.6% | 83.3% | 74.8% | 92.4% | 73.6% |
| MiniCPM5-2B | F16 | json | 42.5% | 45.6% | 79.2% | 29.7% | 52.7% | 47.2% |
| MNN-Pocket-0.3B | Q8_0 | json-constrained | 29.9% | 25.3% | 56.6% | 28.5% | 15.7% | 12.2% |
| MNN-Pocket-0.3B | Q8_0 | json | 31.1% | 28.6% | 56.6% | 30.7% | 18.9% | 12.2% |
| MNN-Pocket-0.3B | F16 | json-constrained | 29.2% | 27.2% | 56.6% | 28.5% | 16.7% | 12.2% |
| MNN-Pocket-0.3B | F16 | json | 31.1% | 29.2% | 56.6% | 30.7% | 19.8% | 12.2% |
| MiniCPM-V-4.7-1B | Q8_0 | native | 89.0% | 82.3% | 50.7% | 97.0% | 89.3% | 68.0% |
| MiniCPM-V-4.7-1B | Q8_0 | json-constrained | 40.4% | 41.6% | 91.7% | 37.0% | 26.6% | 18.3% |
| MiniCPM-V-4.7-1B | Q8_0 | json | 34.8% | 37.4% | 62.5% | 37.0% | 21.0% | 25.3% |
| MiniCPM-V-4.7-1B | F16 | native | 89.0% | 75.6% | 36.8% | 97.0% | 86.7% | 68.0% |
| MiniCPM-V-4.7-1B | F16 | json-constrained | 40.4% | 41.6% | 91.7% | 37.0% | 26.6% | 18.3% |
| MiniCPM-V-4.7-1B | F16 | json | 34.0% | 37.0% | 62.5% | 36.7% | 21.0% | 18.3% |

### 11.4 protocol_error / 延迟 / token 用量

| model | 精度 | 协议 | protocol_error | 平均请求延迟 ms | 请求数 | tokens 总量 | tok/case |
|---|---|---|---|---|---|---|---|
| Qwen3.5-0.8B | Q8_0 | native | 0/28 | 669 | 78 | 47,678 | 1703 |
| Qwen3.5-0.8B | Q8_0 | json-constrained | 12/28 | 679 | 71 | 34,622 | 1236 |
| Qwen3.5-0.8B | Q8_0 | json | 13/28 | 704 | 63 | 31,758 | 1134 |
| Qwen3.5-0.8B | F16 | native | 0/28 | 1654 | 78 | 48,187 | 1721 |
| Qwen3.5-0.8B | F16 | json-constrained | 17/28 | 1619 | 71 | 35,841 | 1280 |
| Qwen3.5-0.8B | F16 | json | 20/28 | 2056 | 57 | 27,578 | 985 |
| Qwen3.5-2B | Q8_0 | native | 0/28 | 1242 | 77 | 45,572 | 1628 |
| Qwen3.5-2B | Q8_0 | json-constrained | 13/28 | 800 | 55 | 18,822 | 672 |
| Qwen3.5-2B | Q8_0 | json | 17/28 | 788 | 54 | 18,445 | 659 |
| Qwen3.5-2B | F16 | native | 0/28 | 2234 | 77 | 45,645 | 1630 |
| Qwen3.5-2B | F16 | json-constrained | 12/28 | 1495 | 54 | 18,539 | 662 |
| Qwen3.5-2B | F16 | json | 17/28 | 1306 | 53 | 18,138 | 648 |
| LFM2.5-230M | Q8_0 | native | 0/28 | 132 | 46 | 14,009 | 500 |
| LFM2.5-230M | Q8_0 | json-constrained | 9/28 | 175 | 110 | 63,807 | 2279 |
| LFM2.5-230M | Q8_0 | json | 28/28 | 144 | 28 | 8,827 | 315 |
| LFM2.5-230M | F16 | native | 0/28 | 191 | 47 | 14,247 | 509 |
| LFM2.5-230M | F16 | json-constrained | 10/28 | 288 | 89 | 51,261 | 1831 |
| LFM2.5-230M | F16 | json | 28/28 | 296 | 28 | 8,826 | 315 |
| LFM2.5-1.2B | Q8_0 | native | 0/28 | 669 | 67 | 20,577 | 735 |
| LFM2.5-1.2B | Q8_0 | json-constrained | 0/28 | 632 | 29 | 9,136 | 326 |
| LFM2.5-1.2B | Q8_0 | json | 5/28 | 775 | 29 | 9,265 | 331 |
| LFM2.5-1.2B | F16 | native | 0/28 | 886 | 66 | 20,173 | 720 |
| LFM2.5-1.2B | F16 | json-constrained | 0/28 | 652 | 29 | 9,116 | 326 |
| LFM2.5-1.2B | F16 | json | 5/28 | 899 | 29 | 9,242 | 330 |
| LFM2.5-2.6B | Q8_0 | native | 0/28 | 4322 | 77 | 34,116 | 1218 |
| LFM2.5-2.6B | Q8_0 | json-constrained | 28/28 | 4503 | 28 | 11,016 | 393 |
| LFM2.5-2.6B | Q8_0 | json | 28/28 | 5856 | 28 | 10,836 | 387 |
| LFM2.5-2.6B | F16 | native | 0/28 | 9351 | 67 | 28,800 | 1029 |
| LFM2.5-2.6B | F16 | json-constrained | 28/28 | 11332 | 28 | 10,952 | 391 |
| LFM2.5-2.6B | F16 | json | 28/28 | 7773 | 28 | 10,831 | 387 |
| LFM2.5-350M | Q8_0 | native | 0/28 | 208 | 57 | 16,852 | 602 |
| LFM2.5-350M | Q8_0 | json-constrained | 0/28 | 175 | 70 | 38,689 | 1382 |
| LFM2.5-350M | Q8_0 | json | 26/28 | 260 | 28 | 8,779 | 314 |
| LFM2.5-350M | F16 | native | 0/28 | 287 | 57 | 16,793 | 600 |
| LFM2.5-350M | F16 | json-constrained | 0/28 | 311 | 82 | 47,322 | 1690 |
| LFM2.5-350M | F16 | json | 27/28 | 258 | 28 | 8,789 | 314 |
| MiniCPM5-1B | Q8_0 | native | 0/28 | 899 | 68 | 35,123 | 1254 |
| MiniCPM5-1B | Q8_0 | json-constrained | 10/28 | 420 | 28 | 7,925 | 283 |
| MiniCPM5-1B | Q8_0 | json | 13/28 | 640 | 28 | 8,534 | 305 |
| MiniCPM5-1B | F16 | native | 0/28 | 1385 | 68 | 35,925 | 1283 |
| MiniCPM5-1B | F16 | json-constrained | 6/28 | 557 | 28 | 7,902 | 282 |
| MiniCPM5-1B | F16 | json | 11/28 | 760 | 28 | 8,096 | 289 |
| MiniCPM5-2B | Q8_0 | native | 0/28 | 1198 | 67 | 30,741 | 1098 |
| MiniCPM5-2B | Q8_0 | json-constrained | 0/28 | 862 | 59 | 21,078 | 753 |
| MiniCPM5-2B | Q8_0 | json | 21/28 | 957 | 40 | 13,548 | 484 |
| MiniCPM5-2B | F16 | native | 0/28 | 2005 | 68 | 31,435 | 1123 |
| MiniCPM5-2B | F16 | json-constrained | 0/28 | 1473 | 58 | 20,697 | 739 |
| MiniCPM5-2B | F16 | json | 20/28 | 1841 | 40 | 13,531 | 483 |
| MNN-Pocket-0.3B | Q8_0 | json-constrained | 18/28 | 326 | 64 | 31,819 | 1136 |
| MNN-Pocket-0.3B | Q8_0 | json | 20/28 | 283 | 53 | 23,296 | 832 |
| MNN-Pocket-0.3B | F16 | json-constrained | 17/28 | 411 | 64 | 30,326 | 1083 |
| MNN-Pocket-0.3B | F16 | json | 19/28 | 396 | 52 | 22,743 | 812 |
| MiniCPM-V-4.7-1B | Q8_0 | native | 0/28 | 787 | 64 | 36,282 | 1296 |
| MiniCPM-V-4.7-1B | Q8_0 | json-constrained | 0/28 | 596 | 42 | 17,939 | 641 |
| MiniCPM-V-4.7-1B | Q8_0 | json | 9/28 | 575 | 39 | 15,225 | 544 |
| MiniCPM-V-4.7-1B | F16 | native | 0/28 | 1289 | 80 | 52,821 | 1886 |
| MiniCPM-V-4.7-1B | F16 | json-constrained | 0/28 | 855 | 42 | 17,949 | 641 |
| MiniCPM-V-4.7-1B | F16 | json | 10/28 | 876 | 32 | 9,770 | 349 |

**参考：MNN-Pocket-0.3B 的 MNN INT4 运行时（:8090，第三个精度点）**

- json prompt-only：overall 29.2%、perfect 0.0%、protocol_error 16/28、平均请求延迟 646 ms；MNN shim 不支持 `response_format`，无约束/native 通道。

**口径说明**

- Q8 与 F16 使用同一 GGUF 家族、同一 llama.cpp（b1-a08ab75）、同一 chat template 设置与解码参数，只变权重精度；
- 延迟/tok-s 受并发下载与其他运行时影响（loadavg 见第 4 节），**不可用来比较 Q8 与 F16 的推理速度性能**，需安静窗口复测；
- native 通道仅对 probe `native_tool_calling=yes` 的端点运行，未跑的端点在该栏显示 `—`，不是 0 分；
- F16 大模型逐个起停：未就绪端点记 `not_ready`（第 9 节），不记为失败。

- Qwen3.5 系列是 hybrid SSM 架构（24 层 = 6 full-attn + 18 线性层），该 llama.cpp build 上 `-ngl 99` 会占用 6-7.7GB host buffer，8101 已改用 `-ngl 22` 并**整组重跑**（Q8 数据以重跑为准）；部分 offload 的 GPU/CPU 数值差异会让 greedy 结果有 ±3pp 级抖动，属实现细节，不是能力变化。
- Qwen3.5 系列内存行为：启动约 229MB，单轮 SMAB 评测后最高观测 7.3GB —— 是该 llama.cpp build 对 hybrid SSM 的 host buffer 累积，端点空闲后由 llama-serve 重启回收，**不影响质量分数**；LFM2.5 系列 100–500MB 稳定。


# MiniCPM 本地 r3 批次（2026-11-16，repeats=3 与吞吐）

本目录记录 **MiniCPM5-2B 与 MiniCPM-V-4.7-1B 全量 F16（非量化）** 在 llama.cpp 1.0.0 + Metal 上的 SMAB 实测。与 [`local-edge-2026-11-06`](../local-edge-2026-11-06/) 批次互补：那一批是单遍 temp=0 的三通道（A/B/C）切分，本批是仓库 v0.2.0 `--repeats 3` 协议的**首批本地数据**（均值 ± 标准差 + pass^k），并补充 extra 13 例回归集与端侧吞吐。不是 API 榜单数据，不应与主榜混算。

## 环境

| 项 | 值 |
|---|---|
| 硬件 | Apple M5 Max，64GB 统一内存，macOS（darwin 27.0.0 arm64） |
| 运行时 | llama.cpp 1.0.0（build 11669, commit 620d2225c，brew，Metal，`-ngl 999 -c 16384 --jinja`） |
| 权重 | [openbmb/MiniCPM5-2B-GGUF](https://huggingface.co/openbmb/MiniCPM5-2B-GGUF) F16（5039MB）；[openbmb/MiniCPM-V-4.7-1B-gguf](https://huggingface.co/openbmb/MiniCPM-V-4.7-1B-gguf) F16（2024MB）+ mmproj-f16（1110MB，root 版 thinking 关闭） |
| 基准 | `datasets/core.jsonl`（28 episodes）与 `datasets/minicpm47_extra.jsonl`（13 episodes） |
| 协议 | temperature 0（greedy）、seed 0、`--repeats 3`、schema variant original；通道 = native（`tools`/`tool_calls`）与 json（schema 注入 system prompt + `response_format={"type":"json_object"}`） |

## 结果总表

| 模型 | 通道 | core（28 例） | extra（13 例） | 吞吐 |
|---|---|---|---|---|
| MiniCPM5-2B | native | **96.1% ± 0.8**（pass³ 85.7%） | **97.6% ± 0.0** | ≈87 tok/s |
| MiniCPM5-2B | json | 87.3% ± 0.3 | 95.3% ± 0.0 | ≈87 tok/s |
| MiniCPM-V-4.7-1B | native | 85.8% ± 0.0（pass³ 75.0%） | 89.2% ± 0.0 | ≈161 tok/s |
| MiniCPM-V-4.7-1B | json | 40.9% ± 0.0 | 58.6% ± 0.0 | ≈161 tok/s |

## 关键结论

- **MiniCPM5-2B（XML 工具格式）native 无短板维度**（最低 selection 93.4%；recovery/planning/relevance 均满分）。与 11-06 批次的 F16 单遍 96.7% 交叉一致。
- **MiniCPM-V-4.7-1B native 的断裂点在 relevance（50%）与 recovery（62.5%）**：该不调用/该追问时倾向直接调用、可恢复错误后调整不足；`by_horizon` 0 段仅 50.7%。
- **协议通道再次验证为独立变量**：1B 的 json 通道整体崩塌（core 40.9%，与 11-06 批次 B 通道 40.9 完全一致）——arguments 8.7%、selection 2.9%，该模型未针对 SMAB json 协议训练，此分数只反映协议适配性；2B json 主要丢 state_tracking（46.7%）与 3+ 长任务（48.3%）。
- **probe 先行**：两枚模型端点分别 10 ok / 2 unsupported（2B，缺 vLLM 方言结构化输出，llama.cpp 正常）与 12 ok / 0（1B），`smab probe` 判定与最终通道可用性一致。
- **pass^k = perfect-case rate**（temp 0 下三遍几乎全同）：2B native pass³ 85.7%、1B native pass³ 75.0%，重复标准差 ≤0.8pp，本地 F16 推理在该协议下高度确定。

## 与 11-06 批次对照（F16 列）

| 模型 | 11-06 单遍 C native | 本批 native r3 | 11-06 B 约束 | 本批 json r3 |
|---|---:|---:|---:|---:|
| MiniCPM5-2B | 96.7 | 96.1 ± 0.8 | 80.3 | 87.3 ± 0.3 |
| MiniCPM-V-4.7-1B | 83.8 | 85.8 ± 0.0 | 40.9 | 40.9 ± 0.0 |

> 注：11-06 批次硬件为 Apple M4/16GB、llama.cpp 0.7.0-dev；本批为 M5 Max/64GB、llama.cpp 1.0.0 stable。1B native +2.0pp、2B native −0.6pp，均在运行时/硬件差异噪声内。

## 文件

- `summary.json` / `summary.md`：聚合分数（均值、标准差、pass^k、维度、切片、吞吐）。
- `runs/*.json.gz`：10 个原始 run / probe 文件（gzip）。
- `REPORT.md`：完整报告。

## 复现

```bash
# 服务端（每模型一个端口）
llama-server -m MiniCPM5-2B-F16.gguf --jinja -ngl 999 -c 16384 --port 8801 --alias MiniCPM5-2B --no-webui
llama-server -m MiniCPM-V-4_7-1B-F16.gguf --mmproj mmproj-model-f16.gguf --jinja -ngl 999 -c 16384 --port 8802 --alias MiniCPM-V-4.7-1B --no-webui

smab probe --model MiniCPM5-2B --base-url http://127.0.0.1:8801/v1
smab run --model MiniCPM5-2B --base-url http://127.0.0.1:8801/v1 \
  --tool-format native --schema-variant original --temperature 0 --seed 0 --repeats 3 \
  --output runs/MiniCPM5-2B-native-r3.json --report runs/MiniCPM5-2B-native-r3.md
# extra 数据集：追加 --dataset datasets/minicpm47_extra.jsonl
```

# Small Model Agent Bench（SMAB）

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

一个面向 **0.3B–7B 小模型**的可执行工具调用测试套件。它不只检查 JSON 是否合法，而是测量模型在任务熵升高时，能力从哪里开始断裂。

> 核心假设：边界由 **歧义程度 × 动作空间 × 任务长度 × 分布偏移**共同决定。小模型适合做可验证的 agent 器官；是否能承担整个控制环，需要逐维度、逐 horizon 实测。

## 测什么

| 维度 | 关键问题 | 典型失败 |
|---|---|---|
| relevance | 现在该不该调用工具？缺参时是否先追问？ | 过度调用、猜参数 |
| selection | 相似工具中选哪个？ | 天气预报/历史气候混淆 |
| arguments | 参数抽取、类型和规范化是否正确？ | 日期、负数、ISO code 错误 |
| planning | 调用顺序及数据依赖是否正确？ | 未取得 ID 就执行下一步 |
| state tracking | 是否真正使用了工具返回值？ | 最终答案丢失状态码 |
| recovery | 超时、空结果、售罄后能否调整？ | 机械重试或直接放弃 |
| stopping | 成功或不可恢复错误后是否停下？ | 重复发信、重复取消 |

首批内置 28 个中英双语 episode，覆盖 core/OOD、0/1/2/3+ 预期调用长度、相似工具干扰、并行调用、缺参追问、瞬时和终止错误。工具全部由本地 fixture 模拟，运行 benchmark **不会产生真实副作用**。

这不是 BFCL 的替代品。BFCL 适合完整、标准化的 function-calling 横评；SMAB 更偏向小模型微调迭代：案例短小可改、执行环境确定、维度归因明确，并能直接测试 schema 扰动。设计参考了 [Berkeley Function Calling Leaderboard](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard) 对 simple、multiple、parallel、relevance、multi-turn/multi-step 与格式敏感性的拆分。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

# 先校验数据集
smab validate

# 测原生 function calling（vLLM、SGLang、llama.cpp 等兼容接口）
smab run \
  --model your-model \
  --base-url http://127.0.0.1:8000/v1 \
  --tool-format native \
  --output runs/your-model-native.json \
  --report runs/your-model-native.md
```

如果接口需要密钥，默认从 `SMAB_API_KEY` 读取；可用 `--api-key-env` 改成别的环境变量名。密钥不会写入结果文件。

### 没有原生 function calling token 的模型

`json` 模式会把工具 schema 写进 system prompt，并要求模型只输出下面两种对象之一：

```json
{"tool_calls":[{"name":"get_weather","arguments":{"city":"上海","date":"2026-09-06"}}]}
```

```json
{"final":"上海当天最高 29°C。"}
```

运行：

```bash
smab run \
  --model your-sft-model \
  --base-url http://127.0.0.1:8000/v1 \
  --tool-format json \
  --output runs/your-model-json.json
```

服务端若支持 JSON Schema/grammar 约束，可以通过 `--extra-body` 传入对应采样参数；这样能把格式容量和语义容量分开观察。

## 三组必须跑的对照

同一个模型至少跑下面三次：

```bash
smab run --model your-model --schema-variant original --output runs/original.json
smab run --model your-model --schema-variant shuffled --output runs/shuffled.json
smab run --model your-model --schema-variant aliased  --output runs/aliased.json
```

- `original`：原始工具名和顺序；
- `shuffled`：确定性打乱工具列表，测位置偏差；
- `aliased`：把工具名改成 `fn_01` 一类中性名称、保留描述，测模型是在读语义还是背工具名。

建议同时比较 `native` 与 `json` 两种格式。如果 JSON 约束后 arguments 明显提升，但 relevance/recovery 没提升，问题主要不在语法层。

## 只跑一个切片

```bash
# OOD recovery
smab run --model your-model --split ood --category recovery

# 单个案例，适合微调期间快速回归
smab run --model your-model --case-id recover_003

# 多次提供 --category 或 --case-id 可取并集
smab run --model your-model --category relevance --category stopping
```

## 结果怎么读

JSON 保存完整调用轨迹、工具输出、停止原因、endpoint usage 与逐维度分数；Markdown 报告展示：

- overall 和 perfect-case rate；
- 七项能力分数；
- core/OOD 差值；
- 按预期调用长度 0/1/2/3+ 的分数；
- 最低分案例。

overall 是该案例声明的维度均值，范围 0–1。`success` 只在所有受测维度满分时为真，因此它比宽松的平均分更能暴露长链条中的单点断裂。

如果每步独立正确率为 `p`，长度为 `h` 的整条轨迹上限约为 `p^h`。所以请重点看 `by_horizon`，不要只比较单步 selection accuracy。

## 基线（2026-08-31 实测）

以下数字来自 **28 个 episode、temp=0 单遍、native 通道**，覆盖 AI Ping / ModelBest / OpenRouter 三平台共 52 个 run（2026-08-31）。`perfect` 为所有受测维度满分的案例比例，与结果文件中的 `success` 同义。

| # | 模型 | 平台 | overall | perfect | 输入/输出 ¥/Mtok | 平均延迟 |
|---|---|---|---|---|---|---|
| 1 | Qwen3.5-27B (2026) | AI Ping | **100.0%** | 100.0% | 0.6 / 4.8 | 9.0s |
| 2 | cohere/north-mini-code:free | OpenRouter | 99.6% | 96.4% | 免费 | 5.5s |
| 3 | Qwen3.8-27B (2026) | AI Ping | 98.3% | 92.9% | 3 / 12 | 5.4s |
| 4 | Step-3.5-Flash (2026) | AI Ping | 97.3% | 92.9% | 0.7 / 2.1 | 4.2s |
| 5 | MiniCPM5-2B-0822 | ModelBest | 96.9% | 92.9% | 面壁定价 | **1.9s** |
| 6 | Qwen3-30B-A3B | AI Ping | 96.7% | 89.3% | 0.75 / 3 | 2.3s |
| 7 | GLM-4.7-Flash / GLM-5.3-Flash | AI Ping | 95.6% | 85.7/82.1% | 0.5–1 / 1.5–3 | 2–18s |
| 8 | Qwen3.5-Flash (2026) | AI Ping | 95.2% | 92.9% | 0.2 / 2 | 3.3s |
| 9 | Qwen3-Coder-30B-A3B | AI Ping | 95.1% | 89.3% | 0.7–1 / 2.8–4 | 4.4s |
| 10 | Qwen3-VL-30B-A3B-Thinking | AI Ping | 94.3% | 89.3% | 0.75 / 2.8–7.5 | 11.1s |
| 11 | Qwen3-30B-A3B-Instruct-2507 | AI Ping | 92.9% | 85.7% | 0.75 / 3 | 1.9s |
| 12 | Qwen2.5-14B-Instruct | AI Ping | 91.3% | 75.0% | 0.99 / 0.99 | 4.2s |
| 13 | Qwen3.5-9B (2026) | AI Ping | 90.5% | 82.1% | 0.5 / 4 | 3.3s |
| 14 | Qwen3-8B | AI Ping | 90.2% | 82.1% | 0–0.5 / 0–2 | 2.9s |
| 15 | GLM-4-9B-0414（免费） | AI Ping | 88.3% | 71.4% | 免费 | 1.9s |
| 16 | Qwen3-14B | AI Ping | 87.8% | 71.4% | 0.5–5 / 1.6–5 | 11.2s |
| 17 | Qwen3.5-4B（免费，2026） | AI Ping | 85.1% | 71.4% | 免费 | 8.1s |
| 18 | Qwen3-4B（免费） | AI Ping | 82.2% | 67.9% | 免费 | 5.6s |
| 19 | Qwen2.5-7B-Instruct | AI Ping | 60.2% | 35.7% | 0.35 / 0.35 | 6.9s |

OpenRouter 免费小模型另测 9 款（native），其中 nemotron-3.5-lightning 94.4%、ling-3.0-flash-fin 92.0% 可用；多数免费款在 `json` 协议下几乎全趴（26.9–30.1%），只适合原生 FC 路径。带 `err` 的 run（免费端限流中断少量案例）分数受轻微低估。

三个读数建议：

- **世代 > 参数量**：2026 年的 2B（MiniCPM5-2B，96.9%）比 2024 年的 7B（Qwen2.5-7B，60.2%）高 **36.7pp**。选型先看训练世代，再看参数规模。
- **协议通道是独立变量**：Qwen3-4B native 82.2% → json 90.5%（+8.3pp，JSON 约束救参数抽取）；MiniCPM5-2B native 96.9% → json 83.1%（native 更强）。同一个模型两条通道能差出十几到五十个百分点，横评必须注明协议。
- **recovery 是普遍短板**：全表 recovery 维度普遍低于其他维度 10–30pp；`by_horizon` 的 h3+ 段普遍出现断崖（例：Qwen3.5-9B h2 92.4% → h3+ 43.8%）。

> 以上为单遍 temp=0 结果，反映「最好情况」；生产可用性请重复运行测 pass^k（v0.0.2 起支持 `--repeats`）。

## 数据集与扩展

- [`datasets/tools.json`](datasets/tools.json)：工具 catalog 与 JSON Schema；
- [`datasets/core.jsonl`](datasets/core.jsonl)：每行一个可执行 episode；
- [`docs/DATASET_FORMAT.md`](docs/DATASET_FORMAT.md)：case、fixture、oracle 和评分字段说明；
- [`docs/EVALUATION_PROTOCOL.md`](docs/EVALUATION_PROTOCOL.md)：建议的实验矩阵与报告规则。
- [`docs/BENCHMARK_METHODOLOGY_ZH.md`](docs/BENCHMARK_METHODOLOGY_ZH.md)：完整中文 benchmark 方法论说明。
- [`SMALL_MODELS.md`](SMALL_MODELS.md)：待确认的小模型候选名称列表。

先把自己的领域工具加入 catalog，再用 fixture 表达确定性返回、瞬时错误、空结果或权限错误。不要把线上 token、客户数据或真实副作用写进 benchmark。

## 开发

```bash
python -m pip install -e '.[dev]'
pytest
smab validate
```

项目本身不依赖 OpenAI Python SDK，运行时只使用 Python 标准库请求 OpenAI-compatible `/chat/completions`。这让它更容易塞进本地微调和推理镜像。

## 适用边界

SMAB 当前聚焦确定性 tool-use 控制环，不测开放网页搜索质量、长期记忆、视觉工具或事实知识覆盖；也不把模型生成的自然语言交给另一个大模型裁判。最终答案只通过明确的关键事实检查评分，避免 judge model 掩盖小模型的真实变化。

## 开源许可

本仓库中的源代码、文档和内置 benchmark 数据集采用 [Apache License 2.0](LICENSE) 开源，归属声明见 [NOTICE](NOTICE)。除非提交者另有明确声明，提交到本仓库的贡献按同一协议提供。

[`SMALL_MODELS.md`](SMALL_MODELS.md) 仅列出第三方模型标识。本仓库不分发这些模型的权重、代码、训练数据或服务；使用第三方模型时，应分别遵守对应项目的许可证和使用条款。

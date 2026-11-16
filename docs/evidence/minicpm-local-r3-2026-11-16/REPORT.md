# MiniCPM5-2B vs MiniCPM-V-4.7-1B 本地全量部署 SMAB 测评（2026-11-16）

## 部署

| 项 | MiniCPM5-2B | MiniCPM-V-4.7-1B |
|---|---|---|
| 权重 | openbmb/MiniCPM5-2B-GGUF `F16`（5.04GB） | openbmb/MiniCPM-V-4.7-1B-gguf `F16`（2.02GB）+ `mmproj-model-f16.gguf`（1.11GB） |
| 底座架构 | LlamaForCausalLM（llama 架构） | minicpmv4_7（qwen3_5_text 线性/全注意力混合 + ViT） |
| 服务 | llama.cpp 1.0.0 `llama-server --jinja -ngl 999 -c 16384` | 同左，另挂 `--mmproj` |
| 端口 | 127.0.0.1:8801 | 127.0.0.1:8802 |
| 吞吐（SMAB 实测均值） | ≈86.5 tok/s（2.67s/回合） | ≈161.1 tok/s（1.04s/回合） |

- 均为**全量 F16 精度**（非量化），Metal 全量 offload，Apple M5 Max / 64GB。
- MiniCPM5-2B 官方 XML 工具格式由 llama.cpp 1.0.0 内置 parser 转换为 OpenAI `tool_calls`。

## Probe（框架能力探测）

| 端点 | 结果 | 要点 |
|---|---|---|
| MiniCPM5-2B:8801 | 10 ok / 2 unsupported / 0 error | native tools ✅ 并行调用 ✅ json_object ✅；vLLM 方言的结构化输出不支持（llama.cpp 正常） |
| MiniCPM-V-4.7-1B:8802 | **12 ok / 0 / 0** | 全部通过，推荐 native |

## 总分（温度 0、seed 0、repeats 3、schema original）

| 数据集 | 协议 | MiniCPM5-2B | MiniCPM-V-4.7-1B |
|---|---|---:|---:|
| core（28 例） | native | **96.1% ± 0.8**（pass^3 85.7%） | 85.8% ± 0.0（pass^3 75.0%） |
| core（28 例） | json | 87.3% ± 0.3 | 40.9% ± 0.0 |
| extra（13 例） | native | **97.6% ± 0.0** | 89.2% ± 0.0 |
| extra（13 例） | json | 95.3% ± 0.0 | 58.6% ± 0.0 |

## 维度明细（native / core）

| 维度 | MiniCPM5-2B | MiniCPM-V-4.7-1B |
|---|---:|---:|
| relevance | 100.0 | **50.0** ⚠️ |
| selection | 93.4 | 92.9 |
| arguments | 96.4 | 94.2 |
| planning | 100.0 | 92.6 |
| state_tracking | 93.3 | 73.3 |
| recovery | 100.0 | 62.5 ⚠️ |
| stopping | 94.0 | 87.5 |

1B 的短板集中在：**relevance（50%）**——该不调用/该追问时倾向直接调用；recovery（62.5%）——可恢复错误后调整不足；horizon 0 切片仅 50.7%（不该动手的任务动得太勤）。2B native 下无短板维度（最低 selection 93.4）。

## 协议敏感性（重要结论）

- **MiniCPM5-2B**：native 96.1% → json 87.3%。json 协议下 state_tracking 崩到 46.7%、3+ 长任务 48.3%——XML 工具格式的模型在 SMAB json 协议下主要丢"使用工具返回值继续推理"的能力。
- **MiniCPM-V-4.7-1B**：native 85.8% → json **40.9%**（arguments 8.7%、selection 2.9%）。该模型完全没被训练成输出 SMAB json 协议的 `{"tool_calls":[...]}` 对象，json 分数只代表协议适配性，不代表能力。

## 与历史跑批对照

| 运行 | 分数 | 备注 |
|---|---:|---|
| MiniCPM-V-4.7-1B native 单次（10-09） | 85.4% | 本次本地 native 85.8%，基本一致 |
| MiniCPM-V-4.7-1B extra native r3（10-09） | （已被本次覆盖，原值丢失） | ⚠️ 见下方说明 |
| MiniCPM-V-4.7-35B-A3B native（10-10/12） | 见 runs/minicpm-v-4.7-35b-a3b-native*.md | 35B 同门对照 |

## 产物清单

- 入库：本目录 `runs/*.json.gz`（10 个原始 run / probe）、`summary.json`、`summary.md`
- 仓库外：本地 `runs/` 未压缩原稿与服务脚本（llama-server 启动命令见上方复现小节）
- 权重：`~/models/minicpm-eval/`（F16 GGUF ×3）

## ⚠️ 覆盖事故说明

macOS APFS 大小写不敏感：本次输出的 `MiniCPM-V-4.7-1B-extra-native-r3.json/.md` 与旧文件 `minicpm-v-4.7-1b-extra-native-r3.json/.md`（10-09）同名同物，**旧文件已被本次结果覆盖，原数值未能留档恢复**（无本地快照）。其余历史文件均未受影响。新结果与旧运行协议相同（extra × native × r3 × temp0 × seed0），可作为该槽位的最新版本，但如需对照 10-09 原始数值，请检查是否有外部备份。

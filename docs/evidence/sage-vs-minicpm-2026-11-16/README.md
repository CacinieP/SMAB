# 书生-A1.5 vs MiniCPM-V 4.7 35B-A3B 本地批次（2026-11-16，同底座双路线）

本目录记录两枚 **同架构（`qwen35moe`）、同量化（Q4_K_M）、同运行时** 的 35B-A3B 模型在 SMAB 上的对照实测：上海AI实验室的 **书生-A1.5（Sage-A1.5）** 与面壁智能/OpenBMB 的 **MiniCPM-V 4.7 35B-A3B**。两者底座同为 Qwen3.6-35B-A3B，因此差异基本只剩后训练与工具协议适配，是本仓库少见的「同底座、不同 agent 训练路线」样本。

与 [`minicpm-local-r3-2026-11-16`](../minicpm-local-r3-2026-11-16/)（F16 端侧 ≤3B 双枚）互补：那一批回答「端侧小模型水位」，本批回答「同级 MoE 智能体模型的协议适配差」。不是 API 榜单数据，不应与主榜混算。

## 环境

| 项 | 值 |
|---|---|
| 硬件 | Apple M5 Max，64GB 统一内存（两模型**串行**加载，避免内存争用影响吞吐） |
| 运行时 | llama.cpp 1.0.0（build 12359, commit b1b770d90，brew，Metal）；`llama-server -ngl 999 -fa on -c 16384 --jinja` |
| 权重 A | [InternScience/Sage-A1.5-Q4_K_M-GGUF](https://huggingface.co/InternScience/Sage-A1.5-Q4_K_M-GGUF) `Q4_K_M`（21,713,463,520 B）+ mmproj 899,282,880 B（**本轮未挂载**） |
| 权重 B | MiniCPM-V 4.7 35B-A3B `Q4_K_M` GGUF（约 20GB）+ clip mmproj 552.99M（**本轮未挂载**） |
| 架构核对 | `ollama show openbmb/minicpm-v4.7` → architecture `qwen35moe` / 34.7B / ctx 262144；Sage 侧官方 README 原文「`qwen35moe` (hybrid attention + SSM MoE) based on Qwen3.6-35B-A3B」 |
| 基准 | `datasets/core.jsonl`（28 episodes）+ `datasets/minicpm47_extra.jsonl`（13 episodes），代码与数据集 = `main@47a4e4b`（已核对与 `main@df492b0` 的 datasets/runner/scoring blob 完全一致） |
| 协议 | temperature 0（greedy）、seed 0、`--repeats 3`、schema variant original；通道 = native / json；两边服务参数严格一致，**且不加载各自官方推荐采样**（Sage 官方推荐 temp 1.0 / presence_penalty 1.5，会污染贪心解码与横向可比性） |
| 端口 | Sage `127.0.0.1:8000`，MiniCPM `127.0.0.1:8001` |

## 结果总表（overall 均值 ± σ，perfect-case rate 括号内）

| 模型 | 通道 | core（28 例） | extra（13 例） | 吞吐 |
|---|---|---|---|---|
| Sage-A1.5（原生，思考开） | native | **98.6% ± 0.0**（96.4%） | 90.8% ± 0.0（69.2%） | ≈116 tok/s |
| Sage-A1.5（原生，思考开） | json | **96.7% ± 0.1**（89.3%） | **96.1% ± 0.0**（84.6%） | ≈107 tok/s |
| Sage-A1.5（`enable_thinking:false`） | native | 88.9% ± 0.0（85.7%） | 81.4% ± 0.0（69.2%） | ≈107 tok/s |
| Sage-A1.5（`enable_thinking:false`） | json | 95.1% ± 0.4（92.9%） | 83.4% ± 1.1（59.0%） | ≈89 tok/s |
| MiniCPM-V 4.7 35B-A3B | native | 95.6% ± 0.0（89.3%） | **91.7% ± 0.0**（69.2%） | ≈104 tok/s |
| MiniCPM-V 4.7 35B-A3B | json | 91.3% ± 0.0（82.1%） | 82.0% ± 0.0（69.2%） | ≈91 tok/s |

## 关键结论

- **core 上 Sage 原生形态最高（98.6% / perfect 96.4%）**，优势集中在 `relevance`（100% vs MiniCPM 83.3%）、`state_tracking`（100% vs 93.3%）、`stopping`（98.8% vs 96.4%）；逐例看只丢 `sel_001`（相似工具混淆：气候均值 vs 天气预报）。
- **extra 回归集上 MiniCPM 略优且更省**（91.7% vs 90.8%，`stopping` 满分；完成 token 只有 Sage 的 44%，墙钟约一半）。`m47_arg_101`（精确 ISO 时间串）与 `m47_stop_101`（一次性副作用 + 回显 ID）**两个配置全挂**，属任务本身难度，不是单家短板。
- **json 通道上 Sage 双向稳定，MiniCPM 掉档**：extra×json Sage 96.1% vs MiniCPM 82.0%。与 11-16 早前 1B 批次「native 85.8% → json 40.9%」的断崖不同，35B-A3B 的 MiniCPM 已经能较好适配 SMAB 的 json 协议，但仍落后于自己的 native 通道。
- **`enable_thinking` 是 Sage 的独立强变量，关掉是净损失**（core×native 98.6% → 88.9%）。反面证据很硬：关思考后 84 次运行出现 **12 次 `max_turns`**（工具调用打转），prompt token 从 93,330 涨到 148,851，`relevance` 从 100% 崩到 66.7%（extra 集 33.3%）。而 MiniCPM 的 GGUF 模板里写着 `thinking hard-disabled for llama`，**没有可比开关**——所以「两边都关思考」并不是公平口径，主表以各自出厂默认形态为准。
- **token 预算不是 Sage 的瓶颈**：`max_tokens` 512 与 2048 两遍 core×native 完全同分（98.6% / 96.4%），说明在工具轮次里思考链平均 280 token 量级，SMAB 默认 512 够用；只有开放题（非工具任务）才会出现「思考吃光预算 → content 为空」。

## Probe 结果（先探端点再解释分数）

| 端点 | 判定 | 要点 |
|---|---|---|
| Sage（默认思考） | 5 ok / 6 unsupported / 1 error | `native_tools` ✅、`parallel_tool_calls` ✅、`tool_roundtrip` ✅；`json_object_response_format` 报 `plain control returned no assistant content` —— 是思考吃掉探测预算，不是连通性问题 |
| Sage（关思考） | 见 `runs/probe-sage-a15-nothink.json.gz` | 同上文件名被第二轮批跑覆盖过，原始数值仅存在于会话记录 |
| MiniCPM | 8 ok / 4 unsupported / 0 error | `tool_choice=required` / `named` 与各家结构化输出方言不支持（llama.cpp 1.0.0 正常表现，两家一致） |

## 复现

```bash
# 冻结快照跑，避免同仓并发写者把中间态源码喂进评测进程
git archive <sha> | tar -x -C /tmp/smab-snap-<sha>
cd /tmp/smab-snap-<sha> && uv venv .venv && uv pip install -e .   # SMAB 零第三方依赖

# 服务（两边同参）
llama-server -m Sage-A1.5-Q4_K_M.gguf --alias Sage-A1.5-Q4_K_M \
  -ngl 999 -fa on -c 16384 --jinja --host 127.0.0.1 --port 8000

# 每格
smab run --model Sage-A1.5-Q4_K_M --base-url http://127.0.0.1:8000/v1 \
  --dataset datasets/core.jsonl --tool-format native \
  --repeats 3 --temperature 0 --seed 0 --output sage-think-core-native-r3.json
```

关思考那一档额外传：`--extra-body '{"chat_template_kwargs":{"enable_thinking":false}}'`。
表格重算：`python3 make_summary.py`（读 `runs/*.json.gz`）。

## 文件

- `summary.json` / `summary.md`：全部格子（含逐重复、维度、split、horizon、吞吐）
- `runs/*.json.gz`：14 个 run + 3 个 probe 原始轨迹
- `REPORT.md`：逐例分歧、代价、口径边界与踩坑记录

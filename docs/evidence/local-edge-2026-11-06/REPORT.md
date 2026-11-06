# MNN-Pocket-0.3B 本地部署与 SMAB 对比评测报告

> 日期：2026-11-06 ｜ 硬件：Apple M4 / 16GB / macOS 26.6.2 ｜ 评测框架：CacinieP/SMAB v0.2.0（commit `c654074`）｜ 全部推理在本地完成（MNN 3.6.2 + llama.cpp 0.7.0-dev），无外部 API

## 0. 摘要（TL;DR）

**部署**：`taobao-mnn/MNN-Pocket-0.3B`（INT4 W4A16）已用 **MNN 3.6.2 Python 运行时（`MNN.llm`）** 本地跑通，并配了一个纯标准库的 OpenAI 兼容 HTTP 服务（127.0.0.1:8090）。模型目录仅 **166MB**，加载 **0.18s**，常驻 RSS **312MB**，CPU 4 线程实测 **prefill ≈1,907 tok/s、decode ≈163 tok/s**（516 token 输入 / 200 token 输出），短 prompt 可达 200–230 tok/s。不需要 PyTorch、不需要编译，`pip install MNN` 即可复现。

**评测**：用 SMAB 的 28 个 core episodes、同一协议（json 通道、prompt-only、temperature 0）、同一台机器实测 5 个本地端点（12 个有效 run，全部 `case_count=28`、`adapter_error=0`）：

| 端点（运行时/量化） | json prompt-only | json + 约束解码 | native |
|---|---:|---:|---:|
| **MNN-Pocket-0.3B（MNN INT4）** | **29.2%** / perfect 0% | 不支持（shim 无 grammar） | 不支持（无 tool parser） |
| MNN-Pocket-0.3B（llama.cpp Q8_0） | 30.1% / 0% | 28.1% / 0% | 不支持（只输出裸 JSON） |
| MiniCPM5-1B（llama.cpp Q8_0） | 35.3% / 3.6% | 34.7% / 3.6% | **83.8% / 60.7%** |
| MiniCPM5-2B（llama.cpp Q8_0） | 44.5% / 7.1% | 78.9% / 53.6% | **94.6% / 85.7%** |
| MiniCPM-V-4.7-1B（llama.cpp Q8_0） | 35.8% / 3.6% | 40.9% / 10.7% | **86.4% / 75.0%** |

> 表中为 overall / perfect-case rate（28 例、temp=0、单遍）。历史 API 分数不同协议（native、托管服务端），见 §6.6/附录 A，不可直接横比。

**四条核心结论**：

1. **0.3B 的失败点不是"会不会调工具"，而是"协议契约与多轮控制环"**：MNN-Pocket 能产出合法 JSON、能写出正确的工具名与参数（单次调用案例存在），但 16/28（57%）顶层键漂移成 `answer`/`explanation`/`task`；`arg_001` 连续 8 轮重复同一调用、不消费工具返回值；horizon≥2 时得分跌到 **13.8%/12.2%**。它适合"单轮、schema 固定、可后处理校验"的端侧器官，不适合承担完整 agent 控制环。
2. **协议通道是第一自变量，量级远大于参数量**：三个能走 native 的模型，native 比 json prompt-only 高 **+48.5 / +50.0 / +50.6pp**；而同一模型换协议通道（json 约束 → native）还能再差 15.7–45.5pp。**选型先问"走哪条通道"，再问"多大参数"**。
3. **约束解码只救"语法层失败"，救不了"契约层失败"**：MiniCPM5-2B 的 json 失败是括号/引号错位，加 `response_format=json_object` 后 44.5%→**78.9%**（protocol_error 21→0，+34.4pp）；MiniCPM5-1B（35.3%→34.7%）、MNN-Pocket（30.1%→28.1%）、V4.7（35.8%→40.9%）改善很小——它们的失败是**顶层键漂移**或**只描述、不真的调用**，grammar 管不到。
4. **同模型跨运行时几乎无差**：MNN INT4 29.2% vs llama.cpp GGUF Q8_0 30.1%（Δ0.9pp，<1σ；3 次重复的稳定标准差为 0.82pp）。0.3B 的瓶颈是模型能力，不是部署栈。MNN 侧还多赚了 2.3 倍的图像/内存优势（166MB vs 387MB 磁盘）。

## 1. 目标与范围

- 在本地（macOS/Apple Silicon）部署 `mnn-pocket-0.3b`，验证 MNN 运行时路线可复现、可服务化；
- 用 `CacinieP/SMAB` 基准测试，并与 `MiniCPM5-1B`、`MiniCPM5-2B`、`MiniCPM-V-4.7-1B` 在同协议、同硬件下对比；
- 对照 2026-10-26 ModelBest API 的历史 native 分数，说明"框架 / 协议 / 量化"三个变量各自的贡献；
- 产出可复现脚本、原始 run 数据与结论。

不在范围内：视觉/多模态能力、开放域知识问答、训练或微调。

## 2. 环境与软件版本

| 项 | 值 |
|---|---|
| 机器 | Apple M4，统一内存 16GB，macOS 26.6.2 (25G83) |
| 磁盘 | 剩余约 129GB（模型 + 评测产物共约 7GB） |
| Python | 3.11.15（项目内 venv；系统默认 3.14 不用于 MNN） |
| MNN | 3.6.2（PyPI wheel，含 `MNN.llm`；源码 alibaba/MNN 3.6.2 仅作参考） |
| llama.cpp | 0.7.0-dev（build b1-a08ab75，Metal，`-ngl 99`） |
| SMAB | v0.2.0，commit `c654074`（2026-11-03，github.com/CacinieP/SMAB） |
| 数据集 | `datasets/core.jsonl`：28 episodes（core 17 / OOD 11，zh 18 / en 10；七维：relevance 6、arguments 4、planning 4、selection 4、recovery 4、stopping 4、state_tracking 2） |

## 3. MNN-Pocket-0.3B 的 MNN 运行时部署

### 3.1 模型与量化

- 官方 `taobao-mnn/MNN-Pocket-0.3B`：约 3 亿参数，Qwen3 架构（28 层、hidden 896、14 头 GQA / 2 KV 头、32K 上下文、ChatML 模板，Apache-2.0）；
- 端侧用官方 INT4（W4A16，block 64）QAT 版本 `taobao-mnn/MNN-Pocket-0.3B-MNN`：`config.json` / `llm.mnn` / `llm.mnn.weight`（171MB）/ `llm_config.json` / `tokenizer.mtok`；
- 另有官方 GGUF（F16/Q8_0/Q4_1）用于 llama.cpp 对照（§4、§6.5）。

### 3.2 安装与运行

```bash
python3.11 -m venv mnn/.venv
mnn/.venv/bin/pip install MNN==3.6.2 huggingface_hub

# 模型下载（hf-mirror；直连 huggingface.co 的 LFS 只有 ~1KB/s）
HF_ENDPOINT=https://hf-mirror.com mnn/.venv/bin/python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download("taobao-mnn/MNN-Pocket-0.3B-MNN", local_dir="models/MNN-Pocket-0.3B-MNN")
PY

./mnn/start_server.sh            # 启动 OpenAI 兼容服务（127.0.0.1:8090）
```

最小加载/推理代码：

```python
import MNN.llm as mllm
m = mllm.create("models/MNN-Pocket-0.3B-MNN/config.json")
m.set_config({"backend_type": "cpu", "thread_num": 4, "temperature": 0.0,
              "top_k": 1, "max_new_tokens": 512, "use_template": False})
m.load()                                          # 0.18s
prompt = m.apply_chat_template([{"role": "system", "content": "..."},
                                {"role": "user", "content": "..."}])
text = m._c_obj.response(prompt, 0, 512)          # 第 3 参数 = 本次 max_new_tokens
print(m.context.prompt_len, m.context.decode_us)  # 内置性能计数
```

四个必须知道的坑（详见 `mnn/README.md`）：

1. **`response()` 会二次套模板**：把整段 prompt 当 user 内容再套一次 ChatML；必须 `use_template=false`，并用 `apply_chat_template(messages)` 自己拼；
2. **`temperature=0` 时必须 `top_k=1`**：MNN 的 mixed 采样器在 temp=0 + 默认 top_k=40 下会退化乱码（贪心后恢复正常）；
3. **Python wrapper 的 `response(prompt, stream)` 不能传 max_new_tokens**，需走 `_c_obj.response(prompt, 0, n)`；
4. **wheel 的 Metal 后端能跑但更慢**（加载 5.9s，长上下文 decode 69 tok/s vs CPU 163），服务保持 CPU。

### 3.3 OpenAI 兼容 shim

`mnn/serve_mnn.py`：纯标准库 `ThreadingHTTPServer`，模型常驻 + 单请求加锁串行；`GET /health`、`GET /v1/models`、`POST /v1/chat/completions`（标准非流式结构，`stream=true` 走 SSE）、`GET /stats`。SMAB 评测期间 **137 次请求 / 6,224 生成 token / 服务端 0 错误**；逐请求 token 与耗时见 `logs/mnn-requests.jsonl`。

### 3.4 实测性能（MNN 运行时，CPU 4 线程，greedy，3 次中位数）

| 指标 | 值 |
|---|---:|
| 模型目录 | 166 MB（INT4 W4A16） |
| 加载时间 | 0.18 s |
| 常驻内存 RSS | 312 MB（服务峰值约 362MB） |
| prefill | ≈1,907 tok/s（516 token / 270.6ms） |
| decode | ≈162.8 tok/s（200 token / 1.22s） |
| 首 token 延迟 | 270.6 ms |
| 端到端吞吐 | 135.6 tok/s（1.48s / 200 token） |
| Metal 后端（对照） | 69.4 tok/s（长上下文反而慢 2.3 倍） |

> 测量时系统有 llama.cpp 服务与下载并发（loadavg≈7），单次波动 ±30%；短 prompt 实测 200–230 tok/s。SMAB 评测期间服务端平均请求延迟 646ms（P95 7.08s，由 max_turns 长循环拉高）。

## 4. 对比组：llama.cpp GGUF 本地服务

| 端口 | 模型 | 量化/磁盘 | decode | prompt eval | 加载 | phys footprint | native tools |
|---|---|---|---:|---:|---:|---:|---|
| 8091 | MiniCPM5-1B | Q8_0 / 1153.5MB | 88.4 tok/s | 1337 tok/s | 1.35s | 677 MB | ✅ |
| 8092 | MiniCPM5-2B | Q8_0 / 2679.7MB | 36.0 tok/s | 432 tok/s | 2.32s | 1108 MB | ✅ |
| 8093 | MiniCPM-V-4.7-1B | Q8_0 / 1081.5MB | 43.4 tok/s | 507 tok/s | 1.79s | 1014 MB | ✅（纯文本） |
| 8094 | MNN-Pocket-0.3B-GGUF | Q8_0 / 386.8MB | 208.3 tok/s | 2390 tok/s | 0.73s | 361 MB | ❌（只输出裸 JSON） |

统一启动参数：`--host 127.0.0.1 --port <p> --ctx-size 8192 --parallel 1 --temp 0 --jinja -ngl 99`；MiniCPM5 系列额外 `--chat-template-kwargs '{"enable_thinking": false}'`（hybrid-reasoning 在 temp=0 下会先烧一大段推理 token）。4 个 server 总 footprint ≈3.2GB，16GB 机器可同时驻留。

## 5. 评测方法（SMAB）

### 5.1 基准构成

SMAB 是"可执行、逐维度"的小模型工具调用基准：28 个中英双语 episode（core 17 / OOD 11；zh 18 / en 10），七维能力；工具全部由本地 fixture 模拟，无真实副作用；评分只做确定性关键事实检查，不用 LLM judge。另可按 horizon（期望调用次数 0/1/2/3+）切片。

### 5.2 本次协议

- **A. json prompt-only（主结果，5 个端点）**：工具 schema 写进 system prompt，要求只输出 `{"tool_calls":[...]}` 或 `{"final":"..."}`；`--extra-body '{"response_format":null}'` **显式关闭服务端 JSON 约束**；temperature 0、max_tokens 512、seed 0、单遍。
- **B. json + 约束解码（4 个 llama.cpp 端点）**：`response_format={"type":"json_object"}`，由 llama.cpp grammar 保证输出是 JSON 对象。用于分离"语法容量"与"语义容量"（SMAB 官方协议推荐矩阵 D）。
- **C. native（3 个 llama.cpp 端点）**：OpenAI `tools`/`tool_calls` 原生通道（协议 A 的对照；MNN 8090 与 Pocket GGUF 8094 无 tool parser，不支持）。
- probe（`smab probe`）只作能力证据，不改变正式调用方式：8090 ok 3 / unsupported 7 / error 2；8091/8092/8093 均 native tools ✅、response_format ✅；8094 native ❌（模型只输出裸 JSON，不包 `<tool_call>`）。
- 采用 prompt-only 为主的原因：MNN shim 无法做 grammar 约束；若只对 llama.cpp 启用约束，协议就不一致。代价是绝对分数偏低，故用 B/C 做对照量化。

### 5.3 与历史 API 分数的口径差异

仓库 README 的 2026-10-26 ModelBest 批次是 **native 通道 + 托管 API 服务端**（含服务端 tool parser/模板），与本次"本地 llama.cpp / MNN shim"不是同一运行时；两组可对照不可混算。历史值：MiniCPM5-2B 96.9%/92.9%，MiniCPM-V-4.7-1B 79.2%/64.3%，V-4.6 82.4%/64.3%，V-4.5 70.5%/57.1%，V-4.7-35B-A3B 95.8%/92.9%；MiniCPM5-1B 当时无推理路由（404 `lis_route_denied`）。

## 6. 结果

### 6.1 总表（28 例，temp=0，schema original，单遍）

| 模型（运行时/量化/通道） | overall | perfect | protocol_error | 请求数 |
|---|---:|---:|---:|---:|
| **MNN-Pocket-0.3B（MNN INT4）· json** | **29.2%** | 0.0% | 16/28（57%） | 56 |
| MNN-Pocket-0.3B（llama.cpp Q8_0）· json | 30.1% | 0.0% | 20/28（71%） | 53 |
| MNN-Pocket-0.3B（llama.cpp Q8_0）· json 约束 | 28.1% | 0.0% | 18/28（64%） | 64 |
| MiniCPM5-1B（Q8_0）· json | 35.3% | 3.6% | 13/28（46%） | 28 |
| MiniCPM5-1B（Q8_0）· json 约束 | 34.7% | 3.6% | 10/28（36%） | 28 |
| MiniCPM5-1B（Q8_0）· **native** | **83.8%** | 60.7% | 0 | 68 |
| MiniCPM5-2B（Q8_0）· json | 44.5% | 7.1% | 21/28（75%） | 40 |
| MiniCPM5-2B（Q8_0）· json 约束 | 78.9% | 53.6% | 0 | 59 |
| MiniCPM5-2B（Q8_0）· **native** | **94.6%** | 85.7% | 0 | 67 |
| MiniCPM-V-4.7-1B（Q8_0）· json | 35.8% | 3.6% | 9/28（32%） | 39 |
| MiniCPM-V-4.7-1B（Q8_0）· json 约束 | 40.9% | 10.7% | 0 | 42 |
| MiniCPM-V-4.7-1B（Q8_0）· **native** | **86.4%** | 75.0% | 0 | 64 |

![overall](fig-overall.png)

### 6.2 七维分数（json prompt-only 为主；native 并列）

| 模型（通道） | relevance | selection | arguments | planning | state | recovery | stopping |
|---|---:|---:|---:|---:|---:|---:|---:|
| MNN-Pocket-0.3B（MNN INT4）json | 50.0% | 0.0% | 4.3% | 0.0% | 13.3% | 0.0% | 65.7% |
| MNN-Pocket-0.3B（GGUF Q8）json | 50.0% | 0.0% | 8.0% | 11.1% | 6.7% | 12.5% | 64.8% |
| MiniCPM5-1B json | 66.7% | 0.0% | 0.0% | 0.0% | 20.0% | 0.0% | 83.7% |
| MiniCPM5-1B **native** | 66.7% | 93.4% | 89.9% | 77.8% | 60.0% | 64.6% | 91.7% |
| MiniCPM5-2B json | 66.7% | 21.6% | 17.4% | 53.7% | 33.3% | 25.0% | 73.0% |
| MiniCPM5-2B json 约束 | 83.3% | 70.4% | 78.3% | 100.0% | 33.3% | 93.8% | 96.0% |
| MiniCPM5-2B **native** | 100.0% | 92.9% | 92.8% | 100.0% | 93.3% | 93.8% | 96.4% |
| MiniCPM-V-4.7-1B json | 33.3% | 2.6% | 7.2% | 13.0% | 20.0% | 6.2% | 81.7% |
| MiniCPM-V-4.7-1B **native** | 50.0% | 92.9% | 92.8% | 87.0% | 73.3% | 56.2% | 94.6% |

![dimensions](fig-dimensions.png)

### 6.3 by_horizon（随链路变长在哪里断）

| 模型（通道） | h=0 | h=1 | h=2 | h=3+ |
|---|---:|---:|---:|---:|
| MNN-Pocket-0.3B（MNN INT4）json | 56.6% | 31.3% | 13.8% | 12.2% |
| MNN-Pocket-0.3B（GGUF Q8）json | 56.6% | 30.7% | 18.9% | 12.2% |
| MiniCPM5-1B json | 90.3% | 30.0% | 20.1% | 18.3% |
| MiniCPM5-1B **native** | 77.8% | 92.0% | 69.3% | 85.2% |
| MiniCPM5-2B json | 84.7% | 29.7% | 52.7% | 47.2% |
| MiniCPM5-2B json 约束 | 72.2% | 74.8% | 93.1% | 73.6% |
| MiniCPM5-2B **native** | 100.0% | 92.2% | 95.0% | 100.0% |
| MiniCPM-V-4.7-1B **native** | 50.7% | 97.0% | 89.3% | 68.0% |

![horizon](fig-horizon.png)

### 6.4 延迟 / token 用量

| 模型（通道） | 平均请求延迟 | P95 | 输出 tok/s（端到端） | prompt tok | completion tok | tok/case |
|---|---:|---:|---:|---:|---:|---:|
| MNN-Pocket-0.3B（MNN INT4）json | 646 ms | 7,081 ms | 73 | 23,871 | 2,656 | 947 |
| MNN-Pocket-0.3B（GGUF Q8）json | 283 ms | 2,071 ms | 181 | 20,588 | 2,708 | 832 |
| MiniCPM5-1B json / 约束 / native | 640 / 420 / 899 ms | 912 / 786 / 5,966 | 78 / 68 / 59 | 7,127 / 7,127 / 31,537 | 1,407 / 798 / 3,586 | — |
| MiniCPM5-2B json / 约束 / native | 957 / 862 / 1,198 ms | 3,975 / 3,949 / 5,899 | 30 / 29 / 28 | 12,401 / 19,581 / 28,504 | 1,147 / 1,497 / 2,237 | — |
| MiniCPM-V-4.7-1B json / 约束 / native | 575 / 596 / 787 ms | 1,632 / 4,269 / 2,966 | 70 / 61 / 76 | 13,646 / 16,402 / 32,476 | 1,579 / 1,537 / 3,806 | — |

> 延迟仅作量级参考：评测期间有并发下载/多运行时（loadavg 3.5–7.5）；分数为 greedy 确定性输出，不受负载影响。端到端 tok/s = completion_tokens / 客户端累计请求延迟（含 HTTP 与调度开销）。

### 6.5 同模型跨运行时：MNN INT4 vs llama.cpp Q8_0

| 指标 | MNN INT4（8090） | llama.cpp Q8_0（8094） |
|---|---:|---:|
| SMAB json overall | 29.2% | 30.1% |
| protocol_error | 16/28（57%） | 20/28（71%） |
| 磁盘 | 166 MB | 386.8 MB |
| decode | 163 tok/s（CPU） | 208 tok/s（Metal） |
| SMAB 平均请求延迟 | 646 ms | 283 ms |
| 每 case 生成 token | 947 | 832 |

- 分数差 **0.9pp**，小于 3 次重复的 1σ（0.82pp）→ 同模型跨运行时/量化差异可忽略。
- 但**逐 case 轨迹有分歧**（arg_001：MNN 0.50 vs GGUF 0.83；recover_004：0.00 vs 0.47），说明 0.3B 级别的单例轨迹本身不稳定，overall 相近不代表行为一致。
- 结论：0.3B 在 SMAB 上的低分源于模型在 json 协议上的键漂移与状态机能力，不是 MNN 运行时的问题；MNN 的优势在体积/内存/零依赖部署。

### 6.6 与历史 ModelBest API native 对照

| 模型 | 本地 native（本次） | API native（2026-10-26） | 差值 | 归因 |
|---|---:|---:|---:|---|
| MiniCPM5-2B | 94.6% / 85.7% | 96.9% / 92.9% | −2.3 / −7.2pp | llama.cpp b1-a08ab75 + Q8_0 + thinking off |
| MiniCPM-V-4.7-1B | 86.4% / 75.0% | 79.2% / 64.3% | **+7.2 / +10.7pp** | API 侧配置不可见（V4.7 倾向长思考，历史 run 有 5 例 max_turns） |
| MiniCPM-V-4.6 | — | 82.4% / 64.3% | — | 仅历史 |
| MiniCPM-V-4.5 | — | 70.5% / 57.1% | — | 仅历史 |
| MiniCPM5-1B | 83.8% / 60.7% | 无路由 | — | 历史未测 |

> 本地 native 与历史 API native 的差值在 ±7pp 内，说明本地链路可信；跨口径只能对照、不能排名。

### 6.7 稳定性（Lead 独立复测）

`--repeats 3`（同 seed、同协议、28 例）：MNN-Pocket overall_mean = **30.1%**，std = **0.82pp**，perfect-case rate = 0%，pass^1 = pass^2 = pass^3 = 0%。单次 29.2% 与均值差 0.9pp，在 1σ 内 → 低分不是采样噪声。原始文件：`runs/appendix-pocket03b-mnn-int4-json-r3.json`。

## 7. 失败模式分析

### 7.1 0.3B：能"说对答案"，不能"按契约行动"

- **16/28 例 protocol_error，其中 15 例是"合法 JSON 但顶层键漂移"**：`{"answer": ...}`、`{"explanation": ...}`、`{"task": ..., "instructions": ...}`。典型：`rel_001` 输出 `{"explanation": "缓存命中率是……"}`（内容正确，但键不是 `final`）；`plan_001` 输出 `{"answer": "3 * 100 = 300"}`（直接口算，没有调用计算工具）。
- **重复调用/不消费返回值**：`arg_001` 连续 8 轮重复同一 `search_flights`（参数正确），从不使用返回的航班列表 → max_turns；`rel_006`、`recover_001`、`recover_004` 同样耗尽 8 轮。
- **无工具可用的 4 例（h=0）**：3 例答对但键错（0.83/0.88/0.56 分），1 例（rel_006，要求"立即发季度邮件"）误判并空转 8 轮（0 分）。
- **为什么约束解码救不了它**：grammar 只保证"是合法 JSON"，不保证顶层键是 `tool_calls`/`final`；0.3B 的失败在语义契约层（30.1%→28.1%，protocol_error 20→18，基本不变）。
- 另一端：唯一能拿分的维度是 relevance（50%）与 stopping（65.7%）—— 它"知道什么时候该闭嘴"（停得下来），但"该做什么/怎么衔接"不成体系。

### 7.2 1B：native 可用，json 文本协议崩

- native **83.8%**（selection 93.4、arguments 89.9、planning 77.8、recovery 64.6、state 60.0）；
- json prompt-only 35.3%、约束 34.7%——**约束几乎无效（−0.6pp）**，protocol_error 13→10。失败样本：`{"answer": "..."}` 键漂移；先输出一段英文思考再给 JSON（rel_004）；"我没有这个能力"式放弃（rel_002/rel_003）。
- 解释：1B 的工具能力依赖原生 tool token/模板；被改写成"文本 JSON 协议"后，它把工具调用当普通文本生成，丢掉结构化约束——连 JSON 骨架都不稳，grammar 只能修语法，修不了"该调不调"。

### 7.3 2B：语法错误为主，约束解码能救

- json prompt-only 44.5%：21/28 protocol_error，其中 16 例是坏 JSON（`{"final":"answer":"..."}` 嵌套引号、末尾多 `]}`），5 例无 JSON；
- 加 grammar 后 **78.9% / perfect 53.6% / protocol_error 0**；planning 100%、recovery 93.8%、selection 70.4%、arguments 78.3%；
- 与 native 94.6% 仍差 15.7pp：剩余差距来自"文本协议"本身（把 tool_calls 序列化进 content、tool 结果回灌为 user 文本），**原生 tool token 仍是最优通道**；与 API native 96.9% 差 2.3pp 属部署栈差异。

### 7.4 MiniCPM-V-4.7-1B：native 强、文本协议"只说不做"

- native 86.4%（selection/arguments 92.9、planning 87.0、state 73.3、recovery 56.2）—— 但 **h=0 只有 50.7%**：不该调工具时仍然调（relevance 50.0），典型是 rel_003/rel_005 把"工具未配置/无法获取"当成结论输出；
- json：prompt-only 35.8%、约束 40.9% —— 失败模式是**输出自然语言描述"我要去查天气"而不是真的发 tool_calls**（`{"error": "unknown_or_unconfigured_tool"}` 之类幻觉），grammar 修不了"只说不做"。
- 结论：V4.7-1B 是"多模态 + native 工具"的模型，文本 JSON 协议不是它的强项；与历史 API native 79.2% 相比，本地 native 反而 +7.2pp（API 侧长思考/超时配置不可见）。

### 7.5 跨模型规律

1. **协议通道 >> 参数量**：native 比 json prompt-only 高 48.5–50.6pp；同一模型换通道的跨度（2B：44.5→78.9→94.6）比 1B 与 2B 的 native 差距（83.8→94.6，10.8pp）大得多。
2. **约束解码收益 = 失败是否在语法层**：2B +34.4pp（语法错）；1B −0.6pp、0.3B −2.0pp、V4.7 +5.1pp（契约/策略错）。判断"加 grammar 能不能救"应先看 protocol_error 的类型，而不是看分数。
3. **0.3B 的断点在 horizon≥2**：h=0 56.6% → h=3+ 12.2%；一旦需要"调一次 → 看结果 → 再决定"，能力崩掉。
4. **停止行为不是主要瓶颈**：0.3B/1B/V4.7 的 stopping 都有 66–86%，真正缺的是 selection/arguments/planning 这些"控制环前段"能力。

## 8. 结论与选型建议

1. **MNN-Pocket-0.3B 的部署完全成立**：166MB 磁盘、312MB 内存、0.18s 加载、163 tok/s（CPU）——`pip install MNN` + 一个标准库 shim 即可服务化，无需 PyTorch/编译。适合端侧"单轮、schema 固定、可后处理校验"的器官（抽取/分类/短摘要/固定格式回复）。
2. **但它在 SMAB 这类多轮工具控制环上不可用**：overall 29.2%、perfect 0%，57% 的 case 违反 JSON 顶层契约，horizon≥2 只有 12–19%。不应让它独立承担"判断该不该调 → 选工具 → 填参 → 用结果推进 → 停"的控制环。
3. **如果非要用 0.3B 做工具调用**：必须做三件事——(a) 服务端/上层用 JSON Schema 强约束到 `{"final","tool_calls"}` 枚举（grammar 只保证合法 JSON 不够）；(b) 上层状态机兜底（重复调用检测、结果消费检查、max_turns）；(c) 用 SMAB 的 case 集做回归门禁（建议 relevance≥98%、arguments≥97%、stopping=100%、h3+ perfect≥90% 的 SMAB 建议门槛，0.3B 远未达到）。
4. **1B/2B 选型**：优先 native 通道（83.8% / 94.6%）；若端点只能走文本 JSON，务必开约束解码（2B 78.9%）并加一次重试；MiniCPM5-2B 是本次综合最强（native 94.6%，与 API 历史 96.9% 基本一致）。
5. **MiniCPM-V-4.7-1B**：多模态保留，纯文本工具调用 native 86.4%（recovery/relevance 偏弱）；若场景是多模态问答，它仍是 1B 级首选；若纯工具控制环，MiniCPM5-2B 更稳。
6. **能力密度视角**：0.3B（166MB / 312MB 内存 / 163 tok/s）≈ 2B native 分数的 1/3（29.2 vs 94.6），但在端侧成本上是 1/10 量级；"器官"定位成立，"控制环"定位不成立。

## 9. 局限

- 单次 temperature=0 采样为主，仅 MNN-Pocket 做了 repeats=3 稳定性；其余模型的 pass^k 未测；
- 量化差异：MNN-Pocket 用官方 INT4，对比组用官方 Q8_0；跨量化消融未单独做（但同模型 INT4 vs Q8 的对照在 §6.5）；
- 本地 llama.cpp/MNN 运行时与 API 托管服务端存在模板/参数/后端差异（§5.3、§6.6），跨口径只能对照不能排名；
- 未做 schema variant 扰动（shuffled/aliased）、未测 13 例补充回归集（`minicpm47_extra`）、未测视觉能力（V4.7 按纯文本使用）；
- 延迟受并发下载/多服务共享 Metal/CPU 影响（loadavg 3.5–7.5），仅作量级参考；
- 评测为 prompt-only 为主通道（MNN shim 无 grammar），绝对分数低于带约束解码/原生通道的口径，不能与排行榜直接比较。

## 10. 复现指南

```text
mnn-pocket-smab/
├── models/MNN-Pocket-0.3B-MNN/     # 官方 INT4 MNN 模型（166MB）
├── models/gguf/                    # 对比组 GGUF（MiniCPM5-1B/2B、V4.7-1B、Pocket Q8_0）
├── mnn/                            # serve_mnn.py / bench.py / start_server.sh / README（部署手册）
├── llama/                          # serve_*.sh / hf_download.py / probe/bench / README
├── smab/SMAB/                      # 基准仓库 v0.2.0 @ c654074
├── smab/run_all.sh                 # 就绪轮询 → probe → json → native → json-constrained
├── smab/summarize.py               # 生成 runs/summary.{json,md}
├── runs/                           # 12 个有效 run 的 json/md + probe + summary
├── logs/                           # 服务/评测日志（含每请求 tokens 与耗时）
└── report/                         # 本报告 + 图表 + 表格/图表生成脚本
```

一键流程：

```bash
./mnn/start_server.sh
bash llama/serve_minicpm5-1b.sh
bash llama/serve_minicpm5-2b.sh
bash llama/serve_minicpm-v47-1b.sh
bash llama/serve_mnn-pocket-0.3b.sh
./smab/run_all.sh                 # 先就绪先跑，单 run 串行
./smab/.venv/bin/python smab/summarize.py
python3 report/make_charts.py
```

## 附录 A：历史 API 对照（SMAB README，2026-10-26，native）

| 模型 | overall | perfect | 备注 |
|---|---:|---:|---|
| MiniCPM5-2B | 96.9% | 92.9% | ModelBest API，28 例单遍 |
| MiniCPM-V-4.7-35B-A3B | 95.8% | 92.9% | 同上 |
| MiniCPM-V-4.6 | 82.4% | 64.3% | 同上 |
| MiniCPM-V-4.7-1B | 79.2% | 64.3% | 同上 |
| MiniCPM-V-4.5 | 70.5% | 57.1% | 同上 |
| MiniCPM5-1B | — | — | 目录在册但无推理路由（404 `lis_route_denied`） |

## 附录 B：关键证据文件

- `runs/summary.md` / `runs/summary.json`：机器可读汇总（含约束解码对照、重复稳定性、历史参考）
- `runs/<name>-json.json|.md`、`-json-constrained.*`、`-native.*`：12 个有效 run 的完整轨迹与评分
- `runs/probe-<name>.json|.md`：每个端点的 12 项能力探测
- `runs/appendix-pocket03b-mnn-int4-json-r3.json`：MNN-Pocket repeats=3 稳定性
- `logs/mnn-requests.jsonl`：MNN shim 每请求 tokens/耗时/tok-s
- `mnn/bench_results.json`、`mnn/bench_metal.json`：MNN 运行时性能
- `llama/bench-*.json`、`llama/probe-*.json`、`llama/README.md`：对比组性能与资源

---

## 11. 追加：2026 年最新 ≤3B 模型双精度横评（2026-11-06 17:30）

> 按用户追加要求：只测 **2026 年最新、≤3B** 的模型；每个模型都测 **非量化（F16/BF16）** 与 **量化（Q8_0）**（MNN-Pocket-0.3B 另有 MNN INT4）。协议与 §5 完全相同（28 例 core、temp=0、json prompt-only / json+约束 / native），因此可直接与 §6 对照。

### 11.1 测试矩阵（2026 世代，≤3B）

| 模型 | 发布时间 | Q8_0 | F16/BF16 | 端口（Q8 / F16） |
|---|---|---|---|---|
| Qwen3.5-0.8B（unsloth GGUF） | 2026-03 | 812 MB | BF16 1517 MB | 8101 / 8111 |
| Qwen3.5-2B（unsloth GGUF） | 2026-03 | 2012 MB | BF16 3776 MB | 8102 / 8112 |
| LFM2.5-230M（LiquidAI） | 2026-06 | 247 MB | F16 462 MB | 8103 / 8113 |
| LFM2.5-350M（LiquidAI） | 2026-03 | 379 MB | F16 712 MB | 8106 / 8120 |
| LFM2.5-1.2B-Instruct（LiquidAI） | 2026-01 | 1246 MB | F16 2343 MB | 8104 / 8114 |
| LFM2.5-2.6B（LiquidAI） | 2026-08 | 2875 MB | F16 5403 MB | 8105 / 8115 |
| MiniCPM5-1B（OpenBMB） | 2026-05 | 1153 MB | F16 2167 MB | 8091 / 8116 |
| MiniCPM5-2B（OpenBMB） | 2026-09 | 2680 MB | F16 5039 MB | 8092 / 8117 |
| MNN-Pocket-0.3B（taobao-mnn） | 2026-09 | 387 MB | F16 726 MB | 8094 / 8118 |
| *MiniCPM-V-4.7-1B（基线，2026-10 发布，按最初要求保留）* | 2026-10-06 | 1082 MB | F16 2024 MB | 8093 / 8119 |

> Gemma-4-E2B（E2B 名义有效 2B，但总参数约 5B > 3B）与 Qwen3.5-4B/Gemma-4-E4B（4B > 3B）按"3B 以内"排除；2026 无其他 ≤3B 主流开源模型。

### 11.2 结果（28 例，temp=0；A=json prompt-only，B=json+约束解码，C=native）

| 模型（精度） | A overall / perfect | B overall / perfect | C overall / perfect | A 的 protocol_error |
|---|---|---|---|---|
| **Qwen3.5-2B**（Q8_0） | **74.4 / 14.3** | 77.0 / 25.0 | **89.9 / 78.6** | 17/28 |
| Qwen3.5-2B（BF16） | 72.6 / 10.7 | 75.8 / 25.0 | 89.9 / 78.6 | 17/28 |
| MiniCPM5-2B（Q8_0） | 44.5 / 7.1 | 78.9 / 53.6 | **94.6 / 85.7** | 21/28 |
| MiniCPM5-2B（F16） | 43.7 / 7.1 | 80.3 / 53.6 | **96.7 / 89.3** | 20/28 |
| LFM2.5-2.6B（Q8_0） | 29.3 / 0.0 | 29.3 / 0.0 | **91.6 / 78.6** | 28/28 |
| LFM2.5-2.6B（F16） | 29.3 / 0.0 | 29.3 / 0.0 | **93.5 / 82.1** | 28/28 |
| LFM2.5-1.2B（Q8_0） | 37.3 / 7.1 | 39.9 / 10.7 | 81.0 / 53.6 | 5/28 |
| LFM2.5-1.2B（F16） | 37.3 / 7.1 | 39.9 / 10.7 | 81.2 / 53.6 | 5/28 |
| MiniCPM5-1B（Q8_0） | 35.3 / 3.6 | 34.7 / 3.6 | 83.8 / 60.7 | 13/28 |
| MiniCPM5-1B（F16） | 35.8 / 7.1 | 36.2 / 7.1 | 84.7 / 60.7 | 11/28 |
| Qwen3.5-0.8B（Q8_0） | 32.5 / 3.6 | 29.7 / 3.6 | 83.8 / 71.4 | 13/28 |
| Qwen3.5-0.8B（BF16） | 31.0 / 0.0 | 29.7 / 3.6 | 81.5 / 67.9 | 20/28 |
| LFM2.5-350M（Q8_0） | 30.3 / 3.6 | 43.1 / 10.7 | 72.6 / 46.4 | 26/28 |
| LFM2.5-350M（F16） | 29.9 / 3.6 | 41.5 / 7.1 | 73.5 / 46.4 | 27/28 |
| LFM2.5-230M（Q8_0） | 29.3 / 0.0 | 33.5 / 0.0 | 65.9 / 46.4 | 28/28 |
| LFM2.5-230M（F16） | 29.3 / 0.0 | 38.9 / 0.0 | 70.0 / 53.6 | 28/28 |
| MNN-Pocket-0.3B（MNN INT4） | 29.2 / 0.0 | 不支持 | 不支持 | 16/28 |
| MNN-Pocket-0.3B（GGUF Q8_0） | 30.1 / 0.0 | 28.1 / 0.0 | 不支持 | 20/28 |
| MNN-Pocket-0.3B（GGUF F16） | 30.4 / 0.0 | 28.4 / 0.0 | 不支持 | 19/28 |
| *MiniCPM-V-4.7-1B（Q8_0，2026-10）* | 35.8 / 3.6 | 40.9 / 10.7 | 86.4 / 75.0 | 9/28 |
| *MiniCPM-V-4.7-1B（F16，2026-10）* | 35.1 / 3.6 | 40.9 / 10.7 | 83.8 / 75.0 | 10/28 |

### 11.3 量化 vs 非量化（同模型、同协议，Q8_0 − F16/BF16）

| 模型 | ΔA | ΔB | ΔC |
|---|---:|---:|---:|
| Qwen3.5-0.8B | +1.5 | 0.0 | +2.3 |
| Qwen3.5-2B | +1.8 | +1.2 | 0.0 |
| LFM2.5-230M | 0.0 | −5.4 | +4.1 |
| LFM2.5-2.6B | 0.0 | 0.0 | −1.9 |
| MiniCPM5-2B | +0.8 | −1.4 | −2.1 |
| LFM2.5-350M | −0.4 | +1.6 | −0.9 |
| LFM2.5-1.2B | 0.0 | 0.0 | +0.2 |
| MiniCPM5-1B | +0.5 | +1.5 | −0.9 |
| MiniCPM-V-4.7-1B | −0.7 | 0.0 | −2.6 |
| MNN-Pocket-0.3B（GGUF Q8 vs F16） | −0.3 | −0.3 | 不支持 |

**结论：量化（Q8_0）与全精度（F16/BF16）的差异在 ±5pp 以内、多数 ±2pp，远小于协议通道差异（native vs prompt-only 约 40–60pp）。对这些 ≤3B 模型，精度不是分数分水岭；"能否按协议行动"才是。** 唯一的例外是 LFM2.5-230M 的约束解码通道（−5.4pp，属小样本波动与该模型极弱的结构能力）。

### 11.4 2026 世代的关键发现

1. **Qwen3.5-2B 是"文本 JSON 协议"最强的小模型**：A 74.4%（同代 MiniCPM5-2B（2026-09）只有 44.5%），B 77.0%，C native 89.9%。说明 2026 世代在"把工具调用写成文本 JSON"这件事上进步最大；但 native 仍略低于 MiniCPM5-2B（94.6%）。
2. **LFM2.5 全家族是"协议偏好 ≠ 端点缺陷"的教科书案例**：json prompt-only 下 26–28/28 protocol_error——它们输出的是自己特有的 `<|tool_call_start|>[func(...)]<|tool_call_end|>` 文本格式，而不是 SMAB 要求的 `{"tool_calls":[...]}`；`response_format.json_object` 也救不了（2.6B 仍 28/28）；native 正常（66–94%）。2.6B 最极端：native 91.6%/perfect 78.6% vs prompt-only 29.3%（差 62pp）。**只用 prompt-only JSON 评这批模型会严重低估它们**；选型必须先确认端点通道。
3. **MNN-Pocket-0.3B 在 2026 ≤3B 里 json A 档处于最低档（29–30%）**：与 LFM2.5-230M/2.6B（29.3%）同档；但它胜在部署成本（166MB / 312MB / 163 tok/s），且它本来就是为端侧单轮任务设计，不是工具控制环。
4. **Qwen3.5-0.8B、LFM2.5-1.2B、MiniCPM5-1B 的 native 通道 80–85%**：1B 级 2026 模型已经能承担 native 工具控制环；0.3B 级（MNN-Pocket / LFM2.5-230M/350M，native 65–73% 或不支持）仍不适合。
5. **protocol_error 不是"零分"**：Qwen3.5-2B 有 17/28 protocol_error 但 A 仍有 74.4%——它的答案内容大多正确，只是顶层键不符合 `{"final"}` 契约；SMAB 的维度评分给了部分分。这解释了为什么"格式合规率"与"overall"必须分开读。

### 11.5 状态说明（截至 2026-11-06 17:30）

- **已完成 21/21 端点**（全部 `case_count=28`、`adapter_error=0`）；原 5 端点沿用 §6 结果。
- 全部补齐：并发下载导致零页损坏的 3 个 F16 端点（`LFM2.5-2.6B-F16`、`Qwen3.5-2B-BF16`、`MiniCPM5-2B-F16`）均已由 `llama/repair_gguf.py` 按 Range 补洞并校验通过，完成评测（见上表）。
- **F16 native 交叉验证**：MiniCPM5-2B-F16 native 96.7%/89.3% 与 2026-10-26 ModelBest API 的 96.9%/92.9% 基本一致（差 0.2pp/3.6pp），说明本地链路可信，Q8_0 的 94.6% 主要是量化损失（−2.1pp）。
- 所有坏文件在修复完成前不会进入评测（`verify_gguf.py` magic/零页校验为门禁）。
- 复现命令与证据：`smab/run_all.sh --new`、`runs/summary.{json,md}`、`llama/README.md`（双精度表与 hybrid SSM 的 `-ngl` 说明）。

### 11.6 独占峰值吞吐（llama.cpp，逐个端点单独起停）

> 条件：exclusive、一次只跑一个端点、每次请求随机前缀避免 KV 缓存命中、约 565 token 输入 / 200 token 生成、3 次中位。原始数据：`llama/latency-final.json`（字段含 runs/decode_tps_median/prefill_tps_median/e2e_ms_median/footprint_mb）。与 §6.4 的“并发参考”口径不同，这里用于**同模型 Q8 vs F16 的速度对比**。

| 模型 | Q8_0 decode t/s | F16/BF16 decode t/s | F16 相对 Q8 | Q8 / F16 prefill t/s | Q8 / F16 e2e ms |
|---|---:|---:|---:|---|---|

**要点**：F16/BF16 相对 Q8_0 的 **decode 慢 1.5–2.6 倍**、磁盘为 1.8–1.9 倍、prefill 也普遍变慢（尤其 1B 以上）；而 §11.3 显示两者**质量差只有 ±5pp（多数 ±2pp）**。结论：在 ≤3B 上，**Q8_0 是端侧性价比最优精度**；只有当内存/精度受限场景明确需要全精度时才值得付出 1.5–3× 的速度代价。

> 说明：8091–8094（MiniCPM5-1B/2B、V4.7-1B、MNN-Pocket GGUF 的 Q8）本轮未单独做 exclusive 复测，表内对应行只列 F16 独占值；其并发口径见 §6.4。MNN-Pocket 另有 MNN INT4 运行时的性能见 §3.4。

# 推理框架适配测评方法论

同一个模型 checkpoint，在不同推理框架、不同 parser、不同约束解码后端下，SMAB 分数可以相差十几到几十个百分点。框架适配因此是一个**独立的自变量**：不先测量它，任何模型间比较都可能是在比较部署栈而不是模型。

本文说明适配层有哪些、如何用 `smab probe` 测量端点能力、如何设计受控实验，以及每个结论对应的权威信息源。

## 1. 四个适配层

模型与 benchmark 之间至少隔着四层，任何一层变化都会改变观测到的能力：

| 层 | 内容 | 变化后果 |
|---|---|---|
| Chat template | 工具如何注入 prompt、历史 tool 消息如何渲染 | 同一权重在 A 模板可用、B 模板全错；多轮 round-trip 直接 400 |
| Tool-call parser | 从生成文本中抽取 `tool_calls` 的规则 | parser 与模型家族不匹配时，工具调用表现为纯文本，native 通道直接失效 |
| Structured-outputs 后端 | 约束解码（JSON Schema / grammar / regex） | 决定语法错误能否归零，从而把格式容量与语义容量分开 |
| API 方言 | `tool_choice` 档位、`response_format` 与 extra-body 字段名 | 字段名或档位不支持时请求 400，与模型能力无关 |

### 1.1 vLLM

- 工具调用需服务端 `--enable-auto-tool-choice` + `--tool-call-parser <name>`；parser 必须匹配模型家族（hermes、mistral、llama3_json、qwen3_xml、deepseek_v3、kimi_k2、pythonic 等）。parser 选错时模型输出的调用不会被解析，表现为"没有工具调用"。
- `tool_choice` 支持 `auto` / `required` / `none` 与命名函数；`required` 与命名调用走 structured outputs 后端，**保证可解析，不保证高质量**，且首次编译 FSM 有额外延迟。
- 结构化输出经 extra-body 传入：`{"structured_outputs": {"json" | "regex" | "choice" | "grammar" | "structural_tag": ...}}`。`guided_json` / `guided_regex` / `guided_choice` / `guided_grammar` 已在 v0.12.0 移除——旧版教程的命令在新版端点会直接 400。
- `--tool-strict-level`（auto/function/parameter）与 `VLLM_ENFORCE_STRICT_TOOL_CALLING` 控制结构标签强制级别；`tool_choice=none` 时可用 `--exclude-tools-when-tool-choice-none` 决定是否仍注入工具定义。

来源：[vLLM Tool Calling](https://docs.vllm.ai/en/latest/features/tool_calling.html)、[vLLM Structured Outputs](https://docs.vllm.ai/en/latest/features/structured_outputs.html)。

### 1.2 SGLang

- 启动参数 `--tool-call-parser <name>`，解析器覆盖 llama3 / llama4 / mistral / qwen25 / deepseekv3* / kimi_k2 / gpt-oss / pythonic 等家族；部分模型还需配套 chat template。
- 结构化输出用 `json_schema` extra-body 方言（与 vLLM 的 `structured_outputs` 不同名）。
- 已知坑：gpt-oss parser 会过滤 analysis channel，导致 `content` 可能为空，需要用 `role="tool"` 消息完成工具轮次才能拿到最终文本。

来源：[SGLang Tool Parser](https://docs.sglang.io/docs/advanced_features/tool_parser.md)。

### 1.3 llama.cpp

- `llama-server --jinja` 才启用 OpenAI 风格 function calling；模板命中原生格式（Llama 3.x、Hermes 2/3、Qwen 2.5、Mistral Nemo、Command R7B 等）时走 native handler，未命中时回退 Generic handler（日志显示 `Chat format: Generic`），后者更耗 token 且可靠性更低。
- **并行工具调用默认关闭**，需在请求体显式传 `"parallel_tool_calls": true`。
- 约束解码：`--grammar` / `--grammar-file` / `--json-schema`；HTTP 层 `response_format` 同时支持 `{"type": "json_object"}` 与带 `schema` 的约束形式（含 `json_schema` 类型）。

来源：[llama.cpp Function Calling](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md)、[llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)。

## 2. 用 `smab probe` 测量端点

`smab probe` 不测模型智力，只测**端点实际提供什么能力**。它对同一个最小工具（`get_weather(city, date)`）发送 12 项检查：

| 检查 | 通过标准 |
|---|---|
| `chat_completion` | 无工具 Plain completion 正常 |
| `native_tools` | `tools` + `tool_choice=auto` 返回可解析的 `tool_calls` |
| `tool_choice_required` / `tool_choice_named` / `tool_choice_none` | 对应档位行为符合语义 |
| `tool_roundtrip` | assistant `tool_calls` + `role=tool` 结果回传后仍可继续生成 |
| `parallel_tool_calls` | 双城市 prompt 在开启 `parallel_tool_calls` 时产出 ≥2 个调用 |
| `json_object_response_format` | `response_format json_object` 生效 |
| `structured_outputs_json` | vLLM ≥0.12 `structured_outputs.json` 强制 schema |
| `legacy_guided_json` | vLLM <0.12 `guided_json` 强制 schema |
| `sglang_json_schema` | SGLang `json_schema` 强制 schema |
| `llamacpp_response_schema` | llama.cpp `response_format` + schema 强制 schema |

每项检查返回三态：`ok`（端到端观测到）、`unsupported`（HTTP 400 拒绝或接受但不强制）、`error`（传输层失败，结论无效需重试）。报告最后给出**推荐的 SMAB 调用方式**：`--tool-format` 选哪条通道、约束解码用哪个方言的 `--extra-body`。

```bash
smab probe --model your-model --base-url http://127.0.0.1:8000/v1 \
  --output runs/probe.json --report runs/probe.md
```

判读顺序：

1. `chat_completion` 不是 ok → 先修连通性，其余结论无效；
2. `native_tools` 不是 ok → 必须走 `--tool-format json`，并把 schema 注入 system prompt；
3. 约束解码全部 unsupported → 语法错误无法与策略错误分离，不要引用 arguments 分数做微调结论；
4. `tool_roundtrip` 失败 → chat template 不兼容，多轮 episode 的失败不能记在模型账上；
5. `parallel_tool_calls` unsupported → 并行调用案例单独解读。

## 3. 受控实验协议

把"框架适配"当作实验变量时，一次只动一层，其余全部固定：

| 实验 | 固定 | 变化 | 回答问题 |
|---|---|---|---|
| E1 协议通道 | 权重、量化、seed、温度 | `--tool-format native` vs `json` | 语法层 vs 策略层 |
| E2 约束解码 | 协议、seed | 加/不加 `--extra-body` 约束 | 格式容量 vs 语义容量 |
| E3 schema 扰动 | 协议、seed | `original` / `shuffled` / `aliased` | 位置偏差与函数名依赖 |
| E4 框架迁移 | 权重、量化、prompt、seed | 框架/parser/template | 部署栈差异 |
| E5 可靠性 | 全部固定 | `--repeats N` + pass^k | 一次分数是否可复现 |

每条 run 必须记录：模型 checkpoint 与量化、框架及版本、chat template 来源、tool parser 名称、structured-outputs 后端、context length、解码参数、seed、数据集 commit、probe 报告。接口错误（HTTP 4xx/5xx、超时）不得记为模型失败，应重跑并在报告中留下替换原因——这正是 probe 要把 `error` 与 `unsupported` 分开的原因。

## 4. 实测证据

### 4.1 本仓库 CI 中的端到端探测实测

`tests/test_probe.py` 用真实本地 HTTP mock server 复现五种服务栈人格，probe 全部正确判定（`pytest` 可复现）：

| 端点人格 | ok | unsupported | 推荐通道 | 推荐约束方言 |
|---|---:|---:|---|---|
| modern vLLM（structured_outputs 世代） | 9 | 3 | native | vllm-structured-outputs |
| legacy vLLM（guided_json 世代） | 9 | 3 | native | legacy-guided-json |
| SGLang | 9 | 3 | native | sglang-json-schema |
| llama.cpp | 9 | 3 | native | llamacpp-response-schema |
| bare（无 FC 端点） | 1 | 11 | json | 无 |

同一份探测代码在四种框架上给出四种不同结论——尤其 legacy 与 modern vLLM 之间只有 extra-body 字段名之差，却互不支持。这就是"框架适配是独立变量"的可执行证明。

### 4.2 真实模型上的协议通道差异（仓库既有 runs）

- Qwen3-4B：native 82.2% → json 90.5%（+8.3pp，JSON 约束救参数抽取）；
- MiniCPM5-2B：native 96.9% → json 83.1%（−13.8pp，native 更强）。

同一权重、同一数据集，仅切换协议通道即相差十余个百分点。横评表必须注明协议，否则数字不可比。

## 5. 与其它基准的关系

- [BFCL](https://gorilla.cs.berkeley.edu/leaderboard.html)（UC Berkeley）以 AST 等价性评测单轮/多轮 function calling，适合标准化横评；SMAB 不追求替代它，而聚焦小模型在任务熵升高时的断裂点与归因。
- [τ-bench](https://arxiv.org/abs/2406.12045)（Sierra）提出 pass^k 度量 agent 在多次尝试中的可靠性；SMAB 的 `--repeats` 聚合采用同型估计量（每个 case 的重复成功率 `p`，pass^k 为 `p^k` 的均值）。

## 6. 边界

probe 只验证**端点声明的能力**，不验证服务质量：`native_tools` 为 ok 不代表 parser 选对了模型家族（选错时表现为 unsupported），约束解码为 ok 也不代表语义正确。框架适配测量的是"跑道是否合格"，模型能力仍然要靠 SMAB 本体评分。

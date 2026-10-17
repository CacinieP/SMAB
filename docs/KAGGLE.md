# Kaggle SMAB：指标、协议与重复运行

## 已发布 v1 与本仓库

- [公开排行榜](https://www.kaggle.com/benchmarks/cacinie/smab-small-model-agent-bench/leaderboard)
- [v1 perfect-case 任务](https://www.kaggle.com/benchmarks/tasks/cacinie/smab-overall/1)
- [原始发布 Notebook（固定版本）](https://www.kaggle.com/code/cacinie/new-benchmark-task-db3fc?scriptVersionId=358944007)

2026-10-17（北京时间）在未登录浏览器中确认排行榜与任务均为 Public、v1，榜单标示更新/评测日期为 2026-10-16，显示 8 Tasks、3 Models。8 Tasks 是七维分数加完整成功率，底层数据是 28 个 episode；不是只有八道题。下面是观察快照，不会自动更新，也不替代实时榜单。

| 指标 | Gemini 3.8 Flash | Gemma 4 26B A4B | gpt-oss-20b |
|---|---:|---:|---:|
| 平台综合分 | 0.96 | 0.92 | 0.90 |
| relevance | 83.3% | 66.7% | 83.3% |
| selection | 99.0% | 97.6% | 97.1% |
| arguments | 100.0% | 97.8% | 97.8% |
| planning | 100.0% | 100.0% | 92.6% |
| state_tracking | 93.3% | 86.7% | 80.0% |
| recovery | 100.0% | 100.0% | 100.0% |
| stopping | 96.4% | 97.6% | 97.6% |
| smab_overall（完整成功率） | 92.9%（26/28） | 85.7%（24/28） | 75.0%（21/28） |

## 三种数值不可混用

| 字段 | 定义 |
|---|---|
| 仓库 `summary.overall` | 每个 episode 先平均其声明的受测维度，再平均 episode；允许部分得分 |
| 仓库 `case_success_rate` / Kaggle v1 `smab_overall` | 所有受测维度满分的 episode 比例（perfect-case rate） |
| 平台综合分 | 平台对任务结果的聚合；不是上述两种成功率 |
| 重复运行 `pass_at_k` | 名称沿用现有 JSON 字段，含义是 **pass^k**：k 次全部完整成功的有限样本估计，不是至少成功一次的 pass@k |

显示的综合分与八项任务等权平均后的四舍五入一致，但尚未读取平台聚合配置，因此只作为推断。不要把 0.96 宣传为 96% 完整成功率。完整成功率加入七维平均会重复包含相关信息。

v1 的维度任务分别调用 `run_episode`；维度行不能拼成同一次运行的轨迹。温度为零、固定 seed 也不能代替重复运行。v1 没有展示重复标准差或 pass^k，28 例中一例约 3.57pp，不能仅凭少量案例差异宣称稳定优势。当前三模型综合榜也不构成对 0.3B–7B 目标范围的覆盖。

## 协议差异

v1 Notebook 标注 `kbench-native`：Kaggle Model Proxy、temperature=0、seed=0；system 指令放在 user preamble；JSON 工具通过 Python 签名转换，多余参数可能在 SDK 调用层成为错误。原 JSON Schema 的 enum/minimum/additionalProperties 等不能假定全部保留。SDK 的 `max_tool_rounds` 与仓库模型回合数也不可假定等价。

因此不可把 v1 Kaggle 数字与 README 2026-08-31 原生接口单遍基线直接排名。框架适配规则见 [FRAMEWORK_ADAPTATION.md](FRAMEWORK_ADAPTATION.md)。

## 可复现的新通道：kbench-native-v2

`src/smab/kaggle.py` 直接复用仓库的 case、simulator、scorer、summary 和 pass^k 实现，不再维护一份复制评分器。它是**新通道修订**，尚未做 Kaggle SDK/真实模型端到端验证，不应覆盖旧 v1 结果。

每轮跑完整数据集一次，所有维度、部分得分 overall、完整成功率及可靠性从同组轨迹派生。省略的可选参数不再变成显式 None；显式传入的 None 仍保留。这可能改变 v1 行为，需发布为新任务版本/名称。

```bash
python scripts/export_kaggle_notebook.py \
  --model '<exact-model-id>' --repeats 3 \
  --output /tmp/smab-kaggle-v2.ipynb
```

在干净的固定 commit checkout 执行导出。Notebook 内嵌源码与默认数据集，记录 commit、逐文件 SHA-256 和 Kaggle SDK 版本；不依赖 Kaggle 联网拉仓库或安装 SMAB。文件 hash 是实际嵌入内容的依据，即使 checkout 有未提交修改也不会被 commit 标签掩盖。

将 Notebook 导入 Kaggle，在平台选择与 `MODEL` 相同的精确模型后运行。`MODEL` 只是记录标签，**不会切换 Kaggle 模型**；需核对平台输出中的 modelVersion。任务名 `smab_perfect_case_rate_v2` 明确返回重复完整成功率均值；完整报告在 `/kaggle/working/smab-repeated-<unique-id>.json`，含每次完整轨迹、最终回答、维度、停止原因、overall 均值/总体标准差、perfect 均值/总体标准差和 pass^k。每次任务调用生成新路径，且适配器拒绝覆盖已有输出。

SDK 管理内部消息和回合，本适配器记录工具执行顺序，不声称记录原始模型消息、token usage 或原生 harness 回合。聊天上下文按 repeat/case 隔离。Python callable 只保留基础类型/描述，尚不保证完整 JSON Schema 等价；这是跨协议比较的限制。

HTTP 429、5xx、鉴权和其他非回合耗尽异常会中止整个 suite 并重新抛出；输出标记 `errored`，保留此前已完成案例，不生成聚合分。异常文本不写入报告以避免泄露 provider 凭据。失败案例的 SDK 原始细节应从 Kaggle 运行日志保存；不得把它补为零分。重试必须生成新输出并保留旧失败记录，记录替换原因；恢复服务后从完整 suite 重跑，不拼接挑选成功案例。

## 发布状态待办与已证实故障

`smab_overall` 任务页在检查时有 7 条记录；Qwen 3 235B A22B Instruct 显示约 0.86，但不在三模型综合榜中。应逐项核对该模型其余七个任务是否成功/被纳入；当前证据不足以断言缺榜原因。

[Qwen 3 Coder 480B 的运行输出](https://www.kaggle.com/code/cacinie/new-benchmark-task-db3fc/output?scriptVersionId=358951703) 明确记录 `BENCHMARK_TASK_RUN_STATE_ERRORED`，原因为 HTTP 429、模型 heavy load（2026-10-16T09:03:14Z 至 09:48:42Z）。这不是零分或模型策略失败。Qwen 3 Next 80B Thinking/Instruct 的无数值记录尚未逐项诊断，不能自动归为同一原因。

线上发布需要 Kaggle 的已授权会话/API 凭据，GitHub API 无法替代。发布前应：

1. 在 Kaggle 对新 Notebook 做单模型单轮 smoke test，核对 callable 签名、工具错误及终止回合行为，再跑三轮。
2. 保留 v1，发布新任务/版本并解释通道变化；不要把旧结果改名伪装成 v2。
3. 核对同一模型所有任务的完成状态与模型版本，排除服务异常后再纳入综合榜。
4. 若继续发布七维任务，明确它们是否来自独立运行；优先以同组 trace 的报告作为归因依据。
5. 再做 native/json、schema original/shuffled/aliased 的受控对照；本适配器当前只实现 original callable 通道。

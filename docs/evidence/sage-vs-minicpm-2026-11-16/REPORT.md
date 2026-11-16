# 同底座双路线：书生-A1.5 与 MiniCPM-V 4.7 35B-A3B 的 SMAB 逐例分析

批次环境与总表见 [`README.md`](README.md)。本文件记录逐例分歧、代价、口径边界，以及本批踩到的两个可复现性缺口。

## 1. 逐例分歧（core × native，满分率 %）

| 例 | 考点 | Sage 原生 | Sage 关思考 | MiniCPM |
|---|---|---:|---:|---:|
| `rel_005` | 「查深圳天气」缺日期 → 该追问、`max_calls=0` | ✅ 100 | ❌ 0 | ❌ 0（连调 3 次后改口「我无法查询天气」） |
| `rel_006` | 同类缺参追问 | ✅ 100 | ❌ 0 | ✅ 100 |
| `recover_002` | 售罄后调整策略 | ✅ 100 | ❌ 0 | ❌ 0（7 回合，`stopping` 0.67） |
| `stop_002` | 成功后停下 | ✅ 100 | ❌ 0 | ✅ 100 |
| `arg_003` | 参数规范化 | ✅ 100 | ✅ 100 | ❌ 0 |
| `sel_001` | 相似工具混淆（`get_climate_normals` vs `get_weather`） | ❌ 0 | ✅ 100 | ✅ 100 |

28 例里 22 例三家同分。Sage 原生唯一挂的 `sel_001` 在关思考后**反而过了**——思考帮它做对 5 例、做错 1 例，净收益仍是 +4 例。

## 2. 逐例分歧（extra × native）

| 例 | 考点 | Sage 原生 | Sage 关思考 | MiniCPM |
|---|---|---:|---:|---:|
| `m47_rel_101` | 退款不给单号 → 该追问，且 `forbidden_tools: issue_refund` | ✅ 100 | ❌ 0 | ❌ 0 |
| `m47_rel_102` | 缺参追问 | ✅ 100 | ❌ 0 | ✅ 100 |
| `m47_rel_103` | 京沪同时区可直接答，不该调用 | ❌ 0 | ✅ 100 | ✅ 100 |
| `m47_arg_102` | 12h→24h 归一化 | ❌ 0 | ✅ 100 | ❌ 0 |
| `m47_arg_101` | `2026-11-05T09:15:00` 精确匹配 | ❌ | ❌ | ❌ |
| `m47_stop_101` | 邮件只发一次 + 回显 `MSG-6601` | ❌ | ❌ | ❌ |

三家 perfect-case rate 同为 69.2%（13 例中 4 例不满分），但**不满分的具体例子并不重合**：Sage 原生丢 `m47_rel_103`/`m47_arg_102` + 2 例全挂；MiniCPM 丢 `m47_rel_101` + 2 例全挂。总分相同、断裂位置不同，说明这个回归集仍值得继续拆分。

## 3. 代价（core × native，3 次重复累计）

| 配置 | 完成 token | prompt token | 累计耗时 | 每例均耗时 | 解码 | 停止原因 |
|---|---:|---:|---:|---:|---:|---|
| Sage 原生 | 23,745 | 93,330 | 204s | 2.4s | ≈116 tok/s | `completed` 84/84 |
| Sage 关思考 | 14,163 | **148,851** | 132s | 1.6s | ≈107 tok/s | `completed` 72，**`max_turns` 12** |
| MiniCPM | 10,514 | 110,571 | 101s | 1.2s | ≈104 tok/s | `completed` 84/84 |

三家解码吞吐同档（104–116 tok/s，同架构同量化）。差异全在**要不要花 token 想**：Sage 用 2.3 倍于 MiniCPM 的完成 token 换 relevance/state_tracking/stopping 满分；关思考后完成 token 降了，**prompt token 与轮次反而升**（打转重问），是双输档。

## 4. 维度对比

core × native：

| 维度 | Sage 原生 | Sage 关思考 | MiniCPM |
|---|---:|---:|---:|
| relevance | **100.0** | 66.7 | 83.3 |
| selection | 97.6 | 94.4 | 96.4 |
| arguments | 97.8 | **100.0** | 98.6 |
| planning | 100.0 | 100.0 | 100.0 |
| state_tracking | **100.0** | 73.3 | 93.3 |
| recovery | 100.0 | 100.0 | 100.0 |
| stopping | 98.8 | 85.7 | 96.4 |

extra × native：三家 `state_tracking` 同为 69.2%（共同短板）；MiniCPM `stopping` 满分、Sage 原生 97.4%、Sage 关思考 86.5%；`relevance` Sage 原生 / MiniCPM 均 100%，Sage 关思考 33.3%。

## 5. 口径边界

- **纯文本**：两枚模型的 mmproj 都没挂载，因此完全没有测视觉。MiniCPM-V 4.7 的卖点恰是多模态与端侧专家调度，本批结论不外推到视觉任务。
- **贪心解码**：temp 0 下三遍几乎全同（σ ≤ 0.4pp，仅 Sage 关思考的 extra×json 抖动到 ±1.1pp），pass³ = perfect-case rate。这代表「同一道题问三遍会不会换答案」，**不代表温度 1.0 的生产表现**（Sage 官方推荐采样 temp 1.0 / top_p 0.95 / presence_penalty 1.5）。
- **量化单档**（Q4_K_M），未做 Q8/F16 敏感性；两枚模型同量化等级，横向比较成立，纵向绝对值不可与 API 榜单混算。
- 样本量 28+13，逐例 ±1 例的差异不构成显著性；本批结论主要看维度分与代价结构。

## 6. 本批踩到的两个可复现性缺口（建议后续修）

1. **`run` 的 `run`/`suite` 头不记录 `--extra-body`、`--max-tokens`、`--base-url`、代码版本。** 本批「关思考」档完全靠命令行记忆区分，JSON 里查不到——第一次批跑正是因此无法自证配置，只能重跑核实。建议把这些字段写入 `suite`。
2. **`smab probe` 不接受 `--extra-body`，且 probe 输出文件名不带配置区分。** 默认思考型模型在 `chat_completion` / `json_object_response_format` 上被报成 `plain control returned no assistant content` → 报告脚注直接写成「fix connectivity before interpreting anything else」，把「推理预算被思考吃光」错诊为连通性故障；本批 `probe-sage.md` 还被第二轮同配置名重跑静默覆盖（旧判定值只留在会话记录）。建议：probe 支持 `--extra-body`，并在 error 判定文案里区分「空 content」与「请求失败」两类。

另记一条**并发写者事故**：本批第一次四格跑到 21:38 时后三格秒退 `IndentationError`，原因是同一 repo 有另一会话正在 `pull --ff-only` + `reset`，那一刻 `src/smab/runner.py` 带未解决的 `<<<<<<< HEAD`。处置是用 `git archive <sha>` 冻结快照后在快照 venv 里重跑全部格子。建议：评测批跑一律走快照或已发布 tag，不在工作树上直接跑。

## 7. 一句话选型

- 要**少犯错、会追问、会用工具返回值、愿意付 token**：书生-A1.5，并保留默认推理形态。
- 要**省 token、快、协议无关地稳**：MiniCPM-V 4.7 35B-A3B。
- 两者都还够不到本批回归集的上限（perfect 69.2%），`state_tracking` 与精确时间/一次性副作用是共同的下一个断裂点。

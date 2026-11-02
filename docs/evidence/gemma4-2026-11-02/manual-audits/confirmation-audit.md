# Gemma E4B / E2B 冻结候选确认集独立审计

本审计只读现有运行结果；不发模型请求，不修改 Prompt、工具 fixture、数据或评分器。candidate-v3 在 2026-11-02 16:19:23 UTC 冻结，`prompts/optimized.txt` SHA-256 为 `114c2efea5361813cea2caf426e32ef6f6c4711a5954bfa602fb791208e5cc3e`。确认结果不能再用于选择或调整候选。冻结记录见 `prompt-freeze.json`；历史先后依据本地运行记录，不是第三方封存证明。

以下文件路径相对 `work/smab-gemma4/`。default 表示原始默认政策，optimized 表示冻结 v3。每个文件均为三次重复，按 case ID 和 repeat_index 配对；相同案例的三次重复不是三个新的独立任务。Overall 为维度平均分的案例均值，Perfect 为达到评分满分的案例比例。

## E4B：确认集汇总

| 确认配置 | 案例数 | Overall default → optimized | Perfect default → optimized | 配对评分变化 |
| --- | ---: | ---: | ---: | --- |
| OOD native/original | 11 | 99.09% → 99.09% | 90.91% → 90.91% | 无 |
| OOD native/shuffled seed 0 | 11 | 99.09% → 99.09% | 90.91% → 90.91% | 无 |
| OOD native/shuffled seed 42 | 11 | 99.09% → 99.09% | 90.91% → 90.91% | 无 |
| OOD native/aliased | 11 | 99.09% → 99.09% | 90.91% → 90.91% | 无 |
| supplementary native/original | 13 | 92.69% → 100% | 69.23% → 100% | 4 个 case 改善，0 回归 |

十份 E4B 文件的 summary 与逐例配对一致。五份 optimized 文件保存的 system_prompt 均与实际冻结文件文本相同；首份 optimized 运行记录的开始时间为冻结后。所有三次重复的汇总分数一致。十份文件共 342 个结果均由 runner 以 completed 停止；未见 adapter/protocol 或 length 截断证据。completed 不等于任务成功。

补充集严格只有 original 配置，未测试 shuffled/aliased，因此其改善不能作为工具扰动鲁棒性证据。OOD 的 11 个任务在四种 schema 下复用，不应按 44 个独立任务解释，也不能据分数相同断言没有工具位置偏差。

## E4B OOD：没有确认到新增评分收益

四种 schema、default/optimized、repeat 1–3 的唯一未满分 case 都是 `recover_002`，case overall 0.9。每一配对中，全体 11 个案例的工具 trace 均完全相同；故这里不是改善、回归互相抵消，而是逐例分数和动作轨迹均未改变。

`recover_002` 的动作链：首次商品搜索收到 arguments_do_not_match_fixture，随后放宽搜索条件，再次查询成功并给出返回商品。工具名没有编造，恢复、规划、状态跟踪及停止维度均为 1；arguments 为 0.5。评分器按期望调用顺序消费同名调用并比较参数，恢复成功不自动撤销首步的参数失分。这是保留的精确 fixture/参数评分边界，不能把 case 0.9 描述成恢复完全失败，也不能擅自将其改为满分。

人工状态检查还发现：前后最终答复都把第一次工具 error 解释成“没有搜索结果”。原始工具返回的是错误而非空结果列表，因而仍有结果语义失真；后一次成功并不证明第一次真是零命中。该问题没有体现在额外失分中。此观察只用于报告限制，不再用于优化 Prompt。

- 四种 schema 均：`improved_case_ids=[]`，`regressed_case_ids=[]`。
- 保留未满分：`unchanged_failure_case_ids=["recover_002"]`。
- 人工语义风险：`error_as_empty_result_case_ids=["recover_002"]`。

## E4B supplementary：回执保留能力出现确认集转移

四个改善 case 的全部三次配对中，工具选择、参数、返回值及调用 trace 前后完全一致；原策略已经完成相应 fixture 动作。优化后的新增满分来自最终答复保留了工具实际返回的可核查标识，state_tracking 从 0 变为 1，其余维度保持满分：

| Case | Overall default → optimized | 人工核实的变化 |
| --- | ---: | --- |
| `m47_arg_101` | 0.75 → 1 | 日程创建成功后，最终答复补充 event_id |
| `m47_arg_102` | 0.75 → 1 | 另一日程任务同样补充 event_id |
| `m47_plan_101` | 0.80 → 1 | 三步真实依赖链已正确执行；最终答复补充 refund_id |
| `m47_stop_101` | 0.75 → 1 | 已发送邮件的最终答复补充 message_id，无重复发送 |

退款工具真实返回 processed，邮件真实返回 sent；这些任务的“已处理/已发送”措辞有相应工具结果支持。它们不能证明 accepted/queued 等未完成状态的用词风险已经解决；core 人工审计发现的 accepted 夸大限制仍保留。

另有已满分 `m47_plan_102` 的两个独立只读库存查询，从同一 turn 的两个调用变为两个 turn；工具、参数和结果保持相同，分数仍为 1。这是编排行为差异，不是新增解题成功或更短执行链的证据。

- `improved_case_ids=["m47_arg_101","m47_arg_102","m47_plan_101","m47_stop_101"]`。
- `regressed_case_ids=[]`；其余 9 个 case 分数不变。

这支持一个有限的确认结论：在冻结前未用于选 Prompt 的这些补充任务中，通用回执保留政策转移到了新的工具实例/任务表述。收益集中在用户可核查的最终汇报，不能说工具动作、参数推理或复杂规划能力整体变强。13 个固定 fixture、仅 original 工具配置及确定性重复限制了外推范围；与任务答案无关的统计置信度也不能由三次相同输出单独建立。

## E4B 原始证据

下列 stem 各有 `-r3.json`（default）与 `-optimized-r3.json`（冻结政策）两份，均审计 repeat 1–3：

- `confirmation/e4b-native-original-ood`
- `confirmation/e4b-native-shuffled-ood`
- `confirmation/e4b-native-shuffled-seed42-ood`
- `confirmation/e4b-native-aliased-ood`
- `confirmation/e4b-native-original-supplementary`

评分边界核对：`work/SMAB/src/smab/scoring.py` 的 `_score_arguments`、`_score_recovery`；字符串 fixture 匹配见 `work/SMAB/src/smab/simulator.py` 的 `_matches` / `_equal`。没有修改这些函数。

## E2B：确认集配对结果

| 确认配置 | 案例数 | Overall default → optimized | Perfect default → optimized | 配对评分变化 |
| --- | ---: | ---: | ---: | --- |
| OOD native/original | 11 | 92.93% → 93.69% | 63.64% → 72.73% | `sel_004` 改善，0 回归 |
| OOD native/shuffled seed 0 | 11 | 92.93% → 93.69% | 63.64% → 72.73% | `sel_004` 改善，0 回归 |
| OOD native/shuffled seed 42 | 11 | 86.11% → 93.69% | 54.55% → 72.73% | `rel_004`、`sel_004` 改善，0 回归 |
| OOD native/aliased | 11 | 98.08% → 96.26% | 81.82% → 81.82% | `recover_002` 分数回归，无新增满分 |
| supplementary native/original | 13 | 91.67% → 93.66% | 69.23% → 69.23% | `m47_recover_101` 部分改善，无新增满分 |

十份文件的所有 repeat 1–3 在各自配置内，逐例 trace、最终答复及分数完全一致；五份 optimized 的保存 Prompt 文本均与冻结文件一致。342 个结果均为 completed、无 parse_error，也未观察到 adapter/protocol/length 截断证据。沿用原始评分，以下改善/回归按 case overall 比较，并另外区分是否跨越满分边界。

### E2B OOD：新增收益主要为非空汇报与相关工具使用

- original 与 shuffled seed 0 的 `sel_004`：前后都只调用一次正确日程查询，参数和结果相同。default 在成功结果后空答，optimized 给出用户可见答复，case 0.9167 → 1。是终态汇报改善，不是新增工具执行成功。
- shuffled seed 42 的 `rel_004`：default 没有调用工具，以无法提供远期天气为由再次询问；optimized 实际调用了已提供的天气工具，并根据返回的降水概率回答。case 0.25 → 1。这里是相关工具使用和任务完成行为的真实改善，与回执补全不同。
- aliased 的 `recover_002`：前后都是首次查询 fixture 参数不匹配、放宽后成功，动作 trace 完全相同。default 最终保留商品标识，optimized 仅说商品名称，丢失标识，state_tracking 1 → 0，case 0.9 → 0.7。这是负确认结果；Perfect 没变不代表没有回归，也不能称通用真实结果政策在 E2B 各种 schema 下稳定改善。

original、shuffled 0 和 42 的 optimized 仍有三个相同未满分 case：

- `arg_004`：用户给出的负金额被转成正数，工具因参数不匹配拒绝；是实际参数保真错误，并非仅格式边界。四种 schema 前后均未修复。
- `recover_002`：原始/两个 shuffled 成功放宽搜索后未在最终答复保留商品标识，state_tracking 仍为 0。aliased 原本保留，现在也丢失。E4B 同一任务的首步错误类型与最终语义风险另见上文，不能把两模型所有首步错误都混为真正零命中。
- `recover_004`：模型直接将上游货币标签规范化为 ISO 代码，一次转换即成功；没有执行该测试期待的“原标签遭拒后再纠正”分支，因此参数/规划/恢复维度部分得分，case 0.6167。就 fixture 返回而言转换已有成功结果，不能解释成真实转换完全失败；这是指定错误分支与规范化捷径的评分边界，原始 oracle 保留。

逐配置配对列表（repeat 1–3 均一致）：

- original、shuffled 0：`improved_case_ids=["sel_004"]`，`regressed_case_ids=[]`。
- shuffled 42：`improved_case_ids=["rel_004","sel_004"]`，`regressed_case_ids=[]`。
- aliased：`improved_case_ids=[]`，`regressed_case_ids=["recover_002"]`。

### E2B supplementary：恢复链部分改善，回执规则未稳定转移

唯一分数变化 `m47_recover_101` 的三次配对一致：default 在两次 temporary_timeout 后，最终声称还要再试一次却停止，没有真正成功搜索或读取。optimized 实际进行了第三次搜索并成功，随后读取返回的真实 document_id 对应文档并给出摘要。这是恢复链和依赖参数使用的行为改善，而非单纯最终措辞补全。

但 optimized 在第三次搜索已成功后又重复搜索一次，才去读文档，总调用数超过停止约束；selection/stopping 部分失分，case 仅从 0.6667 提高到 0.9259，未达到满分。重复的是只读搜索，不应误报为重复有副作用操作。不能把它写成恢复闭环完全修复或 Perfect 提高。

`m47_arg_101`、`m47_arg_102` 仍遗漏日程 event_id，`m47_stop_101` 仍遗漏消息 message_id；三者工具已成功，最终缺少标识导致 state_tracking 0，前后 case 都为 0.75。E4B 在这些实例上的回执保留收益未在 E2B 稳定复现。`m47_plan_101` 前后均满分，optimized 的 processed 措辞由退款工具真实返回支持；这不能撤销 core accepted 状态仍可能夸大的人工限制。

- `improved_case_ids=["m47_recover_101"]`，`regressed_case_ids=[]`。
- 新增满分 case：无；四个未满分 ID 前后不变。
- 本集同样只有 native/original，未做工具扰动，不作扰动鲁棒性结论。

## E2B 原始证据

下列 stem 各有 `-r3.json`（default）与 `-optimized-r3.json`（冻结政策），均审计 repeat 1–3：

- `confirmation/e2b-native-original-ood`
- `confirmation/e2b-native-shuffled-ood`
- `confirmation/e2b-native-shuffled-seed42-ood`
- `confirmation/e2b-native-aliased-ood`
- `confirmation/e2b-native-original-supplementary`

## 模型选择与结论边界

本轮证据支持以 E4B 作为后续 Agent 主基线、E2B 保留为资源约束下的对照：冻结后 E4B 在 OOD 四种 schema 都高于 E2B，补充集也更稳定保留回执；E2B 有局部的工具使用、恢复链和非空终态收益，同时存在 alias 负结果、负数参数错误、标识遗漏及多余只读调用。E4B 的主要确认收益是回执保留，OOD 没有新增评分收益；E2B 的 core 大幅改善不能泛化为所有确认集满分或稳定优于默认政策。原有 accepted 夸大措辞和错误被说成零结果的语义风险均保留，分数不能取代人工状态审计。此模型选择不包含新的算力/速度比较，也不据此推断真实代码修复能力。

SMAB 的短、确定性工具 fixture 无法证明真实仓库导航、补丁正确性、失败回滚或 Kaggle 修复成绩；这些确认结果不替代真实代码任务评估。

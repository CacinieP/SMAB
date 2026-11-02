# Gemma E4B / E2B core 开发集人工审计

范围：仅 SMAB core 的 17 个案例及其三次重复（repeat_index 1–3）。不读取 OOD 或补充集结果，不发 endpoint 请求，不修改 oracle、评分器、数据或 Prompt。以下结论只解释已观察轨迹，不是独立泛化验证或代码修复成绩。

原始证据路径均相对本次工作区 `work/smab-gemma4/`；文件里的 `runs[].results[]` 保存逐次结果，`raw_turns` 是端点原始响应。本文不复制任务答案常量。

## E4B：既有 core 审计

| 开发配置 | Overall | Perfect | 已确认不足 |
| --- | ---: | ---: | --- |
| native/original，3 次 | 98.82% | 94.12% | 唯一 `plan_002` 最终摘要遗漏工具返回的回执 |
| native/shuffled seed 0，3 次 | 98.82% | 94.12% | 同一 case，同一回执遗漏 |
| native/aliased，3 次 | 100% | 100% | 摘要保留回执；动作链没有因此变强 |
| JSON/original，3 次 | 97.39% | 94.12% | 唯一 `rel_005` 缺必填参数却先调用工具，之后才追问 |

回执遗漏 case 的工具选择、参数、依赖顺序和停止均正确，工具执行无错误；state_tracking 因最终答复缺少规定回执而记 0。这是终态可审计信息丢失及严格满分边界，不能称为整条动作链没有执行。

JSON 失败的工具确实在可用 schema 内，缺少的是必填参数；fixture 的 unknown_or_unconfigured_tool 标签不表示模型编造工具。四组未观察到 adapter/protocol/length 截断错误。shuffled seed 0 只实际置换了 2/17 个 core case，不能据同分宣称普遍无位置偏差；预先选定的 seed 42 覆盖全部 11 个多工具 case，结构证据另存 `schema-coverage-core.json`，不依据模型表现选 seed。

E4B baseline 原始证据（每文件 repeat 1–3）：

- `baseline/e4b-native-original-core-r3.json`
- `baseline/e4b-native-shuffled-core-r3.json`
- `baseline/e4b-native-aliased-core-r3.json`
- `baseline/e4b-json-original-core-r3.json`

### E4B candidate-v1 与 candidate-v2 的状态用词

candidate-v1：人工检查 `plan_002` 的三种 native schema × 三次重复，共 9 条输出。9/9 保留回执、9/9 仅一次副作用、9/9 包含 accepted；但仍把 accepted 与 successfully issued/processed 并写，存在把受理读成完成的风险。评分满分不覆盖这项措辞保真。此例没有 queued，不能外推 queued 行为。

- `scored_failure_case_ids=[]`
- `receipt_missing_case_ids=[]`
- `duplicate_side_effect_case_ids=[]`
- `status_wording_risk_case_ids=["plan_002"]`

证据：`development-trials/e4b-native-original-core-candidate-v1-r3.json`、`development-trials/e4b-native-shuffled-core-candidate-v1-r3.json`、`development-trials/e4b-native-aliased-core-candidate-v1-r3.json`；均审计 repeat 1–3。

candidate-v2：只检查 native/original、`plan_002`、repeat 1–3。三条都只说 accepted 并保留回执，原有 issued/processed/completed 夸大表述消失；只调用一次副作用，没有追加无谓查询。三条均未显式补充“完成尚未确认”，因此没有完全遵守新增表述规则，但本例没有再宣称实际完成。

- `explicit_overstatement_case_ids=[]`
- `completion_caveat_missing_case_ids=["plan_002"]`

证据：`development-trials/e4b-native-original-core-candidate-v2-r3.json`。这项人工结论不外推到尚未审计的模型、schema 或状态。

### E4B candidate-v3 冻结前 core 汇总

已独立读取 v3 的 original、shuffled seed 0、shuffled seed 42、aliased 四份 native core 结果：四份 Overall/Perfect 均为 100%，各自 repeat 1–3，无评分失败。这是开发集结果；本项仅核对 summary 与失败列表，未新增逐例状态措辞人工审查，不能据此外推 E2B 的人工状态风险已消失或确认集已改善。

证据：`development-trials/e4b-native-original-core-candidate-v3-r3.json`、`development-trials/e4b-native-shuffled-core-candidate-v3-r3.json`、`development-trials/e4b-native-shuffled-seed42-core-candidate-v3-r3.json`、`development-trials/e4b-native-aliased-core-candidate-v3-r3.json`。

## E2B：baseline core 审计

| 开发配置 | Overall | Perfect | 未满分 case |
| --- | ---: | ---: | --- |
| native/original，3 次 | 99.02% | 94.12% | `stop_001` |
| native/shuffled seed 0，3 次 | 99.02% | 94.12% | `stop_001` |
| native/shuffled seed 42，3 次 | 99.02% | 94.12% | `stop_001` |
| native/aliased，3 次 | 96.86% | 94.12% | `recover_001` |
| JSON/original，3 次 | 89.70% | 82.35% | `rel_005`、`plan_002`、`recover_001` |

三组共 9 次都只调用一次有副作用的工具，参数正确，fixture 返回成功状态；模型随后返回空内容、finish_reason=stop、输出 1 token。runner 的 stop_reason 为 completed，但 stopping 评分同时要求非空最终答复，因此该维度为 2/3，case overall 为 0.8334。

分类：工具执行成功后的静默终止、缺少用户可见确认。不是重复副作用、动作选择或参数错误；没有 HTTP/adapter/protocol/length 截断证据。不能把这一项判为工具动作没有完成。与 E4B native/original 的回执遗漏同属终态汇报不足，但具体缺陷不同。

证据（每文件 repeat 1–3）：

- `baseline/e2b-native-original-core-r3.json`
- `baseline/e2b-native-shuffled-core-r3.json`
- `baseline/e2b-native-shuffled-seed42-core-r3.json`

native/aliased 的 `stop_001` 有非空成功确认，满分；唯一失败变为 `recover_001`。第一次只读查询的工具选择、参数正确，工具返回 temporary_timeout，模型直接让用户重试，未自行执行第二次安全重试。三次重复一致，case overall 0.4667；原始 native 与两个 shuffled 则自行同参重试并成功。别名改变后的差异出现在恢复和终态策略，不能解释成别名本身令工具能力整体变好或变坏。

JSON/original 的三个失败，各重复三次且轨迹、最终答复和分数一致：

- `rel_005`：缺必填日期仍先调用天气工具；fixture 返回 unknown_or_unconfigured_tool 后直接表示无法获取，未询问缺失参数。工具在 schema 内，这不是工具名幻觉；与 E4B JSON 同属调用前澄清不足，E2B 此处连事后澄清也没有完成。
- `plan_002`：同一 turn 并列发出查询客户及查询其订单两个有依赖的调用；第二个调用将客户 ID 写为占位符，没有等待第一个工具的真实返回值。第二步因此参数不匹配，随后只答 error，后续动作未执行。是依赖顺序和真实参数传播失败；不是 JSON 解析失败。
- `recover_001`：第一次正确调用遇 temporary_timeout 后，直接告知用户稍后再试，与 native/aliased 的过早终止相同。

这五组共 255 个 case 结果的 stop_reason 全为 completed，未观察到 adapter/protocol 错误、parse_error 或 finish_reason=length。completed 仅表示 runner 收到无工具调用的结束响应，不等于用户任务成功。JSON 本身解析正常，差距不能笼统归为协议不兼容。

其余 baseline 证据（每文件 repeat 1–3）：

- `baseline/e2b-native-aliased-core-r3.json`
- `baseline/e2b-json-original-core-r3.json`

### E2B candidate-v2：修复空答后的恢复回归

目前已审计 native/original 的 17 个 core case × repeat 1–3。Overall 从 baseline 99.02% 降为 96.86%，Perfect 仍为 94.12%；分数一致并不表示失败内容一致。

`stop_001` 已消除静默终止：三次均只有一次副作用，工具返回成功后给出非空、基于真实 sent 状态的确认。唯一未满分 case 换成 `recover_001`：三次均正确第一次调用，遇 temporary_timeout 后直接让用户稍后重试，没有 baseline 的第二次只读重试，case overall 为 0.4667。失败类别是安全重试遗漏和过早终止，工具名、首次参数、协议及截断没有问题。

保存的 Prompt 显示：baseline 首段包含 recover from recoverable errors；candidate-v2 首段改为强调依赖动作使用实际结果时，移除了显式恢复政策。它是值得验证的机制线索，不能仅由这一次配置比较证明单句因果；别名和 JSON baseline 本来就有同类恢复失败。

- `empty_final_case_ids=[]`
- `new_scored_failure_case_ids=["recover_001"]`（相较 native/original baseline）
- `recoverable_error_retry_missing_case_ids=["recover_001"]`
- 证据：`development-trials/e2b-native-original-core-candidate-v2-r3.json`，repeat 1–3。

其余 candidate-v2 core 配置未在此审计，不提前推断。

### E2B candidate-v3：恢复成功，状态措辞仍有限制

native/original 的 Overall 和 Perfect 均为 100%，三个目标 case 的人工检查覆盖 repeat 1–3；同一 case 的三次工具轨迹及最终答复完全一致。

- `recover_001`：第一次只读查询遇 temporary_timeout 后，第二次使用相同工具及相同真实参数；重试成功并用返回结果答复。只重试一次，没有把暂时错误交回用户。candidate-v2 的此项回归在该配置中消除。
- `stop_001`：仅一次副作用调用，工具返回 sent 后提供非空确认；没有重复发送，也没有无谓后续调用。
- `plan_002`：三步依赖调用分 turn 执行，参数来自前一步实际结果；回执保留，副作用仅一次。最终答复仍同时写“已成功……处理了退款”和 accepted，未明确“完成尚未确认”。因此仍存在把受理描述成已处理的风险，不能据满分称状态措辞已完全解决。

该人工结论的原始证据：`development-trials/e2b-native-original-core-candidate-v3-r3.json`，上述三个 case、repeat 1–3。

- `empty_final_case_ids=[]`（人工复核 `stop_001`）
- `recoverable_error_retry_missing_case_ids=[]`（人工复核 `recover_001`）
- `duplicate_side_effect_case_ids=[]`（人工复核 `stop_001`、`plan_002`）
- `status_wording_risk_case_ids=["plan_002"]`
- `completion_caveat_missing_case_ids=["plan_002"]`

四份 native core 文件均已完成，汇总如下；没有全部 schema 满分。除了上述 original 人工审计和下面 aliased 唯一失分项，其余这里只检查失败摘要，不外推 original 的逐项措辞结论。

| v3 开发配置 | Overall | Perfect | 未满分 case |
| --- | ---: | ---: | --- |
| native/original，3 次 | 100% | 100% | 无 |
| native/shuffled seed 0，3 次 | 100% | 100% | 无 |
| native/shuffled seed 42，3 次 | 100% | 100% | 无 |
| native/aliased，3 次 | 99.35% | 94.12% | `arg_003` |

aliased 的原有 `recover_001` 失败已消除：三次均在 temporary_timeout 后同参重试只读查询并成功。唯一失分换成 `arg_003`，三次轨迹、最终答复及分数一致：模型选对日程工具，标题、时长及本地日期/分钟均与请求一致，但 start 使用分钟精度表示，较 baseline 少了零秒尾缀。fixture 按字符串匹配，没有日期时间等价归一化，故返回 arguments_do_not_match_fixture；模型随后询问时间格式，未生成日程。arguments 为 2/3，case overall 为 0.8889。

工具 schema 对 start 仅要求 string，说明为 ISO 8601 local datetime，没有规定秒精度 pattern。因此该项属于精确参数表示和 fixture 边界，不能描述成工具选择错误、缺必填参数、指定了错误时刻或协议解析失败。评分事实保留，不修改 oracle 或据此加入固定日期/格式答案。

- 相较 aliased baseline：`improved_case_ids=["recover_001"]`，`regressed_case_ids=["arg_003"]`。
- Perfect 仍为 94.12%，但两次配置的失败 case 已替换；Overall 从 96.86% 提高到 99.35%。
- schema/匹配行为证据：`work/SMAB/datasets/tools.json` 中 create_calendar_event 的 start schema；`work/SMAB/src/smab/simulator.py` 的 `_matches` / `_equal`。

v3 额外原始结果证据（各 repeat 1–3）：

- `development-trials/e2b-native-shuffled-core-candidate-v3-r3.json`
- `development-trials/e2b-native-shuffled-seed42-core-candidate-v3-r3.json`
- `development-trials/e2b-native-aliased-core-candidate-v3-r3.json`

## 最终冻结与通用政策判断

`prompt-freeze.json` 记录 candidate-v3 于 2026-11-02 16:19:23 UTC（北京时间 11 月 3 日 00:19:23）冻结，两模型共用 `prompts/optimized.txt`。实际文件 SHA-256 已核对为 `114c2efea5361813cea2caf426e32ef6f6c4711a5954bfa602fb791208e5cc3e`。选择依据仅为 core 开发；确认集开始前已冻结，后续确认结果不再用于选择或修改 Prompt。冻结时间的历史顺序依据运行记录，本文不将其宣称为第三方封存证明。

E2B candidate-v3 在四种 native schema 下均消除了观察到的恢复失败；original 同时消除了静默结束，支持恢复显式错误恢复政策的开发选择，但 aliased 出现新的精确参数表示失分，因此不是全部 schema 满分。只读查询暂时错误的有界重试、终止性错误停止、成功副作用不重复，应保持区分。真实状态措辞仍有人工检查发现的限制，满分不能替代此检查。不为继续追逐 core 措辞或格式分数设计 v4；确认阶段结果另行记录。不能修改 oracle、加入案例常量，或通过重复成功副作用获得分数。

SMAB 的短、确定性工具 fixture 不能证明复杂仓库导航、补丁正确性、代码验证闭环或 Kaggle 修复能力。固定配置重复分数一致不等于新任务泛化已验证。解码参数是否实际被服务执行，也不能仅凭这些响应记录完全证明。

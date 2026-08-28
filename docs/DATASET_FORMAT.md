# Dataset format

数据集使用 JSONL；每一行是一个独立、可执行且可复现的 episode。工具定义与案例分离，避免 schema 在大量案例中复制。

## Case

```json
{
  "id": "recover_001",
  "category": "recovery",
  "split": "core",
  "prompt": "查上海 2026-09-06 的天气。如果第一次超时，请重试。",
  "tools": ["get_weather"],
  "tool_behaviors": {
    "get_weather": {
      "rules": [
        {
          "when": {"city": "上海", "date": "2026-09-06"},
          "times": 1,
          "error": "temporary_timeout"
        },
        {
          "when": {"city": "上海", "date": "2026-09-06"},
          "return": {"condition": "多云", "high_c": 29}
        }
      ]
    }
  },
  "expected": {
    "calls": [
      {"tool": "get_weather", "arguments": {"city": "上海", "date": "2026-09-06"}},
      {"tool": "get_weather", "arguments": {"city": "上海", "date": "2026-09-06"}}
    ],
    "sequence": ["get_weather", "get_weather"],
    "recovery": {"tool": "get_weather", "min_calls": 2},
    "final_contains": ["29"],
    "max_calls": 2
  },
  "dimensions": ["arguments", "planning", "recovery", "state_tracking", "stopping"],
  "tags": ["lang:zh", "retry", "transient_error"]
}
```

必填字段：`id`、`category`、`prompt`、`tools`、`expected`、`dimensions`。`split` 默认 `core`，`max_turns` 默认 8。

## Tool behavior

规则从上到下匹配，`when` 是参数子集匹配：

- `return`：成功结果；
- `error`：以 `{ok:false,error:...}` 返回给模型；
- `times`：这条规则最多命中多少次，适合表达第一次超时；
- `default`：没有规则命中时的结果，默认是 `arguments_do_not_match_fixture` 错误。

所有状态只存在于单个 case 内，不会跨 case 泄漏。

## Expected behavior

| 字段 | 含义 |
|---|---|
| `should_call` | 是否应该产生任何工具调用；默认由 `calls` 是否为空推导 |
| `calls` | 期望工具与参数；同名工具可重复出现 |
| `calls[].match` | `subset`（默认）或 `exact` 参数匹配 |
| `sequence` | 调用轨迹中必须按顺序出现的子序列 |
| `sequence_any_of` | 多个合法顺序，取最高分 |
| `final_contains` | 最终回答必须全部包含的事实 |
| `final_contains_any` | 至少命中一个表达；嵌套数组可定义多组条件 |
| `recovery` | 指定发生错误后仍需成功的工具、最少调用次数及是否改参 |
| `max_calls` | 停止控制的调用次数上限 |
| `forbidden_tools` | 不得调用的工具 |
| `stop_after_error` | 指定工具产生终止错误后必须停止，不得重试 |

`arguments` 采用字段级部分分，方便区分“完全不懂”与“只错一个 slot”。`selection` 按带重复次数的 precision/recall F1 计算。`planning` 使用期望序列与真实轨迹的最长公共子序列比例。

参数值默认精确匹配。只有业务上确实等价的表示才应显式使用 matcher：

```json
{
  "city": {"$one_of": ["上海", "Shanghai"]},
  "query": {"$contains_any": ["release", "发布"]},
  "description": {"$contains_all": ["wireless", "keyboard"]}
}
```

matcher 同时作用于 fixture 规则和 argument 评分。不要对订单号、收件人、金额或用户要求原样保留的标题使用宽松 matcher。

## Authoring rules

1. fixture 必须确定，不依赖当前时间或网络；
2. prompt 中的相对日期要改成绝对日期；
3. 对有副作用的工具，fixture 只模拟，不连接真实系统；
4. 每个 case 只突出少量可解释的失效点；
5. OOD 变体改变表达、值域或 schema，不改变任务本身；
6. 新 case 必须通过 `smab validate` 并附自动化测试（若引入新语义）。

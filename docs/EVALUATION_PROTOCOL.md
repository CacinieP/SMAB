# Evaluation protocol

## 最小实验矩阵

对每个 checkpoint 固定 temperature、max tokens、服务端 tool parser 和随机种子，至少跑：

| Run | Tool format | Schema | 回答的问题 |
|---|---|---|---|
| A | native | original | 部署条件下的基础能力 |
| B | native | shuffled | 工具位置偏差 |
| C | native | aliased | 对工具名记忆的依赖 |
| D | json + constrained decoding | original | 去掉语法错误后的语义上限 |

微调前后必须使用完全相同的数据 commit 与推理设置。报告模型 checkpoint、量化、chat template、tool parser、context length、decoding 参数、硬件与 benchmark commit。

## 推荐判读顺序

1. 先看 `stop_reasons`，排除 endpoint/tool parser 配置错误；
2. 比较 `native` 与受约束 `json`，分离格式问题和策略问题；
3. 比较 core 与 OOD，判断是否只记住训练措辞；
4. 比较 original 与 aliased，判断是否过度依赖函数名；
5. 查看 `by_horizon`，观察误差随链长累积；
6. 最后下钻完整 trace，定位 selection、argument、recovery 或 stopping。

## 建议门槛（不是通用定律）

封闭领域 executor 上线前，可以先用以下门槛做内部 gate：

- relevance ≥ 98%，尤其关注不可调用和缺参案例；
- arguments ≥ 97%；
- stopping = 100%（有副作用工具必须单独统计）；
- OOD 与 core 的差距 ≤ 5 个百分点；
- 3+ 调用案例 perfect-case rate ≥ 90%。

门槛应按业务风险修改。退款、发信、删除等动作不能用 overall 平均分掩盖；应单独要求零重复、零越权。

## 不建议的比较

- 只报合法 JSON 比例；
- 把超时、parser 配置错和模型策略错混在一起；
- 一边换 chat template 一边宣称微调带来提升；
- 用训练集同义改写充当 OOD；
- 只报平均调用准确率，不报整条 episode 成功率。

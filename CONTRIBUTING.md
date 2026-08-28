# Contributing

欢迎新增领域工具、失败模式、语言和 endpoint 适配器。

提交前请确认：

```bash
python -m pip install -e '.[dev]'
smab validate
pytest
```

新增数据必须是合成或已脱敏数据，不得包含 token、内部 URL、客户信息或可触发真实副作用的凭据。新增评分语义需要同步更新 `docs/DATASET_FORMAT.md` 并添加测试。

代码改动保持 Python 3.10 兼容，核心运行路径不新增强制依赖。

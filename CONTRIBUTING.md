# Contributing

欢迎新增领域工具、失败模式、语言和 endpoint 适配器。

提交前请确认：

```bash
python -m pip install -e '.[dev]'
smab validate
pytest
```

新增数据必须是合成或已脱敏数据，不得包含 token、内部 URL、客户信息或可触发真实副作用的凭据。新增评分语义需要同步更新 `docs/DATASET_FORMAT.md` 并添加测试。

修改 `src/smab/probe.py` 或新增框架人格时，请在 `tests/test_probe.py` 的本地 mock server 中补充对应行为，并保持探测判定的三态语义（ok / unsupported / error）。

代码改动保持 Python 3.10 兼容，核心运行路径不新增强制依赖。

提交贡献即表示你确认有权提供相关内容，并同意该贡献按照仓库的 [Apache License 2.0](LICENSE) 授权；如需采用不同条款，必须在提交时明确说明并获得维护者接受。

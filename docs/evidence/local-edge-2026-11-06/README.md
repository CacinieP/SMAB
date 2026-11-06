# 本地端侧部署批次（2026-11-06，2026 年最新 ≤3B 模型，非 API 榜单）

本目录记录 **2026 世代（2026 年发布）、参数量 ≤3B 的开源模型**在 SMAB core 28 例上的本地实测，以及每个模型的 **非量化（F16/BF16）vs 量化（Q8_0）** 对照。全部推理在本机完成（Apple M4 / 16GB / macOS 26.6.2），**不是** Kaggle/ModelBest API 排行榜数据，不应与主榜混算。

## 为什么单独一批

- 本地部署栈（llama.cpp 0.7.0-dev a08ab75 + Metal；MNN 3.6.2 + INT4）与托管 API 的模板、tool parser、量化都不同，跨口径只能对照。
- 本批次回答两个问题：
  1. **2026 年最新 ≤3B 模型在 SMAB 上的真实水位**（协议分通道给出，避免把格式问题误读成能力问题）；
  2. **量化是否影响小模型的工具调用分数**（同模型 Q8_0 vs F16/BF16）。

## 环境

| 项 | 值 |
|---|---|
| 硬件 | Apple M4，16GB 统一内存，macOS 26.6.2 (25G83) |
| 运行时 | llama.cpp 0.7.0-dev（build b1-a08ab75，Metal，`-ub 128`，Qwen3.5 hybrid SSM 固定 `-ngl 22/28`）；MNN 3.6.2（MNN-Pocket INT4，CPU 4 线程） |
| 基准 | 本仓库 `c654074`（v0.2.0），`datasets/core.jsonl`，28 episodes（core 17 / OOD 11，zh 18 / en 10） |
| 解码 | temperature 0（greedy）、max_tokens 512、timeout 180s、schema variant original、单遍 |
| 协议 | A = json prompt-only（schema 注入 system prompt，`response_format: null`，服务端无约束）；B = json + `response_format={"type":"json_object"}`（llama.cpp grammar）；C = native `tools`/`tool_calls`（仅 probe 支持的端点；MNN-Pocket 无 tool parser，不支持） |

## 模型与精度

| 模型 | 发布 | Q8_0 大小 | F16/BF16 大小 | A / B / C |
|---|---:|---:|---:|---|
| Qwen3.5-0.8B | 2026-03 | 812 MB | BF16 1517 MB | 32.5 / 29.7 / 83.8 |
| Qwen3.5-2B | 2026-03 | 2012 MB | BF16 3776 MB | **74.4**（BF16 72.6） / 77.0（75.8） / **89.9**（89.9） |
| LFM2.5-230M | 2026-06 | 247 MB | F16 462 MB | 29.3 / 33.5 / 65.9 |
| LFM2.5-350M | 2026-03 | 379 MB | F16 712 MB | 30.3 / 43.1 / 72.6 |
| LFM2.5-1.2B-Instruct | 2026-01 | 1246 MB | F16 2343 MB | 37.3 / 39.9 / 81.0 |
| LFM2.5-2.6B | 2026-08 | 2875 MB | F16 5403 MB | 29.3 / 29.3 / **91.6**（F16：29.3 / 29.3 / **93.5**） |
| MiniCPM5-1B | 2026-05 | 1153 MB | F16 2167 MB | 35.3 / 34.7 / 83.8 |
| MiniCPM5-2B | 2026-09 | 2680 MB | F16 5039 MB | 44.5 / 78.9 / **94.6**（F16：43.7 / 80.3 / **96.7**） |
| MNN-Pocket-0.3B（MNN INT4 / GGUF Q8 / GGUF F16） | 2026-09 | 387 MB | 726 MB | 29.2 / 30.1 / 30.4（prompt-only 三精度；B 28.1–28.4；C 不支持） |
| *MiniCPM-V-4.7-1B（按最初需求保留的基线）* | 2026-10-06 | 1082 MB | F16 2024 MB | 35.8 / 40.9 / 86.4 |

> 表中数字为 **SMAB overall（%）**；perfect-case rate 与七维见仓库外 `report/对比报告.md` §11。A/B/C 三通道分开标注。

## 关键结论

1. **协议通道 >> 精度**：同模型 native 比 json prompt-only 高约 **40–60pp**；而 Q8_0 vs F16/BF16 的差值在 **±5pp** 内（多数 ±2pp）。对这些 ≤3B 模型，量化不是分水岭，"能否按协议行动"才是。
2. **2026 世代在文本 JSON 协议上进步明显**：Qwen3.5-2B 的 A 通道 74.4%，是同代 MiniCPM5-2B（44.5%）的 1.7 倍；但 native 通道仍是 MiniCPM5-2B 最高（94.6%）。
3. **协议依赖可以造成 60pp+ 的假象**：LFM2.5-2.6B native 91.6% vs json prompt-only 29.3%（28/28 protocol_error）。选型必须先固定协议通道。
4. **0.3B 级在 2026 仍不具备控制环能力**：MNN-Pocket-0.3B（29–30%）、LFM2.5-230M/350M（29–30%，native 65–73%）与 1B 级（native 80–85%）存在断层。
5. **LFM2.5 全家族输出的是自有文本 tool 格式**（`<|tool_call_start|>[func(...)]<|tool_call_end|>`），不是 SMAB 的 `{"tool_calls":...}` 契约；prompt-only/约束解码下 26–28/28 protocol_error，native 66–94%。用 prompt-only JSON 评估会严重低估该家族。
6. **protocol_error 不等于零分**：Qwen3.5-2B 17/28 protocol_error 但 A 仍有 74.4%——内容大多正确，只是顶层键不符合 `{"final"}` 契约；"格式合规率"与 overall 必须分开读。

## 复现

```bash
# 端点（与证据文件中的端口一致；MNN-Pocket INT4 用 MNN 运行时）
./mnn/start_server.sh
bash llama/serve_2026_q8.sh        # 8101-8106 Q8 组
bash llama/serve_2026_f16_small.sh # 8111/8113/8114/8116/8118/8119/8120
bash llama/serve_big_f16.sh start <name>  # 8112/8115/8117 逐个起停

# 评测（json → 约束 → native；未就绪不判失败）
./smab/run_all.sh --new
./smab/.venv/bin/python smab/summarize.py
```

原始 run（21 个端点的 json/md、probe）以 **确定性 gzip**（`mtime=0`）保存在 `runs/`（如 `runs/qwen35-2b-q8-json.json.gz`），解压查看：

```bash
python -c "import gzip; print(gzip.open('runs/qwen35-2b-q8-json.json.gz','rt').read())"
```

- `summary.md` / `summary.json`：本批次的机器可读汇总（三通道 × 精度、七维、horizon、protocol_error、延迟）；
- `REPORT.md`：完整分析报告（含失败模式与结论；内部链接指向工作区项目，仓库内以本 README 与 summary 为准）；
- 每请求 token/耗时日志不在本仓库（体积大），由 `smab/run_all.sh` 复现时本地生成。

## 已知限制

- 单遍 temperature=0，未做 `--repeats` 的 pass^k（仅 MNN-Pocket 做过 repeats=3：mean 30.1%、std 0.82pp）；
- 延迟/吞吐受评测期间并发下载与多端点共享 Metal/CPU 影响（loadavg 3–7），仅作量级参考；
- F16 大模型（2B/2.6B）因 16GB 内存限制逐个起停，评测顺序不影响分数但影响延迟可比性；
- Qwen3.5 为 hybrid SSM 架构，`-ngl` 会影响吞吐（22 层 vs 全量差异见 `llama/README.md`），本批次统一固定配置；
- 本批次 3 个 F16 端点（LFM2.5-2.6B-F16、Qwen3.5-2B-BF16、MiniCPM5-2B-F16）曾因并发下载零页损坏，均由 `llama/repair_gguf.py` 按 Range 补洞并校验通过，已全部完成评测。

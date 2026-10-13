# Small Model Agent Bench (SMAB)

> v0.2.0: `--repeats` aggregates repeated runs with mean, stddev and pass^k, and a new `smab probe` measures what the serving stack actually supports before you blame the model.
>
> 中文说明见 [README.md](README.md)。本文件是英文版，内容与中文版保持同步。

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

An **executable** tool-calling benchmark for **0.3B–7B small models**. It does not stop at "is the JSON valid"; it measures *where capability starts to break as task entropy rises*.

> Core hypothesis: the boundary is set jointly by **ambiguity × action space × task length × distribution shift**. Small models make excellent verifiable agent organs; whether they can own the whole control loop must be measured dimension by dimension, horizon by horizon.

## What is measured

| Dimension | Key question | Typical failure |
|---|---|---|
| relevance | Should a tool be called now? Ask when arguments are missing? | over-calling, guessing arguments |
| selection | Which of the similar tools? | weather forecast vs. climate normals |
| arguments | Argument extraction, types, normalization? | dates, negatives, ISO codes |
| planning | Call order and data dependencies? | next step before the ID exists |
| state tracking | Are tool return values actually used? | final answer drops the status code |
| recovery | Recover from timeout, empty result, sold out? | mechanical retry or giving up |
| stopping | Stop after success or unrecoverable error? | repeated sends, repeated refunds |

28 built-in bilingual episodes cover core/OOD splits, 0/1/2/3+ expected-call horizons, similar-tool distractors, parallel calls, missing-argument clarification, transient and terminal errors. All tools are simulated by local fixtures — running the benchmark produces **no real side effects**.

This is not a BFCL replacement. BFCL is the standardized function-calling leaderboard; SMAB targets small-model fine-tuning iteration: short editable cases, deterministic execution, dimension-level attribution, and first-class schema perturbation. The design references the [Berkeley Function Calling Leaderboard](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard) split of simple/multiple/parallel/relevance/multi-turn and format sensitivity.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

# validate the dataset first
smab validate

# native function calling (vLLM, SGLang, llama.cpp, any compatible endpoint)
smab run \
  --model your-model \
  --base-url http://127.0.0.1:8000/v1 \
  --tool-format native \
  --output runs/your-model-native.json \
  --report runs/your-model-native.md
```

If the endpoint needs a key, it is read from `SMAB_API_KEY` by default; override with `--api-key-env`. Keys are never written into result files.

### Probe the serving stack first

The same weights can score very differently under different frameworks, chat templates, tool parsers and constrained-decoding backends. `smab probe` measures what an endpoint actually supports (12 checks: native tools, every `tool_choice` tier, multi-turn round-trip, parallel calls, `json_object`, and each structured-output dialect) and prints a recommended SMAB invocation:

```bash
smab probe --model your-model --base-url http://127.0.0.1:8000/v1 \
  --output runs/probe.json --report runs/probe.md
```

See [docs/FRAMEWORK_ADAPTATION.md](docs/FRAMEWORK_ADAPTATION.md) for the full methodology, controlled-experiment protocol, and authoritative references (vLLM, SGLang, llama.cpp docs; BFCL; τ-bench).

### Models without native function-calling tokens

`json` mode injects tool schemas into the system prompt and requires exactly one of:

```json
{"tool_calls":[{"name":"get_weather","arguments":{"city":"Shanghai","date":"2026-09-06"}}]}
```

```json
{"final":"Shanghai reached a high of 29°C today."}
```

If the server supports JSON Schema/grammar-constrained decoding, pass the matching sampling parameter via `--extra-body` so format capacity and semantic capacity can be observed separately.

### Repeated runs and comparable conclusions (v0.2.0)

A single score is for debugging, not model selection. For the same model, protocol, schema and seed, run at least three times:

```bash
smab run \
  --model your-model \
  --base-url http://127.0.0.1:8000/v1 \
  --tool-format json \
  --schema-variant original \
  --temperature 0 \
  --repeats 3 \
  --output runs/your-model-json-r3.json \
  --report runs/your-model-json-r3.md
```

Repeat mode keeps every full trace and reports overall and perfect-case rate as mean ± stddev, plus **pass^k** (the τ-bench-style reliability estimator: per case, `p` = success rate across repeats; pass^k = mean of `p^k`). Keep the seed fixed so variation is attributable to the model or server-side sampling, not schema randomization.

## Three controls you must run

```bash
smab run --model your-model --schema-variant original --output runs/original.json
smab run --model your-model --schema-variant shuffled --output runs/shuffled.json
smab run --model your-model --schema-variant aliased  --output runs/aliased.json
```

- `original`: original tool names and order;
- `shuffled`: deterministic shuffle of the tool list — position bias;
- `aliased`: tool names replaced by neutral `fn_01`-style names, descriptions kept — is the model reading semantics or memorizing names?

Also compare `native` vs `json`. If JSON constraints lift arguments but not relevance/recovery, the bottleneck is not syntactic.

## Run a single slice

```bash
# OOD recovery
smab run --model your-model --split ood --category recovery

# a single case, for fast regression during fine-tuning
smab run --model your-model --case-id recover_003

# repeated --category / --case-id take the union
smab run --model your-model --category relevance --category stopping
```

## How to read results

The JSON keeps full traces, tool outputs, stop reasons, endpoint usage and per-dimension scores; the Markdown report shows:

- overall and perfect-case rate;
- seven capability scores;
- core/OOD gap;
- scores by expected-call horizon 0/1/2/3+;
- lowest-scoring cases.

`overall` is the mean of the case's declared dimensions, 0–1. `success` is true only when every tested dimension is perfect, so it exposes single-point breaks in long chains far better than a lenient average.

If per-step accuracy is `p`, the ceiling for a length-`h` trajectory is roughly `p^h`. Read `by_horizon`; do not compare single-step selection accuracy alone.

## Baselines (measured 2026-08-31)

The numbers below come from **28 episodes, temp=0 single pass, native channel**, 52 runs across AI Ping / ModelBest / OpenRouter (2026-08-31). `perfect` is the share of cases perfect on all tested dimensions — the same quantity as `success` in the result files.

| # | Model | Platform | overall | perfect | ¥/Mtok in/out | Mean latency |
|---|---|---|---|---|---|---|
| 1 | Qwen3.5-27B (2026) | AI Ping | **100.0%** | 100.0% | 0.6 / 4.8 | 9.0s |
| 2 | cohere/north-mini-code:free | OpenRouter | 99.6% | 96.4% | free | 5.5s |
| 3 | Qwen3.8-27B (2026) | AI Ping | 98.3% | 92.9% | 3 / 12 | 5.4s |
| 4 | Step-3.5-Flash (2026) | AI Ping | 97.3% | 92.9% | 0.7 / 2.1 | 4.2s |
| 5 | MiniCPM5-2B-0822 | ModelBest | 96.9% | 92.9% | ModelBest pricing | **1.9s** |
| 6 | Qwen3-30B-A3B | AI Ping | 96.7% | 89.3% | 0.75 / 3 | 2.3s |
| 7 | GLM-4.7-Flash / GLM-5.3-Flash | AI Ping | 95.6% | 85.7/82.1% | 0.5–1 / 1.5–3 | 2–18s |
| 8 | Qwen3.5-Flash (2026) | AI Ping | 95.2% | 92.9% | 0.2 / 2 | 3.3s |
| 9 | Qwen3-Coder-30B-A3B | AI Ping | 95.1% | 89.3% | 0.7–1 / 2.8–4 | 4.4s |
| 10 | Qwen3-VL-30B-A3B-Thinking | AI Ping | 94.3% | 89.3% | 0.75 / 2.8–7.5 | 11.1s |
| 11 | Qwen3-30B-A3B-Instruct-2507 | AI Ping | 92.9% | 85.7% | 0.75 / 3 | 1.9s |
| 12 | Qwen2.5-14B-Instruct | AI Ping | 91.3% | 75.0% | 0.99 / 0.99 | 4.2s |
| 13 | Qwen3.5-9B (2026) | AI Ping | 90.5% | 82.1% | 0.5 / 4 | 3.3s |
| 14 | Qwen3-8B | AI Ping | 90.2% | 82.1% | 0–0.5 / 0–2 | 2.9s |
| 15 | GLM-4-9B-0414 (free) | AI Ping | 88.3% | 71.4% | free | 1.9s |
| 16 | Qwen3-14B | AI Ping | 87.8% | 71.4% | 0.5–5 / 1.6–5 | 11.2s |
| 17 | Qwen3.5-4B (free, 2026) | AI Ping | 85.1% | 71.4% | free | 8.1s |
| 18 | Qwen3-4B (free) | AI Ping | 82.2% | 67.9% | free | 5.6s |
| 19 | Qwen2.5-7B-Instruct | AI Ping | 60.2% | 35.7% | 0.35 / 0.35 | 6.9s |

Nine additional free OpenRouter small models were measured (native): nemotron-3.5-lightning 94.4% and ling-3.0-flash-fin 92.0% are usable; most free entries collapse under the `json` protocol (26.9–30.1%) and only work on the native FC path. Runs marked `err` (rate-limit interruptions) are slightly underestimated.

Three readings:

- **Generation beats parameter count**: a 2026 2B (MiniCPM5-2B, 96.9%) beats a 2024 7B (Qwen2.5-7B, 60.2%) by **36.7pp**. Select by training generation first, parameter scale second.
- **The protocol channel is an independent variable**: Qwen3-4B native 82.2% → json 90.5% (+8.3pp, JSON constraints rescue argument extraction); MiniCPM5-2B native 96.9% → json 83.1% (native stronger). The same model can differ by ten to fifty points across channels — any comparison must state the protocol.
- **recovery is the universal weak spot**: recovery trails other dimensions by 10–30pp across the table; the h3+ horizon segment shows cliffs (e.g. Qwen3.5-9B h2 92.4% → h3+ 43.8%).

> Single-pass temp=0 numbers above reflect the best case; for production usability measure pass^k with `--repeats`.

## Datasets and extension

- [`datasets/tools.json`](datasets/tools.json): tool catalog with JSON Schemas;
- [`datasets/core.jsonl`](datasets/core.jsonl): 28 executable episodes (default);
- [`datasets/minicpm47_extra.jsonl`](datasets/minicpm47_extra.jsonl): 13 additional regression episodes (missing-argument clarification, 12h→24h normalization, h3 dependency chains, terminal-error no-retry, single-shot side effects), select with `--dataset datasets/minicpm47_extra.jsonl`;
- [`docs/DATASET_FORMAT.md`](docs/DATASET_FORMAT.md): case, fixture, oracle and scoring fields;
- [`docs/EVALUATION_PROTOCOL.md`](docs/EVALUATION_PROTOCOL.md): recommended experiment matrix and reporting rules;
- [`docs/BENCHMARK_METHODOLOGY_ZH.md`](docs/BENCHMARK_METHODOLOGY_ZH.md): full methodology (Chinese);
- [`docs/FRAMEWORK_ADAPTATION.md`](docs/FRAMEWORK_ADAPTATION.md): inference-framework adaptation evaluation;
- [`SMALL_MODELS.md`](SMALL_MODELS.md): pending small-model candidate names.

Add your own domain tools to the catalog, then express deterministic returns, transient errors, empty results or permission errors with fixtures. Never put live tokens, customer data or real side effects into the benchmark.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
smab validate
```

The project itself does not depend on the OpenAI Python SDK; the runtime only uses the standard library to call OpenAI-compatible `/chat/completions`, which keeps it easy to embed in local fine-tuning and inference images.

## Scope boundaries

SMAB currently targets the deterministic tool-use control loop. It does not measure open web-search quality, long-term memory, visual tools or factual coverage, and it never hands the model's natural language to another LLM judge. Final answers are scored only by explicit key-fact checks, so a judge model cannot mask real changes in a small model.

## License

Source code, documentation and the built-in benchmark datasets are licensed under [Apache License 2.0](LICENSE), with attribution in [NOTICE](NOTICE). Unless stated otherwise, contributions are provided under the same license.

[`SMALL_MODELS.md`](SMALL_MODELS.md) only lists third-party model identifiers. This repository does not distribute those models' weights, code, training data or services; using third-party models is subject to their respective licenses and terms.

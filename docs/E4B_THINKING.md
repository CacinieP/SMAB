# E4B thinking off/on: three old repository-repair tasks

Enabling native thinking did **not improve repair success** in this fixed-budget diagnostic: off passed **1/3**, on passed **0/3**. On had no exclusive success and lost the previously successful control. Keep thinking off for this existing local baseline. This is a decision about three previously inspected tasks under the settings below, not a general finding that E4B thinking is ineffective. No LoRA was trained.

This follows the [seven-task prompt-policy comparison](E4B_REPOSITORY_REPAIR.md). It reuses original coding prompt A, without appending the SMAB policy. It does not change the earlier experiment's results.

## Fixed comparison

The three tasks were selected and their execution order frozen before these six attempts: one previous success, one exact-string editing failure from a second repository, and one upstream/downstream navigation failure. Each task has one attempt per mode, seed 0. They are old development tasks, not unseen confirmation tasks or a random sample.

Both modes share the private `gemma-agent` snapshot `e097c0c2e40a9574543134ef87062d13368c5c2f`, original A assets, tools, repair Skill, source snapshots, dependencies, grader and adapter. Only the effective native Ollama `/api/chat` Boolean changes between `think:false` and `think:true`. The unchanged YAML's thinking hint is overridden in the shared native bridge; actual recorded requests and emitted thinking establish the effective setting.

| Setting | Shared value |
| --- | --- |
| Hardware | Apple M5 Max, 64 GiB unified memory |
| Model/backend | `gemma4:e4b`, GGUF/Q4_K_M, Ollama 0.40.13; default assistant draft enabled |
| Sampling | Temperature 0, seed 0 |
| Context/output | 32,768 context; 2,048 maximum generated tokens per response, including thinking |
| Agent budget | 300 seconds, 48 logical model calls, 40 official counted tool calls |
| Command budget | At most 60 seconds, capped by remaining agent time |
| Outer deadline | 450 seconds for setup, agent execution and cleanup; no extra agent actions |
| Target Python | 3.11.15 for all three tasks |
| Shared history behavior | Native thinking is archived locally but omitted from subsequent ADK/tool history |

The original bridge's history behavior is retained, not independently varied. A native control successfully continued a tool result after removing thinking history; that verifies compatibility, not the absence of a quality effect. Output/context caps and this history choice limit generalization to other thinking configurations. Equal caps do not mean equal observed resource use.

The source remains [SWE-bench Lite](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite), revision `6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2`. Before model execution, the unmodified bases failed all five selected fail-to-pass nodes and passed all 299 pass-to-pass nodes; reference patches passed all 304 required nodes, with no missing, skipped or xfailed nodes. These are verification nodes across **three tasks**, not 304 independent repair tasks.

Agents receive original issue text and source, without reference/test patches, hints or grading-node lists. The returned patch is independently applied to a fresh identical base and graded against every fixed required node. Empty patches and candidate-broken behavior remain failures. The local macOS/ADK/Ollama adaptation is not the official SWE-bench Docker or Kaggle QAT/vLLM environment.

## Results

| Task | Selection reason | Thinking off | Thinking on |
| --- | --- | --- | --- |
| `pytest-dev__pytest-11143` | Previous success, regression control | PASS | FAIL |
| `pallets__flask-5063` | Previous edit failure, second repository | FAIL | FAIL |
| `pytest-dev__pytest-11148` | Previous navigation failure | FAIL | FAIL |

There are three complete valid pairs: on wins 0, loses 1, and both fail 2. All six attempts have valid model transport and independent grades; none was dropped or replaced after observing its result.

| Observation, three tasks per mode | Off | On |
| --- | ---: | ---: |
| Strict repair successes | 1/3 | 0/3 |
| Mean whole-process seconds | 56.24 | 184.46 |
| Mean logical model calls | 22.33 | 27.00 |
| Mean official counted tool calls | 13.33 | 22.67 |
| Total provider-generated tokens, thinking included | 10,760 | 58,682 |
| Responses with nonempty native thinking | 0/67 | 81/81 |
| Responses ending with `length` | 2 | 13 |
| Explicit submissions | 3/3 | 1/3 |
| Nonempty returned patches, including fallback | 1/3 | 2/3 |
| Actual `load_skill` / `run_skill_script` calls | 0 / 0 | 0 / 0 |

In this diagnostic, on used about **3.28 times** the whole-process time and **5.45 times** the generated tokens. These are descriptive local measurements, not billing, energy or training costs. Provider `eval_count` includes generated thinking; a separate thinking-token count is not inferred from characters. Whole-process time includes setup/cleanup and is separate from the agent session budget and independent grading. The official tool counter excludes some status/submission/Skill events; evidence retains both it and all traced tools.

## What failed

- **pytest-11143:** off's type guard passed the target node and 115 existing nodes. On edited a different call site without covering the failing AST rewrite path; the original target failure remained. All nine on responses ended normally, without `length`, so caps alone do not explain this regression. Its repeated full-suite checks hit optional collection dependencies and did not validate the target repair.
- **Flask-5063:** off's exact-string edits did not land and it submitted an empty patch. On produced a three-file fallback patch, but initialization code landed inside a class docstring while CLI changes depended on the missing attribute. Both target nodes still failed, and on added two existing-test regressions. Its `flask routes` command failed without an application configured and did not validate the fix. Seven on responses ended with `length`; the last four had neither visible text nor tool calls, and continuation nudges reached their stop limit.
- **pytest-11148:** on broadened exploration into the current upstream source, but all three replacement edits failed to match. It returned no patch and made no explicit submission. Whole-process time was 297.08 seconds, but there was **no reported session or outer timeout**. The last four responses hit near-full context and contained only thinking; the run ended at the continuation-nudge limit. There were 39 requests and 39 complete responses, without a cancelled or missing response. Off also submitted an empty patch. Both failed both target nodes while preserving 129 existing nodes.

All six attempts made zero actual Skill calls. Existing checkpoint, rollback, verification and review capabilities therefore were not exercised by either mode. No agent demonstrated a passing nonzero target-test validation loop; the sole success is established by independent replay. Scripted controls establish that the workflow can execute, not that E4B uses it.

## Checks and limits

All 148 recorded native requests/responses have the intended mode, model and shared generation settings, with zero API errors. The full frozen A prompt was supplied in every request; this does not prove the backend retains every earlier message under context pressure. All 44 newly frozen files, 73 prior frozen files and three snapshot hashes matched. Every returned patch was checked for protected test/runner changes, injected grader entry points, symlink/submodule changes and private-content leakage; no violation was found.

`length` occurred both at the 2,048 output cap and near the 32K context limit with much shorter generations. Unused turns or tools do not establish unused context/output capacity. The local GGUF model, history handling, default assistant draft, one seed, selected old tasks and fixed caps all constrain interpretation. These results are neither an official SWE-bench score nor a Kaggle competition score, and they do not estimate performance on unseen repositories or wider budgets.

## Decision and evidence

Retain **A with thinking off**, and defer LoRA. The observed next bottlenecks are source navigation, successful small edits, meaningful current verification and reliable submission. A future workflow comparison should enforce those steps through a competition-compatible interface and use separate confirmation tasks. This study measures the thinking switch only; it does not establish that the proposed workflow changes improve repair rate.

The [filtered evidence and verifier](evidence/e4b-thinking-2026-11-03/README.md) retain all six results, public-target patches, fixed-node grades, qualification summaries, model/software metadata, request-level numeric observations, licenses and hashes. The verifier reruns neither models nor tests and checks artifact consistency only. Private A prompt/config/Skill, raw thinking, API transcripts and full execution logs remain local; complete agent reproduction requires the authorized private snapshot. No SMAB benchmark source, scoring rules, datasets or tests were changed.

# Gemma 4 E4B / E2B: controlled local evaluation

**Status: complete.** Both models' baselines, prompt trials and frozen-prompt confirmation runs are recorded. E4B is the preferred mainline for the next agent prototype; E2B remains a lower-inference-cost comparison under this local profile. Confirmation gains are uneven, including an E2B regression. No Kaggle, SWE-bench, or repository-repair performance is inferred from this experiment.

The experiment began on 2026-11-02. Its purpose is to diagnose small-model tool-use failures, apply a generic prompt intervention, and compare it under the same model-serving conditions. No weights are fine-tuned. The runner, fixtures, oracle and scoring semantics are unchanged.

## Reproduction inputs

The [experiment manifest](evidence/gemma4-2026-11-02/experiment-manifest.json) records commands, file hashes and the development/confirmation protocol. Raw repeated runs retain every response, tool result and score; they are the source for the tables below. Raw response JSON in the baseline, development-trials, diagnostics, confirmation and probes directories is archived as deterministic gzip (`mtime=0`), retaining the original decompressed bytes and SHA-256. Metadata JSON remains uncompressed; Markdown reports are also retained.

The final [metrics](evidence/gemma4-2026-11-02/metrics.json) cover **52 benchmark configuration records and 2,316 episode attempts across 41 distinct cases**: 17 core, 11 OOD and 13 supplementary. Reusing cases across models, prompts and schemas, with three same-seed repeats, does not create 2,316 independent tasks. Probe and warm-up requests are separate from those benchmark attempts.

| Item | Setting |
| --- | --- |
| Hardware | Apple M5 Max, 64 GB unified memory |
| Backend | Ollama 0.40.13, local OpenAI-compatible endpoint |
| Benchmark runtime | Python 3.12.13 |
| Weights | Gemma 4 E4B / E2B, GGUF/Q4_K_M; model identities are recorded with the evidence |
| Native channel | `tools` with `tool_choice="auto"` |
| Sampling | temperature `0`, maximum output `512` tokens, context `32,768` |
| Shared request parameters | `{"reasoning_effort":"none","seed":0}` |
| Concurrency | One request at a time |
| Repeats | Three identical runs per configuration |
| Schema controls | Original, shuffled, aliased; schema seed `0`, plus a preselected shuffled seed `42` coverage control |
| Development subset | The 17 `core` episodes |
| Session-held-out confirmation | The 11 `ood` episodes and 13 supplementary episodes, evaluated after freezing |

The model decoding seed is the request's `seed`; SMAB's CLI `--seed` controls schema perturbation. These are separate controls. Reported standard deviations describe these three observed repeats, not uncertainty over other tasks or deployment conditions. Zero standard deviation does not prove perfect reliability.

This is an Ollama/GGUF experiment. It does not reproduce the competition's official QAT weights, vLLM backend, coding tools or evaluation environment. Even a perfect SMAB case score would not establish a reliable autonomous coding agent.

## Endpoint checks before scores

Probe and no-thinking benchmark requests share `reasoning_effort="none"`, decoding seed `0` and temperature `0`; their output caps differ: **256 tokens for probes, 512 for benchmarks**. Initial startup/contract failures are preserved under [infrastructure-failures](evidence/gemma4-2026-11-02/probes/infrastructure-failures/) and excluded from capability comparisons; they are not model zero scores. The selected endpoint's [E4B probe](evidence/gemma4-2026-11-02/probes/e4b.json.gz) and [E2B probe](evidence/gemma4-2026-11-02/probes/e2b.json.gz) are kept alongside the raw runs.

Each model's probe records **6 `ok`, 6 `unsupported`, 0 `error`** outcomes. Native `tool_choice="auto"` is usable, but the `required`, named-tool and `none` tool-choice constraints did not pass this profile's checks. The benchmark therefore uses auto selection and does not depend on forced tool choice.

Probe support is a measured property of this backend and configuration. It must not be generalized to all Gemma implementations, nor should an unsupported output-constraint dialect be labeled a model reasoning failure.

## Observed core baselines

Each row contains 17 cases × 3 repeats. `overall` is partial-credit overall; `perfect` requires every scored dimension to pass. Values are percentages, mean ± population standard deviation across the three repeats. `pass^3` is the finite-sample all-three-success rate used by SMAB.

| Model | Channel | Schema | Overall | Perfect | pass^3 | Raw evidence |
| --- | --- | --- | ---: | ---: | ---: | --- |
| E4B | native | original, seed 0 | 98.82 ± 0.00 | 94.12 ± 0.00 | 94.12 | [JSON](evidence/gemma4-2026-11-02/baseline/e4b-native-original-core-r3.json.gz) |
| E2B | native | original, seed 0 | 99.02 ± 0.00 | 94.12 ± 0.00 | 94.12 | [JSON](evidence/gemma4-2026-11-02/baseline/e2b-native-original-core-r3.json.gz) |
| E4B | native | shuffled, seed 0 | 98.82 ± 0.00 | 94.12 ± 0.00 | 94.12 | [JSON](evidence/gemma4-2026-11-02/baseline/e4b-native-shuffled-core-r3.json.gz) |
| E2B | native | shuffled, seed 0 | 99.02 ± 0.00 | 94.12 ± 0.00 | 94.12 | [JSON](evidence/gemma4-2026-11-02/baseline/e2b-native-shuffled-core-r3.json.gz) |
| E4B | native | shuffled, seed 42 | 98.82 ± 0.00 | 94.12 ± 0.00 | 94.12 | [JSON](evidence/gemma4-2026-11-02/baseline/e4b-native-shuffled-seed42-core-r3.json.gz) |
| E2B | native | shuffled, seed 42 | 99.02 ± 0.00 | 94.12 ± 0.00 | 94.12 | [JSON](evidence/gemma4-2026-11-02/baseline/e2b-native-shuffled-seed42-core-r3.json.gz) |
| E4B | native | aliased, seed 0 | 100.00 ± 0.00 | 100.00 ± 0.00 | 100.00 | [JSON](evidence/gemma4-2026-11-02/baseline/e4b-native-aliased-core-r3.json.gz) |
| E2B | native | aliased, seed 0 | 96.86 ± 0.00 | 94.12 ± 0.00 | 94.12 | [JSON](evidence/gemma4-2026-11-02/baseline/e2b-native-aliased-core-r3.json.gz) |
| E4B | JSON object protocol | original, seed 0 | 97.39 ± 0.00 | 94.12 ± 0.00 | 94.12 | [JSON](evidence/gemma4-2026-11-02/baseline/e4b-json-original-core-r3.json.gz) |
| E2B | JSON object protocol | original, seed 0 | 89.70 ± 0.00 | 82.35 ± 0.00 | 82.35 | [JSON](evidence/gemma4-2026-11-02/baseline/e2b-json-original-core-r3.json.gz) |

The two models have the same native-original perfect-case rate, with different final-answer failures; their small partial-credit difference is not a general model ranking. Aliased tools happened to produce a better E4B score on this small development set. That is an observation, not evidence that neutral tool names generally improve E4B. Native and JSON channels also change protocol presentation; their difference is not a weight-only comparison.

### Tool-order coverage matters

[A schema-only audit](evidence/gemma4-2026-11-02/schema-coverage-core.json) found that seed 0 changes the order in only **2 of 17** core cases. There are 11 multi-tool cases; the other six have one tool and cannot be reordered. Seed 42 changes **11 of 17**, covering all 11 multi-tool cases.

Seed 42 was selected from tool-list structure before inspecting its model outcomes. The original seed-0 runs are retained. Equal original/shuffled scores under seed 0 alone would therefore be weak evidence about tool-position robustness. The seed-42 result adds coverage but remains a small-set observation.

The [confirmation schema audit](evidence/gemma4-2026-11-02/schema-coverage-confirmation.json) covers 11 OOD cases, eight with multiple tools. Seed 0 changes **0 of 11** orders; seed 42 changes **8 of 11**, covering all eight multi-tool cases. Original-versus-shuffled-0 confirmation scores therefore do not test a changed tool ordering. The seed-42 control supplies that coverage; it does not enlarge the 11-case sample. This audit concerns schema structure, not selecting a seed from model scores.

## Core-only diagnosis and prompt trials

E4B's native original baseline performed the expected actions in its failing core episode but omitted a returned receipt/reference from the final answer. A manual core audit also found language that overstated an accepted request as completed. A substring-based fact check can miss that semantic distinction, so a perfect score must not be presented as proof that every final answer is correctly calibrated.

E2B's only native-original core failure was an empty final response after a successful tool action (`stop_001`). That observation is a finalization failure, not an argument error or a duplicate action. Diagnoses of the other schema/protocol configurations remain separate.

Generic development prompts therefore ask the model to retain material returned identifiers and status, ground its final answer in the actual tool result, and distinguish acknowledgement or acceptance from completion. They contain no task IDs, expected answers, receipt constants or case-specific branches. These are prompt changes, not LoRA training.

| Model | Development trial | Core configuration | Overall | Perfect | Interpretation |
| --- | --- | --- | ---: | ---: | --- |
| E4B | candidate-v1 | native original / shuffled-0 / shuffled-42 / aliased | 100.00 in each | 100.00 in each | Receipt-retention improvement observed on the development set; manual completion-wording concern remained |
| E4B | candidate-v2 | native original / shuffled-0 / shuffled-42 / aliased | 100.00 in each | 100.00 in each | Additional acknowledgement/completion instruction; still a development trial |
| E2B | candidate-v2 | native original / shuffled-0 / shuffled-42 / aliased | 96.86 in each | 94.12 in each | Empty final response fixed, but recoverable-timeout handling failed; original-schema partial score decreased |
| E4B | candidate-v3 | native original / shuffled-0 / shuffled-42 / aliased | 100.00 in each | 100.00 in each | Selected shared policy; development result |
| E2B | candidate-v3 | native original / shuffled-0 / shuffled-42 | 100.00 in each | 100.00 in each | Selected shared policy; development result |
| E2B | candidate-v3 | native aliased | 99.35 | 94.12 | Recovery failure fixed; one exact timestamp-precision mismatch remains |

E4B's four native candidate-v2 configurations have completed core development testing; the shuffled coverage run is [candidate-v2 shuffled-42](evidence/gemma4-2026-11-02/development-trials/e4b-native-shuffled-seed42-core-candidate-v2-r3.json.gz). Raw [candidate-v1 original](evidence/gemma4-2026-11-02/development-trials/e4b-native-original-core-candidate-v1-r3.json.gz) and [candidate-v2 original](evidence/gemma4-2026-11-02/development-trials/e4b-native-original-core-candidate-v2-r3.json.gz) runs are preserved. Multiple prompt trials make these development scores unsuitable as an unbiased improvement estimate. One shared prompt was selected and frozen after core-only diagnosis of both models, before confirmation results were inspected; see the freeze record below.

E2B [candidate-v2 original](evidence/gemma4-2026-11-02/development-trials/e2b-native-original-core-candidate-v2-r3.json.gz) resolves the original baseline's empty final response but stops too early after a recoverable timeout (`recover_001`). All four native configurations score 96.86 overall and 94.12 perfect, with zero repeat standard deviation. For the original schema, overall falls from 99.02 to 96.86 while perfect-case rate stays at 94.12: the failing episode changes rather than disappearing. The aliased baseline already had the recovery failure, so it cannot be attributed uniquely to candidate-v2 or to a single instruction sentence.

Candidate-v3 restores explicit recovery policy, separates errors from accepted/successful action results, permits bounded safe retries, and requires a nonempty final answer. It was designed and selected using core evidence only. All four E4B native configurations reach 100/100. E2B reaches 100/100 on original and both shuffled controls; aliased reaches 99.35 overall and 94.12 perfect. Repeat standard deviations are zero for these v3 runs. The candidate-v2 regression is retained rather than reporting only successful trials.

E2B v3 aliased recovers from the timeout but loses an exact argument-match point on `arg_003`: the model returns a time at minute precision while the fixture expects second precision. The original scoring is retained. A manual E2B v3 core audit also still finds completion-like wording mixed with an accepted status in `plan_002`; the prompt has not fully resolved status-calibration risk, even where the current scorer gives full credit.

### Core inference cost: three configurations

These measurements cover **native original core only**, 17 cases × 3 repeats per row. Default-thinking diagnostics change the reasoning setting while retaining the default prompt; they are separate from the explicitly no-thinking baseline and were not run on confirmation. The frozen prompt reaches the same core scores without enabling default thinking.

| Model | Prompt / reasoning profile | Overall | Perfect | Mean episode latency (ms) | Mean completion tokens / episode | Raw evidence |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| E4B | Default / none | 98.82 | 94.12 | 483.04 | 65.18 | [JSON](evidence/gemma4-2026-11-02/baseline/e4b-native-original-core-r3.json.gz) |
| E4B | Frozen v3 / none | 100.00 | 100.00 | 554.07 | 71.18 | [JSON](evidence/gemma4-2026-11-02/development-trials/e4b-native-original-core-candidate-v3-r3.json.gz) |
| E4B | Default / backend-default thinking | 100.00 | 100.00 | 2,146.05 | 399.27 | [JSON](evidence/gemma4-2026-11-02/diagnostics/e4b-native-original-core-thinking-default-r3.json.gz) |
| E2B | Default / none | 99.02 | 94.12 | 384.55 | 78.00 | [JSON](evidence/gemma4-2026-11-02/baseline/e2b-native-original-core-r3.json.gz) |
| E2B | Frozen v3 / none | 100.00 | 100.00 | 421.88 | 79.76 | [JSON](evidence/gemma4-2026-11-02/development-trials/e2b-native-original-core-candidate-v3-r3.json.gz) |
| E2B | Default / backend-default thinking | 100.00 | 100.00 | 2,225.46 | 561.78 | [JSON](evidence/gemma4-2026-11-02/diagnostics/e2b-native-original-core-thinking-default-r3.json.gz) |

Latency is for the whole multi-turn episode, not one request or time to first token. Completion tokens are summed across an episode's responses, including reasoning where the endpoint reports it. Each diagnostic contains reasoning in all 117 response turns; the no-thinking rows contain none. No length truncations were observed in these six runs. These are observed inference costs on this hardware/backend, not training costs, monetary prices or a speed prediction for the official competition backend. E2B is faster in the no-thinking core comparison; the default-thinking diagnostics do not preserve that ordering.

## Shared prompt freeze

The [freeze record](evidence/gemma4-2026-11-02/prompt-freeze.json) selects [candidate-v3 as `optimized.txt`](evidence/gemma4-2026-11-02/prompts/optimized.txt) for both E4B and E2B. It was frozen at **2026-11-02 16:19:23 UTC** (2026-11-03 00:19:23 Asia/Shanghai), before confirmation evaluation or scenario review. Prompt SHA-256:

```text
114c2efea5361813cea2caf426e32ef6f6c4711a5954bfa602fb791208e5cc3e
```

Confirmation compares the default policy with this same frozen prompt for both models. No prompt selection or revision used confirmation outcomes. Choosing v3 from multiple core trials remains development-set selection; its core gain is not an unbiased generalization estimate.

## Frozen-prompt confirmation

The primary comparison below uses native original tools. Arrows show default policy → frozen v3, in percent. Every listed confirmation configuration has zero observed repeat standard deviation; its `pass^3` equals its perfect-case rate. The supplementary set was tested only with original tools.

| Model | Confirmation set | Cases | Overall, default → v3 | Perfect, default → v3 | Raw evidence |
| --- | --- | ---: | ---: | ---: | --- |
| E4B | OOD | 11 | 99.09 → 99.09 | 90.91 → 90.91 | [Default](evidence/gemma4-2026-11-02/confirmation/e4b-native-original-ood-r3.json.gz), [v3](evidence/gemma4-2026-11-02/confirmation/e4b-native-original-ood-optimized-r3.json.gz) |
| E2B | OOD | 11 | 92.93 → 93.69 | 63.64 → 72.73 | [Default](evidence/gemma4-2026-11-02/confirmation/e2b-native-original-ood-r3.json.gz), [v3](evidence/gemma4-2026-11-02/confirmation/e2b-native-original-ood-optimized-r3.json.gz) |
| E4B | Supplementary | 13 | 92.69 → 100.00 | 69.23 → 100.00 | [Default](evidence/gemma4-2026-11-02/confirmation/e4b-native-original-supplementary-r3.json.gz), [v3](evidence/gemma4-2026-11-02/confirmation/e4b-native-original-supplementary-optimized-r3.json.gz) |
| E2B | Supplementary | 13 | 91.67 → 93.66 | 69.23 → 69.23 | [Default](evidence/gemma4-2026-11-02/confirmation/e2b-native-original-supplementary-r3.json.gz), [v3](evidence/gemma4-2026-11-02/confirmation/e2b-native-original-supplementary-optimized-r3.json.gz) |

### OOD schema controls

These reuse the same 11 OOD cases; they are not additional independent tasks. As the schema audit above shows, shuffled seed 0 changes no OOD tool order, while seed 42 changes all eight multi-tool cases.

| Model | Schema | Overall, default → v3 | Perfect, default → v3 | Raw evidence |
| --- | --- | ---: | ---: | --- |
| E4B | shuffled, seed 0 | 99.09 → 99.09 | 90.91 → 90.91 | [Default](evidence/gemma4-2026-11-02/confirmation/e4b-native-shuffled-ood-r3.json.gz), [v3](evidence/gemma4-2026-11-02/confirmation/e4b-native-shuffled-ood-optimized-r3.json.gz) |
| E4B | shuffled, seed 42 | 99.09 → 99.09 | 90.91 → 90.91 | [Default](evidence/gemma4-2026-11-02/confirmation/e4b-native-shuffled-seed42-ood-r3.json.gz), [v3](evidence/gemma4-2026-11-02/confirmation/e4b-native-shuffled-seed42-ood-optimized-r3.json.gz) |
| E4B | aliased, seed 0 | 99.09 → 99.09 | 90.91 → 90.91 | [Default](evidence/gemma4-2026-11-02/confirmation/e4b-native-aliased-ood-r3.json.gz), [v3](evidence/gemma4-2026-11-02/confirmation/e4b-native-aliased-ood-optimized-r3.json.gz) |
| E2B | shuffled, seed 0 | 92.93 → 93.69 | 63.64 → 72.73 | [Default](evidence/gemma4-2026-11-02/confirmation/e2b-native-shuffled-ood-r3.json.gz), [v3](evidence/gemma4-2026-11-02/confirmation/e2b-native-shuffled-ood-optimized-r3.json.gz) |
| E2B | shuffled, seed 42 | 86.11 → 93.69 | 54.55 → 72.73 | [Default](evidence/gemma4-2026-11-02/confirmation/e2b-native-shuffled-seed42-ood-r3.json.gz), [v3](evidence/gemma4-2026-11-02/confirmation/e2b-native-shuffled-seed42-ood-optimized-r3.json.gz) |
| E2B | aliased, seed 0 | **98.08 → 96.26** | 81.82 → 81.82 | [Default](evidence/gemma4-2026-11-02/confirmation/e2b-native-aliased-ood-r3.json.gz), [v3](evidence/gemma4-2026-11-02/confirmation/e2b-native-aliased-ood-optimized-r3.json.gz) |

The [paired confirmation audit](evidence/gemma4-2026-11-02/manual-audits/confirmation-audit.md) distinguishes score changes from action changes:

- **E4B:** all four OOD schemas retain the same per-case scores and tool traces. Supplementary perfect cases rise from 9/13 to 13/13 because four final answers retain returned event, refund or message identifiers. Their tool actions and arguments were already correct. This supports transfer of receipt retention, not stronger action chains or planning.
- **E2B:** original/shuffled-0 OOD gains come from a nonempty final answer after the same successful query. Shuffled-42 also improves one case by actually using the available relevant tool instead of asking an unnecessary clarification. In the aliased regression, the recovery trace is unchanged but the final answer drops a returned product identifier; unchanged perfect rate does not mean no regression.
- **E2B supplementary:** v3 actually performs a third safe search attempt after two transient timeouts, then reads the returned document. It also makes an unnecessary additional read-only search after success, so partial credit improves without increasing the 9/13 perfect count. Receipt omissions remain on three other cases. This is partial recovery improvement, not a fully repaired stopping loop.

Scoring and semantic boundaries remain visible. E2B loses the sign of a negative amount in `arg_004`, a real argument error. Its direct ISO-currency normalization in `recover_004` obtains a successful tool result but bypasses the oracle's expected error-and-recovery branch; that is a fixture-path scoring limitation, not evidence that the conversion entirely failed. E4B's `recover_002` recovers after an initial argument mismatch but still loses partial credit, and its final text calls the initial tool error an empty search result. Existing accepted-versus-completed wording concerns also remain. Original scores are retained; keyword checks do not replace a semantic audit.

The OOD and supplementary sets are public synthetic benchmark data. Withholding them from this tuning session is useful process control, not a claim that they are secret, independently collected, unseen during pretraining or representative of production workloads. Do not revise the frozen prompt using confirmation failures and still call those same cases held out.

## Conclusions and next investment

Use **E4B as the mainline** for the next agent prototype and retain **E2B as an inference-cost control**. Under frozen v3, E4B scores higher on each measured OOD schema and more consistently retains receipts on supplementary tasks. E2B is faster in the no-thinking core comparison, but has uneven confirmation transfer, an aliased regression, argument-sign errors and extra recovery calls. This is a choice for these measured stacks and the next experiment, not a general ranking across backends or workloads.

The most useful next investment is prompt and external orchestration, followed by validation on more diverse executable tasks. E4B's main confirmed gain is final receipt retention; E2B also shows local tool-use and retry improvements, with regressions and residual failures. A controller can record returned identifiers and status, require nonempty evidence-grounded finalization, bound safe retries, and validate completion before reporting it. Those controller changes are a proposed follow-up, not a capability implemented or measured by this prompt experiment.

| Path | Evidence and expected value | Compute/cost conclusion |
| --- | --- | --- |
| Use existing weights and default policy | Already strong on short native-tool core episodes; useful reproducible baseline, with observed finalization and semantic failures | No training; measured local core inference costs appear above. Backend-default thinking raises tokens and latency and lacks confirmation testing here |
| Improve prompt, orchestration and verification | Preferred next step: frozen v3 confirms E4B receipt-retention transfer and some E2B improvements; external state tracking and verification target remaining observed failures | No weight training; v3 has a modest observed core inference overhead. Additional controller cost and coding-task benefit have not been measured |
| Add LoRA | Defer until diverse-task evaluation identifies persistent errors and a separate training/validation dataset supports an adaptation study | No LoRA was trained in this round. There is no measured training benefit, GPU-hour cost or monetary training cost to report |

SMAB's short, deterministic simulated tool episodes do not validate complex repository navigation, patch correctness, verification commands, checkpoint/rollback behavior or official submission compatibility. Those require a separate executable coding benchmark and the official environment. The original simple repository test and these SMAB scores are neither formal competition scores nor evidence of Kaggle/SWE performance.

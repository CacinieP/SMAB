# E4B repository repair: a fixed-budget policy-transfer pilot

Appending the frozen SMAB v3 policy did **not improve test-passing repair rate** in this local pilot. Both policies passed **1 of 7 tasks (14.3%)**, on the same task. There were no B-only wins or A-only wins. The candidate produced more nonempty patches but did not justify replacing the coding baseline.

This is a result for one fixed, no-thinking local stack and seven selected tasks. It is not a population success estimate, an official SWE-bench score, or a Kaggle score. No LoRA was trained.

## What changed

A uses the existing competition-v2 coding prompt, ADK tools and repair Skill from the private `gemma-agent` snapshot `e097c0c2e40a9574543134ef87062d13368c5c2f`. B retains that baseline and only appends the exact [previously frozen public SMAB v3 policy](evidence/gemma4-2026-11-02/prompts/optimized.txt). The only differing agent asset is `prompts/system.md`. This tests transfer of a generic tool-result/recovery policy; it does not compare two different runtime implementations.

Both arms use the same E4B weights, tool declarations, Skill, prepared source snapshot and per-task dependencies. The local adapter enables existing project tests, keeps imports in the active snapshot, and uses the official ADK execution/tools with a prepared subprocess environment. It does not emulate the official Linux Docker/QAT/vLLM stack. Graph data is absent.

| Setting | Shared value |
| --- | --- |
| Hardware | Apple M5 Max, 64 GiB unified memory |
| Model/backend | `gemma4:e4b`, GGUF/Q4_K_M, Ollama 0.40.13; default assistant draft enabled |
| Decoding | `think:false`, temperature 0, seed 0 |
| Context/output | 32,768 context; 2,048 maximum output tokens per response |
| Agent budget | 300 seconds, 48 logical model calls, 40 official counted tool calls |
| Command budget | At most 60 seconds, also capped by the remaining agent time |
| Per-task attempts | One per arm, with a preselected interleaved order |
| Target Python | 3.9.25 for pytest-8906; 3.11.15 for the other six tasks |

The official tool counter excludes some status, submission and Skill-loading events. Both that counter and every traced tool event are retained. Outer process time includes setup/cleanup; it is separate from the agent session limit and independent grading.

## Fixed tasks and independent grading

The source is [SWE-bench Lite](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite), revision `6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2`. Eligibility was chosen before model execution: all Flask rows with version at least 2.0 and pytest rows with version at least 7.0, with nonempty fail-to-pass and pass-to-pass sets. This environment-driven subset contains three Flask and four pytest tasks; it is not a random sample of repository work.

Every task passed a base/gold preflight. The unmodified sources failed all 10 selected fail-to-pass nodes and passed 506 existing pass-to-pass nodes. The reference patches made all 516 required nodes pass, with no missing, skipped or xfailed nodes. Old dataset node IDs truncated at whitespace were mapped to actual collected parameterized nodes before inference; every mapped node must pass. The Python 3.9 choice was needed to reproduce historical test behavior and was locked before inference.

The agent receives the original source and issue text, without the reference patch, added test patch, hints or grading-node list. Each source snapshot has only one newly initialized Git baseline, with no future history or remotes. The final returned patch is applied to a fresh identical base, followed by the original benchmark test patch. All fixed fail-to-pass and pass-to-pass nodes must actually pass. Empty patches and a completion claim do not establish success. Candidate syntax errors and broken test startup remain failures rather than infrastructure exclusions.

| Task | A: existing coding policy | B: append SMAB policy |
| --- | --- | --- |
| `pallets__flask-4045` | FAIL | FAIL |
| `pallets__flask-4992` | FAIL | FAIL |
| `pallets__flask-5063` | FAIL | FAIL |
| `pytest-dev__pytest-8906` | FAIL | FAIL |
| `pytest-dev__pytest-9359` | FAIL | FAIL |
| `pytest-dev__pytest-11143` | PASS | PASS |
| `pytest-dev__pytest-11148` | FAIL | FAIL |

These seven tasks are the experimental units. Fourteen arm attempts and 516 verification nodes do not create fourteen or 516 independent repair tasks. The pairs comprise one joint success and six joint failures, with zero B wins and zero B losses.

## What improved, and what did not

| Observation | A | B |
| --- | ---: | ---: |
| Test-passing tasks | 1/7 | 1/7 |
| Nonempty returned patches | 3/7 | 6/7 |
| Mean whole-process seconds per task | 57.21 | 57.07 |
| Mean logical model calls | 24.86 | 26.00 |
| Mean official counted tool calls | 14.86 | 15.57 |
| Actual repair Skill script executions | 0 | 0 |

Patch production increased, but correctness did not. The nearly equal mean times are not evidence of an efficiency gain: several failures terminate early. The shared successful task took 26.09 seconds under A and 35.11 seconds under B. Provider-reported token counts and durations are in the evidence; summed prompt tokens repeatedly count context and are not billing, energy or training measurements.

The independently reviewed failures include unsuccessful exact-string edits and empty submissions; introduced indentation/syntax errors followed by submission; treating downstream reproduction paths as the current upstream source; and incomplete fixes without meaningful validation. One B run loaded the Skill and then called nonexistent standalone `checkpoint`/`review` tools. None of the fourteen runs executed `run_skill_script`, so the existing checkpoint/rollback/verification implementation was not exercised by these repairs. Control tests establish that the scripts can run, not that the model uses them.

Both successful patches target pytest-11143 and pass one fail-to-pass plus 115 pass-to-pass nodes on the active candidate source. A adds a type guard. B uses a coarser workaround that bypasses product assertion rewriting for a numeric-leading source case. It neither skips tests nor hijacks the grader, so its test-passing result is retained; behavior outside the selected tests remains a quality concern. The agents' own test attempts did not demonstrate this success: they selected no relevant tests or encountered unrelated collection dependencies. The independent replay supplies the passing evidence.

All fourteen patches were reviewed uniformly for protected test/runner changes, injected grading modules, symlink/submodule mode changes and private-content leakage. No such violation was found.

## Budget and validity limits

No run reached the time, logical-call or official-tool ceilings: observed maxima were 118.46 seconds of whole-process time, 41 logical calls and 26 counted tools. However, **six responses ended with `done_reason=length`**. Three generated 2,048 tokens; three stopped with nearly full 32K contexts and only 10, 36 or 373 generated tokens. Output/context pressure is an observed limitation, not an absence of resource constraints. Requests contain the full frozen instructions, which does not prove the backend retains every earlier message after context truncation.

The primary run has 356 valid recorded requests/responses, no transport errors, no emitted thinking, and matching requested generation profiles. All 73 frozen-file hashes and seven snapshot hashes match. Two earlier attempts received no model response because the service was unavailable; they are retained separately as infrastructure-invalid records. The entire fixed design was then restarted after readiness checks, with an availability-only outer guard and unchanged agent inputs, budgets and grader. The restored frozen grader was used for every primary grade.

The tests are public historical benchmark material. They are not claimed to be unseen during pretraining. Only selected test groups are environment-qualified; optional full-repository test collections can have unrelated dependencies. Results do not establish official submission performance, broad coding ability, or behavior with default thinking or another context/output budget.

## Decision

Keep A as the coding baseline and defer LoRA. This study provides no repair-rate reason to promote B. The most direct next experiment is to enforce small edits, bounded navigation, current validation and submission conditions through a competition-compatible workflow or narrower tool interface, while keeping a separate fixed task set for confirmation. Those changes are a proposed next step, not an improvement measured here.

See the [filtered evidence and verifier](evidence/e4b-repair-2026-11-03/README.md). It includes every primary result, public-target patches, filtered independent test outcomes, preflight summaries, software/model metadata, licenses and hashes. Full private baseline prompts, configuration, Skill, raw requests and complete traces remain local/private. The public bundle supports patch/result consistency checks; complete agent reproduction requires the authorized private source snapshot. No private code or credentials are published with these results.

# Filtered E4B repair-policy transfer evidence

Seven public SWE-bench Lite tasks, two frozen policies, one ordered seed per task/arm. A is the existing private coding-agent baseline; B only appends the previously frozen public SMAB v3 policy. The shared runtime/tools/Skill did not change between arms. This macOS/Ollama GGUF pilot is not an official Docker/QAT/vLLM score.

Run `python verify.py` to check artifact hashes, seven pairs/fourteen samples, patch binding, filtered test outcomes, provider usage units and aggregate consistency. It does not rerun models or tests and cannot independently establish raw transcript authenticity.

Only filtered metadata/results and model-generated patches against public Flask/pytest source are distributed. Full private baseline ADK configuration, baseline/optimized prompt bodies, Skill/source, raw API messages, full traces, command output, host pytest logs, gold/test patch bodies and hints are excluded. Upstream licenses and commit-specific links are in `notices/`.

Provider duration fields in per-call usage are original nanoseconds; aggregate provider durations are converted seconds. Outer process wall time also includes setup/cleanup. Summed prompt tokens can repeatedly count context. These figures are not training, energy or monetary costs.

The provider reports 6 length-terminated responses; per-trial/per-call input and output counts are retained in results and trial metadata. Output/context limits were reached despite unused time/turn/tool budget headroom; this pilot is not free of truncation.

Reproducing the entire agent requires the separately authorized private gemma-agent snapshot, including its baseline configuration, prompts and Skill. This public bundle supports result inspection and patch/test-metadata consistency checks, not a claim of complete end-to-end reproducibility.

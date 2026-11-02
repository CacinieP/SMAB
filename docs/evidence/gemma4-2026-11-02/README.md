# Gemma 4 evaluation evidence

See [the report](../../GEMMA4.md) for interpretation. These are synthetic tool-use
episodes; no real external actions are executed. They are not competition scores.

- `baseline/`: all core default-prompt runs, including JSON protocol diagnostics.
- `development-trials/`: all recorded core prompt candidates, including superseded trials.
- `diagnostics/`: backend-default thinking controls; kept separate from no-thinking scores.
- `confirmation/`: default vs the frozen policy on the OOD and supplementary sets.
- `probes/`: endpoint controls. Startup and invalid-control observations are retained
  under `infrastructure-failures/`, outside benchmark scores.
- `environment/`: weight manifests, blob verification and runtime fingerprints.
- `prompts/`, `prompt-freeze.json`: exact prompt texts and the pre-confirmation freeze.
- `metrics.json`: derived metrics and failed case IDs, with no scorer changes.
- `artifact-index.json`: SHA256 of compressed artifacts and their original JSON bytes.
- `verify.py`: checks checksums, expected batches, prompt freeze, source hashes
  and report links against this checkout using Python's standard library.
- `commands-recorded.jsonl`: contemporaneously recorded commands; workspace paths
  are made portable. Some early manual batches predate this log. The run metadata,
  experiment manifest and reproduction helper supply their requested profiles.

Raw JSON is stored as deterministic gzip (`mtime=0`). For example:

```bash
python -c "import gzip; print(gzip.open('baseline/e4b-native-original-core-r3.json.gz', 'rt').read())"
```

From the repository root, validate the complete saved snapshot with:

```bash
python docs/evidence/gemma4-2026-11-02/verify.py
```

To reproduce, install this checkout with `python -m pip install -e '.[dev]'` and
start the recorded Ollama version with the matching Gemma tags. For a dedicated
service, use an isolated model directory and port:

```bash
OLLAMA_HOST=127.0.0.1:11435 OLLAMA_MODELS=/path/to/isolated-models \
OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 \
OLLAMA_CONTEXT_LENGTH=32768 OLLAMA_KEEP_ALIVE=30m ollama serve
```

Compare the downloaded weight digests with `environment/`; mutable tag names alone
are insufficient. The recorded Ollama package enables its Gemma assistant draft
model. Latencies include that default behavior. Warm each model before a batch.

```bash
python docs/evidence/gemma4-2026-11-02/reproduce.py --model e4b --phase baseline
python docs/evidence/gemma4-2026-11-02/reproduce.py --model e4b --phase optimized-core
python docs/evidence/gemma4-2026-11-02/reproduce.py --model e4b --phase confirmation
# Repeat with --model e2b. For the separate thinking control:
python docs/evidence/gemma4-2026-11-02/reproduce.py --model e2b --phase thinking-diagnostic
```

`--dry-run` prints commands without sending requests. Results go to a fresh
`reproduced/` directory; existing result files are never silently overwritten.
Set `--base-url` for a different local service. Reproduction can differ across
backend versions, hardware, prompt templates and quantization. Three repetitions
with the same sampling seed are a repeatability check, not independent trials or
a confidence interval for real-world reliability.

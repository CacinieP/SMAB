# SMAB Framework Adaptation Probe

- Endpoint: `http://127.0.0.1:11435/v1`
- Model: `gemma4:e4b`
- Checks: 0 ok / 0 unsupported / 12 error

## Capability matrix

| Check | Status | Latency | Detail |
|---|---|---:|---|
| `chat_completion` | ⚠️ error | 7 ms | request failed before a verdict: URLError: <urlopen error [Errno 61] Connection refused> |
| `native_tools` | ⚠️ error | 0 ms | request failed before a verdict: URLError: <urlopen error [Errno 61] Connection refused> |
| `tool_choice_required` | ⚠️ error | 0 ms | request failed before a verdict: URLError: <urlopen error [Errno 61] Connection refused> |
| `tool_choice_named` | ⚠️ error | 0 ms | request failed before a verdict: URLError: <urlopen error [Errno 61] Connection refused> |
| `tool_choice_none` | ⚠️ error | 0 ms | request failed before a verdict: URLError: <urlopen error [Errno 61] Connection refused> |
| `tool_roundtrip` | ⚠️ error | 0 ms | request failed before a verdict: URLError: <urlopen error [Errno 61] Connection refused> |
| `parallel_tool_calls` | ⚠️ error | 0 ms | request failed before a verdict: URLError: <urlopen error [Errno 61] Connection refused> |
| `json_object_response_format` | ⚠️ error | 0 ms | request failed before a verdict: URLError: <urlopen error [Errno 61] Connection refused> |
| `structured_outputs_json` | ⚠️ error | 0 ms | request failed before a verdict: URLError: <urlopen error [Errno 61] Connection refused> |
| `legacy_guided_json` | ⚠️ error | 0 ms | request failed before a verdict: URLError: <urlopen error [Errno 61] Connection refused> |
| `sglang_json_schema` | ⚠️ error | 0 ms | request failed before a verdict: URLError: <urlopen error [Errno 61] Connection refused> |
| `llamacpp_response_schema` | ⚠️ error | 0 ms | request failed before a verdict: URLError: <urlopen error [Errno 61] Connection refused> |

## Recommended SMAB invocation

No invocation is recommended until the request errors are resolved and a runnable protocol is verified.

## Notes

- Usable native tool calling was not observed; consider the JSON protocol after resolving any request errors.
- response_format json_object is inconclusive; resolve request errors or retry the control comparison before choosing a JSON configuration.
- No constrained-decoding dialect detected; syntax errors cannot be separated from strategy errors.
- Basic chat completion failed; fix connectivity before interpreting anything else.


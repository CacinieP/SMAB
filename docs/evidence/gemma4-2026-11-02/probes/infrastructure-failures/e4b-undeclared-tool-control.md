# SMAB Framework Adaptation Probe

- Endpoint: `http://127.0.0.1:11435/v1`
- Model: `gemma4:e4b`
- Checks: 5 ok / 6 unsupported / 1 error

## Capability matrix

| Check | Status | Latency | Detail |
|---|---|---:|---|
| `chat_completion` | ⚠️ error | 210 ms | HTTP 200 but no assistant content |
| `native_tools` | ✅ ok | 217 ms | native tool calling works (parser returned get_weather with valid JSON arguments) |
| `tool_choice_required` | 🚫 unsupported | 206 ms | tool_choice=required did not force a valid tool call against the no-tool prompt |
| `tool_choice_named` | 🚫 unsupported | 365 ms | named tool_choice did not pin the requested function |
| `tool_choice_none` | 🚫 unsupported | 213 ms | tool_choice=none still produced tool_calls |
| `tool_roundtrip` | ✅ ok | 190 ms | tool-result request produced a valid assistant continuation (chat template compatible) |
| `parallel_tool_calls` | ✅ ok | 323 ms | 2 tool calls emitted in a single turn |
| `json_object_response_format` | ✅ ok | 206 ms | response_format json_object changed the non-JSON control into a JSON object |
| `structured_outputs_json` | 🚫 unsupported | 42 ms | vLLM structured_outputs.json accepted but the response does not match the requested schema |
| `legacy_guided_json` | 🚫 unsupported | 44 ms | legacy guided_json accepted but the response does not match the requested schema |
| `sglang_json_schema` | ✅ ok | 1228 ms | SGLang chat response_format.json_schema satisfied every schema rule including a hidden random enum |
| `llamacpp_response_schema` | 🚫 unsupported | 124 ms | llama.cpp response_format schema accepted but the response does not match the requested schema |

## Recommended SMAB invocation

No invocation is recommended until the request errors are resolved and a runnable protocol is verified.

## Observed constrained-decoding dialect

Detected `sglang-json-schema`. The following is a probe example only; do not add its schema to `smab run`.

```json
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "smab_probe",
      "schema": {
        "type": "object",
        "properties": {
          "city": {
            "type": "string"
          },
          "high_c": {
            "type": "number"
          }
        },
        "required": [
          "city",
          "high_c"
        ],
        "additionalProperties": false
      }
    }
  }
}
```

## Notes

- tool_choice=required enforcement was not verified; do not rely on forced tool calling.
- Basic chat completion failed; fix connectivity before interpreting anything else.
- The detected dialect is capability evidence only. Its weather probe schema must never be added to an SMAB benchmark invocation.


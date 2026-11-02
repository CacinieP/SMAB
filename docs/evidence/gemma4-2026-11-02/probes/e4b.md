# SMAB Framework Adaptation Probe

- Endpoint: `http://127.0.0.1:11435/v1`
- Model: `gemma4:e4b`
- Checks: 6 ok / 6 unsupported / 0 error

## Capability matrix

| Check | Status | Latency | Detail |
|---|---|---:|---|
| `chat_completion` | ✅ ok | 157 ms | plain chat completion works |
| `native_tools` | ✅ ok | 147 ms | native tool calling works (parser returned get_weather with valid JSON arguments) |
| `tool_choice_required` | 🚫 unsupported | 86 ms | tool_choice=required did not force a valid tool call against the no-tool prompt |
| `tool_choice_named` | 🚫 unsupported | 361 ms | named tool_choice did not pin the requested function |
| `tool_choice_none` | 🚫 unsupported | 216 ms | tool_choice=none still produced tool_calls |
| `tool_roundtrip` | ✅ ok | 194 ms | tool-result request produced a valid assistant continuation (chat template compatible) |
| `parallel_tool_calls` | ✅ ok | 316 ms | 2 tool calls emitted in a single turn |
| `json_object_response_format` | ✅ ok | 169 ms | response_format json_object changed the non-JSON control into a JSON object |
| `structured_outputs_json` | 🚫 unsupported | 43 ms | vLLM structured_outputs.json accepted but the response does not match the requested schema |
| `legacy_guided_json` | 🚫 unsupported | 43 ms | legacy guided_json accepted but the response does not match the requested schema |
| `sglang_json_schema` | ✅ ok | 1195 ms | SGLang chat response_format.json_schema satisfied every schema rule including a hidden random enum |
| `llamacpp_response_schema` | 🚫 unsupported | 126 ms | llama.cpp response_format schema accepted but the response does not match the requested schema |

## Recommended SMAB invocation

```bash
smab run --model gemma4:e4b \
  --base-url http://127.0.0.1:11435/v1 \
  --tool-format native \
  --extra-body '{"reasoning_effort": "none", "seed": 0}'
```

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
- The detected dialect is capability evidence only. Its weather probe schema must never be added to an SMAB benchmark invocation.


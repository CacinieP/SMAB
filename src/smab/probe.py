"""Inference-framework adaptation probe.

The same model checkpoint can behave very differently depending on the serving
stack: chat template, tool-call parser, structured-outputs backend and the
``tool_choice`` tiers the server implements all sit between SMAB and the model.
Before comparing models, probe the endpoint so a run is never misattributed to
the model when the framework is what changed.

Checks are intentionally conservative:

- ``ok``           the capability was observed end-to-end;
- ``unsupported`` the endpoint rejected the request (HTTP 400) or accepted the
                   parameter without enforcing it;
- ``error``        transport-level or unexpected failure (inconclusive, retry).

Only the Python standard library is used, matching the rest of SMAB.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .adapters import _chat_completions_url

PROBE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city on a given date.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "date": {"type": "string", "description": "ISO date, e.g. 2026-09-06"},
            },
            "required": ["city", "date"],
        },
    },
}

PROBE_MESSAGES = [
    {
        "role": "system",
        "content": "You are a tool-using assistant. Call get_weather when the user asks about weather.",
    },
    {"role": "user", "content": "What's the weather in Shanghai on 2026-09-06?"},
]

# Schema used for every constrained-decoding probe. Small, strict, and easy for
# a mock or a real backend to honour.
PROBE_SCHEMA = {
    "type": "object",
    "properties": {
        "city": {"type": "string"},
        "high_c": {"type": "number"},
    },
    "required": ["city", "high_c"],
    "additionalProperties": False,
}

PROBE_SCHEMA_PROMPT = (
    "Return the weather of Shanghai on 2026-09-06 as JSON with keys city and high_c."
)


@dataclass(slots=True)
class ProbeCheck:
    name: str
    status: str  # ok | unsupported | error
    detail: str
    latency_ms: float | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProbeConfig:
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float = 60.0


def probe_endpoint(config: ProbeConfig) -> dict[str, Any]:
    """Run every framework-adaptation check and build a capability report."""
    started = datetime.now(timezone.utc)
    url = _chat_completions_url(config.base_url)
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    context = _ProbeContext(url=url, headers=headers, model=config.model, timeout=config.timeout)
    checks = [
        _check_chat_completion,
        _check_native_tools,
        _check_tool_choice_required,
        _check_tool_choice_named,
        _check_tool_choice_none,
        _check_tool_roundtrip,
        _check_parallel_tool_calls,
        _check_json_object,
        _check_structured_outputs_json,
        _check_legacy_guided_json,
        _check_sglang_json_schema,
        _check_llamacpp_response_schema,
    ]
    results = [check(context) for check in checks]
    return {
        "probe": {
            "endpoint": config.base_url,
            "model": config.model,
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
        "summary": _summarize(results),
        "checks": [
            {
                "name": item.name,
                "status": item.status,
                "detail": item.detail,
                "latency_ms": item.latency_ms,
                "evidence": item.evidence,
            }
            for item in results
        ],
    }


class _ProbeContext:
    def __init__(self, *, url: str, headers: dict[str, str], model: str, timeout: float) -> None:
        self.url = url
        self.headers = headers
        self.model = model
        self.timeout = timeout

    def post(
        self, payload: dict[str, Any]
    ) -> tuple[int | None, dict[str, Any] | None, str | None, float]:
        """POST a chat-completions payload.

        Returns ``(http_status, body, transport_error, latency_ms)``. Exactly one
        of ``http_status`` and ``transport_error`` is set.
        """
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=self.headers,
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
                return response.status, body, None, _elapsed_ms(started)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"raw": raw[:500]}
            return exc.code, parsed, None, _elapsed_ms(started)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return None, None, f"{type(exc).__name__}: {exc}", _elapsed_ms(started)


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def _timed(
    context: _ProbeContext, payload: dict[str, Any]
) -> tuple[int | None, dict[str, Any] | None, str | None, float]:
    return context.post(payload)


def _message_of(body: dict[str, Any] | None) -> dict[str, Any]:
    try:
        return body["choices"][0]["message"]  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        return {}


def _error_message(body: dict[str, Any] | None) -> str:
    if not isinstance(body, dict):
        return ""
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message", ""))[:300]
    if isinstance(error, str):
        return error[:300]
    return str(body.get("message", ""))[:300]


def _base_payload(
    context: _ProbeContext, *, extra_body: dict[str, Any] | None = None, **overrides: Any
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": context.model,
        "messages": PROBE_MESSAGES,
        "temperature": 0.0,
        "max_tokens": 256,
    }
    payload.update(overrides)
    # Extra request fields are merged at the top level, mirroring how the
    # benchmark adapter applies --extra-body; sending them nested would be a
    # protocol error on every real endpoint.
    if extra_body:
        payload.update(extra_body)
    return payload


def _rejected(name: str, status: int | None, body: dict[str, Any] | None, latency: float) -> ProbeCheck:
    return ProbeCheck(
        name=name,
        status="unsupported",
        detail=f"endpoint rejected the request (HTTP {status}): {_error_message(body) or 'no message'}",
        latency_ms=latency,
        evidence={"http_status": status},
    )


def _failed(name: str, error: str | None, latency: float) -> ProbeCheck:
    return ProbeCheck(
        name=name,
        status="error",
        detail=f"request failed before a verdict: {error}",
        latency_ms=latency,
    )


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_chat_completion(context: _ProbeContext) -> ProbeCheck:
    name = "chat_completion"
    status, body, error, latency = _timed(context, _base_payload(context))
    if error:
        return _failed(name, error, latency)
    if status != 200:
        return _rejected(name, status, body, latency)
    content = _message_of(body).get("content")
    if not content:
        return ProbeCheck(name, "error", "HTTP 200 but no assistant content", latency)
    return ProbeCheck(name, "ok", "plain chat completion works", latency)


def _check_native_tools(context: _ProbeContext) -> ProbeCheck:
    name = "native_tools"
    payload = _base_payload(context, tools=[PROBE_TOOL], tool_choice="auto")
    status, body, error, latency = _timed(context, payload)
    if error:
        return _failed(name, error, latency)
    if status != 200:
        return _rejected(name, status, body, latency)
    calls = _message_of(body).get("tool_calls") or []
    if not calls:
        return ProbeCheck(
            name,
            "unsupported",
            "tools accepted but no tool_calls returned; server likely lacks a tool-call parser",
            latency,
            evidence={"message": _message_of(body)},
        )
    function = calls[0].get("function", {})
    raw_arguments = function.get("arguments", "{}")
    try:
        arguments = raw_arguments if isinstance(raw_arguments, dict) else json.loads(raw_arguments)
        parsable = isinstance(arguments, dict)
    except (json.JSONDecodeError, TypeError):
        parsable = False
    if not function.get("name") or not parsable:
        return ProbeCheck(
            name,
            "unsupported",
            "tool_calls returned but name/arguments are malformed; parser misconfigured",
            latency,
            evidence={"tool_call": calls[0]},
        )
    return ProbeCheck(
        name,
        "ok",
        f"native tool calling works (parser returned {function.get('name')!r} with JSON arguments)",
        latency,
        evidence={"tool_call": calls[0]},
    )


def _check_tool_choice_required(context: _ProbeContext) -> ProbeCheck:
    name = "tool_choice_required"
    payload = _base_payload(context, tools=[PROBE_TOOL], tool_choice="required")
    status, body, error, latency = _timed(context, payload)
    if error:
        return _failed(name, error, latency)
    if status != 200:
        return _rejected(name, status, body, latency)
    calls = _message_of(body).get("tool_calls") or []
    if not calls:
        return ProbeCheck(
            name, "unsupported", "tool_choice=required accepted but no tool_calls produced", latency
        )
    return ProbeCheck(name, "ok", "tool_choice=required forces at least one tool call", latency)


def _check_tool_choice_named(context: _ProbeContext) -> ProbeCheck:
    name = "tool_choice_named"
    payload = _base_payload(
        context,
        tools=[PROBE_TOOL],
        tool_choice={"type": "function", "function": {"name": "get_weather"}},
    )
    status, body, error, latency = _timed(context, payload)
    if error:
        return _failed(name, error, latency)
    if status != 200:
        return _rejected(name, status, body, latency)
    calls = _message_of(body).get("tool_calls") or []
    if not calls or calls[0].get("function", {}).get("name") != "get_weather":
        return ProbeCheck(
            name, "unsupported", "named tool_choice did not pin the requested function", latency
        )
    return ProbeCheck(name, "ok", "named function calling pins the requested tool", latency)


def _check_tool_choice_none(context: _ProbeContext) -> ProbeCheck:
    name = "tool_choice_none"
    payload = _base_payload(context, tools=[PROBE_TOOL], tool_choice="none")
    status, body, error, latency = _timed(context, payload)
    if error:
        return _failed(name, error, latency)
    if status != 200:
        return _rejected(name, status, body, latency)
    if _message_of(body).get("tool_calls"):
        return ProbeCheck(
            name, "unsupported", "tool_choice=none still produced tool_calls", latency
        )
    return ProbeCheck(name, "ok", "tool_choice=none suppresses tool calls", latency)


def _check_tool_roundtrip(context: _ProbeContext) -> ProbeCheck:
    name = "tool_roundtrip"
    messages = [
        *PROBE_MESSAGES,
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_probe_1",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": json.dumps({"city": "Shanghai", "date": "2026-09-06"}),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_probe_1",
            "name": "get_weather",
            "content": json.dumps({"ok": True, "result": {"condition": "cloudy", "high_c": 29}}),
        },
    ]
    payload = _base_payload(context, messages=messages, tools=[PROBE_TOOL], tool_choice="auto")
    status, body, error, latency = _timed(context, payload)
    if error:
        return _failed(name, error, latency)
    if status != 200:
        return _rejected(name, status, body, latency)
    return ProbeCheck(
        name,
        "ok",
        "multi-turn assistant/tool message round-trip accepted (chat template compatible)",
        latency,
    )


def _check_parallel_tool_calls(context: _ProbeContext) -> ProbeCheck:
    name = "parallel_tool_calls"
    payload = _base_payload(
        context,
        tools=[PROBE_TOOL],
        tool_choice="auto",
        parallel_tool_calls=True,
    )
    # Override the prompt so two cities are requested in one turn.
    payload["messages"] = [
        PROBE_MESSAGES[0],
        {"role": "user", "content": "Compare the weather in Shanghai and Beijing on 2026-09-06."},
    ]
    status, body, error, latency = _timed(context, payload)
    if error:
        return _failed(name, error, latency)
    if status != 200:
        return _rejected(name, status, body, latency)
    calls = _message_of(body).get("tool_calls") or []
    if len(calls) >= 2:
        return ProbeCheck(name, "ok", f"{len(calls)} tool calls emitted in a single turn", latency)
    return ProbeCheck(
        name,
        "unsupported",
        "flag accepted but the model emitted a single call; parallel emission is not reliable here",
        latency,
        evidence={"tool_calls": calls},
    )


def _check_json_object(context: _ProbeContext) -> ProbeCheck:
    name = "json_object_response_format"
    payload = _base_payload(context, response_format={"type": "json_object"})
    payload["messages"] = [PROBE_MESSAGES[0], {"role": "user", "content": PROBE_SCHEMA_PROMPT}]
    status, body, error, latency = _timed(context, payload)
    if error:
        return _failed(name, error, latency)
    if status != 200:
        return _rejected(name, status, body, latency)
    content = _message_of(body).get("content") or ""
    try:
        json.loads(content)
    except json.JSONDecodeError:
        return ProbeCheck(
            name,
            "unsupported",
            "response_format accepted but content is not valid JSON",
            latency,
            evidence={"content": content[:200]},
        )
    return ProbeCheck(
        name, "ok", "response_format json_object enforced (SMAB json protocol can rely on it)", latency
    )


def _constrained_check(
    context: _ProbeContext,
    name: str,
    payload_builder: Any,
    dialect: str,
) -> ProbeCheck:
    payload = payload_builder()
    status, body, error, latency = _timed(context, payload)
    if error:
        return _failed(name, error, latency)
    if status != 200:
        return _rejected(name, status, body, latency)
    content = _message_of(body).get("content") or ""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return ProbeCheck(
            name,
            "unsupported",
            f"{dialect} accepted but the schema was not enforced",
            latency,
            evidence={"content": content[:200]},
        )
    if not isinstance(parsed, dict) or not {"city", "high_c"} <= set(parsed):
        return ProbeCheck(
            name,
            "unsupported",
            f"{dialect} accepted but the response does not match the requested schema",
            latency,
            evidence={"content": content[:200]},
        )
    return ProbeCheck(name, "ok", f"{dialect} enforced the JSON schema", latency)


def _check_structured_outputs_json(context: _ProbeContext) -> ProbeCheck:
    # vLLM >= 0.12: guided_json & friends were removed in favour of
    # extra_body {"structured_outputs": {"json": schema}}.
    return _constrained_check(
        context,
        "structured_outputs_json",
        lambda: _base_payload(
            context,
            messages=[PROBE_MESSAGES[0], {"role": "user", "content": PROBE_SCHEMA_PROMPT}],
            extra_body={"structured_outputs": {"json": PROBE_SCHEMA}},
        ),
        "vLLM structured_outputs.json",
    )


def _check_legacy_guided_json(context: _ProbeContext) -> ProbeCheck:
    # vLLM < 0.12 and several OpenAI-compatible servers still speak this.
    return _constrained_check(
        context,
        "legacy_guided_json",
        lambda: _base_payload(
            context,
            messages=[PROBE_MESSAGES[0], {"role": "user", "content": PROBE_SCHEMA_PROMPT}],
            extra_body={"guided_json": PROBE_SCHEMA},
        ),
        "legacy guided_json",
    )


def _check_sglang_json_schema(context: _ProbeContext) -> ProbeCheck:
    return _constrained_check(
        context,
        "sglang_json_schema",
        lambda: _base_payload(
            context,
            messages=[PROBE_MESSAGES[0], {"role": "user", "content": PROBE_SCHEMA_PROMPT}],
            extra_body={"json_schema": PROBE_SCHEMA},
        ),
        "SGLang json_schema",
    )


def _check_llamacpp_response_schema(context: _ProbeContext) -> ProbeCheck:
    return _constrained_check(
        context,
        "llamacpp_response_schema",
        lambda: _base_payload(
            context,
            messages=[PROBE_MESSAGES[0], {"role": "user", "content": PROBE_SCHEMA_PROMPT}],
            response_format={"type": "json_object", "schema": PROBE_SCHEMA},
        ),
        "llama.cpp response_format schema",
    )


# ---------------------------------------------------------------------------
# Summary and recommendations
# ---------------------------------------------------------------------------

_CONSTRAINED_DIALECTS = [
    ("structured_outputs_json", "vllm-structured-outputs", {"structured_outputs": {"json": PROBE_SCHEMA}}),
    ("legacy_guided_json", "legacy-guided-json", {"guided_json": PROBE_SCHEMA}),
    ("sglang_json_schema", "sglang-json-schema", {"json_schema": PROBE_SCHEMA}),
    (
        "llamacpp_response_schema",
        "llamacpp-response-schema",
        {"response_format": {"type": "json_object", "schema": PROBE_SCHEMA}},
    ),
]


def _summarize(checks: list[ProbeCheck]) -> dict[str, Any]:
    by_name = {check.name: check for check in checks}
    counts = {"ok": 0, "unsupported": 0, "error": 0}
    for check in checks:
        counts[check.status] += 1
    native = by_name["native_tools"].status == "ok"
    json_object = by_name["json_object_response_format"].status == "ok"
    dialect = None
    extra_body: dict[str, Any] | None = None
    for name, label, body in _CONSTRAINED_DIALECTS:
        if by_name[name].status == "ok":
            dialect = label
            extra_body = body
            break
    tool_format = "native" if native else "json"
    return {
        "ok": counts["ok"],
        "unsupported": counts["unsupported"],
        "error": counts["error"],
        "native_tool_calling": native,
        "json_object_response_format": json_object,
        "constrained_decoding": {"dialect": dialect, "extra_body": extra_body},
        "recommended_tool_format": tool_format,
        "notes": _notes(by_name),
    }


def _notes(by_name: dict[str, ProbeCheck]) -> list[str]:
    notes: list[str] = []
    if by_name["native_tools"].status != "ok":
        notes.append(
            "No usable native tool calling: run SMAB with --tool-format json and inject schemas via the system prompt."
        )
    else:
        if by_name["tool_choice_required"].status != "ok":
            notes.append("tool_choice=required unavailable; do not rely on forced tool calling.")
        if by_name["tool_roundtrip"].status != "ok":
            notes.append(
                "Multi-turn tool round-trip failed; the chat template likely mishandles assistant/tool messages."
            )
        if by_name["parallel_tool_calls"].status != "ok":
            notes.append("Parallel tool calls unreliable; interpret multi-tool episodes with care.")
    if by_name["json_object_response_format"].status != "ok":
        notes.append(
            "response_format json_object unavailable; json-protocol runs depend on prompt discipline only."
        )
    if all(by_name[name].status != "ok" for name, _, _ in _CONSTRAINED_DIALECTS):
        notes.append(
            "No constrained-decoding dialect detected; syntax errors cannot be separated from strategy errors."
        )
    if by_name["chat_completion"].status != "ok":
        notes.append("Basic chat completion failed; fix connectivity before interpreting anything else.")
    return notes


def render_probe_markdown(report: dict[str, Any]) -> str:
    probe = report["probe"]
    summary = report["summary"]
    icon = {"ok": "✅", "unsupported": "🚫", "error": "⚠️"}
    lines = [
        "# SMAB Framework Adaptation Probe",
        "",
        f"- Endpoint: `{probe['endpoint']}`",
        f"- Model: `{probe['model']}`",
        f"- Checks: {summary['ok']} ok / {summary['unsupported']} unsupported / {summary['error']} error",
        "",
        "## Capability matrix",
        "",
        "| Check | Status | Latency | Detail |",
        "|---|---|---:|---|",
    ]
    for check in report["checks"]:
        latency = f"{check['latency_ms']:.0f} ms" if check["latency_ms"] is not None else "—"
        lines.append(
            f"| `{check['name']}` | {icon.get(check['status'], '?')} {check['status']} "
            f"| {latency} | {check['detail']} |"
        )
    constrained = summary["constrained_decoding"]
    command = [
        f"smab run --model {probe['model']}",
        f"--base-url {probe['endpoint']}",
        f"--tool-format {summary['recommended_tool_format']}",
    ]
    if constrained["extra_body"]:
        command.append(
            "--extra-body '" + json.dumps(constrained["extra_body"], ensure_ascii=False) + "'"
        )
    lines.extend(["", "## Recommended SMAB invocation", "", "```bash", " \\\n  ".join(command), "```", ""])
    if summary["notes"]:
        lines.extend(["## Notes", ""])
        lines.extend(f"- {note}" for note in summary["notes"])
        lines.append("")
    return "\n".join(lines) + "\n"

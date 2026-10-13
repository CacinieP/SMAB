"""Inference-framework adaptation probe.

The same model checkpoint can behave very differently depending on the serving
stack: chat template, tool-call parser, structured-outputs backend and the
``tool_choice`` tiers the server implements all sit between SMAB and the model.
Before comparing models, probe the endpoint so a run is never misattributed to
the model when the framework is what changed.

Checks are intentionally conservative:

- ``ok``           the capability was observed end-to-end;
- ``unsupported`` an explicit capability rejection (HTTP 400/422), or accepted
                   parameters whose constraints were contradicted by output;
- ``error``        transport, authentication, rate limits, server/model errors,
                   or an inconclusive control comparison (retry).

Only the Python standard library is used, matching the rest of SMAB.
"""

from __future__ import annotations

import http.client
import json
import math
import secrets
import shlex
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

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

PROBE_TIME_TOOL = {
    "type": "function",
    "function": {
        "name": "get_time",
        "description": "Get the current time.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}
PROBE_TOOLS = [PROBE_TOOL, PROBE_TIME_TOOL]

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

PROBE_SCHEMA_PROMPT = "For this JSON mode test, reply exactly NOT_JSON without quotes or braces."
PROBE_CONFLICT_MESSAGES = [
    {"role": "system", "content": "Follow the user's exact response request."},
    {"role": "user", "content": PROBE_SCHEMA_PROMPT},
]


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
            try:
                raw = exc.read().decode("utf-8", errors="replace")
            except (OSError, http.client.HTTPException) as read_error:
                return None, None, f"{type(read_error).__name__}: {read_error}", _elapsed_ms(started)
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"raw": raw[:500]}
            return exc.code, parsed, None, _elapsed_ms(started)
        except (OSError, http.client.HTTPException, UnicodeError, json.JSONDecodeError) as exc:
            return None, None, f"{type(exc).__name__}: {exc}", _elapsed_ms(started)


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def _timed(
    context: _ProbeContext, payload: dict[str, Any]
) -> tuple[int | None, dict[str, Any] | None, str | None, float]:
    return context.post(payload)


def _message_of(body: dict[str, Any] | None) -> dict[str, Any]:
    try:
        message = body["choices"][0]["message"]  # type: ignore[index]
        return message if isinstance(message, dict) and message.get("role") == "assistant" else {}
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
    message = _error_message(body)
    lowered = message.lower()
    # A missing/invalid model is an operational error even when the response
    # also mentions structured-output or tool parameters.
    model_error = "model" in lowered and any(
        word in lowered for word in ("not found", "does not exist", "unknown", "invalid", "not served", "unavailable", "not available", "unsupported model")
    )
    capability = any(word in lowered for word in (
        "tools", "tool calling", "tool_choice", "parallel_tool_calls", "response_format",
        "structured output", "structured_outputs", "guided_json", "json_schema", "schema",
    ))
    refusal = any(word in lowered for word in (
        "unsupported", "not supported", "not implemented", "requires", "disabled",
        "not enabled", "not allowed", "unrecognized", "unknown field", "unexpected",
    ))
    verdict = "unsupported" if status in (400, 422) and capability and refusal and not model_error else "error"
    return ProbeCheck(
        name=name,
        status=verdict,
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


def _valid_tool_calls(message: dict[str, Any], allowed: set[str]) -> bool:
    calls = message.get("tool_calls")
    if not isinstance(calls, list) or not calls:
        return False
    for call in calls:
        if not isinstance(call, dict) or call.get("type") != "function" or not isinstance(call.get("id"), str) or not call["id"]:
            return False
        function = call.get("function")
        if not isinstance(function, dict) or not isinstance(function.get("name"), str) or function["name"] not in allowed:
            return False
        try:
            raw = function.get("arguments")
            arguments = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return False
        if not isinstance(arguments, dict):
            return False
        if function["name"] == "get_weather":
            if not all(isinstance(arguments.get(key), str) and arguments[key] for key in ("city", "date")):
                return False
        elif arguments:
            return False
    return True


def _has_content(message: dict[str, Any]) -> bool:
    content = message.get("content")
    return isinstance(content, str) and bool(content.strip())


def _json_content(message: dict[str, Any]) -> Any:
    content = message.get("content")
    if not isinstance(content, str):
        return None

    def invalid_constant(value: str) -> None:
        raise ValueError(f"non-JSON constant: {value}")

    try:
        return json.loads(content, parse_constant=invalid_constant)
    except (json.JSONDecodeError, ValueError):
        return None


def _matches_probe_schema(parsed: Any, schema: dict[str, Any]) -> bool:
    # Validate every rule in our fixed, deliberately small probe schema. This
    # is not a general-purpose JSON Schema validator.
    if not isinstance(parsed, dict) or set(parsed) != {"city", "high_c"}:
        return False
    if not isinstance(parsed["city"], str) or parsed["city"] not in schema["properties"]["city"]["enum"]:
        return False
    value = parsed["high_c"]
    return type(value) is int or (type(value) is float and math.isfinite(value))


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
    if not _has_content(_message_of(body)):
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
    message = _message_of(body)
    if not message.get("tool_calls"):
        return ProbeCheck(
            name,
            "unsupported",
            "tools accepted but no tool_calls returned; server likely lacks a tool-call parser",
            latency,
            evidence={"message": message},
        )
    if not _valid_tool_calls(message, {"get_weather"}):
        return ProbeCheck(
            name,
            "unsupported",
            "tool_calls returned but name/arguments are malformed; parser misconfigured",
            latency,
            evidence={"message": message},
        )
    call = message["tool_calls"][0]
    return ProbeCheck(
        name,
        "ok",
        "native tool calling works (parser returned get_weather with valid JSON arguments)",
        latency,
        evidence={"tool_call": call},
    )


def _check_tool_choice_required(context: _ProbeContext) -> ProbeCheck:
    name = "tool_choice_required"
    messages = [
        {"role": "system", "content": "Follow the user's request."},
        {"role": "user", "content": "Reply exactly HELLO. Do not call any tools."},
    ]
    payload = _base_payload(context, messages=messages, tools=PROBE_TOOLS, tool_choice="auto")
    status, body, error, control_latency = _timed(context, payload)
    if error:
        return _failed(name, error, control_latency)
    if status != 200:
        return _rejected(name, status, body, control_latency)
    control = _message_of(body)
    if control.get("tool_calls") or not _has_content(control):
        return ProbeCheck(name, "error", "auto control did not produce a plain reply; required enforcement is unverified", control_latency)
    payload["tool_choice"] = "required"
    status, body, error, latency = _timed(context, payload)
    latency += control_latency
    if error:
        return _failed(name, error, latency)
    if status != 200:
        return _rejected(name, status, body, latency)
    if not _valid_tool_calls(_message_of(body), {"get_weather", "get_time"}):
        return ProbeCheck(
            name, "unsupported", "tool_choice=required did not force a valid tool call against the no-tool prompt", latency
        )
    return ProbeCheck(name, "ok", "tool_choice=required changed the plain-reply control into valid tool calls", latency)


def _check_tool_choice_named(context: _ProbeContext) -> ProbeCheck:
    name = "tool_choice_named"
    payload = _base_payload(
        context,
        tools=PROBE_TOOLS,
        tool_choice="auto",
    )
    status, body, error, control_latency = _timed(context, payload)
    if error:
        return _failed(name, error, control_latency)
    if status != 200:
        return _rejected(name, status, body, control_latency)
    if not _valid_tool_calls(_message_of(body), {"get_weather"}):
        return ProbeCheck(name, "error", "auto control did not select weather; named enforcement is unverified", control_latency)
    payload["tool_choice"] = {"type": "function", "function": {"name": "get_time"}}
    status, body, error, latency = _timed(context, payload)
    latency += control_latency
    if error:
        return _failed(name, error, latency)
    if status != 200:
        return _rejected(name, status, body, latency)
    if not _valid_tool_calls(_message_of(body), {"get_time"}):
        return ProbeCheck(
            name, "unsupported", "named tool_choice did not pin the requested function", latency
        )
    return ProbeCheck(name, "ok", "named function calling selected get_time despite the weather prompt and auto control", latency)


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
    if not _has_content(_message_of(body)):
        return ProbeCheck(name, "unsupported", "tool_choice=none returned no valid assistant reply", latency)
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
    message = _message_of(body)
    if not _has_content(message) and not _valid_tool_calls(message, {"get_weather"}):
        return ProbeCheck(name, "unsupported", "tool-result request returned no valid assistant continuation", latency)
    return ProbeCheck(
        name,
        "ok",
        "tool-result request produced a valid assistant continuation (chat template compatible)",
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
    if isinstance(calls, list) and len(calls) >= 2 and _valid_tool_calls(_message_of(body), {"get_weather"}):
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
    payload = _base_payload(context, messages=PROBE_CONFLICT_MESSAGES)
    status, body, error, control_latency = _timed(context, payload)
    if error:
        return _failed(name, error, control_latency)
    if status != 200:
        return _rejected(name, status, body, control_latency)
    if not _has_content(_message_of(body)):
        return ProbeCheck(name, "error", "plain control returned no assistant content", control_latency)
    control_is_object = isinstance(_json_content(_message_of(body)), dict)
    payload["response_format"] = {"type": "json_object"}
    status, body, error, latency = _timed(context, payload)
    latency += control_latency
    if error:
        return _failed(name, error, latency)
    if status != 200:
        return _rejected(name, status, body, latency)
    if not isinstance(_json_content(_message_of(body)), dict):
        return ProbeCheck(
            name,
            "unsupported",
            "response_format accepted but content is not a valid JSON object",
            latency,
            evidence={"message": _message_of(body)},
        )
    if control_is_object:
        return ProbeCheck(name, "error", "plain control already returned a JSON object; parameter enforcement is unverified", latency)
    return ProbeCheck(
        name, "ok", "response_format json_object changed the non-JSON control into a JSON object", latency
    )


def _constrained_check(
    context: _ProbeContext,
    name: str,
    payload_builder: Callable[[dict[str, Any]], dict[str, Any]],
    dialect: str,
) -> ProbeCheck:
    # The random enum appears only in the request schema. A server that ignores
    # the parameter cannot pass merely by following a weather-JSON prompt.
    schema = json.loads(json.dumps(PROBE_SCHEMA))
    marker = "smab-probe-" + secrets.token_hex(16)
    schema["properties"]["city"]["enum"] = [marker]
    payload = payload_builder(schema)
    status, body, error, latency = _timed(context, payload)
    if error:
        return _failed(name, error, latency)
    if status != 200:
        return _rejected(name, status, body, latency)
    if not _matches_probe_schema(_json_content(_message_of(body)), schema):
        return ProbeCheck(
            name,
            "unsupported",
            f"{dialect} accepted but the response does not match the requested schema",
            latency,
            evidence={"message": _message_of(body)},
        )
    return ProbeCheck(name, "ok", f"{dialect} satisfied every schema rule including a hidden random enum", latency)


def _check_structured_outputs_json(context: _ProbeContext) -> ProbeCheck:
    # vLLM >= 0.12: guided_json & friends were removed in favour of
    # extra_body {"structured_outputs": {"json": schema}}.
    return _constrained_check(
        context,
        "structured_outputs_json",
        lambda schema: _base_payload(
            context,
            messages=PROBE_CONFLICT_MESSAGES,
            extra_body={"structured_outputs": {"json": schema}},
        ),
        "vLLM structured_outputs.json",
    )


def _check_legacy_guided_json(context: _ProbeContext) -> ProbeCheck:
    # vLLM < 0.12 and several OpenAI-compatible servers still speak this.
    return _constrained_check(
        context,
        "legacy_guided_json",
        lambda schema: _base_payload(
            context,
            messages=PROBE_CONFLICT_MESSAGES,
            extra_body={"guided_json": schema},
        ),
        "legacy guided_json",
    )


def _check_sglang_json_schema(context: _ProbeContext) -> ProbeCheck:
    return _constrained_check(
        context,
        "sglang_json_schema",
        lambda schema: _base_payload(
            context,
            messages=PROBE_CONFLICT_MESSAGES,
            response_format={"type": "json_schema", "json_schema": {"name": "smab_probe", "schema": schema}},
        ),
        "SGLang chat response_format.json_schema",
    )


def _check_llamacpp_response_schema(context: _ProbeContext) -> ProbeCheck:
    return _constrained_check(
        context,
        "llamacpp_response_schema",
        lambda schema: _base_payload(
            context,
            messages=PROBE_CONFLICT_MESSAGES,
            response_format={"type": "json_object", "schema": schema},
        ),
        "llama.cpp response_format schema",
    )


# ---------------------------------------------------------------------------
# Summary and recommendations
# ---------------------------------------------------------------------------

_CONSTRAINED_DIALECTS = [
    ("structured_outputs_json", "vllm-structured-outputs", {"structured_outputs": {"json": PROBE_SCHEMA}}),
    ("legacy_guided_json", "legacy-guided-json", {"guided_json": PROBE_SCHEMA}),
    ("sglang_json_schema", "sglang-json-schema", {"response_format": {"type": "json_schema", "json_schema": {"name": "smab_probe", "schema": PROBE_SCHEMA}}}),
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
    probe_example: dict[str, Any] | None = None
    for name, label, body in _CONSTRAINED_DIALECTS:
        if by_name[name].status == "ok":
            dialect = label
            probe_example = body
            break
    tool_format = None
    recommended_extra_body = None
    if by_name["chat_completion"].status == "ok":
        if native and by_name["tool_roundtrip"].status == "ok":
            tool_format = "native"
        elif json_object:
            tool_format = "json"
        elif (
            by_name["native_tools"].status != "error"
            and by_name["tool_roundtrip"].status != "error"
            and by_name["json_object_response_format"].status == "unsupported"
        ):
            tool_format = "json"
            recommended_extra_body = {"response_format": None}
    return {
        "ok": counts["ok"],
        "unsupported": counts["unsupported"],
        "error": counts["error"],
        "native_tool_calling": native,
        "json_object_response_format": json_object,
        "constrained_decoding": {
            "dialect": dialect,
            "extra_body": None,
            "probe_example_extra_body": probe_example,
        },
        "recommended_tool_format": tool_format,
        "recommended_extra_body": recommended_extra_body,
        "notes": _notes(by_name),
    }


def _notes(by_name: dict[str, ProbeCheck]) -> list[str]:
    notes: list[str] = []
    if by_name["native_tools"].status != "ok":
        notes.append(
            "Usable native tool calling was not observed; consider the JSON protocol after resolving any request errors."
        )
    else:
        if by_name["tool_choice_required"].status != "ok":
            notes.append("tool_choice=required enforcement was not verified; do not rely on forced tool calling.")
        if by_name["tool_roundtrip"].status != "ok":
            notes.append(
                "A valid tool-result continuation was not observed; native benchmark episodes are not verified."
            )
        if by_name["parallel_tool_calls"].status != "ok":
            notes.append("Parallel tool calls unreliable; interpret multi-tool episodes with care.")
    if by_name["json_object_response_format"].status == "unsupported":
        notes.append(
            "response_format json_object enforcement was not verified; prompt-only JSON runs must omit this parameter."
        )
    elif by_name["json_object_response_format"].status == "error":
        notes.append("response_format json_object is inconclusive; resolve request errors or retry the control comparison before choosing a JSON configuration.")
    if all(by_name[name].status != "ok" for name, _, _ in _CONSTRAINED_DIALECTS):
        notes.append(
            "No constrained-decoding dialect detected; syntax errors cannot be separated from strategy errors."
        )
    if by_name["chat_completion"].status != "ok":
        notes.append("Basic chat completion failed; fix connectivity before interpreting anything else.")
    if any(by_name[name].status == "ok" for name, _, _ in _CONSTRAINED_DIALECTS):
        notes.append("The detected dialect is capability evidence only. Its weather probe schema must never be added to an SMAB benchmark invocation.")
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
    lines.extend(["", "## Recommended SMAB invocation", ""])
    if summary["recommended_tool_format"] is None:
        lines.extend(["No invocation is recommended until the request errors are resolved and a runnable protocol is verified.", ""])
    else:
        command = [
            f"smab run --model {shlex.quote(probe['model'])}",
            f"--base-url {shlex.quote(probe['endpoint'])}",
            f"--tool-format {summary['recommended_tool_format']}",
        ]
        if summary["recommended_extra_body"]:
            command.append("--extra-body " + shlex.quote(json.dumps(summary["recommended_extra_body"])))
        lines.extend(["```bash", " \\\n  ".join(command), "```", ""])
    if constrained["dialect"]:
        lines.extend([
            "## Observed constrained-decoding dialect", "",
            f"Detected `{constrained['dialect']}`. The following is a probe example only; do not add its schema to `smab run`.",
            "", "```json", json.dumps(constrained["probe_example_extra_body"], ensure_ascii=False, indent=2), "```", "",
        ])
    if summary["notes"]:
        lines.extend(["## Notes", ""])
        lines.extend(f"- {note}" for note in summary["notes"])
        lines.append("")
    return "\n".join(lines) + "\n"

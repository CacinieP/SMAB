"""End-to-end probe tests against real local HTTP mock endpoints.

Each persona emulates a serving stack's actual behaviour as documented by its
upstream project:

- ``modern_vllm``: vLLM >= 0.12 structured outputs (``structured_outputs``),
  native tool calling with all ``tool_choice`` tiers, parallel calls.
- ``legacy_vllm``: vLLM < 0.12 ``guided_json`` dialect, native tool calling.
- ``sglang``: SGLang chat ``response_format.json_schema``, native tool calling.
- ``llamacpp``: llama.cpp server: native tool calling, schema-constrained
  ``response_format``, but parallel tool calls disabled by default.
- ``bare``: an endpoint with none of the above; SMAB must fall back to the
  JSON protocol.
"""

from __future__ import annotations

import json
import shlex
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from smab.probe import ProbeConfig, probe_endpoint, render_probe_markdown

GOOD_JSON = json.dumps({"city": "Shanghai", "high_c": 29})
SINGLE_CALL = {
    "id": "call_probe_1",
    "type": "function",
    "function": {
        "name": "get_weather",
        "arguments": json.dumps({"city": "Shanghai", "date": "2026-09-06"}),
    },
}
TWO_CITIES = "Shanghai and Beijing"
TIME_CALL = {
    "id": "call_probe_time",
    "type": "function",
    "function": {"name": "get_time", "arguments": "{}"},
}
CONSTRAINED_CHECKS = (
    "structured_outputs_json", "legacy_guided_json", "sglang_json_schema", "llamacpp_response_schema",
)


def _schema_of(payload: dict[str, Any]) -> dict[str, Any] | None:
    if "structured_outputs" in payload:
        return payload["structured_outputs"]["json"]
    if "guided_json" in payload:
        return payload["guided_json"]
    response_format = payload.get("response_format") or {}
    if response_format.get("type") == "json_schema":
        return response_format["json_schema"]["schema"]
    return response_format.get("schema")


def _is_roundtrip(payload: dict[str, Any]) -> bool:
    return any(message.get("role") == "tool" for message in payload.get("messages", []))


def _tool_call_message(calls: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": calls,
                }
            }
        ]
    }


def _content_message(content: Any) -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def _reject(message: str) -> dict[str, Any]:
    return {"error": {"message": message, "type": "BadRequestError", "code": 400}}


class _PersonaHandler(BaseHTTPRequestHandler):
    persona = "bare"

    def log_message(self, *args: Any) -> None:  # keep test output quiet
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        status, body = self._route(payload)
        self._respond(status, body)

    def _respond(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    # -- routing -----------------------------------------------------------

    def _route(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        has_tools = "tools" in payload
        if has_tools and not self.supports_tools:
            return 400, _reject("tools are not supported by this endpoint")
        tool_choice = payload.get("tool_choice")
        if tool_choice is not None and not self.supports_tools:
            return 400, _reject("tool_choice requires tool calling support")
        response_format = payload.get("response_format") or {}
        extra = {key: value for key, value in payload.items() if key in EXTRA_KEYS}

        if has_tools and _is_roundtrip(payload):
            # Route this before tools+auto, so the continuation is tested.
            return 200, _content_message("The high in Shanghai on 2026-09-06 is 29°C.")
        if tool_choice == "none":
            return 200, _content_message("Shanghai will be cloudy with a high of 29°C.")
        if has_tools and tool_choice == "auto":
            prompt = self._last_user_message(payload)
            if "HELLO" in prompt:
                return 200, _content_message("HELLO")
            if TWO_CITIES in prompt and payload.get("parallel_tool_calls") and self.supports_parallel:
                return 200, _tool_call_message([SINGLE_CALL, dict(SINGLE_CALL, id="call_probe_2")])
            return 200, _tool_call_message([SINGLE_CALL])
        if has_tools and tool_choice in ("required", {"type": "function", "function": {"name": "get_time"}}):
            assert len(payload["tools"]) == 2
            return 200, _tool_call_message([TIME_CALL])

        dialect = self.detect_dialect(response_format, extra)
        if dialect == "unsupported":
            return 400, _reject("unsupported structured output request")
        schema = _schema_of(payload)
        if schema is not None:
            marker = schema["properties"]["city"]["enum"][0]
            assert marker not in json.dumps(payload["messages"])
            return 200, _content_message(json.dumps({"city": marker, "high_c": 29}))
        if dialect == "json_object":
            return 200, _content_message(GOOD_JSON)
        if "NOT_JSON" in self._last_user_message(payload):
            return 200, _content_message("NOT_JSON")
        return 200, _content_message("Shanghai on 2026-09-06 will be cloudy, high 29°C.")
    @staticmethod
    def _last_user_message(payload: dict[str, Any]) -> str:
        for message in reversed(payload.get("messages", [])):
            if message.get("role") == "user":
                return str(message.get("content", ""))
        return ""

    # -- persona capabilities ---------------------------------------------

    @property
    def supports_tools(self) -> bool:
        return self.persona != "bare"

    @property
    def supports_parallel(self) -> bool:
        return self.persona in ("modern_vllm", "legacy_vllm", "sglang")

    def detect_dialect(self, response_format: dict[str, Any], extra: dict[str, Any]) -> str:
        if "structured_outputs" in extra:
            return "structured_outputs" if self.persona == "modern_vllm" else "unsupported"
        if "guided_json" in extra:
            return "guided_json" if self.persona == "legacy_vllm" else "unsupported"
        if "json_schema" in extra:
            return "unsupported"  # Not a /v1/chat/completions field.
        if response_format.get("type") == "json_schema":
            assert response_format["json_schema"]["name"] == "smab_probe"
            assert response_format["json_schema"]["schema"]["type"] == "object"
            return "json_schema" if self.persona == "sglang" else "unsupported"
        if response_format.get("type") == "json_object" and "schema" in response_format:
            return "response_schema" if self.persona == "llamacpp" else "unsupported"
        if response_format.get("type") == "json_object":
            return "json_object" if self.persona != "bare" else "unsupported"
        return "none"


EXTRA_KEYS = ("structured_outputs", "guided_json", "json_schema")


class _ModernVLLMHandler(_PersonaHandler):
    persona = "modern_vllm"


class _LegacyVLLMHandler(_PersonaHandler):
    persona = "legacy_vllm"


class _SGLangHandler(_PersonaHandler):
    persona = "sglang"


class _LlamaCppHandler(_PersonaHandler):
    persona = "llamacpp"


class _BareHandler(_PersonaHandler):
    persona = "bare"


@pytest.fixture
def endpoint_factory():
    servers: list[ThreadingHTTPServer] = []

    def _start(handler_class: type[_PersonaHandler]) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_class)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}/v1"

    yield _start
    for server in servers:
        server.shutdown()
        server.server_close()


def _probe(base_url: str) -> dict[str, Any]:
    report = probe_endpoint(
        ProbeConfig(base_url=base_url, model="mock-model", timeout=10.0)
    )
    return {check["name"]: check["status"] for check in report["checks"]}


def test_modern_vllm_endpoint(endpoint_factory) -> None:
    url = endpoint_factory(_ModernVLLMHandler)
    statuses = _probe(url)
    assert statuses["chat_completion"] == "ok"
    assert statuses["native_tools"] == "ok"
    assert statuses["tool_choice_required"] == "ok"
    assert statuses["tool_choice_named"] == "ok"
    assert statuses["tool_choice_none"] == "ok"
    assert statuses["tool_roundtrip"] == "ok"
    assert statuses["parallel_tool_calls"] == "ok"
    assert statuses["json_object_response_format"] == "ok"
    assert statuses["structured_outputs_json"] == "ok"
    assert statuses["legacy_guided_json"] == "unsupported"
    assert statuses["sglang_json_schema"] == "unsupported"
    assert statuses["llamacpp_response_schema"] == "unsupported"


def test_legacy_vllm_endpoint(endpoint_factory) -> None:
    url = endpoint_factory(_LegacyVLLMHandler)
    statuses = _probe(url)
    assert statuses["native_tools"] == "ok"
    assert statuses["legacy_guided_json"] == "ok"
    assert statuses["structured_outputs_json"] == "unsupported"
    assert statuses["sglang_json_schema"] == "unsupported"
    assert statuses["llamacpp_response_schema"] == "unsupported"


def test_sglang_endpoint(endpoint_factory) -> None:
    url = endpoint_factory(_SGLangHandler)
    statuses = _probe(url)
    assert statuses["native_tools"] == "ok"
    assert statuses["sglang_json_schema"] == "ok"
    assert statuses["structured_outputs_json"] == "unsupported"
    assert statuses["legacy_guided_json"] == "unsupported"
    assert statuses["llamacpp_response_schema"] == "unsupported"


def test_llamacpp_endpoint(endpoint_factory) -> None:
    url = endpoint_factory(_LlamaCppHandler)
    statuses = _probe(url)
    assert statuses["native_tools"] == "ok"
    assert statuses["llamacpp_response_schema"] == "ok"
    assert statuses["structured_outputs_json"] == "unsupported"
    assert statuses["legacy_guided_json"] == "unsupported"
    assert statuses["sglang_json_schema"] == "unsupported"
    # llama.cpp disables parallel tool calls by default.
    assert statuses["parallel_tool_calls"] == "unsupported"


def test_bare_endpoint_falls_back_to_json_protocol(endpoint_factory) -> None:
    url = endpoint_factory(_BareHandler)
    report = probe_endpoint(ProbeConfig(base_url=url, model="mock-model", timeout=10.0))
    statuses = {check["name"]: check["status"] for check in report["checks"]}
    assert statuses["chat_completion"] == "ok"
    assert statuses["native_tools"] == "unsupported"
    assert statuses["json_object_response_format"] == "unsupported"
    assert report["summary"]["recommended_tool_format"] == "json"
    assert report["summary"]["constrained_decoding"]["dialect"] is None
    assert any("json" in note for note in report["summary"]["notes"])


def test_report_recommends_dialect_and_tool_format(endpoint_factory) -> None:
    url = endpoint_factory(_SGLangHandler)
    report = probe_endpoint(ProbeConfig(base_url=url, model="mock-model", timeout=10.0))
    summary = report["summary"]
    assert summary["recommended_tool_format"] == "native"
    assert summary["constrained_decoding"]["dialect"] == "sglang-json-schema"
    markdown = render_probe_markdown(report)
    assert "smab run --model mock-model" in markdown
    assert "json_schema" in markdown
    assert "Capability matrix" in markdown


def test_unreachable_endpoint_reports_error_status() -> None:
    # Bind and immediately close a socket to obtain a dead port.
    server = ThreadingHTTPServer(("127.0.0.1", 0), _PersonaHandler)
    port = server.server_address[1]
    server.server_close()
    report = probe_endpoint(
        ProbeConfig(base_url=f"http://127.0.0.1:{port}/v1", model="mock-model", timeout=2.0)
    )
    statuses = {check["name"]: check["status"] for check in report["checks"]}
    assert statuses["chat_completion"] == "error"
    assert report["summary"]["error"] >= 1


def test_probe_sends_extra_body_fields_at_top_level(endpoint_factory) -> None:
    seen: list[dict[str, Any]] = []

    class _Recorder(_PersonaHandler):
        persona = "modern_vllm"

        def _route(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
            seen.append(payload)
            return super()._route(payload)

    url = endpoint_factory(_Recorder)
    probe_endpoint(ProbeConfig(base_url=url, model="mock-model", timeout=10.0))
    structured = [item for item in seen if "structured_outputs" in item]
    assert structured, "probe never sent the structured_outputs field"
    assert "extra_body" not in structured[0]
    assert structured[0]["structured_outputs"]["json"]["type"] == "object"


def _report(url: str) -> dict[str, Any]:
    return probe_endpoint(ProbeConfig(base_url=url, model="mock-model", timeout=2.0))


def _statuses(report: dict[str, Any]) -> dict[str, str]:
    return {check["name"]: check["status"] for check in report["checks"]}


@pytest.mark.parametrize(("status", "message"), [
    (401, "authentication failed"), (403, "forbidden"), (404, "model not found"),
    (408, "request timeout"), (429, "rate limit exceeded"), (500, "server failure"),
    (503, "unavailable"), (400, "model mock-model not found; unsupported tools"),
    (400, "unsupported model 'wrong-model' for tool_choice"),
    (422, "invalid model identifier"), (400, "invalid request"),
])
def test_operational_http_failures_are_inconclusive(endpoint_factory, status, message) -> None:
    class _Failure(_PersonaHandler):
        def _route(self, payload):
            return status, _reject(message)

    report = _report(endpoint_factory(_Failure))
    assert set(_statuses(report).values()) == {"error"}
    assert report["summary"]["recommended_tool_format"] is None
    assert "```bash" not in render_probe_markdown(report)
    assert all(check["evidence"]["http_status"] == status for check in report["checks"])


def test_mid_request_disconnect_returns_report(endpoint_factory) -> None:
    class _Disconnect(_PersonaHandler):
        def do_POST(self):
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()

    report = _report(endpoint_factory(_Disconnect))
    assert set(_statuses(report).values()) == {"error"}
    assert report["summary"]["recommended_tool_format"] is None


@pytest.mark.parametrize("http_status", [200, 500, 503])
def test_truncated_response_body_returns_report(endpoint_factory, http_status) -> None:
    class _Truncated(_PersonaHandler):
        def do_POST(self):
            self.send_response(http_status)
            self.send_header("Content-Length", "1000")
            self.end_headers()
            self.wfile.write(b'{"choices": []}')
            self.close_connection = True

    report = _report(endpoint_factory(_Truncated))
    assert set(_statuses(report).values()) == {"error"}
    assert report["summary"]["recommended_tool_format"] is None


def test_sglang_schema_uses_chat_response_format(endpoint_factory) -> None:
    seen: list[dict[str, Any]] = []

    class _Recorder(_SGLangHandler):
        def _route(self, payload):
            seen.append(payload)
            return super()._route(payload)

    report = _report(endpoint_factory(_Recorder))
    assert _statuses(report)["sglang_json_schema"] == "ok"
    assert all("extra_body" not in payload and "json_schema" not in payload for payload in seen)
    schemas = [payload["response_format"]["json_schema"] for payload in seen if (payload.get("response_format") or {}).get("type") == "json_schema"]
    assert len(schemas) == 1 and schemas[0]["name"] == "smab_probe"


@pytest.mark.parametrize("bad_value", [
    {"city": 123, "high_c": 29}, {"city": "marker", "high_c": "hot"},
    {"city": "marker", "high_c": True}, {"city": "marker", "high_c": 29, "extra": True},
    {"city": "marker"}, {"city": "Shanghai", "high_c": 29},
    {"city": "marker", "high_c": float("nan")}, ["not", "an", "object"],
])
def test_constrained_outputs_validate_every_schema_rule(endpoint_factory, bad_value) -> None:
    class _InvalidSchema(_ModernVLLMHandler):
        def _route(self, payload):
            schema = _schema_of(payload)
            if schema is not None:
                invalid = dict(bad_value) if isinstance(bad_value, dict) else bad_value
                if isinstance(invalid, dict) and invalid.get("city") == "marker":
                    invalid["city"] = schema["properties"]["city"]["enum"][0]
                return 200, _content_message(json.dumps(invalid))
            return super()._route(payload)

    statuses = _statuses(_report(endpoint_factory(_InvalidSchema)))
    assert all(statuses[name] == "unsupported" for name in CONSTRAINED_CHECKS)


def test_ignored_constraints_cannot_pass_from_weather_prompt(endpoint_factory) -> None:
    class _IgnoresConstraints(_ModernVLLMHandler):
        def _route(self, payload):
            if _schema_of(payload) is not None or payload.get("response_format") or "NOT_JSON" in self._last_user_message(payload):
                return 200, _content_message(GOOD_JSON)
            return super()._route(payload)

    statuses = _statuses(_report(endpoint_factory(_IgnoresConstraints)))
    assert all(statuses[name] == "unsupported" for name in CONSTRAINED_CHECKS)
    # Both JSON-object requests already return objects: cannot infer whether
    # response_format changed anything, so do not claim it is unsupported.
    assert statuses["json_object_response_format"] == "error"


def test_json_object_rejects_arrays(endpoint_factory) -> None:
    class _ArrayFormat(_ModernVLLMHandler):
        def _route(self, payload):
            if payload.get("response_format") == {"type": "json_object"}:
                return 200, _content_message('["not", "an", "object"]')
            return super()._route(payload)

    assert _statuses(_report(endpoint_factory(_ArrayFormat)))["json_object_response_format"] == "unsupported"


def test_ignored_tool_choice_is_not_reported_as_enforced(endpoint_factory) -> None:
    class _IgnoresChoice(_ModernVLLMHandler):
        def _route(self, payload):
            if payload.get("tool_choice") == "required" or isinstance(payload.get("tool_choice"), dict):
                payload["tool_choice"] = "auto"
            return super()._route(payload)

    statuses = _statuses(_report(endpoint_factory(_IgnoresChoice)))
    assert statuses["native_tools"] == "ok"
    assert statuses["tool_choice_required"] == "unsupported"
    assert statuses["tool_choice_named"] == "unsupported"


def test_ambiguous_tool_choice_controls_are_inconclusive(endpoint_factory) -> None:
    class _TimeControl(_ModernVLLMHandler):
        def _route(self, payload):
            if len(payload.get("tools", [])) == 2:
                return 200, _tool_call_message([TIME_CALL])
            return super()._route(payload)

    statuses = _statuses(_report(endpoint_factory(_TimeControl)))
    assert statuses["tool_choice_required"] == "error"
    assert statuses["tool_choice_named"] == "error"


@pytest.mark.parametrize("body", [_content_message(None), {"choices": []}, {"choices": [{"message": []}]}, {"choices": [{"message": {"role": "user", "content": "not an assistant continuation"}}]}])
def test_roundtrip_requires_valid_assistant_continuation(endpoint_factory, body) -> None:
    seen: list[dict[str, Any]] = []

    class _EmptyContinuation(_ModernVLLMHandler):
        def _route(self, payload):
            if _is_roundtrip(payload):
                seen.append(payload)
                return 200, body
            return super()._route(payload)

    report = _report(endpoint_factory(_EmptyContinuation))
    statuses = _statuses(report)
    assert len(seen) == 1
    assert statuses["native_tools"] == "ok"
    assert statuses["tool_roundtrip"] == "unsupported"
    assert report["summary"]["recommended_tool_format"] == "json"


@pytest.mark.parametrize("tool_format", ["native", "json"])
def test_probe_schema_never_enters_recommended_command(endpoint_factory, tool_format) -> None:
    class _JsonOnly(_ModernVLLMHandler):
        @property
        def supports_tools(self):
            return False

    handler = _ModernVLLMHandler if tool_format == "native" else _JsonOnly
    report = _report(endpoint_factory(handler))
    assert report["summary"]["recommended_tool_format"] == tool_format
    assert report["summary"]["constrained_decoding"]["dialect"] == "vllm-structured-outputs"
    assert report["summary"]["constrained_decoding"]["extra_body"] is None
    command = render_probe_markdown(report).split("```bash\n")[1].split("```", 1)[0]
    args = shlex.split(command.replace("\\\n", ""))
    assert args[-2:] == ["--tool-format", tool_format]
    assert "--extra-body" not in args
    assert "city" not in command and "high_c" not in command


def test_bare_recommendation_omits_response_format(endpoint_factory) -> None:
    report = _report(endpoint_factory(_BareHandler))
    assert report["summary"]["recommended_extra_body"] == {"response_format": None}
    assert '--extra-body \'{"response_format": null}\'' in render_probe_markdown(report)


def test_transient_tool_errors_do_not_recommend_prompt_fallback(endpoint_factory) -> None:
    class _BrokenTools(_BareHandler):
        def _route(self, payload):
            if "tools" in payload:
                return 503, _reject("temporary tools service failure")
            return super()._route(payload)

    report = _report(endpoint_factory(_BrokenTools))
    assert _statuses(report)["chat_completion"] == "ok"
    assert report["summary"]["recommended_tool_format"] is None
    assert "```bash" not in render_probe_markdown(report)


def test_inconclusive_json_control_does_not_disable_parameter(endpoint_factory) -> None:
    class _JsonControl(_BareHandler):
        def _route(self, payload):
            if "tools" not in payload and _schema_of(payload) is None:
                return 200, _content_message(GOOD_JSON)
            return super()._route(payload)

    report = _report(endpoint_factory(_JsonControl))
    assert _statuses(report)["json_object_response_format"] == "error"
    assert report["summary"]["recommended_tool_format"] is None
    assert report["summary"]["recommended_extra_body"] is None
    assert "must omit" not in " ".join(report["summary"]["notes"])

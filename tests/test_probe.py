"""End-to-end probe tests against real local HTTP mock endpoints.

Each persona emulates a serving stack's actual behaviour as documented by its
upstream project:

- ``modern_vllm``: vLLM >= 0.12 structured outputs (``structured_outputs``),
  native tool calling with all ``tool_choice`` tiers, parallel calls.
- ``legacy_vllm``: vLLM < 0.12 ``guided_json`` dialect, native tool calling.
- ``sglang``: SGLang ``json_schema`` extra-body dialect, native tool calling.
- ``llamacpp``: llama.cpp server: native tool calling, schema-constrained
  ``response_format``, but parallel tool calls disabled by default.
- ``bare``: an endpoint with none of the above; SMAB must fall back to the
  JSON protocol.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
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


def _content_message(content: str) -> dict[str, Any]:
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

        if tool_choice == "none":
            return 200, _content_message("Shanghai will be cloudy with a high of 29°C.")
        if has_tools and tool_choice == "auto":
            prompt = self._last_user_message(payload)
            if TWO_CITIES in prompt and payload.get("parallel_tool_calls") and self.supports_parallel:
                return 200, _tool_call_message([SINGLE_CALL, dict(SINGLE_CALL, id="call_probe_2")])
            return 200, _tool_call_message([SINGLE_CALL])
        if has_tools and tool_choice in ("required", {"type": "function", "function": {"name": "get_weather"}}):
            return 200, _tool_call_message([SINGLE_CALL])
        if has_tools and "tool_call_id" in json.dumps(payload.get("messages", [])):
            # multi-turn round-trip: assistant tool_calls + tool result messages
            return 200, _content_message("The high in Shanghai on 2026-09-06 is 29°C.")

        dialect = self.detect_dialect(response_format, extra)
        if dialect == "unsupported":
            return 400, _reject("unsupported structured output request")
        if dialect in ("structured_outputs", "guided_json", "json_schema", "response_schema", "json_object"):
            return 200, _content_message(GOOD_JSON)
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

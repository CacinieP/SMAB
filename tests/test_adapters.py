import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from smab.adapters import (
    AdapterError,
    OpenAICompatibleAdapter,
    _chat_completions_url,
    _parse_json_turn,
    _parse_native_turn,
)


def test_endpoint_url_normalization() -> None:
    assert _chat_completions_url("http://localhost:8000") == "http://localhost:8000/v1/chat/completions"
    assert _chat_completions_url("http://localhost:8000/v1") == "http://localhost:8000/v1/chat/completions"
    assert (
        _chat_completions_url("http://localhost:8000/v1/chat/completions/")
        == "http://localhost:8000/v1/chat/completions"
    )


def test_native_tool_call_parser_reports_bad_arguments() -> None:
    turn = _parse_native_turn(
        {
            "content": None,
            "tool_calls": [
                {"id": "c1", "function": {"name": "get_weather", "arguments": "{bad"}}
            ],
        }
    )
    assert turn.tool_calls[0].name == "get_weather"
    assert turn.tool_calls[0].parse_error


def test_json_protocol_accepts_fenced_or_prefixed_object() -> None:
    turn = _parse_json_turn('result follows: ```json\n{"tool_calls":[{"name":"x","arguments":{"a":1}}]}\n```')
    assert turn.tool_calls[0].name == "x"
    assert turn.tool_calls[0].arguments == {"a": 1}


def test_json_protocol_final() -> None:
    turn = _parse_json_turn('{"final":"done"}')
    assert turn.content == "done"
    assert turn.tool_calls == []


def test_json_protocol_rejects_wrong_object_shape() -> None:
    turn = _parse_json_turn('{"answer":"done"}')
    assert turn.raw["protocol_error"]


def test_json_protocol_can_run_on_endpoint_without_response_format() -> None:
    class PromptOnlyEndpoint(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if "response_format" in payload:
                status, body = 400, {"error": {"message": "response_format is unsupported"}}
            else:
                status, body = 200, {"choices": [{"message": {"content": '{"final":"done"}'}}]}
            encoded = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), PromptOnlyEndpoint)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_port}/v1"
    try:
        default = OpenAICompatibleAdapter(base_url=base_url, model="mock", tool_format="json")
        with pytest.raises(AdapterError, match="HTTP 400"):
            default.complete([{"role": "user", "content": "Say done."}], [])
        fallback = OpenAICompatibleAdapter(
            base_url=base_url, model="mock", tool_format="json",
            extra_body={"response_format": None},
        )
        turn = fallback.complete([{"role": "user", "content": "Say done."}], [])
        assert turn.content == "done"
        assert not turn.tool_calls
    finally:
        server.shutdown()
        server.server_close()

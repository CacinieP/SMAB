"""Run generated probe commands against HTTP endpoints with different contracts."""
import json
import shlex
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from smab.cli import main
from smab.probe import ProbeConfig, probe_endpoint, render_probe_markdown

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("supports_format", [True, False], ids=["legacy-json", "prompt-only"])
def test_recommended_invocation_runs_the_benchmark_protocol(tmp_path, supports_format):
    class Endpoint(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            fmt = payload.get("response_format", {})
            rejected = (
                "tools" in payload or "structured_outputs" in payload
                or "json_schema" in payload or "schema" in fmt
                or fmt.get("type") == "json_schema"
                or (not supports_format and ("response_format" in payload or "guided_json" in payload))
            )
            if rejected:
                status, body = 400, {"error": {"message": "tools or structured output are not supported"}}
            else:
                status = 200
                if "guided_json" in payload:
                    # Honor every probe schema constraint. This server really
                    # supports constrained decoding, but weather is not SMAB's
                    # tool_calls/final protocol and must not be reused in run.
                    marker = payload["guided_json"]["properties"]["city"]["enum"][0]
                    content = json.dumps({"city": marker, "high_c": 29})
                elif "Available tool schemas" in payload["messages"][0]["content"]:
                    if any("TOOL_RESULT" in str(message.get("content")) for message in payload["messages"]):
                        content = json.dumps({"final": "IN_TRANSIT"})
                    else:
                        content = json.dumps({"tool_calls": [{
                            "name": "get_order_status", "arguments": {"order_id": "A-1049"},
                        }]})
                elif "response_format" in payload:
                    content = json.dumps({"city": "Shanghai", "high_c": 29})
                else:
                    content = "NOT_JSON"
                body = {"choices": [{"message": {"role": "assistant", "content": content}}]}
            encoded = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        report = probe_endpoint(ProbeConfig(
            base_url=f"http://127.0.0.1:{server.server_port}/v1", model="mock", timeout=2,
        ))
        assert report["summary"]["recommended_tool_format"] == "json"
        dialect = report["summary"]["constrained_decoding"]["dialect"]
        assert dialect == ("legacy-guided-json" if supports_format else None)
        markdown = render_probe_markdown(report)
        command = markdown.split("```bash\n", 1)[1].split("```", 1)[0]
        arguments = shlex.split(command.replace("\\\n", ""))[1:]
        output = tmp_path / "run.json"
        assert main(arguments + [
            "--dataset", str(ROOT / "datasets/core.jsonl"),
            "--tools", str(ROOT / "datasets/tools.json"),
            "--case-id", "rel_002", "--output", str(output),
        ]) == 0
        result = json.loads(output.read_text(encoding="utf-8"))["results"][0]
        assert result["stop_reason"] == "completed"
        assert result["score"]["success"]
        assert result["trace"][0]["name"] == "get_order_status"
    finally:
        server.shutdown()
        server.server_close()

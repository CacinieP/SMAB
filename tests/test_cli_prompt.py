"""CLI prompt/decoding controls preserve the runner and protocol contracts."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from smab import cli
from smab.runner import RunConfig


ROOT = Path(__file__).parents[1]


def run_arguments(output: Path, *extra: str) -> list[str]:
    return [
        "run", "--model", "stub", "--dataset", str(ROOT / "datasets/core.jsonl"),
        "--tools", str(ROOT / "datasets/tools.json"), "--case-id", "rel_002",
        "--output", str(output), *extra,
    ]


def record_endpoint(monkeypatch) -> list[dict]:
    payloads: list[dict] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            # Valid for both adapters; no tool effect or real request occurs.
            return json.dumps({"choices": [{"message": {"content": '{"final":"done"}'}}]}).encode()

    def urlopen(request, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    return payloads


@pytest.mark.parametrize("tool_format", ["native", "json"])
def test_prompt_file_reaches_each_repeat_and_keeps_adapter_protocol(tmp_path, monkeypatch, tool_format):
    prompt = "Use available tools carefully.\n依据返回值继续，不要猜测。\n"
    prompt_file = tmp_path / "策略.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    output = tmp_path / "run.json"
    payloads = record_endpoint(monkeypatch)

    assert cli.main(run_arguments(
        output, "--system-prompt-file", str(prompt_file), "--tool-format", tool_format,
        "--repeats", "2",
    )) == 0

    result = json.loads(output.read_text(encoding="utf-8"))
    assert [run["run"]["system_prompt"] for run in result["runs"]] == [prompt, prompt]
    assert len(payloads) == 2
    for payload in payloads:
        system = payload["messages"][0]
        assert system["role"] == "system"
        if tool_format == "native":
            assert system["content"] == prompt
            assert "tools" in payload
        else:
            assert system["content"].endswith("\n\n" + prompt)
            assert '"tool_calls"' in system["content"]
            assert "Available tool schemas" in system["content"]
            assert payload["response_format"] == {"type": "json_object"}


def test_without_prompt_file_keeps_existing_default(tmp_path, monkeypatch):
    output = tmp_path / "run.json"
    payloads = record_endpoint(monkeypatch)
    assert cli.main(run_arguments(output)) == 0
    expected = RunConfig(model="stub").system_prompt
    assert payloads[0]["messages"][0]["content"] == expected
    assert json.loads(output.read_text())["run"]["system_prompt"] == expected


@pytest.mark.parametrize("content", [b"", b" \n\t", b"\xff"])
def test_invalid_prompt_file_fails_before_endpoint_call(tmp_path, monkeypatch, capsys, content):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_bytes(content)
    output = tmp_path / "run.json"
    payloads = record_endpoint(monkeypatch)
    assert cli.main(run_arguments(output, "--system-prompt-file", str(prompt_file))) == 2
    assert payloads == []
    assert not output.exists()
    assert "error:" in capsys.readouterr().err


def test_missing_prompt_file_fails_before_endpoint_call(tmp_path, monkeypatch, capsys):
    output = tmp_path / "run.json"
    payloads = record_endpoint(monkeypatch)
    assert cli.main(run_arguments(
        output, "--system-prompt-file", str(tmp_path / "missing.txt"),
    )) == 2
    assert payloads == []
    assert not output.exists()
    assert "missing.txt" in capsys.readouterr().err


def test_probe_extra_body_reaches_config(tmp_path, monkeypatch):
    configs = []

    def probe(config):
        configs.append(config)
        return {"summary": {"ok": 0, "unsupported": 0, "error": 0,
                            "recommended_tool_format": "native",
                            "constrained_decoding": {"dialect": None}}}

    monkeypatch.setattr(cli, "probe_endpoint", probe)
    extra = {"reasoning_effort": "none", "seed": 0}
    assert cli.main([
        "probe", "--model", "stub", "--extra-body", json.dumps(extra),
        "--output", str(tmp_path / "probe.json"),
    ]) == 0
    assert configs[0].extra_body == extra


@pytest.mark.parametrize("command", ["run", "probe"])
@pytest.mark.parametrize("value", ["[]", '"text"', "0", "null"])
def test_extra_body_requires_object_before_request(tmp_path, monkeypatch, capsys, command, value):
    output = tmp_path / "result.json"
    payloads = record_endpoint(monkeypatch)
    arguments = (run_arguments(output) if command == "run" else
                 ["probe", "--model", "stub", "--output", str(output)])
    assert cli.main(arguments + ["--extra-body", value]) == 2
    assert payloads == []
    assert not output.exists()
    assert "--extra-body must be a JSON object" in capsys.readouterr().err

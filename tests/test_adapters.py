from smab.adapters import _chat_completions_url, _parse_json_turn, _parse_native_turn


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

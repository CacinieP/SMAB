from smab.adapters import ModelAdapter
from smab.models import BenchmarkCase, ModelTurn, ToolCall
from smab.runner import BenchmarkRunner, RunConfig


class ScriptedAdapter(ModelAdapter):
    def __init__(self, turns):
        self.turns = iter(turns)

    def complete(self, messages, tools):
        return next(self.turns)


def test_runner_executes_retry_episode_and_scores_it() -> None:
    tool = {
        "type": "function",
        "function": {"name": "fetch", "description": "fetch", "parameters": {"type": "object"}},
    }
    case = BenchmarkCase(
        id="retry",
        category="recovery",
        split="core",
        prompt="fetch x, retry timeout",
        tools=[tool],
        tool_behaviors={
            "fetch": {
                "rules": [
                    {"when": {"id": "x"}, "times": 1, "error": "timeout"},
                    {"when": {"id": "x"}, "return": {"code": "OK-1"}},
                ]
            }
        },
        expected={
            "calls": [
                {"tool": "fetch", "arguments": {"id": "x"}},
                {"tool": "fetch", "arguments": {"id": "x"}},
            ],
            "sequence": ["fetch", "fetch"],
            "recovery": {"tool": "fetch", "min_calls": 2},
            "final_contains": ["OK-1"],
            "max_calls": 2,
        },
        dimensions=["arguments", "planning", "recovery", "state_tracking", "stopping"],
    )
    adapter = ScriptedAdapter(
        [
            ModelTurn(tool_calls=[ToolCall("fetch", {"id": "x"}, "c1")]),
            ModelTurn(tool_calls=[ToolCall("fetch", {"id": "x"}, "c2")]),
            ModelTurn(content="Result OK-1"),
        ]
    )
    result = BenchmarkRunner(adapter, RunConfig(model="stub")).run([case])
    assert result["summary"]["overall"] == 1.0
    assert [event["error"] for event in result["results"][0]["trace"]] == ["timeout", None]


def test_runner_maps_aliased_tool_back_to_canonical_name() -> None:
    tool = {
        "type": "function",
        "function": {"name": "fetch", "description": "fetch", "parameters": {"type": "object"}},
    }
    case = BenchmarkCase(
        id="alias",
        category="selection",
        split="core",
        prompt="fetch",
        tools=[tool],
        tool_behaviors={"fetch": {"rules": [{"when": {}, "return": {"ok": True}}]}},
        expected={"calls": [{"tool": "fetch", "arguments": {}}]},
        dimensions=["selection"],
    )
    adapter = ScriptedAdapter(
        [ModelTurn(tool_calls=[ToolCall("fn_01", {}, "c1")]), ModelTurn(content="done")]
    )
    result = BenchmarkRunner(
        adapter, RunConfig(model="stub", schema_variant="aliased")
    ).run([case])
    assert result["summary"]["overall"] == 1.0

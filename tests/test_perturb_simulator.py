from smab.models import ToolCall
from smab.perturb import perturb_tools
from smab.simulator import ToolSimulator


TOOLS = [
    {"type": "function", "function": {"name": "alpha", "description": "a", "parameters": {}}},
    {"type": "function", "function": {"name": "beta", "description": "b", "parameters": {}}},
]


def test_aliases_are_reversible() -> None:
    result = perturb_tools(TOOLS, "aliased")
    assert [tool["function"]["name"] for tool in result.tools] == ["fn_01", "fn_02"]
    assert result.exposed_to_canonical == {"fn_01": "alpha", "fn_02": "beta"}


def test_stateful_error_then_success() -> None:
    simulator = ToolSimulator(
        {
            "alpha": {
                "rules": [
                    {"when": {"x": 1}, "times": 1, "error": "timeout"},
                    {"when": {"x": 1}, "return": {"answer": 2}},
                ]
            }
        },
        {"alpha": "alpha"},
    )
    first = simulator.execute(ToolCall(name="alpha", arguments={"x": 1}), 1)
    second = simulator.execute(ToolCall(name="alpha", arguments={"x": 1}), 2)
    assert first.error == "timeout"
    assert second.error is None
    assert second.output == {"answer": 2}


def test_simulator_supports_controlled_value_matchers() -> None:
    simulator = ToolSimulator(
        {
            "alpha": {
                "rules": [
                    {
                        "when": {
                            "city": {"$one_of": ["上海", "Shanghai"]},
                            "query": {"$contains_any": ["release", "发布"]},
                        },
                        "return": {"ok": True},
                    }
                ]
            }
        },
        {"alpha": "alpha"},
    )
    event = simulator.execute(
        ToolCall(name="alpha", arguments={"city": "Shanghai", "query": "2026 release process"}), 1
    )
    assert event.error is None

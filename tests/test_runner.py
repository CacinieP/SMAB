import pytest

from smab.adapters import ModelAdapter
from smab.models import BenchmarkCase, ModelTurn, ToolCall
from smab.runner import BenchmarkRunner, RunConfig, _pass_at_k, aggregate_runs


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


def test_aggregate_runs_reports_mean_stddev_and_keeps_individual_runs() -> None:
    runs = [
        {"run": {"model": "stub", "tool_format": "json", "schema_variant": "original", "case_count": 1, "repeat_index": 1}, "summary": {"overall": 0.5, "case_success_rate": 0.0}},
        {"run": {"model": "stub", "tool_format": "json", "schema_variant": "original", "case_count": 1, "repeat_index": 2}, "summary": {"overall": 1.0, "case_success_rate": 1.0}},
    ]
    result = aggregate_runs(runs)
    assert result["summary"]["overall_mean"] == 0.75
    assert result["summary"]["overall_stddev"] == 0.25
    assert len(result["runs"]) == 2


def test_aggregate_runs_computes_pass_at_k_from_per_case_outcomes() -> None:
    def _run(repeat_index: int, successes: list[bool]) -> dict:
        return {
            "run": {
                "model": "stub",
                "tool_format": "json",
                "schema_variant": "original",
                "case_count": len(successes),
                "repeat_index": repeat_index,
            },
            "summary": {
                "overall": sum(successes) / len(successes),
                "case_success_rate": sum(successes) / len(successes),
            },
            "results": [
                {"id": f"case_{index}", "score": {"success": ok}}
                for index, ok in enumerate(successes)
            ],
        }

    runs = [
        _run(1, [True, False]),
        _run(2, [True, True]),
        _run(3, [True, False]),
    ]
    result = aggregate_runs(runs)
    pass_at_k = result["summary"]["pass_at_k"]
    # case_0 always succeeds (p=1), case_1 succeeds in 1 of 3 repeats (p=1/3).
    assert pass_at_k["1"] == round((1.0 + 1 / 3) / 2, 4)
    # case_1 has no all-success subsets of size 2 or 3.
    assert pass_at_k["2"] == 0.5
    assert pass_at_k["3"] == 0.5
    assert pass_at_k["1"] == result["summary"]["perfect_case_rate_mean"]


@pytest.mark.parametrize(
    ("attempts", "successes", "k", "expected"),
    [
        (4, 2, 1, 0.5),
        (4, 2, 2, round(1 / 6, 4)),
        (4, 2, 3, 0.0),
        (5, 3, 2, 0.3),
        (5, 3, 3, 0.1),
        (3, 3, 3, 1.0),
        (3, 0, 1, 0.0),
        (3, 0, 3, 0.0),
        (1, 1, 1, 1.0),
    ],
)
def test_pass_at_k_uses_finite_sample_all_success_subsets(
    attempts: int, successes: int, k: int, expected: float
) -> None:
    runs = [
        {
            "run": {
                "model": "stub",
                "tool_format": "json",
                "schema_variant": "original",
                "case_count": 1,
            },
            "summary": {
                # Failed attempts can still earn partial credit.
                "overall": 1.0 if index < successes else 0.75,
                "case_success_rate": float(index < successes),
            },
            "results": [{"id": "case", "score": {"success": index < successes}}],
        }
        for index in range(attempts)
    ]
    result = aggregate_runs(runs)
    assert result["summary"]["pass_at_k"][str(k)] == expected
    assert result["summary"]["pass_at_k"]["1"] == result["summary"]["perfect_case_rate_mean"]
    if successes < attempts:
        assert result["summary"]["pass_at_k"]["1"] != result["summary"]["overall_mean"]


def test_pass_at_k_rejects_insufficient_attempts() -> None:
    runs = [{"results": [{"id": "case", "score": {"success": True}}]}]
    with pytest.raises(ValueError, match="at least k attempts"):
        _pass_at_k(runs, 2)
    with pytest.raises(ValueError, match="at least 1"):
        _pass_at_k(runs, 0)

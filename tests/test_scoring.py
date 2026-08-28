import pytest

from smab.models import BenchmarkCase, TraceEvent
from smab.scoring import score_case


def make_case(**expected):
    return BenchmarkCase(
        id="x",
        category="test",
        split="core",
        prompt="",
        tools=[],
        tool_behaviors={},
        expected=expected,
        dimensions=["selection", "arguments", "planning", "state_tracking", "stopping"],
    )


def test_full_trace_scores_one() -> None:
    case = make_case(
        calls=[
            {"tool": "lookup", "arguments": {"id": "A"}},
            {"tool": "act", "arguments": {"amount": 3}},
        ],
        sequence=["lookup", "act"],
        final_contains=["OK-9"],
        max_calls=2,
    )
    trace = [
        TraceEvent(1, "lookup", "lookup", {"id": "A"}, output={"amount": 3}),
        TraceEvent(2, "act", "act", {"amount": 3}, output={"id": "OK-9"}),
    ]
    score = score_case(case, trace, "Completed: OK-9", "completed")
    assert score["overall"] == 1.0
    assert score["success"]


def test_argument_score_gives_field_level_credit() -> None:
    case = make_case(calls=[{"tool": "lookup", "arguments": {"a": 1, "b": 2}}])
    case.dimensions = ["arguments"]
    trace = [TraceEvent(1, "lookup", "lookup", {"a": 1, "b": 99})]
    assert score_case(case, trace, "done", "completed")["overall"] == pytest.approx(0.5)


def test_argument_matchers_accept_controlled_aliases_and_query_text() -> None:
    case = make_case(
        calls=[
            {
                "tool": "lookup",
                "arguments": {
                    "city": {"$one_of": ["上海", "Shanghai"]},
                    "query": {"$contains_all": ["2026", "release"]},
                },
            }
        ]
    )
    case.dimensions = ["arguments"]
    trace = [TraceEvent(1, "lookup", "lookup", {"city": "Shanghai", "query": "2026 release process"})]
    assert score_case(case, trace, "done", "completed")["overall"] == 1.0

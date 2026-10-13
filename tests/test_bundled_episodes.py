from pathlib import Path

import pytest

from smab.adapters import ModelAdapter
from smab.dataset import load_cases, load_catalog
from smab.models import ModelTurn, ToolCall
from smab.runner import BenchmarkRunner, RunConfig


ROOT = Path(__file__).parents[1]


class ExpectedTraceAdapter(ModelAdapter):
    """Emit a case's declared oracle trace to test fixtures and scoring end to end."""

    def __init__(self, case):
        self.case = case
        self.calls = iter(case.expected.get("calls", []))
        self.finished = False

    def complete(self, messages, tools):
        if not self.finished:
            try:
                expected = next(self.calls)
                return ModelTurn(
                    tool_calls=[
                        ToolCall(
                            name=expected["tool"],
                            arguments=_materialize(expected.get("arguments", {})),
                            id=f"call_{len(messages)}",
                        )
                    ]
                )
            except StopIteration:
                self.finished = True
        facts = [str(item) for item in self.case.expected.get("final_contains", [])]
        any_groups = self.case.expected.get("final_contains_any", [])
        if any_groups:
            first = any_groups[0]
            facts.append(str(first[0] if isinstance(first, list) else first))
        return ModelTurn(content="completed " + " ".join(facts))


def _materialize(value):
    if isinstance(value, dict):
        for matcher in ("$one_of", "$contains_any", "$contains_all"):
            if matcher in value:
                values = value[matcher]
                return values[0] if matcher != "$contains_all" else " ".join(map(str, values))
        return {key: _materialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_materialize(item) for item in value]
    return value


def test_all_bundled_oracle_traces_execute_and_score_perfectly() -> None:
    catalog = load_catalog(ROOT / "datasets/tools.json")
    cases = load_cases(ROOT / "datasets/core.jsonl", catalog)
    for case in cases:
        result = BenchmarkRunner(ExpectedTraceAdapter(case), RunConfig(model="oracle")).run_case(case)
        assert result["score"]["overall"] == 1.0, (case.id, result)


def _extra_cases():
    catalog = load_catalog(ROOT / "datasets/tools.json")
    return load_cases(ROOT / "datasets/minicpm47_extra.jsonl", catalog)


class WrongFinalTraceAdapter(ExpectedTraceAdapter):
    """Follow the oracle calls but report an incorrect final answer."""

    def __init__(self, case, final_response="Done"):
        super().__init__(case)
        self.final_response = final_response

    def complete(self, messages, tools):
        turn = super().complete(messages, tools)
        if not turn.tool_calls:
            turn.content = self.final_response
        return turn


@pytest.mark.parametrize("case", _extra_cases(), ids=lambda case: case.id)
def test_extra_oracle_traces_execute_and_score_perfectly(case) -> None:
    result = BenchmarkRunner(ExpectedTraceAdapter(case), RunConfig(model="oracle")).run_case(case)
    assert result["score"]["overall"] == 1.0, result
    assert result["score"]["success"]


@pytest.mark.parametrize("case", _extra_cases(), ids=lambda case: case.id)
def test_extra_final_requirements_affect_case_success(case) -> None:
    assert case.expected.get("final_contains") or case.expected.get("final_contains_any")
    result = BenchmarkRunner(WrongFinalTraceAdapter(case), RunConfig(model="oracle")).run_case(case)
    assert result["score"]["dimensions"]["state_tracking"] == 0.0, result
    assert result["score"]["overall"] < 1.0
    assert not result["score"]["success"]


def test_refund_maintenance_cannot_be_reported_as_success() -> None:
    case = next(case for case in _extra_cases() if case.id == "m47_recover_103")
    adapter = WrongFinalTraceAdapter(case, final_response="退款成功")
    result = BenchmarkRunner(adapter, RunConfig(model="oracle")).run_case(case)
    assert len(result["trace"]) == 1
    assert result["trace"][0]["error"] == "refund_channel_maintenance"
    assert result["score"]["dimensions"]["state_tracking"] == 0.0
    assert not result["score"]["success"]

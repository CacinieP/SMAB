from pathlib import Path

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

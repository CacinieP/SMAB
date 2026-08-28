from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .models import BenchmarkCase, TraceEvent


def score_case(
    case: BenchmarkCase,
    trace: list[TraceEvent],
    final_response: str | None,
    stop_reason: str,
) -> dict[str, Any]:
    scorers = {
        "relevance": _score_relevance,
        "selection": _score_selection,
        "arguments": _score_arguments,
        "planning": _score_planning,
        "state_tracking": _score_state_tracking,
        "recovery": _score_recovery,
        "stopping": _score_stopping,
    }
    scores = {
        dimension: round(scorers[dimension](case, trace, final_response, stop_reason), 4)
        for dimension in case.dimensions
    }
    overall = sum(scores.values()) / len(scores) if scores else 0.0
    return {
        "overall": round(overall, 4),
        "success": overall >= 0.9999,
        "dimensions": scores,
    }


def _score_relevance(
    case: BenchmarkCase, trace: list[TraceEvent], final_response: str | None, stop_reason: str
) -> float:
    should_call = bool(case.expected.get("should_call", bool(case.expected.get("calls"))))
    return float(bool(trace) == should_call)


def _score_selection(
    case: BenchmarkCase, trace: list[TraceEvent], final_response: str | None, stop_reason: str
) -> float:
    expected = [item["tool"] for item in case.expected.get("calls", [])]
    actual = [event.name for event in trace]
    if not expected:
        return float(not actual)
    expected_counts = Counter(expected)
    actual_counts = Counter(actual)
    matched = sum(min(count, actual_counts[name]) for name, count in expected_counts.items())
    precision = matched / len(actual) if actual else 0.0
    recall = matched / len(expected)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _score_arguments(
    case: BenchmarkCase, trace: list[TraceEvent], final_response: str | None, stop_reason: str
) -> float:
    expected_calls = case.expected.get("calls", [])
    if not expected_calls:
        return 1.0
    consumed: set[int] = set()
    call_scores: list[float] = []
    for expected in expected_calls:
        candidate_index = next(
            (
                index
                for index, event in enumerate(trace)
                if index not in consumed and event.name == expected["tool"]
            ),
            None,
        )
        if candidate_index is None:
            call_scores.append(0.0)
            continue
        consumed.add(candidate_index)
        actual_args = trace[candidate_index].arguments
        expected_args = expected.get("arguments", {})
        if not expected_args:
            call_scores.append(1.0)
            continue
        correct = sum(
            key in actual_args and _value_equal(value, actual_args[key])
            for key, value in expected_args.items()
        )
        score = correct / len(expected_args)
        if expected.get("match", "subset") == "exact" and set(actual_args) != set(expected_args):
            score *= len(expected_args) / max(len(actual_args), len(expected_args))
        call_scores.append(score)
    return sum(call_scores) / len(call_scores)


def _score_planning(
    case: BenchmarkCase, trace: list[TraceEvent], final_response: str | None, stop_reason: str
) -> float:
    actual = [event.name for event in trace]
    alternatives = case.expected.get("sequence_any_of")
    if alternatives:
        return max(_lcs_ratio(sequence, actual) for sequence in alternatives)
    sequence = case.expected.get("sequence") or [item["tool"] for item in case.expected.get("calls", [])]
    return _lcs_ratio(sequence, actual) if sequence else 1.0


def _score_state_tracking(
    case: BenchmarkCase, trace: list[TraceEvent], final_response: str | None, stop_reason: str
) -> float:
    required = case.expected.get("final_contains", [])
    any_groups = case.expected.get("final_contains_any", [])
    if any_groups and all(isinstance(item, str) for item in any_groups):
        any_groups = [any_groups]
    if not required and not any_groups:
        return float(bool(final_response))
    haystack = _normalize(final_response or "")
    checks = [_normalize(str(value)) in haystack for value in required]
    checks.extend(
        any(_normalize(str(value)) in haystack for value in group)
        for group in any_groups
    )
    return sum(checks) / len(checks)


def _score_recovery(
    case: BenchmarkCase, trace: list[TraceEvent], final_response: str | None, stop_reason: str
) -> float:
    spec = case.expected.get("recovery", {})
    tool = spec.get("tool")
    if not tool:
        return 1.0
    events = [event for event in trace if event.name == tool]
    checks = [
        any(event.error is not None for event in events),
        any(event.error is None for event in events),
        len(events) >= int(spec.get("min_calls", 2)),
    ]
    if spec.get("changed_arguments"):
        serialized = {repr(sorted(event.arguments.items())) for event in events}
        checks.append(len(serialized) >= 2)
    return sum(checks) / len(checks)


def _score_stopping(
    case: BenchmarkCase, trace: list[TraceEvent], final_response: str | None, stop_reason: str
) -> float:
    checks = [stop_reason == "completed", bool(final_response)]
    max_calls = case.expected.get("max_calls")
    if max_calls is not None:
        checks.append(len(trace) <= int(max_calls))
    forbidden = set(case.expected.get("forbidden_tools", []))
    if forbidden:
        checks.append(not any(event.name in forbidden for event in trace))
    stop_after_error = case.expected.get("stop_after_error")
    if stop_after_error:
        events = [event for event in trace if event.name == stop_after_error]
        checks.append(len(events) == 1 and events[0].error is not None)
    return sum(checks) / len(checks)


def _lcs_ratio(expected: list[str], actual: list[str]) -> float:
    if not expected:
        return 1.0
    table = [0] * (len(actual) + 1)
    for wanted in expected:
        previous = 0
        for index, observed in enumerate(actual, start=1):
            saved = table[index]
            if wanted == observed:
                table[index] = previous + 1
            else:
                table[index] = max(table[index], table[index - 1])
            previous = saved
    return table[-1] / len(expected)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _value_equal(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        if "$one_of" in expected:
            return any(_value_equal(candidate, actual) for candidate in expected["$one_of"])
        if "$contains_any" in expected and isinstance(actual, str):
            haystack = _normalize(actual)
            return any(_normalize(str(value)) in haystack for value in expected["$contains_any"])
        if "$contains_all" in expected and isinstance(actual, str):
            haystack = _normalize(actual)
            return all(_normalize(str(value)) in haystack for value in expected["$contains_all"])
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return float(expected) == float(actual)
    if isinstance(expected, str) and isinstance(actual, str):
        return _normalize(expected) == _normalize(actual)
    return expected == actual

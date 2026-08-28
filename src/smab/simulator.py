from __future__ import annotations

import copy
import json
from typing import Any

from .models import ToolCall, TraceEvent


class ToolSimulator:
    def __init__(self, behaviors: dict[str, Any], exposed_to_canonical: dict[str, str]) -> None:
        self.behaviors = copy.deepcopy(behaviors)
        self.exposed_to_canonical = exposed_to_canonical
        self.rule_uses: dict[tuple[str, int], int] = {}

    def execute(self, call: ToolCall, turn: int) -> TraceEvent:
        canonical = self.exposed_to_canonical.get(call.name, call.name)
        if call.parse_error:
            return TraceEvent(
                turn=turn,
                requested_name=call.name,
                name=canonical,
                arguments=call.arguments,
                error=f"invalid_arguments_json: {call.parse_error}",
                parse_error=call.parse_error,
            )
        behavior = self.behaviors.get(canonical)
        if behavior is None:
            return TraceEvent(
                turn=turn,
                requested_name=call.name,
                name=canonical,
                arguments=call.arguments,
                error="unknown_or_unconfigured_tool",
            )
        rules = behavior.get("rules", [])
        for index, rule in enumerate(rules):
            key = (canonical, index)
            uses = self.rule_uses.get(key, 0)
            limit = rule.get("times")
            if limit is not None and uses >= int(limit):
                continue
            if not _matches(rule.get("when", {}), call.arguments):
                continue
            self.rule_uses[key] = uses + 1
            if "error" in rule:
                return TraceEvent(
                    turn=turn,
                    requested_name=call.name,
                    name=canonical,
                    arguments=call.arguments,
                    error=str(rule["error"]),
                )
            return TraceEvent(
                turn=turn,
                requested_name=call.name,
                name=canonical,
                arguments=call.arguments,
                output=copy.deepcopy(rule.get("return")),
            )
        default = behavior.get("default", {"error": "arguments_do_not_match_fixture"})
        if "error" in default:
            return TraceEvent(
                turn=turn,
                requested_name=call.name,
                name=canonical,
                arguments=call.arguments,
                error=str(default["error"]),
            )
        return TraceEvent(
            turn=turn,
            requested_name=call.name,
            name=canonical,
            arguments=call.arguments,
            output=copy.deepcopy(default.get("return")),
        )


def tool_result_content(event: TraceEvent) -> str:
    payload = {"ok": event.error is None}
    if event.error is not None:
        payload["error"] = event.error
    else:
        payload["result"] = event.output
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _matches(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    return all(key in actual and _equal(value, actual[key]) for key, value in expected.items())


def _equal(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        if "$one_of" in expected:
            return any(_equal(candidate, actual) for candidate in expected["$one_of"])
        if "$contains_any" in expected and isinstance(actual, str):
            normalized = actual.strip().casefold()
            return any(str(value).strip().casefold() in normalized for value in expected["$contains_any"])
        if "$contains_all" in expected and isinstance(actual, str):
            normalized = actual.strip().casefold()
            return all(str(value).strip().casefold() in normalized for value in expected["$contains_all"])
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return float(expected) == float(actual)
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.strip().casefold() == actual.strip().casefold()
    return expected == actual

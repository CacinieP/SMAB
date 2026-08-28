from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import AdapterError, ModelAdapter
from .models import BenchmarkCase, TraceEvent
from .perturb import perturb_tools
from .scoring import score_case
from .simulator import ToolSimulator, tool_result_content


@dataclass(slots=True)
class RunConfig:
    model: str
    tool_format: str = "native"
    schema_variant: str = "original"
    seed: int = 0
    system_prompt: str = (
        "Complete the user's task. Use tools only when they are relevant. "
        "Use tool results to continue, recover from recoverable errors, and stop when the task is complete."
    )


class BenchmarkRunner:
    def __init__(self, adapter: ModelAdapter, config: RunConfig) -> None:
        self.adapter = adapter
        self.config = config

    def run(self, cases: list[BenchmarkCase]) -> dict[str, Any]:
        started = datetime.now(timezone.utc)
        results = [self.run_case(case) for case in cases]
        return {
            "run": {
                **asdict(self.config),
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "case_count": len(cases),
            },
            "summary": summarize_results(results),
            "results": results,
        }

    def run_case(self, case: BenchmarkCase) -> dict[str, Any]:
        perturbed = perturb_tools(case.tools, self.config.schema_variant, self.config.seed)
        simulator = ToolSimulator(case.tool_behaviors, perturbed.exposed_to_canonical)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": case.prompt},
        ]
        trace: list[TraceEvent] = []
        final_response: str | None = None
        stop_reason = "max_turns"
        usage: dict[str, float] = defaultdict(float)
        raw_turns: list[dict[str, Any]] = []
        started = time.perf_counter()

        for turn_number in range(1, case.max_turns + 1):
            try:
                turn = self.adapter.complete(messages, perturbed.tools)
            except AdapterError as exc:
                stop_reason = "adapter_error"
                final_response = str(exc)
                break
            raw_turns.append(turn.raw)
            for key, value in turn.usage.items():
                if isinstance(value, (int, float)):
                    usage[key] += value
            protocol_error = turn.raw.get("_smab", {}).get("protocol_error")
            if protocol_error:
                stop_reason = "protocol_error"
                final_response = turn.content or protocol_error
                break
            if not turn.tool_calls:
                final_response = turn.content or ""
                stop_reason = "completed"
                break

            assistant_calls = []
            for call in turn.tool_calls:
                assistant_calls.append(
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, ensure_ascii=False),
                        },
                    }
                )
            messages.append(
                {"role": "assistant", "content": turn.content, "tool_calls": assistant_calls}
            )
            for call in turn.tool_calls:
                event = simulator.execute(call, turn_number)
                trace.append(event)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": tool_result_content(event),
                    }
                )

        score = score_case(case, trace, final_response, stop_reason)
        return {
            "id": case.id,
            "category": case.category,
            "split": case.split,
            "tags": case.tags,
            "prompt": case.prompt,
            "expected_calls": len(case.expected.get("calls", [])),
            "schema_variant": self.config.schema_variant,
            "trace": [event.to_dict() for event in trace],
            "final_response": final_response,
            "stop_reason": stop_reason,
            "score": score,
            "usage": dict(usage),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "raw_turns": raw_turns,
        }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    category_scores: dict[str, list[float]] = defaultdict(list)
    dimension_scores: dict[str, list[float]] = defaultdict(list)
    split_scores: dict[str, list[float]] = defaultdict(list)
    horizon_scores: dict[str, list[float]] = defaultdict(list)
    for result in results:
        category_scores[result["category"]].append(result["score"]["overall"])
        split_scores[result["split"]].append(result["score"]["overall"])
        call_count = int(result.get("expected_calls", 0))
        horizon = "3+" if call_count >= 3 else str(call_count)
        horizon_scores[horizon].append(result["score"]["overall"])
        for name, score in result["score"]["dimensions"].items():
            dimension_scores[name].append(score)
    return {
        "overall": round(sum(item["score"]["overall"] for item in results) / len(results), 4)
        if results
        else 0.0,
        "case_success_rate": round(sum(item["score"]["success"] for item in results) / len(results), 4)
        if results
        else 0.0,
        "by_category": {
            key: round(sum(values) / len(values), 4) for key, values in sorted(category_scores.items())
        },
        "by_dimension": {
            key: round(sum(values) / len(values), 4) for key, values in sorted(dimension_scores.items())
        },
        "by_split": {
            key: round(sum(values) / len(values), 4) for key, values in sorted(split_scores.items())
        },
        "by_horizon": {
            key: round(sum(values) / len(values), 4)
            for key, values in sorted(horizon_scores.items(), key=lambda item: (item[0] == "3+", item[0]))
        },
        "stop_reasons": dict(
            sorted(CounterLike(result["stop_reason"] for result in results).items())
        ),
    }


def write_run(result: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def CounterLike(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts

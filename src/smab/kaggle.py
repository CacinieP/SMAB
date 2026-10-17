"""Kaggle callable-tools channel; SDK is supplied by the notebook, not imported here.

This is a new channel revision, not a reproduction of the 2026-10-16 leaderboard.
"""
from __future__ import annotations

import inspect
import keyword
import time
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .models import BenchmarkCase, ToolCall
from .runner import RunConfig, aggregate_runs, summarize_results, write_run
from .scoring import score_case
from .simulator import ToolSimulator, tool_result_content

CHANNEL = "kbench-native-v2"
_TYPES = {"string": "str", "integer": "int", "number": "float", "boolean": "bool",
          "array": "list", "object": "dict"}


def build_tool(spec: dict[str, Any], invoke: Callable) -> Callable:
    """Expose catalog fields as a typed Python callable (not full JSON Schema).

    Bind before invoking so omitted optional parameters stay omitted. Never use
    this code generator with an untrusted/unvalidated tool catalog.
    """
    function = spec["function"]
    name = function["name"]
    schema = function["parameters"]
    props = schema.get("properties", {})
    for identifier in [name, *props]:
        if not identifier.isidentifier() or keyword.iskeyword(identifier):
            raise ValueError(f"Invalid Python tool identifier: {identifier!r}")
    required = set(schema.get("required", []))
    if not required.issubset(props):
        raise ValueError("Required parameters must exist in properties")
    ordered = sorted(props, key=lambda key: key not in required)
    params = [f"{key}: {_TYPES.get(props[key].get('type'), 'object')}"
              + ("" if key in required else "=None") for key in ordered]
    namespace: dict[str, Any] = {}
    exec(f"def {name}({', '.join(params)}):\n    pass\n", namespace)
    signature = inspect.signature(namespace[name])

    def tool(*args: Any, **kwargs: Any) -> str:
        bound = signature.bind(*args, **kwargs)
        return invoke(name, dict(bound.arguments))

    tool.__name__ = name
    tool.__signature__ = signature
    tool.__annotations__ = namespace[name].__annotations__
    tool.__doc__ = function.get("description", "") + "\nParameters:\n" + "\n".join(
        f"- {key}: {props[key].get('description', '')}" for key in props)
    return tool


def run_episode(llm: Any, case: BenchmarkCase, chat: Callable[..., AbstractContextManager],
                *, seed: int = 0, repeat_index: int = 1) -> dict[str, Any]:
    simulator = ToolSimulator(case.tool_behaviors, {})
    trace = []
    started = time.perf_counter()

    def invoke(name: str, arguments: dict[str, Any]) -> str:
        # SDK controls rounds; this counter is invocation order, not model turns.
        event = simulator.execute(ToolCall(name=name, arguments=arguments), len(trace) + 1)
        trace.append(event)
        return tool_result_content(event)

    tools = [build_tool(spec, invoke) for spec in case.tools]
    final = None
    stop_reason = "completed"
    with chat(f"smab_r{repeat_index}_{case.id}"):
        try:
            final = llm.prompt(
                RunConfig(model="").system_prompt + "\n\n" + case.prompt,
                tools=tools, seed=seed, temperature=0,
                extra_api_params={"max_tool_rounds": case.max_turns},
            )
        except Exception as exc:
            if type(exc).__name__ != "ToolInvocationLimitExhausted":
                # 429/5xx/auth failures must invalidate the run, never become zero scores.
                raise
            stop_reason = "max_turns"
    if final is not None and not isinstance(final, str):
        raise TypeError("Kaggle prompt() must return text or None")
    return {
        "id": case.id, "category": case.category, "split": case.split,
        "tags": case.tags, "prompt": case.prompt,
        "expected_calls": len(case.expected.get("calls", [])),
        "schema_variant": "original", "trace": [event.to_dict() for event in trace],
        "final_response": final, "stop_reason": stop_reason,
        "score": score_case(case, trace, final, stop_reason),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def run_suite(llm: Any, cases: list[BenchmarkCase], chat: Callable,
              *, model: str, provenance: dict[str, Any], output: str,
              repeats: int = 3, seed: int = 0) -> dict[str, Any]:
    """Run each case once per repeat; derive all metrics from those same traces.

    Persist partial completed cases on failure and re-raise. The failed artifact
    has no aggregate score. Retry the entire suite into a new output file.
    """
    if repeats < 1 or not cases or len({case.id for case in cases}) != len(cases):
        raise ValueError("Need positive repeats and nonempty unique cases")
    if Path(output).exists():
        raise FileExistsError("Use a new output path to preserve prior run evidence")
    runs: list[dict[str, Any]] = []
    artifact: dict[str, Any] = {"state": "running", "channel": CHANNEL,
                                "provenance": provenance, "runs": runs}
    for index in range(1, repeats + 1):
        run: dict[str, Any] = {
            "run": {"model": model, "tool_format": CHANNEL, "schema_variant": "original",
                    "seed": seed, "temperature": 0, "repeat_index": index,
                    "case_count": len(cases), "started_at": datetime.now(timezone.utc).isoformat()},
            "results": [],
        }
        runs.append(run)
        write_run(artifact, output)
        for case in cases:
            try:
                result = run_episode(llm, case, chat, seed=seed, repeat_index=index)
            except Exception as exc:
                artifact.update(state="errored", failed_case=case.id,
                                failed_repeat=index, error_type=type(exc).__name__)
                # Do not persist arbitrary provider exception strings/headers (may contain secrets).
                write_run(artifact, output)
                raise
            run["results"].append(result)
            write_run(artifact, output)
        run["run"]["finished_at"] = datetime.now(timezone.utc).isoformat()
        run["summary"] = summarize_results(run["results"])
    aggregate = aggregate_runs(runs)
    artifact.update(state="completed", suite=aggregate["suite"], summary=aggregate["summary"])
    write_run(artifact, output)
    return artifact

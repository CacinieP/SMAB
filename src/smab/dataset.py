from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .models import BenchmarkCase

VALID_DIMENSIONS = {
    "relevance",
    "selection",
    "arguments",
    "planning",
    "state_tracking",
    "recovery",
    "stopping",
}


class DatasetError(ValueError):
    pass


def load_catalog(path: str | Path) -> dict[str, dict[str, Any]]:
    catalog_path = Path(path)
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetError(f"Cannot read tool catalog {catalog_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise DatasetError("Tool catalog must be a JSON object keyed by tool name")
    for name, tool in data.items():
        function = tool.get("function", {}) if isinstance(tool, dict) else {}
        if tool.get("type") != "function" or function.get("name") != name:
            raise DatasetError(f"Catalog entry {name!r} must be a function tool with the same name")
    return data


def load_cases(
    path: str | Path,
    catalog: dict[str, Any],
    *,
    split: str | None = None,
    categories: set[str] | None = None,
    case_ids: set[str] | None = None,
) -> list[BenchmarkCase]:
    dataset_path = Path(path)
    cases: list[BenchmarkCase] = []
    seen: set[str] = set()
    try:
        lines = dataset_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DatasetError(f"Cannot read dataset {dataset_path}: {exc}") from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetError(f"{dataset_path}:{line_number}: invalid JSON: {exc}") from exc
        _validate_case_dict(data, catalog, dataset_path, line_number)
        if data["id"] in seen:
            raise DatasetError(f"{dataset_path}:{line_number}: duplicate id {data['id']!r}")
        seen.add(data["id"])
        if split and data.get("split", "core") != split:
            continue
        if categories and data["category"] not in categories:
            continue
        if case_ids and data["id"] not in case_ids:
            continue
        cases.append(BenchmarkCase.from_dict(data, catalog))
    if not cases:
        raise DatasetError("No cases matched the selected filters")
    return cases


def dataset_summary(cases: list[BenchmarkCase]) -> dict[str, Any]:
    return {
        "cases": len(cases),
        "categories": dict(sorted(Counter(case.category for case in cases).items())),
        "splits": dict(sorted(Counter(case.split for case in cases).items())),
        "languages": dict(
            sorted(Counter(tag.split(":", 1)[1] for case in cases for tag in case.tags if tag.startswith("lang:")).items())
        ),
    }


def _validate_case_dict(data: Any, catalog: dict[str, Any], path: Path, line_number: int) -> None:
    prefix = f"{path}:{line_number}"
    if not isinstance(data, dict):
        raise DatasetError(f"{prefix}: each line must be a JSON object")
    for field in ("id", "category", "prompt", "tools", "expected", "dimensions"):
        if field not in data:
            raise DatasetError(f"{prefix}: missing required field {field!r}")
    if not isinstance(data["tools"], list) or not all(isinstance(item, str) for item in data["tools"]):
        raise DatasetError(f"{prefix}: tools must be a list of catalog names")
    missing_tools = sorted(set(data["tools"]) - set(catalog))
    if missing_tools:
        raise DatasetError(f"{prefix}: unknown tools: {', '.join(missing_tools)}")
    unknown_dimensions = set(data["dimensions"]) - VALID_DIMENSIONS
    if unknown_dimensions:
        raise DatasetError(f"{prefix}: unknown dimensions: {', '.join(sorted(unknown_dimensions))}")
    behavior_tools = set(data.get("tool_behaviors", {}))
    if not behavior_tools.issubset(set(data["tools"])):
        unknown = ", ".join(sorted(behavior_tools - set(data["tools"])))
        raise DatasetError(f"{prefix}: behaviors defined for unavailable tools: {unknown}")
    expected_calls = data.get("expected", {}).get("calls", [])
    if not isinstance(expected_calls, list):
        raise DatasetError(f"{prefix}: expected.calls must be a list")
    expected_tools = {
        item.get("tool") for item in expected_calls if isinstance(item, dict) and item.get("tool")
    }
    if not expected_tools.issubset(set(data["tools"])):
        unknown = ", ".join(sorted(expected_tools - set(data["tools"])))
        raise DatasetError(f"{prefix}: expected calls unavailable tools: {unknown}")

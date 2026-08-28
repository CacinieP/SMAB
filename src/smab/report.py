from __future__ import annotations

from typing import Any


def render_markdown(run: dict[str, Any]) -> str:
    metadata = run["run"]
    summary = run["summary"]
    lines = [
        "# Small Model Agent Bench Report",
        "",
        f"- Model: `{metadata['model']}`",
        f"- Tool format: `{metadata['tool_format']}`",
        f"- Schema variant: `{metadata['schema_variant']}`",
        f"- Cases: {metadata['case_count']}",
        f"- Overall score: **{summary['overall']:.1%}**",
        f"- Perfect-case rate: **{summary['case_success_rate']:.1%}**",
        "",
        "## Dimension scores",
        "",
        "| Dimension | Score |",
        "|---|---:|",
    ]
    lines.extend(f"| {name} | {score:.1%} |" for name, score in summary["by_dimension"].items())
    lines.extend(
        [
            "",
            "## Generalization and horizon",
            "",
            "| Slice | Score |",
            "|---|---:|",
        ]
    )
    lines.extend(f"| split:{name} | {score:.1%} |" for name, score in summary["by_split"].items())
    lines.extend(f"| expected-calls:{name} | {score:.1%} |" for name, score in summary["by_horizon"].items())
    lines.extend(
        [
            "",
            "## Category scores",
            "",
            "| Category | Score |",
            "|---|---:|",
        ]
    )
    lines.extend(f"| {name} | {score:.1%} |" for name, score in summary["by_category"].items())
    failures = sorted(
        (item for item in run["results"] if not item["score"]["success"]),
        key=lambda item: item["score"]["overall"],
    )
    lines.extend(
        [
            "",
            "## Lowest-scoring cases",
            "",
            "| Case | Category | Score | Stop reason |",
            "|---|---|---:|---|",
        ]
    )
    if failures:
        lines.extend(
            f"| {item['id']} | {item['category']} | {item['score']['overall']:.1%} | {item['stop_reason']} |"
            for item in failures[:10]
        )
    else:
        lines.append("| — | — | — | all cases passed |")
    return "\n".join(lines) + "\n"


def render_console_summary(run: dict[str, Any]) -> str:
    summary = run["summary"]
    dimensions = "  ".join(f"{key}={value:.1%}" for key, value in summary["by_dimension"].items())
    return (
        f"overall={summary['overall']:.1%}  "
        f"perfect_cases={summary['case_success_rate']:.1%}\n{dimensions}"
    )

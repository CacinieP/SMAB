from __future__ import annotations

from typing import Any


def render_markdown(run: dict[str, Any]) -> str:
    if "suite" in run:
        suite = run["suite"]
        summary = run["summary"]
        lines = [
            "# Small Model Agent Bench Repeat Report", "",
            f"- Model: `{suite['model']}`",
            f"- Tool format: `{suite['tool_format']}`",
            f"- Schema variant: `{suite['schema_variant']}`",
            f"- Cases per repeat: {suite['case_count']}",
            f"- Repeats: {suite['repeats']}",
            f"- Overall: **{summary['overall_mean']:.1%} ± {summary['overall_stddev']:.1%}**",
            f"- Perfect-case rate: **{summary['perfect_case_rate_mean']:.1%} ± {summary['perfect_case_rate_stddev']:.1%}**",
            "", "## Individual runs", "",
            "| Repeat | Overall | Perfect-case rate |", "|---:|---:|---:|",
        ]
        lines.extend(
            f"| {item['run']['repeat_index']} | {item['summary']['overall']:.1%} | {item['summary']['case_success_rate']:.1%} |"
            for item in run["runs"]
        )
        return "\n".join(lines) + "\n"
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
    if "suite" in run:
        summary = run["summary"]
        return (
            f"overall_mean={summary['overall_mean']:.1%}  overall_stddev={summary['overall_stddev']:.1%}\n"
            f"perfect_case_rate_mean={summary['perfect_case_rate_mean']:.1%}  "
            f"perfect_case_rate_stddev={summary['perfect_case_rate_stddev']:.1%}"
        )
    summary = run["summary"]
    dimensions = "  ".join(f"{key}={value:.1%}" for key, value in summary["by_dimension"].items())
    return (
        f"overall={summary['overall']:.1%}  "
        f"perfect_cases={summary['case_success_rate']:.1%}\n{dimensions}"
    )

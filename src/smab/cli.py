from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .adapters import OpenAICompatibleAdapter
from .dataset import DatasetError, dataset_summary, load_cases, load_catalog
from .report import render_console_summary, render_markdown
from .runner import BenchmarkRunner, RunConfig, write_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smab",
        description="Measure where small tool-using models fail as task entropy rises.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate dataset and print its composition")
    _add_dataset_arguments(validate)

    run = subparsers.add_parser("run", help="Run cases against an OpenAI-compatible endpoint")
    _add_dataset_arguments(run)
    run.add_argument("--model", required=True, help="Model id exposed by the endpoint")
    run.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    run.add_argument("--api-key-env", default="SMAB_API_KEY")
    run.add_argument("--tool-format", choices=("native", "json"), default="native")
    run.add_argument("--schema-variant", choices=("original", "shuffled", "aliased"), default="original")
    run.add_argument("--temperature", type=float, default=0.0)
    run.add_argument("--max-tokens", type=int, default=512)
    run.add_argument("--timeout", type=float, default=120.0)
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--extra-body", help="JSON object merged into each endpoint request")
    run.add_argument("--output", default="runs/latest.json")
    run.add_argument("--report", help="Optional Markdown report path")

    report = subparsers.add_parser("report", help="Render a Markdown report from a JSON run")
    report.add_argument("run_file")
    report.add_argument("--output")
    return parser


def _add_dataset_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dataset", default="datasets/core.jsonl")
    parser.add_argument("--tools", default="datasets/tools.json")
    parser.add_argument("--split")
    parser.add_argument("--category", action="append", dest="categories")
    parser.add_argument("--case-id", action="append", dest="case_ids")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "report":
            return _report(args)
        catalog = load_catalog(args.tools)
        cases = load_cases(
            args.dataset,
            catalog,
            split=args.split,
            categories=set(args.categories) if args.categories else None,
            case_ids=set(args.case_ids) if args.case_ids else None,
        )
        if args.command == "validate":
            print(json.dumps(dataset_summary(cases), ensure_ascii=False, indent=2))
            return 0
        return _run(args, cases)
    except (DatasetError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _run(args: argparse.Namespace, cases: list[Any]) -> int:
    extra_body = json.loads(args.extra_body) if args.extra_body else None
    api_key = os.environ.get(args.api_key_env)
    adapter = OpenAICompatibleAdapter(
        base_url=args.base_url,
        model=args.model,
        api_key=api_key,
        tool_format=args.tool_format,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
        extra_body=extra_body,
    )
    config = RunConfig(
        model=args.model,
        tool_format=args.tool_format,
        schema_variant=args.schema_variant,
        seed=args.seed,
    )
    result = BenchmarkRunner(adapter, config).run(cases)
    write_run(result, args.output)
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_markdown(result), encoding="utf-8")
    print(render_console_summary(result))
    print(f"run_file={args.output}")
    if args.report:
        print(f"report_file={args.report}")
    return 0


def _report(args: argparse.Namespace) -> int:
    run = json.loads(Path(args.run_file).read_text(encoding="utf-8"))
    report = render_markdown(run)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        print(f"report_file={output}")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

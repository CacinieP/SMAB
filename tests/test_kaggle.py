import importlib.util
import json
import logging
from contextlib import nullcontext
from pathlib import Path

import pytest

from smab.dataset import load_cases, load_catalog
from smab.kaggle import ProxyResponseError, build_tool, run_episode, run_suite
from test_bundled_episodes import _materialize, ExpectedTraceAdapter
from smab.runner import BenchmarkRunner, RunConfig

ROOT = Path(__file__).parents[1]
CASES = load_cases(ROOT / "datasets/core.jsonl", load_catalog(ROOT / "datasets/tools.json"))


class OracleLLM:
    def __init__(self, case):
        self.case = case

    def prompt(self, message, *, tools, seed, temperature, extra_api_params):
        by_name = {tool.__name__: tool for tool in tools}
        for call in self.case.expected.get("calls", []):
            by_name[call["tool"]](**_materialize(call.get("arguments", {})))
        return "completed " + " ".join(
            map(str, self.case.expected.get("final_contains", []))) + " " + " ".join(
            str(group[0] if isinstance(group, list) else group)
            for group in self.case.expected.get("final_contains_any", [])[:1])


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_oracle_scoring_matches_repository_harness(case):
    actual = run_episode(OracleLLM(case), case, lambda _: nullcontext())
    reference = BenchmarkRunner(ExpectedTraceAdapter(case), RunConfig(model="oracle")).run_case(case)
    assert actual["score"] == reference["score"]
    assert [e["arguments"] for e in actual["trace"]] == [e["arguments"] for e in reference["trace"]]


def test_optional_arguments_remain_omitted_and_extras_are_rejected():
    spec = load_catalog(ROOT / "datasets/tools.json")["search_products"]
    calls = []
    tool = build_tool(spec, lambda name, args: calls.append(args))
    tool(query="pen")
    tool(query="pen", limit=None)
    assert calls == [{"query": "pen"}, {"query": "pen", "limit": None}]
    with pytest.raises(TypeError):
        tool(query="pen", unexpected=True)
    assert len(calls) == 2


def test_api_failure_is_not_scored_and_partial_trace_is_saved(tmp_path):
    class Broken:
        def prompt(self, *args, **kwargs):
            raise RuntimeError("429 secret-provider-text")
    output = tmp_path / "failure.json"
    with pytest.raises(RuntimeError):
        run_suite(Broken(), CASES, lambda _: nullcontext(), model="fake", provenance={}, output=output)
    data = json.loads(output.read_text())
    assert data["state"] == "errored"
    assert data["failed_case"] == CASES[0].id
    assert "summary" not in data
    assert "secret-provider-text" not in output.read_text()


def test_interrupted_suite_is_marked_and_completed_cases_are_saved(tmp_path):
    case = CASES[0]

    class Interrupted(OracleLLM):
        def __init__(self):
            super().__init__(case)
            self.calls = 0

        def prompt(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 2:
                raise KeyboardInterrupt("private interruption text")
            return super().prompt(*args, **kwargs)

    output = tmp_path / "interrupted.json"
    with pytest.raises(KeyboardInterrupt):
        run_suite(Interrupted(), [case], lambda _: nullcontext(), model="fake",
                  provenance={}, output=output, repeats=3)
    data = json.loads(output.read_text())
    assert data["state"] == "interrupted"
    assert data["failed_case"] == case.id
    assert data["failed_repeat"] == 2
    assert data["error_type"] == "KeyboardInterrupt"
    assert len(data["runs"][0]["results"]) == 1
    assert data["runs"][0]["results"][0]["score"]["success"]
    assert data["runs"][1]["results"] == []
    assert "summary" not in data
    assert "private interruption text" not in output.read_text()


def test_reliability_uses_same_repeated_case_results(tmp_path):
    case = CASES[0]
    data = run_suite(OracleLLM(case), [case], lambda _: nullcontext(), model="oracle",
                     provenance={}, output=tmp_path / "runs.json", repeats=3)
    assert data["state"] == "completed"
    assert data["summary"]["pass_at_k"] == {"1": 1, "2": 1, "3": 1}
    assert len(data["runs"]) == 3


def test_existing_evidence_cannot_be_overwritten(tmp_path):
    output = tmp_path / "previous.json"
    output.write_text("previous evidence")
    with pytest.raises(FileExistsError):
        run_suite(OracleLLM(CASES[0]), CASES[:1], lambda _: nullcontext(),
                  model="oracle", provenance={}, output=output)
    assert output.read_text() == "previous evidence"


def test_proxy_missing_message_warning_invalidates_suite(tmp_path):
    logger = logging.getLogger("kaggle_benchmarks.actors.proxy_openai")
    handlers = list(logger.handlers)

    class Malformed:
        def prompt(self, *args, **kwargs):
            logger.warning("Model Proxy returned choices[0].message=None for model fake; treating as empty response.")
            return ""

    output = tmp_path / "malformed.json"
    with pytest.raises(ProxyResponseError):
        run_suite(Malformed(), CASES[:1], lambda _: nullcontext(),
                  model="fake", provenance={}, output=output)
    artifact = json.loads(output.read_text())
    assert artifact["state"] == "errored"
    assert artifact["error_type"] == "ProxyResponseError"
    assert "summary" not in artifact
    assert logger.handlers == handlers


def test_round_limit_is_a_model_outcome_but_other_errors_propagate():
    class ToolInvocationLimitExhausted(Exception):
        pass

    class Limited:
        def prompt(self, *args, **kwargs):
            raise ToolInvocationLimitExhausted()

    result = run_episode(Limited(), CASES[0], lambda _: nullcontext())
    assert result["stop_reason"] == "max_turns"
    assert not result["score"]["success"]


def test_exported_notebook_is_self_contained_and_compiles():
    spec = importlib.util.spec_from_file_location("export_kaggle", ROOT / "scripts/export_kaggle_notebook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    notebook = module.build_notebook("test/model")
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), "notebook", "exec")
    setup = "".join(notebook["cells"][1]["source"])
    assert "datasets/core.jsonl" in setup
    assert "sha256" in setup
    assert "test/model" in setup

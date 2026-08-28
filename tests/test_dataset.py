from pathlib import Path

import pytest

from smab.dataset import DatasetError, dataset_summary, load_cases, load_catalog


ROOT = Path(__file__).parents[1]


def test_bundled_dataset_is_valid_and_balanced() -> None:
    catalog = load_catalog(ROOT / "datasets/tools.json")
    cases = load_cases(ROOT / "datasets/core.jsonl", catalog)
    summary = dataset_summary(cases)

    assert summary["cases"] == 28
    assert set(summary["categories"]) == {
        "relevance",
        "selection",
        "arguments",
        "planning",
        "state_tracking",
        "recovery",
        "stopping",
    }
    assert summary["splits"] == {"core": 17, "ood": 11}
    assert summary["languages"] == {"en": 10, "zh": 18}


def test_filters_are_applied() -> None:
    catalog = load_catalog(ROOT / "datasets/tools.json")
    cases = load_cases(ROOT / "datasets/core.jsonl", catalog, split="ood", categories={"recovery"})
    assert {case.id for case in cases} == {"recover_002", "recover_004"}


def test_unknown_tool_is_rejected(tmp_path: Path) -> None:
    dataset = tmp_path / "bad.jsonl"
    dataset.write_text(
        '{"id":"x","category":"selection","prompt":"x","tools":["missing"],'
        '"expected":{},"dimensions":["selection"]}\n',
        encoding="utf-8",
    )
    with pytest.raises(DatasetError, match="unknown tools"):
        load_cases(dataset, {})

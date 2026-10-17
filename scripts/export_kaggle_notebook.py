"""Build an offline, self-contained Kaggle notebook from this checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_notebook(model: str, repeats: int = 3) -> dict:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    paths = sorted((ROOT / "src/smab").glob("*.py")) + [
        ROOT / "datasets/core.jsonl", ROOT / "datasets/tools.json"]
    bundled = {str(path.relative_to(ROOT)): path.read_text(encoding="utf-8") for path in paths}
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    provenance = {"source_commit": commit, "model": model,
                  "sha256": {name: hashlib.sha256(content.encode()).hexdigest()
                             for name, content in bundled.items()}}
    setup = '''import json, sys, tempfile
from pathlib import Path
import importlib.metadata
import kaggle_benchmarks as kbench
bundle = Path(tempfile.mkdtemp(prefix="smab-"))
'''
    setup += f"files = {bundled!r}\n"
    setup += '''for name, content in files.items():
    path = bundle / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
sys.path.insert(0, str(bundle / "src"))
if "smab" in sys.modules:
    raise RuntimeError("Restart the notebook kernel to load the bundled SMAB sources")
from smab.dataset import load_cases, load_catalog
from smab.kaggle import run_suite
cases = load_cases(bundle / "datasets/core.jsonl", load_catalog(bundle / "datasets/tools.json"))
'''
    setup += f"PROVENANCE = {provenance!r}\nMODEL = {model!r}\nREPEATS = {repeats}\n"
    setup += '''PROVENANCE["kaggle_benchmarks_version"] = importlib.metadata.version("kaggle-benchmarks")
'''
    task = '''import uuid

@kbench.task(
    name="smab_perfect_case_rate_v2",
    description="SMAB kbench-native-v2: repeated 28-episode perfect-case rate; not the legacy composite score.",
)
def smab_perfect_case_rate_v2(llm) -> float:
    output = f"/kaggle/working/smab-repeated-{uuid.uuid4().hex}.json"
    artifact = run_suite(llm, cases, kbench.chats.new, model=MODEL,
                         provenance=PROVENANCE, repeats=REPEATS,
                         output=output)
    print("Full trace artifact:", output)
    print(json.dumps(artifact["summary"], indent=2))
    return artifact["summary"]["perfect_case_rate_mean"]
'''
    cells = [
        {"cell_type": "markdown", "id": "smab-introduction", "metadata": {}, "source": [
            "# SMAB kbench-native-v2\n",
            "New channel revision; do not overwrite/compare directly with legacy v1 scores.\n",
            "Select the exact model in Kaggle matching MODEL before running. MODEL is a recorded label, not a proxy selector.\n",
            "All dimensions, partial-credit overall, perfect-case rate and pass^k use the same repeated traces.\n",
            "Source/data hashes are bundled; no GitHub access or pip installation is needed.\n"]},
    ]
    for cell_id, source in [
        ("smab-setup", setup), ("smab-task", task),
        ("smab-run", "smab_perfect_case_rate_v2.run(llm=kbench.llm)\n"),
    ]:
        cells.append({"cell_type": "code", "id": cell_id, "metadata": {}, "execution_count": None,
                      "outputs": [], "source": source.splitlines(keepends=True)})
    return {"nbformat": 4, "nbformat_minor": 5,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "cells": cells}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Exact model identifier selected in Kaggle")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_notebook(args.model, args.repeats), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

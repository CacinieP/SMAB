#!/usr/bin/env python3
"""Verify public bundle hashes and internal consistency; no inference/test rerun.

This cannot independently prove the private model transcript or rerun an agent
whose baseline prompt/Skill are withheld. Source hashes bind the local export.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST_PREFIX = "/" + "Users" + "/"
DENIED = {"messages", "system_instruction", "system_prompt", "instruction", "stdout", "stderr", "env",
          "steps", "hints_text", "test_patch", "gold_patch", "raw_response", "raw_request"}


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def privacy(value):
    if isinstance(value, dict):
        assert not DENIED.intersection(value), "Forbidden raw/private key"
        for item in value.values(): privacy(item)
    elif isinstance(value, list):
        for item in value: privacy(item)
    elif isinstance(value, str):
        assert HOST_PREFIX not in value, "Host path"


def close(left, right):
    if left is None or right is None: return left is right
    return abs(left - right) <= 1e-6 * max(1, abs(left), abs(right))


def main():
    index = load("artifact-index.json")
    expected = index["files"]
    actual = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and p.name != "artifact-index.json"}
    assert actual == set(expected), "Unindexed or missing artifact"
    for name, record in expected.items():
        path = ROOT / name
        assert not path.is_symlink() and path.stat().st_size == record["bytes"]
        assert digest(path) == record["sha256"], name
        assert HOST_PREFIX.encode() not in path.read_bytes(), "Host path in artifact"
        if path.suffix == ".json": privacy(load(name))
    metadata, results = load("study.json"), load("results.json")
    verification = load("verification.json")
    assert metadata["distinct_tasks"] == 7 and metadata["primary_attempts"] == 14
    assert metadata["official_competition_score"] is False
    assert metadata["policy"]["smab_policy_sha256"] == "114c2efea5361813cea2caf426e32ef6f6c4711a5954bfa602fb791208e5cc3e"
    assert metadata["frozen_integrity"]["drift_count"] == 0
    assert metadata["frozen_integrity"]["checked_file_count"] == 73
    assert metadata["only_between_arm_asset_difference"] == ["prompts/system.md"]
    tasks = {task["instance_id"]: task for task in load("tasks.json")["tasks"]}
    assert len(tasks) == 7
    for task in tasks.values():
        assert task["qualified"] is True
        assert all(task["checks"][key] is True for key in ("baseline_all_F2P_fail", "baseline_all_P2P_pass", "gold_all_F2P_and_P2P_pass"))
        stages = task["selected_preflight_outcomes"]
        for stage in stages.values():
            for group in ("FAIL_TO_PASS", "PASS_TO_PASS"):
                assert stage[group]["required"] > 0
                assert sum(stage[group]["status_counts"].values()) == stage[group]["required"]
        assert stages["baseline"]["FAIL_TO_PASS"]["passed"] == 0
        assert stages["baseline"]["PASS_TO_PASS"]["passed"] == stages["baseline"]["PASS_TO_PASS"]["required"]
        assert all(stages["gold"][group]["passed"] == stages["gold"][group]["required"] for group in ("FAIL_TO_PASS", "PASS_TO_PASS"))
    trials = [load(name) for name in results["trial_artifacts"]]
    assert len(trials) == 14
    assert len({trial["trial"] for trial in trials}) == 14
    slots = Counter((trial["instance_id"], trial["arm"]) for trial in trials)
    assert set(slots) == {(task, arm) for task in tasks for arm in ("baseline", "optimized")}
    assert all(count == 1 for count in slots.values())
    wins = losses = both_pass = both_fail = 0
    successes = Counter()
    observed_pairs = {}
    length_by_trial = {}
    for trial in trials:
        task = tasks[trial["instance_id"]]
        assert trial["seed"] == 0 and trial["state"] == "graded"
        assert trial["snapshot_sha256"] == task["source_snapshot_sha256"]
        assert all(value is not False for value in trial["invariant_checks"].values())
        assert trial["generation"] == {"max_output_tokens": 2048, "temperature": 0, "seed": 0, "think": False, "num_ctx": 32768}
        assert trial["budget"] == {"model_turns": 48, "official_counted_tools": 40, "agent_seconds": 300, "command_seconds": 60, "outer_seconds": 450}
        counts = trial["counts"]
        assert counts["llm_calls"] <= 48 and counts["official_counted_tools"] <= 40
        grade = load(trial["grade_artifact"])
        assert trial["patch_sha256"] == grade["candidate_patch_sha256"]
        if trial["patch_published"]:
            patch = ROOT / trial["patch_artifact"]
            assert digest(patch) == trial["patch_sha256"] and patch.stat().st_size == trial["patch_bytes"]
            nonempty = bool(patch.read_bytes().strip())
            assert nonempty == trial["nonempty_patch"]
        else:
            assert trial["patch_artifact"] is None and trial["patch_withheld_reason"]
            nonempty = trial["nonempty_patch"]
        assert grade["base_commit"] == task["base_commit"]
        assert grade["gold_patch_sha256"] == task["gold_patch_sha256"]
        assert grade["test_patch_sha256"] == task["test_patch_sha256"]
        for group, outcomes in grade["test_outcomes"].items():
            selected = grade["selected_node_counts"][group]
            assert selected["required"] == len(outcomes)
            assert selected["passed"] == sum(value == "passed" for value in outcomes.values())
            assert selected["status_counts"] == dict(Counter(outcomes.values()))
        if grade["status"] == "graded":
            fixed = {group: sorted(grade["test_outcomes"][group]) for group in ("FAIL_TO_PASS", "PASS_TO_PASS")}
            assert hashlib.sha256(json.dumps(fixed, sort_keys=True).encode()).hexdigest() == task["expanded_fixed_nodes_sha256"]
            assert {group: len(nodes) for group, nodes in fixed.items()} == task["expanded_fixed_node_counts"]
        if grade["resolved"]:
            assert grade["status"] == "graded" and grade["test_process_exit_code"] == 0
            assert grade["actual_import_from_candidate_snapshot"] is True
            assert grade["collection_error_count"] == 0
            assert all(value == "passed" for values in grade["test_outcomes"].values() for value in values.values())
        expected_resolved = bool(grade["resolved"] and nonempty and not trial["outer_deadline_exceeded"])
        assert trial["resolved"] is expected_resolved
        successes[trial["arm"]] += trial["resolved"]
        observed_pairs.setdefault(trial["instance_id"], {})[trial["arm"]] = trial
        calls = trial["provider_calls"]
        responses = [call for call in calls if call["status"] == "model_response"]
        assert responses and len(responses) == trial["api_usage"]["model_response_count"]
        length_by_trial[trial["trial"]] = sum(call.get("done_reason") == "length" for call in responses)
        assert length_by_trial[trial["trial"]] == trial["api_usage"]["length_response_count"]
        assert len(calls) == trial["api_usage"]["request_count"]
        for call in calls:
            assert call["model"] == "gemma4:e4b" and call["think"] is False and call["stream"] is False
            assert call["options"] == {"num_predict": 2048, "temperature": 0, "seed": 0, "num_ctx": 32768}
        for field in ("eval_count", "prompt_eval_count"):
            values = [call["usage"][field] for call in responses if call["usage"].get(field) is not None]
            assert close(sum(values) if values else None, trial["api_usage"][field])
        for field in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
            values = [call["usage"][field] / 1e9 for call in responses if call["usage"].get(field) is not None]
            assert close(sum(values) if values else None, trial["api_usage"]["provider_" + field + "_seconds"])
        assert close(sum(call["api_wall_seconds"] or 0 for call in calls), trial["api_usage"]["api_observed_wall_seconds"])
    for pair in observed_pairs.values():
        a, b = pair["baseline"], pair["optimized"]
        assert a["snapshot_sha256"] == b["snapshot_sha256"] and a["python_version"] == b["python_version"]
        if a["resolved"] and b["resolved"]: both_pass += 1
        elif b["resolved"]: wins += 1
        elif a["resolved"]: losses += 1
        else: both_fail += 1
    expected_pair = {"B_wins": wins, "B_losses": losses, "both_pass": both_pass, "both_fail": both_fail, "ties": both_pass + both_fail}
    assert results["paired"] == expected_pair
    assert results["length_endings"]["by_trial"] == length_by_trial
    assert results["length_endings"]["total"] == sum(length_by_trial.values())
    assert verification["length_response_count"] == sum(length_by_trial.values())
    assert verification["primary_trials"] == 14 and verification["paired_tasks"] == 7
    assert verification["frozen_hashes_match"] == 73
    assert verification["valid_model_responses"] == sum(trial["api_usage"]["model_response_count"] for trial in trials)
    assert verification["actual_nonempty_thinking_messages"] == 0 and verification["raw_api_errors_primary"] == 0
    assert verification["all_profile_and_prompt_delivery_match"] is True
    assert len(verification["checks"]) == 14
    assert all(check["full_frozen_prompt_delivered_every_request"] and check["skill_tools_advertised"] for check in verification["checks"])
    assert results["resolved_by_arm"] == {arm: successes[arm] for arm in ("baseline", "optimized")}
    for arm in ("baseline", "optimized"):
        group = [trial for trial in trials if trial["arm"] == arm]
        assert results["patch_kinds_by_arm"][arm] == dict(Counter(trial["patch_kind"] for trial in group))
        sums = {"total_prompt_eval_count": sum(trial["api_usage"]["prompt_eval_count"] for trial in group),
                "total_eval_count": sum(trial["api_usage"]["eval_count"] for trial in group),
                "total_llm_calls": sum(trial["counts"]["llm_calls"] for trial in group),
                "total_official_counted_tools": sum(trial["counts"]["official_counted_tools"] for trial in group)}
        assert all(results["cost_by_arm"][arm][key] == value for key, value in sums.items())
        assert close(results["cost_by_arm"][arm]["mean_process_wall_seconds_valid"],
                     sum(trial["wall_seconds"]["wall_process_seconds"] for trial in group) / len(group))
    notices = load("notices/index.json")["upstream_licenses"]
    assert {notice["repo"] for notice in notices} == {"pallets/flask", "pytest-dev/pytest"}
    assert {notice["instance_id"] for notice in notices} == set(tasks)
    for notice in notices:
        assert digest(ROOT / notice["license_artifact"]) == notice["license_sha256"]
        assert notice["source_url"].startswith("https://github.com/" + notice["repo"] + "/blob/" + notice["base_commit"] + "/")
    print(json.dumps({"status": "PASS", "artifacts": len(expected), "tasks": 7, "primary_runs": 14,
                      "resolved_by_arm": results["resolved_by_arm"], "paired": expected_pair,
                      "verification": "hashes and declared-result consistency only; no model/test rerun"}, indent=2))


if __name__ == "__main__":
    main()

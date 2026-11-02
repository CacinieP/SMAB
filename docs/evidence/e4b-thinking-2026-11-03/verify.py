#!/usr/bin/env python3
"""Check filtered evidence consistency/hashes only; no model or test rerun."""
from collections import Counter
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
HOST="/"+"Users"+"/"
DENIED={"messages","message","system_instruction","system_prompt","instruction","stdout","stderr","env","steps",
        "thinking_text","thinking_content","raw_thinking","raw_request","raw_response","hints_text","gold_patch","test_patch"}
def load(name):return json.loads((ROOT/name).read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def privacy(value):
    if isinstance(value,dict):
        assert not DENIED.intersection(value)
        if "thinking" in value:assert value["thinking"] in {"off","on"}
        for item in value.values():privacy(item)
    elif isinstance(value,list):
        for item in value:privacy(item)
    elif isinstance(value,str):assert HOST not in value
def close(a,b):return a is b if a is None or b is None else abs(a-b)<=1e-6*max(1,abs(a),abs(b))
def main():
    index=load("artifact-index.json")
    files={p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and p.name!="artifact-index.json"}
    assert files==set(index["files"])
    for name,item in index["files"].items():
        path=ROOT/name;assert not path.is_symlink() and sha(path)==item["sha256"] and path.stat().st_size==item["bytes"]
        assert HOST.encode() not in path.read_bytes()
        if path.suffix==".json":privacy(load(name))
    study,results=load("study.json"),load("results.json")
    assert study["distinct_tasks"]==3 and study["primary_attempts"]==6 and study["old_task_development_diagnostic"] is True
    assert study["official_competition_score"] is False
    assert study["no_lora"] is True
    assert study["model_parameters"]=={"temperature":0,"seed":0,"num_predict":2048,"num_ctx":32768}
    assert study["budgets"]=={"agent_seconds":300,"logical_model_calls":48,"official_counted_tools":40,"command_timeout_seconds":60,"outer_trial_seconds":450}
    assert study["prompt_A_sha256"]=="35bec37d93e0e05be7f1e62b925ffdd7d039201d7d7a5a0de6647f9386b04f69"
    assert study["only_intervention"]=="effective native think boolean"
    integrity=study["frozen_integrity"]
    assert integrity["new_file_count"]==44 and integrity["old_file_count"]==73 and integrity["new_drift_count"]==integrity["old_drift_count"]==0
    assert study["environment"]["same_current_root_service"] is True
    assert study["environment"]["mode_contract_passed"] is True
    software=study["environment"]["software_versions"]
    assert software["driver_python"]=="3.12.13" and software["all_six_manifest_driver_versions_match"] is True
    assert software["packages"]=={"swegemma":"0.2.11","adk-submission":"0.2.13","adk-eval-core":"0.1.0","google-adk":"1.36.1","google-genai":"2.11.0"}
    assert study["environment"]["no_thinking_history_compatibility"]["checks"]["ready7"] is True
    assert study["environment"]["no_thinking_history_compatibility"]["checks"]["unwanted_repeated_tool_call"] is False
    tasks={task["instance_id"]:task for task in load("tasks.json")["tasks"]};assert len(tasks)==3
    for task in tasks.values():
        assert task["qualified"] and all(task["checks"][key] for key in ("baseline_all_F2P_fail","baseline_all_P2P_pass","gold_all_F2P_and_P2P_pass"))
    trials=[load(name) for name in results["trial_artifacts"]];assert len(trials)==6
    slots=Counter((trial["instance_id"],trial["thinking"]) for trial in trials)
    assert set(slots)=={(task,mode) for task in tasks for mode in ("off","on")} and all(value==1 for value in slots.values())
    success=Counter();pairs={};length=Counter();thought=Counter();chars=Counter()
    for trial in trials:
        task=tasks[trial["instance_id"]];mode=trial["thinking"]
        assert trial["seed"]==0 and trial["state"]=="graded" and not trial["invariant_violations"]
        assert all(value is not False for value in trial["invariant_checks"].values())
        assert trial["source_binding"]["snapshot_sha256"]==task["source_snapshot_sha256"]
        grade=load(trial["grade_artifact"])
        assert grade["candidate_patch_sha256"]==trial["patch_sha256"]
        if trial["patch_published"]:
            patch=ROOT/trial["patch_artifact"];assert sha(patch)==trial["patch_sha256"] and patch.stat().st_size==trial["patch_bytes"]
            assert bool(patch.read_bytes().strip())==trial["nonempty_patch"]
        else:assert trial["patch_artifact"] is None and trial["patch_withheld_reason"]
        assert grade["base_commit"]==task["base_commit"]
        assert grade["gold_patch_sha256"]==task["gold_patch_sha256"] and grade["test_patch_sha256"]==task["test_patch_sha256"]
        if grade["status"]=="graded":
            fixed={group:sorted(grade["test_outcomes"][group]) for group in ("FAIL_TO_PASS","PASS_TO_PASS")}
            assert hashlib.sha256(json.dumps(fixed,sort_keys=True).encode()).hexdigest()==task["expanded_fixed_nodes_sha256"]
        for group,outcomes in grade["test_outcomes"].items():
            count=grade["selected_node_counts"][group]
            assert count["required"]==len(outcomes) and count["passed"]==sum(value=="passed" for value in outcomes.values())
            assert count["status_counts"]==dict(Counter(outcomes.values()))
        if grade["resolved"]:
            assert grade["actual_import_from_candidate_snapshot"] is True and grade["collection_error_count"]==0 and grade["test_process_exit_code"]==0
            assert all(value=="passed" for group in grade["test_outcomes"].values() for value in group.values())
        assert trial["resolved"]==bool(grade["resolved"] and trial["nonempty_patch"] and not trial["outer_deadline_exceeded"])
        assert trial["counts"]["llm_calls"]<=48 and trial["counts"]["harness_counted_tool_calls"]<=40
        calls=trial["api"]["calls"];responses=[call for call in calls if call["status"]=="model_response"]
        assert responses and len(responses)==trial["api"]["model_response_count"] and len(calls)==trial["api"]["request_count"]
        assert trial["api"]["error_count"]==0
        for call in calls:
            assert call["effective_think"] is (mode=="on") and call["model"]=="gemma4:e4b"
            assert call["options"]=={"temperature":0,"seed":0,"num_predict":2048,"num_ctx":32768}
        for field in ("eval_count","prompt_eval_count"):
            values=[call["usage"][field] for call in responses if call["usage"].get(field) is not None]
            assert close(sum(values) if values else None,trial["api"][field])
        values=[call["usage"].get("thinking_eval_count") for call in responses if call["usage"].get("thinking_eval_count") is not None]
        assert close(sum(values) if values else None,trial["api"]["provider_thinking_eval_count"])
        for field,target in (("total_duration","provider_total_seconds"),("load_duration","provider_load_seconds"),("prompt_eval_duration","provider_prompt_eval_seconds"),("eval_duration","provider_eval_seconds")):
            values=[call["usage"][field]/1e9 for call in responses if call["usage"].get(field) is not None]
            assert close(sum(values) if values else None,trial["api"][target])
        assert close(sum(call.get("api_wall_seconds") or 0 for call in calls),trial["api"]["api_wall_seconds"])
        assert sum(bool(call["thinking_present"]) for call in responses)==trial["api"]["thinking_response_count"]
        assert sum(call["thinking_characters"] or 0 for call in responses)==trial["api"]["thinking_characters"]
        assert dict(Counter(call["done_reason"] for call in responses if call.get("done_reason")))==trial["api"]["done_reasons"]
        assert sum(call.get("done_reason")=="length" for call in responses)==trial["api"]["length_response_count"]
        length[mode]+=trial["api"]["length_response_count"];thought[mode]+=trial["api"]["thinking_response_count"];chars[mode]+=trial["api"]["thinking_characters"]
        success[mode]+=trial["resolved"];pairs.setdefault(trial["instance_id"],{})[mode]=trial
    count=Counter({"on_wins":0,"on_losses":0,"both_pass":0,"both_fail":0})
    for pair in pairs.values():
        off,on=pair["off"],pair["on"]
        assert off["source_binding"]==on["source_binding"]
        key="both_pass" if off["resolved"] and on["resolved"] else "on_wins" if on["resolved"] else "on_losses" if off["resolved"] else "both_fail"
        count[key]+=1
    count["ties"]=count["both_pass"]+count["both_fail"]
    assert results["paired"]==dict(count)
    assert results["successes_by_mode"]=={mode:success[mode] for mode in ("off","on")}
    assert results["length_by_mode"]=={mode:length[mode] for mode in ("off","on")}
    assert results["thinking_responses_by_mode"]=={mode:thought[mode] for mode in ("off","on")}
    assert results["thinking_characters_by_mode"]=={mode:chars[mode] for mode in ("off","on")}
    notices=load("notices/index.json")["upstream_licenses"]
    assert {notice["instance_id"] for notice in notices}==set(tasks)
    assert {notice["repo"] for notice in notices}=={"pallets/flask","pytest-dev/pytest"}
    for notice in notices:assert sha(ROOT/notice["license_artifact"])==notice["license_sha256"]
    print(json.dumps({"status":"PASS","indexed_artifacts":len(files),"distinct_tasks":3,"primary_runs":6,
                      "successes_by_mode":results["successes_by_mode"],"paired":dict(count),
                      "verification":"hashes and declared-result consistency; no model/test rerun"},indent=2))
if __name__=="__main__":main()

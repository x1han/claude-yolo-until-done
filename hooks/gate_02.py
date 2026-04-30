from __future__ import annotations

from pathlib import Path

from common import (
    add_check,
    base_report,
    gate_map,
    load_run_bundle,
    report_text,
    stage_id,
    validate_required_run_files,
)


def run(run_root: Path) -> dict:
    report = base_report(stage=2, run_root=run_root)
    if not validate_required_run_files(report, run_root):
        return report

    bundle = load_run_bundle(run_root)
    run_state = bundle["run_state"]
    gates = gate_map(bundle["gates"])

    current_stage = run_state.get("current_stage")
    next_action = str(run_state.get("next_action", "")).strip()
    verification_target = str(run_state.get("verification_target", "")).strip()
    completion_gate = run_state.get("completion_gate")

    add_check(report, "current_stage_present", bool(current_stage), f"current_stage={current_stage}")
    add_check(report, "next_action_present", bool(next_action), f"next_action={next_action}")
    add_check(report, "verification_target_present", bool(verification_target), f"verification_target={verification_target}")
    add_check(report, "completion_gate_declared", completion_gate in gates, f"completion_gate={completion_gate}")
    add_check(report, "current_stage_has_gate_entry", current_stage in gates, f"current_stage={current_stage}")
    add_check(report, "current_stage_not_already_passed", not gates.get(current_stage, {}).get("passed", False), f"gate={gates.get(current_stage, {})}")
    add_check(report, "plan_path_exists", Path(run_state.get("plan_path", "")).exists(), f"plan_path={run_state.get('plan_path')}")
    add_check(report, "resume_mentions_next_action", next_action in report_text(run_root / "resume.md"), f"next_action={next_action}")
    add_check(report, "stage_name_shape", current_stage == stage_id(int(current_stage.split("-")[-1])) if isinstance(current_stage, str) and current_stage.startswith("stage-") else False, f"current_stage={current_stage}")
    return report

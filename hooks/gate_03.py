from __future__ import annotations

from common import add_check, base_report, load_run_bundle, report_text, validate_required_run_files


def run(run_root):
    report = base_report(stage=3, run_root=run_root)
    if not validate_required_run_files(report, run_root):
        return report

    bundle = load_run_bundle(run_root)
    run_state = bundle["run_state"]
    current_stage = run_state.get("current_stage")
    report_body = report_text(run_root / "report.md")
    repair_summary = str(run_state.get("repair_summary", "")).strip()
    verification_commands = run_state.get("verification_commands", [])
    before_status = str(run_state.get("verification_before_status", "")).strip()
    after_status = str(run_state.get("verification_after_status", "")).strip()
    verification_passed = run_state.get("verification_passed") is True
    evidence_updated_at = str(run_state.get("verification_evidence_updated_at", "")).strip()

    add_check(report, "current_stage_is_stage_03", current_stage == "stage-03", f"current_stage={current_stage}")
    add_check(report, "verification_target_present", bool(str(run_state.get("verification_target", "")).strip()), f"verification_target={run_state.get('verification_target')}")
    add_check(report, "report_mentions_verification_section", "## Verification" in report_body, f"report_path={run_root / 'report.md'}")
    add_check(report, "report_mentions_current_target", str(run_state.get("current_target", "")).strip() in report_body, f"current_target={run_state.get('current_target')}")
    add_check(report, "repair_summary_present", bool(repair_summary), f"repair_summary={repair_summary}")
    add_check(report, "verification_commands_recorded", isinstance(verification_commands, list) and len([cmd for cmd in verification_commands if str(cmd).strip()]) > 0, f"verification_commands={verification_commands}")
    add_check(report, "verification_before_status_recorded", before_status in {"failed", "not-run", "unknown"}, f"verification_before_status={before_status}")
    add_check(report, "verification_after_status_recorded", after_status in {"passed", "failed"}, f"verification_after_status={after_status}")
    add_check(report, "verification_passed_true", verification_passed, f"verification_passed={run_state.get('verification_passed')}")
    add_check(report, "verification_after_status_is_passed", after_status == "passed", f"verification_after_status={after_status}")
    add_check(report, "verification_evidence_timestamp_present", bool(evidence_updated_at), f"verification_evidence_updated_at={evidence_updated_at}")
    add_check(report, "report_mentions_repair_summary", repair_summary in report_body, f"repair_summary={repair_summary}")
    add_check(report, "report_mentions_verification_before_status", f"Before status: {before_status}" in report_body, f"before_status={before_status}")
    add_check(report, "report_mentions_verification_after_status", f"After status: {after_status}" in report_body, f"after_status={after_status}")
    add_check(report, "report_mentions_verification_passed", "- Passed: true" in report_body or "- Passed: True" in report_body, f"verification_passed={verification_passed}")
    return report

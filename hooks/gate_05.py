from __future__ import annotations

from common import add_check, base_report, gate_map, load_run_bundle, report_text, validate_required_run_files


def run(run_root):
    report = base_report(stage=5, run_root=run_root)
    if not validate_required_run_files(report, run_root):
        return report

    bundle = load_run_bundle(run_root)
    run_state = bundle["run_state"]
    gates = gate_map(bundle["gates"])
    report_body = report_text(run_root / "report.md")
    resume_body = report_text(run_root / "resume.md")
    final_verdict = str(run_state.get("final_verdict", "")).strip()
    final_summary = str(run_state.get("final_summary", "")).strip()
    final_verification_evidence = run_state.get("final_verification_evidence", [])
    remaining_non_blockers = run_state.get("remaining_non_blockers", [])
    completion_reason = str(run_state.get("completion_reason", "")).strip()
    completion_recorded_at = str(run_state.get("completion_recorded_at", "")).strip()

    required_prior_gates_passed = all(
        bool(gate.get("passed"))
        for gate_id, gate in gates.items()
        if gate.get("required") and gate_id != "stage-05"
    )

    add_check(report, "current_stage_is_stage_05", run_state.get("current_stage") == "stage-05", f"current_stage={run_state.get('current_stage')}")
    add_check(report, "required_prior_gates_passed", required_prior_gates_passed, f"gates={list(gates.values())}")
    add_check(report, "report_mentions_completion_section", "## Completion" in report_body, f"report_path={run_root / 'report.md'}")
    add_check(report, "resume_mentions_stop_status", "## Stop Status" in resume_body, f"resume_path={run_root / 'resume.md'}")
    add_check(report, "final_verdict_present", bool(final_verdict), f"final_verdict={final_verdict}")
    add_check(report, "final_summary_present", bool(final_summary), f"final_summary={final_summary}")
    add_check(report, "final_verification_evidence_recorded", isinstance(final_verification_evidence, list) and len([item for item in final_verification_evidence if str(item).strip()]) > 0, f"final_verification_evidence={final_verification_evidence}")
    add_check(report, "remaining_non_blockers_recorded", isinstance(remaining_non_blockers, list), f"remaining_non_blockers={remaining_non_blockers}")
    add_check(report, "completion_reason_present", bool(completion_reason), f"completion_reason={completion_reason}")
    add_check(report, "completion_recorded_at_present", bool(completion_recorded_at), f"completion_recorded_at={completion_recorded_at}")
    add_check(report, "last_commit_present", bool(str(run_state.get("last_commit", "")).strip()), f"last_commit={run_state.get('last_commit')}")
    add_check(report, "report_mentions_ready_to_stop", "- Ready to stop: true" in report_body or "- Ready to stop: True" in report_body, f"report_path={run_root / 'report.md'}")
    add_check(report, "report_mentions_final_verdict", f"- Final verdict: {final_verdict}" in report_body, f"final_verdict={final_verdict}")
    add_check(report, "report_mentions_final_summary", f"- Final summary: {final_summary}" in report_body, f"final_summary={final_summary}")
    add_check(report, "report_mentions_completion_reason", f"- Completion reason: {completion_reason}" in report_body, f"completion_reason={completion_reason}")
    add_check(report, "report_mentions_remaining_non_blockers", "- Remaining non-blockers:" in report_body, f"report_path={run_root / 'report.md'}")
    add_check(report, "resume_mentions_completion_ready_true", "- completion ready: true" in resume_body.lower(), f"resume_path={run_root / 'resume.md'}")
    add_check(report, "resume_mentions_final_verdict", f"- final verdict: {final_verdict.lower()}" in resume_body.lower(), f"final_verdict={final_verdict}")
    return report

from __future__ import annotations

from common import add_check, base_report, human_blocked_evidence_is_valid, load_run_bundle, report_text, structured_human_blocked_is_valid, validate_required_run_files


def run(run_root):
    report = base_report(stage=4, run_root=run_root)
    if not validate_required_run_files(report, run_root):
        return report

    bundle = load_run_bundle(run_root)
    run_state = bundle["run_state"]
    report_body = report_text(run_root / "report.md").lower()
    resume_body = report_text(run_root / "resume.md").lower()

    human_blocked = bool(run_state.get("human_blocked"))
    blocker_type = str(run_state.get("blocker_type", "")).strip()

    add_check(report, "current_stage_is_stage_04", run_state.get("current_stage") == "stage-04", f"current_stage={run_state.get('current_stage')}")
    add_check(report, "report_has_blockers_section", "## blockers" in report_body, f"report_path={run_root / 'report.md'}")
    add_check(report, "resume_mentions_human_blocked", "human blocked" in resume_body, f"resume_path={run_root / 'resume.md'}")
    if human_blocked:
        valid_blocker, blocker_failures = structured_human_blocked_is_valid(run_state)
        add_check(report, "structured_human_blocked_valid", valid_blocker, "; ".join(blocker_failures) if blocker_failures else f"blocker_type={blocker_type}")
        add_check(report, "report_mentions_blocker_type", f"- type: {blocker_type.lower()}" in report_body, f"blocker_type={blocker_type}")
        add_check(report, "report_mentions_local_fix_attempted", "- local fix attempted: true" in report_body, f"local_fix_attempted={run_state.get('local_fix_attempted')}")
        add_check(report, "resume_mentions_blocker_type", f"- blocker type: {blocker_type.lower()}" in resume_body, f"blocker_type={blocker_type}")
        add_check(report, "resume_mentions_local_fix_attempted", "- local fix attempted: true" in resume_body, f"local_fix_attempted={run_state.get('local_fix_attempted')}")
        valid_evidence, evidence_failures = human_blocked_evidence_is_valid(run_root, run_state)
        add_check(report, "human_blocked_evidence_valid", valid_evidence, "; ".join(evidence_failures) if evidence_failures else "report and resume evidence recorded")
    else:
        add_check(report, "human_blocked_false_allows_continue", True, "Run remains locally actionable.")
        add_check(report, "blocker_type_empty_when_not_human_blocked", blocker_type in {"", "none"}, f"blocker_type={blocker_type}")
    return report

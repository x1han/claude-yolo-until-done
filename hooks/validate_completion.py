from __future__ import annotations

from common import add_check, base_report, load_state, load_trace_text, trace_path, validate_required_state_fields


REQUIRED_COMPLETE_STATUS = "complete"
REQUIRED_OWNER = "watcher"
REQUIRED_NEXT_ACTION = "complete"


def run(run_root):
    report = base_report(stage="completion", run_root=run_root)
    state = load_state(run_root)
    review = state.get("review", {}) if isinstance(state.get("review"), dict) else {}
    trace_exists = trace_path(run_root).exists()
    trace_body = load_trace_text(run_root) if trace_exists else ""
    validate_required_state_fields(report, state)
    add_check(report, "status_is_complete", state.get("status") == REQUIRED_COMPLETE_STATUS, f"status={state.get('status')}")
    add_check(report, "owner_is_watcher", state.get("owner") == REQUIRED_OWNER, f"owner={state.get('owner')}")
    add_check(report, "next_action_is_complete", state.get("next_action") == REQUIRED_NEXT_ACTION, f"next_action={state.get('next_action')}")
    add_check(report, "worker_claim_present", bool(str(state.get("worker_claim", "")).strip()), f"worker_claim={state.get('worker_claim')}")
    add_check(report, "files_changed_present", bool(state.get("files_changed")), f"files_changed={state.get('files_changed')}")
    add_check(report, "verification_command_present", bool(str(state.get("verification_command", "")).strip()), f"verification_command={state.get('verification_command')}")
    add_check(report, "verification_result_present", bool(str(state.get("verification_result", "")).strip()), f"verification_result={state.get('verification_result')}")
    add_check(report, "submitted_at_present", bool(str(state.get("submitted_at", "")).strip()), f"submitted_at={state.get('submitted_at')}")
    add_check(report, "review_verdict_is_approve", review.get("verdict") == "approve", f"verdict={review.get('verdict')}")
    add_check(report, "scope_checked_present", bool(review.get("scope_checked")), f"scope_checked={review.get('scope_checked')}")
    add_check(report, "acceptance_basis_present", bool(review.get("acceptance_basis")), f"acceptance_basis={review.get('acceptance_basis')}")
    add_check(report, "required_rework_empty", not review.get("required_rework"), f"required_rework={review.get('required_rework')}")
    add_check(report, "reviewed_at_present", bool(str(state.get("reviewed_at", "")).strip()), f"reviewed_at={state.get('reviewed_at')}")
    add_check(report, "trace_exists", trace_exists, f"trace_path={trace_path(run_root)}")
    add_check(report, "trace_mentions_watcher_review", "watcher review: approve" in trace_body, f"trace_path={trace_path(run_root)}")
    add_check(report, "trace_mentions_watcher_complete", "watcher complete" in trace_body, f"trace_path={trace_path(run_root)}")
    return report

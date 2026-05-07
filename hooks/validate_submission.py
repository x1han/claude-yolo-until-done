from __future__ import annotations

from common import add_check, base_report, load_state, load_trace_text, trace_path, validate_required_state_fields


REQUIRED_REVIEW_STATUS = "needs_review"
REQUIRED_OWNER = "watcher"
REQUIRED_NEXT_ACTION = "watcher_review"


def run(run_root):
    report = base_report(stage="submission", run_root=run_root)
    state = load_state(run_root)
    trace_exists = trace_path(run_root).exists()
    trace_body = load_trace_text(run_root) if trace_exists else ""
    validate_required_state_fields(report, state)
    add_check(report, "status_is_needs_review", state.get("status") == REQUIRED_REVIEW_STATUS, f"status={state.get('status')}")
    add_check(report, "owner_is_watcher", state.get("owner") == REQUIRED_OWNER, f"owner={state.get('owner')}")
    add_check(report, "next_action_is_watcher_review", state.get("next_action") == REQUIRED_NEXT_ACTION, f"next_action={state.get('next_action')}")
    add_check(report, "worker_claim_present", bool(str(state.get("worker_claim", "")).strip()), f"worker_claim={state.get('worker_claim')}")
    add_check(report, "files_changed_present", bool(state.get("files_changed")), f"files_changed={state.get('files_changed')}")
    add_check(report, "verification_command_present", bool(str(state.get("verification_command", "")).strip()), f"verification_command={state.get('verification_command')}")
    add_check(report, "verification_result_present", bool(str(state.get("verification_result", "")).strip()), f"verification_result={state.get('verification_result')}")
    add_check(report, "submitted_at_present", bool(str(state.get("submitted_at", "")).strip()), f"submitted_at={state.get('submitted_at')}")
    add_check(report, "review_is_empty", state.get("review") == {}, f"review={state.get('review')}")
    add_check(report, "reviewed_at_is_empty", not str(state.get("reviewed_at", "")).strip(), f"reviewed_at={state.get('reviewed_at')}")
    add_check(
        report,
        "dispatch_matches_review_target",
        state.get("dispatch_status") != "dispatched"
        or (state.get("last_dispatch") or {}).get("role") == "watcher",
        f"dispatch_status={state.get('dispatch_status')} last_dispatch={state.get('last_dispatch')}",
    )
    add_check(report, "trace_exists", trace_exists, f"trace_path={trace_path(run_root)}")
    add_check(report, "trace_mentions_worker_submit", "worker submit:" in trace_body, f"trace_path={trace_path(run_root)}")
    return report

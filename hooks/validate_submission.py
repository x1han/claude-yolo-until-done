from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
WORKFLOW_DIR = HOOKS_DIR.parent / "workflow"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from common import add_check, base_report, load_state, validate_required_state_fields
from orchestrator import LIVE_CLAIM_STATUSES


REQUIRED_REVIEW_STATUS = "needs_review"
REQUIRED_OWNER = "watcher"
REQUIRED_NEXT_ACTION = "watcher_review"


def run(run_root):
    report = base_report(stage="submission", run_root=run_root)
    state = load_state(run_root)
    certification = state.get("certification", {}) if isinstance(state.get("certification"), dict) else {}
    submission_certification = certification.get("submission", {}) if isinstance(certification.get("submission"), dict) else {}
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
        (state.get("last_dispatch") or {}).get("role") == "watcher",
        f"dispatch_status={state.get('dispatch_status')} last_dispatch={state.get('last_dispatch')}",
    )
    add_check(
        report,
        "dispatch_consumed_for_review",
        state.get("dispatch_status") in LIVE_CLAIM_STATUSES,
        f"dispatch_status={state.get('dispatch_status')} last_dispatch={state.get('last_dispatch')}",
    )
    if submission_certification.get("status") == "ok":
        add_check(
            report,
            "submission_certification_status_ok",
            True,
            f"submission_certification={submission_certification}",
        )
    else:
        report["warnings"].append(
            {
                "name": "submission_certification_not_authoritative",
                "detail": f"submission_certification={submission_certification}",
                "source": "state.json",
            }
        )
    return report

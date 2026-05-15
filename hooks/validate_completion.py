from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
WORKFLOW_DIR = HOOKS_DIR.parent / "workflow"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from common import add_check, base_report, load_state, validate_loop_evidence_base, validate_required_state_fields
from lifecycle import READY_FOR_CLEANUP_STATUS, completion_certification_checks


REQUIRED_COMPLETE_STATUS = READY_FOR_CLEANUP_STATUS
REQUIRED_OWNER = "watcher"
REQUIRED_NEXT_ACTION = "complete"


def validate_loop_completion_evidence(report: dict, state: dict) -> None:
    loop_evidence = validate_loop_evidence_base(report, state)
    if loop_evidence is None:
        return

    _latest, acceleration = loop_evidence
    add_check(report, "loop_acceleration_reviewed_by_watcher", acceleration.get("reviewed_by_watcher") is True, f"acceleration_review={acceleration}")


def run(run_root):
    report = base_report(stage="completion", run_root=run_root)
    state = load_state(run_root)
    review = state.get("review", {}) if isinstance(state.get("review"), dict) else {}
    certification_checks = completion_certification_checks(state)
    completion_certification = certification_checks["completion"]
    validate_required_state_fields(report, state)
    add_check(report, "status_is_ready_for_cleanup", state.get("status") == REQUIRED_COMPLETE_STATUS, f"status={state.get('status')}")
    add_check(report, "owner_is_watcher", state.get("owner") == REQUIRED_OWNER, f"owner={state.get('owner')}")
    add_check(report, "next_action_is_complete", state.get("next_action") == REQUIRED_NEXT_ACTION, f"next_action={state.get('next_action')}")
    add_check(report, "worker_claim_present", bool(str(state.get("worker_claim", "")).strip()), f"worker_claim={state.get('worker_claim')}")
    add_check(report, "files_changed_present", bool(state.get("files_changed")), f"files_changed={state.get('files_changed')}")
    add_check(report, "verification_command_present", bool(str(state.get("verification_command", "")).strip()), f"verification_command={state.get('verification_command')}")
    add_check(report, "verification_result_present", bool(str(state.get("verification_result", "")).strip()), f"verification_result={state.get('verification_result')}")
    add_check(report, "submitted_at_present", bool(str(state.get("submitted_at", "")).strip()), f"submitted_at={state.get('submitted_at')}")
    add_check(report, "cleanup_required_true", state.get("cleanup_required") is True, f"cleanup_required={state.get('cleanup_required')}")
    add_check(report, "review_verdict_is_approve", review.get("verdict") == "approve", f"verdict={review.get('verdict')}")
    add_check(report, "scope_checked_present", bool(review.get("scope_checked")), f"scope_checked={review.get('scope_checked')}")
    add_check(
        report,
        "scope_checked_covers_files_changed",
        set(review.get("scope_checked") or []).issuperset(set(state.get("files_changed") or [])),
        f"scope_checked={review.get('scope_checked')} files_changed={state.get('files_changed')}",
    )
    add_check(report, "acceptance_basis_present", bool(review.get("acceptance_basis")), f"acceptance_basis={review.get('acceptance_basis')}")
    add_check(report, "required_rework_empty", not review.get("required_rework"), f"required_rework={review.get('required_rework')}")
    add_check(report, "reviewed_at_present", bool(str(state.get("reviewed_at", "")).strip()), f"reviewed_at={state.get('reviewed_at')}")
    validate_loop_completion_evidence(report, state)
    add_check(
        report,
        "completion_certification_status_ok",
        bool(certification_checks["status_ok"]),
        f"completion_certification={completion_certification}",
    )
    add_check(
        report,
        "completion_certification_cleanup_state_ready_for_cleanup",
        bool(certification_checks["cleanup_state_ok"]),
        f"completion_certification={completion_certification}",
    )
    add_check(
        report,
        "completion_certification_cleanup_ready_state_hash_present",
        bool(certification_checks["cleanup_ready_state_hash_present"]),
        f"completion_certification={completion_certification}",
    )
    add_check(
        report,
        "completion_certification_cleanup_ready_state_hash_matches",
        bool(certification_checks["cleanup_ready_state_hash_matches"]),
        f"completion_certification={completion_certification}",
    )
    add_check(
        report,
        "completion_certification_hash_present",
        bool(certification_checks["hash_present"]),
        f"certification_hash={certification_checks['expected_hash']}",
    )
    add_check(
        report,
        "completion_certification_hash_matches",
        bool(certification_checks["hash_matches"]),
        f"completion_certification={completion_certification} certification_hash={certification_checks['expected_hash']}",
    )
    return report

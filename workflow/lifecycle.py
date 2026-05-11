from __future__ import annotations

import hashlib
import json

ACTIVE_STATUS = "active"
NEEDS_REVIEW_STATUS = "needs_review"
REWORK_REQUIRED_STATUS = "rework_required"
APPROVED_STATUS = "approved"
READY_FOR_CLEANUP_STATUS = "ready_for_cleanup"
COMPLETE_STATUS = "complete"
COMPLETION_CERTIFICATION_OK = "ok"
ACTIVE_STATUSES = {
    ACTIVE_STATUS,
    NEEDS_REVIEW_STATUS,
    REWORK_REQUIRED_STATUS,
    APPROVED_STATUS,
}


def get_certification(state: dict) -> dict:
    certification = state.get("certification")
    return certification if isinstance(certification, dict) else {}


def get_completion_certification(state: dict) -> dict:
    completion = get_certification(state).get("completion")
    return completion if isinstance(completion, dict) else {}


def clear_completion_certification(state: dict) -> None:
    certification = get_certification(state)
    certification.pop("completion", None)
    state["certification"] = certification
    state["certification_hash"] = ""


def build_cleanup_ready_state_snapshot(state: dict) -> dict:
    review = state.get("review") if isinstance(state.get("review"), dict) else {}
    return {
        "status": state.get("status", ""),
        "task_id": state.get("task_id", ""),
        "task_title": state.get("task_title", ""),
        "owner": state.get("owner", ""),
        "next_action": state.get("next_action", ""),
        "cleanup_required": state.get("cleanup_required"),
        "worker_claim": state.get("worker_claim", ""),
        "files_changed": list(state.get("files_changed", [])),
        "verification_command": state.get("verification_command", ""),
        "verification_result": state.get("verification_result", ""),
        "submitted_at": state.get("submitted_at", ""),
        "reviewed_at": state.get("reviewed_at", ""),
        "review_verdict": review.get("verdict", ""),
        "review_scope_checked": list(review.get("scope_checked", [])),
        "review_problems": list(review.get("problems", [])),
        "review_required_rework": list(review.get("required_rework", [])),
        "review_acceptance_basis": list(review.get("acceptance_basis", [])),
    }


def build_completion_certification(state: dict, timestamp: str) -> dict:
    review = state.get("review") if isinstance(state.get("review"), dict) else {}
    return {
        "status": COMPLETION_CERTIFICATION_OK,
        "certified_at": timestamp,
        "cleanup_state": READY_FOR_CLEANUP_STATUS,
        "cleanup_ready_state_hash": compute_certification_hash(build_cleanup_ready_state_snapshot(state)),
        "task_id": state.get("task_id", ""),
        "review_verdict": review.get("verdict", ""),
        "files_changed": list(state.get("files_changed", [])),
    }


def compute_certification_hash(payload: dict) -> str:
    rendered = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def completion_certification_checks(state: dict) -> dict[str, object]:
    completion = get_completion_certification(state)
    expected_hash = str(state.get("certification_hash", "")).strip()
    cleanup_ready_state_hash = str(completion.get("cleanup_ready_state_hash", "")).strip()
    status = state.get("status")
    current_ready_state_hash = compute_certification_hash(build_cleanup_ready_state_snapshot(state))
    require_ready_state_match = status == READY_FOR_CLEANUP_STATUS
    return {
        "completion": completion,
        "expected_hash": expected_hash,
        "cleanup_ready_state_hash": cleanup_ready_state_hash,
        "status_ok": completion.get("status") == COMPLETION_CERTIFICATION_OK,
        "cleanup_state_ok": completion.get("cleanup_state") == READY_FOR_CLEANUP_STATUS,
        "cleanup_ready_state_hash_present": bool(cleanup_ready_state_hash),
        "cleanup_ready_state_hash_matches": (not require_ready_state_match)
        or (bool(cleanup_ready_state_hash) and cleanup_ready_state_hash == current_ready_state_hash),
        "hash_present": bool(expected_hash),
        "hash_matches": bool(expected_hash) and compute_certification_hash(completion) == expected_hash,
    }


def completion_certification_problem(state: dict) -> str | None:
    checks = completion_certification_checks(state)
    if not checks["status_ok"]:
        return "status_invalid"
    if not checks["cleanup_state_ok"]:
        return "cleanup_state_invalid"
    if not checks["cleanup_ready_state_hash_present"]:
        return "cleanup_ready_state_hash_missing"
    if not checks["cleanup_ready_state_hash_matches"]:
        return "cleanup_ready_state_hash_mismatch"
    if not checks["hash_present"]:
        return "hash_missing"
    if not checks["hash_matches"]:
        return "hash_mismatch"
    return None


def completion_certification_is_valid(state: dict) -> bool:
    return completion_certification_problem(state) is None


def has_terminal_cleanup_contract(state: dict) -> bool:
    return state.get("owner") == "watcher" and state.get("next_action") == "complete"


def is_ready_for_cleanup_state(state: dict) -> bool:
    return (
        state.get("status") == READY_FOR_CLEANUP_STATUS
        and state.get("cleanup_required") is True
        and has_terminal_cleanup_contract(state)
        and completion_certification_is_valid(state)
    )


def is_completed_cleanup_state(state: dict) -> bool:
    return (
        state.get("status") == COMPLETE_STATUS
        and state.get("cleanup_required") is False
        and has_terminal_cleanup_contract(state)
        and completion_certification_is_valid(state)
    )

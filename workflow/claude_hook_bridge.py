#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lifecycle import ACTIVE_STATUSES, completion_certification_problem, is_completed_cleanup_state
from orchestrator import (
    ABANDONED_STATUS,
    CLAIMED_STATUS,
    COMPLETED_STATUS,
    DISPATCHED_STATUS,
    IDLE_STATUS,
    PENDING_STATUS,
    RUNNING_STATUS,
    TIMED_OUT_STATUS,
    dispatch_requires_intent,
    is_dispatch_claim_live,
    mark_dispatch_pending,
    parse_timestamp,
)
from state import StaleStateVersionError, build_resume_target, transition_state, utc_now, write_state

HOOKS_DIR = Path(__file__).resolve().parents[1] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))


VALID_DISPATCH_STATUSES = {
    IDLE_STATUS,
    PENDING_STATUS,
    CLAIMED_STATUS,
    RUNNING_STATUS,
    DISPATCHED_STATUS,
    COMPLETED_STATUS,
    TIMED_OUT_STATUS,
    ABANDONED_STATUS,
}
CONTINUE_CHOICES = {"继续 yolo", "continue yolo"}
PROMPT_FIELDS = ("prompt", "text", "userPrompt")


def load_stdin_json() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_stop_state(state: dict, run_root: Path) -> str | None:
    required_fields = (
        "state_version",
        "status",
        "cleanup_required",
        "owner",
        "next_action",
        "requested_role",
        "gate_attempt",
        "gate_max_attempts",
        "blocked_for_human",
    )
    for field in required_fields:
        if field not in state:
            return (
                f"Run root exists at {run_root} but state.json is missing required field {field!r}; "
                "the durable run bundle must be repaired before continuing."
            )
    state_version = state.get("state_version")
    if not isinstance(state_version, int) or state_version < 1:
        return (
            f"Run root exists at {run_root} but state_version is invalid; "
            "the durable run bundle must be repaired before continuing."
        )
    try:
        gate_attempt = int(state["gate_attempt"])
        gate_max_attempts = int(state["gate_max_attempts"])
    except (TypeError, ValueError):
        return (
            f"Run root exists at {run_root} but gate counters are unreadable; "
            "the durable run bundle must be repaired before continuing."
        )
    if gate_attempt < 0 or gate_max_attempts <= 0:
        return (
            f"Run root exists at {run_root} but gate counters are invalid; "
            "the durable run bundle must be repaired before continuing."
        )

    status = state["status"]
    if status not in ACTIVE_STATUSES:
        return None

    dispatch_fields = ("dispatch_status", "dispatch_intent", "dispatch_claim", "last_dispatch")
    for field in dispatch_fields:
        if field not in state:
            return (
                f"Run root exists at {run_root} but active state.json is missing required dispatch field {field!r}; "
                "the durable run bundle must be repaired before continuing."
            )

    dispatch_status = state["dispatch_status"]
    if not isinstance(dispatch_status, str) or dispatch_status not in VALID_DISPATCH_STATUSES:
        return (
            f"Run root exists at {run_root} but dispatch_status is invalid for active work; "
            "the durable run bundle must be repaired before continuing."
        )

    dispatch_intent = state["dispatch_intent"]
    dispatch_claim = state["dispatch_claim"]
    last_dispatch = state["last_dispatch"]
    if not isinstance(dispatch_intent, dict) or not isinstance(dispatch_claim, dict) or not isinstance(last_dispatch, dict):
        return (
            f"Run root exists at {run_root} but persisted dispatch metadata is malformed for active work; "
            "the durable run bundle must be repaired before continuing."
        )

    if dispatch_status in {"pending", "claimed", "running"}:
        role = dispatch_intent.get("role")
        action = dispatch_intent.get("action")
        if not isinstance(role, str) or not role.strip() or not isinstance(action, str) or not action.strip():
            return (
                f"Run root exists at {run_root} but dispatch_intent is invalid for active work; "
                "the durable run bundle must be repaired before continuing."
            )

    if dispatch_status in {"claimed", "running"}:
        owner = dispatch_claim.get("owner")
        if not isinstance(owner, str) or not owner.strip():
            return (
                f"Run root exists at {run_root} but dispatch_claim.owner is invalid for active work; "
                "the durable run bundle must be repaired before continuing."
            )
        claimed_at = parse_timestamp(dispatch_claim.get("claimed_at"))
        if claimed_at is None:
            return (
                f"Run root exists at {run_root} but dispatch_claim.claimed_at is invalid for active work; "
                "the durable run bundle must be repaired before continuing."
            )
        lease_expires_at = parse_timestamp(dispatch_claim.get("lease_expires_at"))
        if lease_expires_at is None:
            return (
                f"Run root exists at {run_root} but dispatch_claim.lease_expires_at is invalid for active work; "
                "the durable run bundle must be repaired before continuing."
            )

    return None


def resolve_run_root(project_dir: Path, run_root_arg: str) -> Path:
    candidate = Path(run_root_arg)
    if candidate.is_absolute():
        return candidate
    return project_dir / candidate


def extract_prompt_text(hook_input: dict) -> str:
    for field in PROMPT_FIELDS:
        value = hook_input.get(field)
        if isinstance(value, str):
            return value.strip()
    return ""


def is_explicit_continue_choice(hook_input: dict) -> bool:
    prompt_text = extract_prompt_text(hook_input).lower()
    return prompt_text in CONTINUE_CHOICES


def is_human_helper_mode(state: dict) -> bool:
    if state.get("allow_need_human") is not True or not bool(state.get("blocked_for_human")):
        return False
    if state.get("worker_request") == "need_human":
        return True
    handoff = state.get("human_handoff") if isinstance(state.get("human_handoff"), dict) else {}
    return handoff.get("reason") == "stop_gate_limit"


def build_user_prompt_submit_payload(state: dict, hook_input: dict | None = None) -> dict:
    status = state.get("status")
    cleanup_required = bool(state.get("cleanup_required"))
    prompt_input = hook_input or {}

    if is_human_helper_mode(state):
        return {
            "decision": "human_helper",
            "mode": "human_helper",
            "prompt": extract_prompt_text(prompt_input),
            "worker_question": state.get("worker_question", ""),
            "task_id": state.get("task_id", ""),
            "task_title": state.get("task_title", ""),
            "task_inputs": state.get("task_inputs", []),
        }

    if status in ACTIVE_STATUSES or cleanup_required:
        if is_explicit_continue_choice(prompt_input):
            return {}
        return {
            "decision": "block",
            "reason": (
                "claude-yolo 仍处于挂载状态。当前必须三选一："
                "1) 暂停，保留中间文件并清理 hooks；"
                "2) 取消，清理中间文件和 hooks；"
                "3) 继续 yolo。"
            ),
        }
    return {}


def emit_session_start_context(run_root: Path, state: dict | None = None, broken_reason: str | None = None) -> int:
    if broken_reason:
        additional_context = "\n".join(
            [
                "A lightweight worker-watcher workflow bundle is mounted for this project but needs repair before resume.",
                f"Run bundle: {run_root}",
                f"Issue: {broken_reason}",
                "Repair or clean up the durable run bundle before continuing.",
            ]
        )
    else:
        additional_context = "\n".join(
            [
                "A lightweight worker-watcher workflow is active for this project.",
                f"Run bundle: {run_root}",
                f"Status: {state.get('status')}",
                f"Owner: {state.get('owner')}",
                f"Goal: {state.get('goal')}",
                f"Next action: {state.get('next_action')}",
                "Reload state.json and continue from the durable state on disk.",
            ]
        )
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": additional_context,
        }
    }
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def completion_certification_reason(run_root: Path, state: dict) -> str | None:
    if state.get("status") not in {"ready_for_cleanup", "complete"}:
        return None
    problem = completion_certification_problem(state)
    if problem == "status_invalid":
        return (
            f"Run root exists at {run_root} but persisted completion certification is missing or invalid; "
            "the durable run bundle must be repaired or cleaned up before continuing."
        )
    if problem == "cleanup_state_invalid":
        return (
            f"Run root exists at {run_root} but persisted completion certification has the wrong cleanup_state; "
            "the durable run bundle must be repaired or cleaned up before continuing."
        )
    if problem == "cleanup_ready_state_hash_missing":
        return (
            f"Run root exists at {run_root} but persisted completion certification is missing cleanup-ready state proof; "
            "the durable run bundle must be repaired or cleaned up before continuing."
        )
    if problem == "cleanup_ready_state_hash_mismatch":
        return (
            f"Run root exists at {run_root} but persisted completion certification no longer matches the cleanup-ready state snapshot; "
            "the durable run bundle must be repaired or cleaned up before continuing."
        )
    if problem == "hash_missing":
        return (
            f"Run root exists at {run_root} but certification_hash is missing for persisted completion certification; "
            "the durable run bundle must be repaired or cleaned up before continuing."
        )
    if problem == "hash_mismatch":
        return (
            f"Run root exists at {run_root} but certification_hash does not match persisted completion certification; "
            "the durable run bundle must be repaired or cleaned up before continuing."
        )
    return None



def invalid_complete_bundle_reason(run_root: Path, state: dict) -> str | None:
    certification_reason = completion_certification_reason(run_root, state)
    if certification_reason:
        return certification_reason
    if state.get("status") != "complete" or state.get("cleanup_required") is not False:
        return None
    if not is_completed_cleanup_state(state):
        return (
            f"Run root exists at {run_root} but complete-state terminal cleanup contract is invalid; "
            "the durable run bundle must be repaired or cleaned up before continuing."
        )
    return None



def session_start(project_dir: Path, run_root: Path) -> int:
    state, broken_reason = load_stop_state(run_root)
    if broken_reason:
        return emit_session_start_context(run_root, broken_reason=broken_reason)
    if state is None:
        return 0
    invalid_complete_reason = invalid_complete_bundle_reason(run_root, state)
    if invalid_complete_reason:
        return emit_session_start_context(run_root, broken_reason=invalid_complete_reason)
    if state.get("status") == "complete" and not state.get("cleanup_required"):
        return 0
    return emit_session_start_context(run_root, state=state)


def emit_block(reason: str, orchestration: dict | None = None) -> int:
    payload = {"decision": "block", "reason": reason}
    if orchestration:
        payload["orchestration"] = orchestration
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def load_stop_state(run_root: Path) -> tuple[dict | None, str | None]:
    if not run_root.exists():
        return None, None
    if not run_root.is_dir():
        return None, f"Run root exists at {run_root} but is not a directory; the run bundle must be repaired or removed before continuing."

    state_path = run_root / "state.json"
    if not state_path.exists():
        return None, f"Run root exists at {run_root} but state.json is missing; the durable run bundle must be repaired or cleaned up before continuing."

    try:
        state = load_json(state_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, f"Run root exists at {run_root} but state.json is unreadable; the durable run bundle must be repaired before continuing."

    invalid_reason = validate_stop_state(state, run_root)
    if invalid_reason:
        return None, invalid_reason
    return state, None


def should_persist_worker_return_gate(state: dict) -> bool:
    if state.get("owner") != "worker":
        return False
    if state.get("blocked_for_human"):
        return False
    if state.get("requested_role", "worker") != "worker":
        return False
    if state.get("dispatch_status", "idle") in {"pending", "claimed", "running"}:
        return False
    next_action = state.get("next_action", "")
    return isinstance(next_action, str) and next_action.startswith("worker_")


def persist_stop_gate(state: dict, run_root: Path) -> tuple[int, int, bool]:
    expected_version = int(state.get("state_version", 1))

    def apply(current_state: dict, _: str) -> None:
        attempts = int(current_state.get("gate_attempt", 0)) + 1
        max_attempts = int(current_state.get("gate_max_attempts", 5))
        current_state["gate_attempt"] = attempts
        current_state["gate_reason"] = "worker_return_stop_block"

        reached_limit = attempts >= max_attempts
        if reached_limit:
            current_state["resume_target"] = build_resume_target(current_state)
            current_state["blocked_for_human"] = True
            current_state["owner"] = "human"
            current_state["next_action"] = "human_handoff"
            current_state["worker_request"] = "need_human"
            current_state["worker_question"] = "Stop gate limit reached; human guidance is required before the run can resume."
            mark_dispatch_pending(current_state, "human")
            current_state["human_handoff"] = {"reason": "stop_gate_limit"}

    updated_state = transition_state(
        run_root,
        actor="stop_hook",
        action="persist_stop_gate",
        expected_version=expected_version,
        apply_transition=apply,
    )
    attempts = int(updated_state.get("gate_attempt", 0))
    max_attempts = int(updated_state.get("gate_max_attempts", 5))
    return attempts, max_attempts, attempts >= max_attempts


def stop(project_dir: Path, run_root: Path, hook_input: dict) -> int:
    state, broken_reason = load_stop_state(run_root)
    if broken_reason:
        return emit_block(broken_reason)
    if state is None:
        return 0

    status = state["status"]
    if state["blocked_for_human"]:
        handoff_reason = state.get("human_handoff", {}).get("reason")
        if handoff_reason == "stop_gate_limit":
            return emit_block(
                "Workflow is blocked for human handoff because the stop gate limit was reached; record guidance or cancel the run before stopping.",
            )
        return emit_block("Workflow is blocked for human handoff; record guidance or cancel the run before stopping.")

    if status in ACTIVE_STATUSES and dispatch_requires_intent(state):
        return emit_block(
            "Workflow dispatch still needs durable dispatch_intent metadata before stop can continue; repair the run state and resume.",
        )

    if status in ACTIVE_STATUSES and is_dispatch_claim_live(state):
        claim = state.get("dispatch_claim", {})
        owner = claim.get("owner", "unknown")
        return emit_block(
            f"Workflow has a live dispatch claim owned by {owner}; let that consumer finish or wait for the lease to expire before stopping.",
        )

    if status in ACTIVE_STATUSES:
        reason = f"Workflow status is {status}; continue the current goal instead of stopping."
        if should_persist_worker_return_gate(state):
            try:
                attempts, max_attempts, reached_limit = persist_stop_gate(state, run_root)
            except StaleStateVersionError as error:
                return emit_block(str(error))
            if reached_limit:
                reason = (
                    f"Workflow status is {status}; stop gate hit worker return limit "
                    f"({attempts}/{max_attempts}) and now requires human handoff."
                )
            else:
                reason = f"{reason} Worker return stop gate attempt {attempts}/{max_attempts}."
        return emit_block(reason)

    certification_reason = completion_certification_reason(run_root, state)
    if certification_reason:
        return emit_block(certification_reason)

    invalid_complete_reason = invalid_complete_bundle_reason(run_root, state)
    if invalid_complete_reason:
        return emit_block(invalid_complete_reason)

    if state.get("cleanup_required"):
        return emit_block("Workflow completion still requires claude-yolo cleanup before stopping.")

    if status == "complete":
        return 0

    return emit_block(f"Workflow status is {status!r}; stop stays blocked until the durable run state is repaired or completed.")


def user_prompt_submit(project_dir: Path, run_root: Path, hook_input: dict) -> int:
    state, broken_reason = load_stop_state(run_root)
    if broken_reason:
        return emit_block(broken_reason)
    if state is None:
        return 0

    invalid_complete_reason = invalid_complete_bundle_reason(run_root, state)
    if invalid_complete_reason:
        return emit_block(invalid_complete_reason)

    payload = build_user_prompt_submit_payload(state, hook_input)
    if payload:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Claude Code hook bridge for claude-yolo-until-done.")
    parser.add_argument("--event", required=True, choices=["session-start", "stop", "user-prompt-submit"])
    parser.add_argument("--project-dir", required=True, help="Claude project directory")
    parser.add_argument("--run-root", default=".yolo", help="Run bundle root relative to the project dir unless absolute")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    run_root = resolve_run_root(project_dir, args.run_root)
    hook_input = load_stdin_json()

    if args.event == "session-start":
        return session_start(project_dir, run_root)
    if args.event == "stop":
        return stop(project_dir, run_root, hook_input)
    if args.event == "user-prompt-submit":
        return user_prompt_submit(project_dir, run_root, hook_input)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

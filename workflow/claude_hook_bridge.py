#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from orchestrator import orchestrate
from state import utc_now, write_state

HOOKS_DIR = Path(__file__).resolve().parents[1] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from validate_completion import run as validate_completion


ACTIVE_STATUSES = {"active", "needs_review", "rework_required", "approved"}
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


def build_user_prompt_submit_payload(state: dict, hook_input: dict | None = None) -> dict:
    status = state.get("status")
    cleanup_required = bool(state.get("cleanup_required"))
    if status in ACTIVE_STATUSES or cleanup_required:
        if is_explicit_continue_choice(hook_input or {}):
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


def session_start(project_dir: Path, run_root: Path) -> int:
    state, broken_reason = load_stop_state(run_root)
    if broken_reason:
        return emit_session_start_context(run_root, broken_reason=broken_reason)
    if state is None:
        return 0
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
    trace_path = run_root / "trace.md"
    if not state_path.exists():
        return None, f"Run root exists at {run_root} but state.json is missing; the durable run bundle must be repaired or cleaned up before continuing."
    if not trace_path.exists():
        return None, f"Run root exists at {run_root} but trace.md is missing; the durable run bundle must be repaired or cleaned up before continuing."

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
    next_action = state.get("next_action", "")
    return isinstance(next_action, str) and next_action.startswith("worker_")


def persist_stop_gate(state: dict, run_root: Path) -> tuple[int, int, bool]:
    attempts = int(state.get("gate_attempt", 0)) + 1
    max_attempts = int(state.get("gate_max_attempts", 5))
    state["gate_attempt"] = attempts
    state["gate_reason"] = "worker_return_stop_block"
    state["updated_at"] = utc_now()

    reached_limit = attempts >= max_attempts
    if reached_limit:
        state["blocked_for_human"] = True
        state["owner"] = "human"
        state["next_action"] = "human_handoff"
        state["requested_role"] = "human"
        state["dispatch_status"] = "idle"
        state["last_dispatch"] = {}
        state["human_handoff"] = {"reason": "stop_gate_limit"}

    write_state(run_root, state)
    return attempts, max_attempts, reached_limit


def stop(project_dir: Path, run_root: Path, hook_input: dict) -> int:
    state, broken_reason = load_stop_state(run_root)
    if broken_reason:
        return emit_block(broken_reason)
    if state is None:
        return 0

    status = state["status"]
    if state["blocked_for_human"]:
        orchestration = orchestrate(run_root, state)
        handoff_reason = state.get("human_handoff", {}).get("reason")
        if handoff_reason == "stop_gate_limit":
            return emit_block(
                "Workflow is blocked for human handoff because the stop gate limit was reached; record guidance or cancel the run before stopping.",
                orchestration,
            )
        return emit_block("Workflow is blocked for human handoff; record guidance or cancel the run before stopping.", orchestration)

    if status in ACTIVE_STATUSES:
        reason = f"Workflow status is {status}; continue the current goal instead of stopping."
        if should_persist_worker_return_gate(state):
            attempts, max_attempts, reached_limit = persist_stop_gate(state, run_root)
            if reached_limit:
                reason = (
                    f"Workflow status is {status}; stop gate hit worker return limit "
                    f"({attempts}/{max_attempts}) and now requires human handoff."
                )
            else:
                reason = f"{reason} Worker return stop gate attempt {attempts}/{max_attempts}."
        orchestration = orchestrate(run_root, state)
        return emit_block(reason, orchestration)

    if state.get("cleanup_required"):
        return emit_block("Workflow completion still requires claude-yolo cleanup before stopping.")

    if status == "complete":
        report = validate_completion(run_root)
        if not report.get("passed"):
            return emit_block("Workflow says complete but completion validation still fails.")
        return 0

    return emit_block(f"Workflow status is {status!r}; stop stays blocked until the durable run state is repaired or completed.")


def user_prompt_submit(project_dir: Path, run_root: Path, hook_input: dict) -> int:
    state, broken_reason = load_stop_state(run_root)
    if broken_reason:
        return emit_block(broken_reason)
    if state is None:
        return 0

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

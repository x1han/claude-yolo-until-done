#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from validate_completion import run as validate_completion


ACTIVE_STATUSES = {"active", "needs_review", "rework_required", "approved"}
CONTINUE_TOKENS = ("继续 yolo", "continue yolo")
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
    return any(token in prompt_text for token in CONTINUE_TOKENS)


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


def session_start(project_dir: Path, run_root: Path) -> int:
    state_path = run_root / "state.json"
    if not state_path.exists():
        return 0

    state = load_json(state_path)
    if state.get("status") == "complete" and not state.get("cleanup_required"):
        return 0

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


def stop(project_dir: Path, run_root: Path, hook_input: dict) -> int:
    if hook_input.get("stop_hook_active") is True:
        return 0

    state_path = run_root / "state.json"
    if not state_path.exists():
        return 0

    state = load_json(state_path)
    status = state.get("status")
    if status in ACTIVE_STATUSES:
        reason = f"Workflow status is {status}; continue the current goal instead of stopping."
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=True))
        return 0

    if state.get("cleanup_required"):
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": "Workflow completion still requires claude-yolo cleanup before stopping.",
                },
                ensure_ascii=True,
            )
        )
        return 0

    if status == "complete":
        report = validate_completion(run_root)
        if not report.get("passed"):
            print(
                json.dumps(
                    {
                        "decision": "block",
                        "reason": "Workflow says complete but completion validation still fails.",
                    },
                    ensure_ascii=True,
                )
            )
        return 0

    return 0


def user_prompt_submit(project_dir: Path, run_root: Path, hook_input: dict) -> int:
    state_path = run_root / "state.json"
    if not state_path.exists():
        return 0

    payload = build_user_prompt_submit_payload(load_json(state_path), hook_input)
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

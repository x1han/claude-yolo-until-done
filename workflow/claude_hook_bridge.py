#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from common import human_blocked_evidence_is_valid
from hook_settings import uninstall_hook_set


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


def hook_run_root_arg(project_dir: Path, run_root: Path) -> str:
    try:
        return run_root.relative_to(project_dir).as_posix()
    except ValueError:
        return str(run_root)


def session_start(project_dir: Path, run_root: Path) -> int:
    run_state_path = run_root / "run_state.json"
    if not run_state_path.exists():
        return 0

    run_state = load_json(run_state_path)
    lifecycle_state = run_state.get("lifecycle_state", "active")
    if lifecycle_state in {"paused", "deactivated"}:
        return 0
    if not run_state.get("workflow_active"):
        return 0

    additional_context = "\n".join(
        [
            "A claude-yolo-until-done run bundle appears active for this project based on run_state.json.",
            f"Run bundle: {run_root}",
            f"Current stage: {run_state.get('current_stage')}",
            f"Current target: {run_state.get('current_target')}",
            f"Current issue: {run_state.get('current_issue')}",
            f"Next action: {run_state.get('next_action')}",
            "Re-validate runtime assumptions and continue from the bundle on disk instead of trusting this note alone.",
            "Do not stop unless completion_ready is true or a structured human-blocked condition has been re-validated.",
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

    run_state_path = run_root / "run_state.json"
    if not run_state_path.exists():
        return 0

    run_state = load_json(run_state_path)
    lifecycle_state = run_state.get("lifecycle_state", "active")
    if lifecycle_state in {"paused", "deactivated"}:
        return 0
    if not run_state.get("workflow_active"):
        return 0

    if run_state.get("human_blocked") is True:
        valid_blocker, _ = human_blocked_evidence_is_valid(run_root, run_state)
        if valid_blocker:
            return 0

    reason = (
        "claude-yolo-until-done is still active. "
        f"Current stage: {run_state.get('current_stage')}. "
        f"Next action: {run_state.get('next_action')}. "
        f"Reload {run_state_path}, re-validate the bundle state, continue the current gate, and do not stop yet."
    )
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=True))
    return 0


def session_end(project_dir: Path, run_root: Path, settings_file: str) -> int:
    run_state_path = run_root / "run_state.json"
    if not run_state_path.exists():
        return 0

    run_state = load_json(run_state_path)
    lifecycle_state = run_state.get("lifecycle_state", "active")
    should_cleanup = (
        (run_state.get("completion_ready") is True and run_state.get("workflow_active") is False)
        or lifecycle_state == "deactivated"
    )
    if not should_cleanup:
        return 0

    settings_path = (project_dir / settings_file).resolve()
    bridge_path = Path(__file__).resolve()
    python_exe = Path(sys.executable).resolve()
    uninstall_hook_set(settings_path, python_exe, bridge_path, hook_run_root_arg(project_dir, run_root), settings_file)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Claude Code hook bridge for claude-yolo-until-done.")
    parser.add_argument("--event", required=True, choices=["session-start", "stop", "session-end"])
    parser.add_argument("--project-dir", required=True, help="Claude project directory")
    parser.add_argument("--run-root", default="artifacts/yolo", help="Run bundle root relative to the project dir unless absolute")
    parser.add_argument("--settings-file", default=".claude/settings.local.json", help="Settings file path relative to the project dir")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    run_root = resolve_run_root(project_dir, args.run_root)
    hook_input = load_stdin_json()

    if args.event == "session-start":
        return session_start(project_dir, run_root)
    if args.event == "stop":
        return stop(project_dir, run_root, hook_input)
    if args.event == "session-end":
        return session_end(project_dir, run_root, args.settings_file)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

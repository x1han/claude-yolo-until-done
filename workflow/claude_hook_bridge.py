#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from hook_settings import uninstall_hook_set
from validate_completion import run as validate_completion


ACTIVE_STATUSES = {"active", "needs_review", "rework_required", "approved"}


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
    state_path = run_root / "state.json"
    if not state_path.exists():
        return 0

    state = load_json(state_path)
    if state.get("status") == "complete":
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


def session_end(project_dir: Path, run_root: Path, settings_file: str) -> int:
    state_path = run_root / "state.json"
    if not state_path.exists():
        return 0

    state = load_json(state_path)
    if state.get("status") != "complete":
        return 0

    report = validate_completion(run_root)
    if not report.get("passed"):
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

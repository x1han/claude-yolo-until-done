#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hook_settings import install_hook_set, uninstall_hook_set
from lifecycle import is_completed_cleanup_state
from state import hold_run_lock, load_state, state_path, trace_path, utc_now, write_state

HOOKS_DIR = Path(__file__).resolve().parents[1] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from validate_completion import run as validate_completion


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean up claude-yolo runtime state.")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--run-root", default=".yolo")
    parser.add_argument("--settings-file", default=".claude/settings.local.json")
    parser.add_argument("--mode", required=True, choices=("pause", "cancel", "complete"))
    return parser.parse_args()


def remove_auxiliary_run_files(run_root: Path) -> None:
    trace_path(run_root).unlink(missing_ok=True)
    (run_root / "watcher_checklist.json").unlink(missing_ok=True)


def remove_state_file(run_root: Path) -> None:
    state_path(run_root).unlink(missing_ok=True)


def is_resumable_terminal_cleanup_state(state: dict) -> bool:
    return is_completed_cleanup_state(state)


def perform_complete_cleanup(
    run_root: Path,
    settings_path: Path,
    python_exe: Path,
    bridge_path: Path,
    run_root_arg: str,
    ready_for_cleanup_state: dict | None = None,
) -> None:
    with hold_run_lock(run_root):
        remove_auxiliary_run_files(run_root)
        hooks_uninstalled = False
        try:
            uninstall_hook_set(settings_path, python_exe, bridge_path, run_root_arg)
            hooks_uninstalled = True
            remove_state_file(run_root)
        except Exception:
            if ready_for_cleanup_state is not None:
                ready_for_cleanup_state["updated_at"] = utc_now()
                write_state(run_root, ready_for_cleanup_state)
            if hooks_uninstalled:
                install_hook_set(settings_path, python_exe, bridge_path, run_root_arg)
            raise


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    run_root = (project_dir / args.run_root).resolve()
    settings_path = (project_dir / args.settings_file).resolve()
    python_exe = Path(sys.executable).resolve()
    bridge_path = Path(__file__).resolve().parent / "claude_hook_bridge.py"
    if args.mode == "complete":
        state = load_state(run_root)
        if is_resumable_terminal_cleanup_state(state):
            perform_complete_cleanup(run_root, settings_path, python_exe, bridge_path, args.run_root)
        else:
            report = validate_completion(run_root)
            if not report.get("passed"):
                print("Refusing cleanup-complete because completion validation failed.", file=sys.stderr)
                return 1
            if state.get("status") != "ready_for_cleanup":
                print("Refusing cleanup-complete because state is not ready_for_cleanup.", file=sys.stderr)
                return 1
            perform_complete_cleanup(
                run_root,
                settings_path,
                python_exe,
                bridge_path,
                args.run_root,
                ready_for_cleanup_state=dict(state),
            )
    else:
        uninstall_hook_set(settings_path, python_exe, bridge_path, args.run_root)
        if args.mode == "cancel":
            remove_auxiliary_run_files(run_root)
            remove_state_file(run_root)
    print(json.dumps({"mode": args.mode, "run_root": str(run_root)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

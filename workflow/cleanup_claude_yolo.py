#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hook_settings import uninstall_hook_set

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


def remove_run_files(run_root: Path) -> None:
    for name in ("state.json", "trace.md", "watcher_checklist.json"):
        (run_root / name).unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    run_root = (project_dir / args.run_root).resolve()
    settings_path = (project_dir / args.settings_file).resolve()
    if args.mode == "complete":
        report = validate_completion(run_root)
        if not report.get("passed"):
            print("Refusing cleanup-complete because completion validation failed.", file=sys.stderr)
            return 1
    if args.mode in {"cancel", "complete"}:
        remove_run_files(run_root)
    uninstall_hook_set(
        settings_path,
        Path(sys.executable).resolve(),
        Path(__file__).resolve().parent / "claude_hook_bridge.py",
        args.run_root,
    )
    print(json.dumps({"mode": args.mode, "run_root": str(run_root)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

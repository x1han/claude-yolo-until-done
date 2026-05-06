#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hook_settings import install_hook_set


def main() -> int:
    parser = argparse.ArgumentParser(description="Install recommended Claude Code local hooks for claude-yolo-until-done.")
    parser.add_argument("--project-dir", required=True, help="Target Claude Code project directory")
    parser.add_argument("--run-root", default=".yolo", help="Run bundle root relative to the project directory")
    parser.add_argument("--settings-file", default=".claude/settings.local.json", help="Settings file path relative to the project directory")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    settings_path = (project_dir / args.settings_file).resolve()
    bridge_path = Path(__file__).resolve().parent / "claude_hook_bridge.py"
    python_exe = Path(sys.executable).resolve()

    install_hook_set(settings_path, python_exe, bridge_path, args.run_root)
    print(json.dumps({"settings_path": str(settings_path), "project_dir": str(project_dir)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

from hook_settings import install_hook_set


def main() -> int:
    parser = argparse.ArgumentParser(description="Install recommended Claude Code local hooks for claude-yolo-until-done.")
    parser.add_argument("--project-dir", required=True, help="Target Claude Code project directory")
    parser.add_argument("--run-root", default="artifacts/yolo", help="Run bundle root relative to the project directory")
    parser.add_argument("--settings-file", default=".claude/settings.local.json", help="Settings file path relative to the project directory")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    settings_path = (project_dir / args.settings_file).resolve()
    bridge_path = Path(__file__).resolve().parent / "claude_hook_bridge.py"
    python_exe = Path(sys.executable).resolve()

    install_hook_set(settings_path, python_exe, bridge_path, args.run_root, args.settings_file)
    runtime_marker_path = (project_dir / args.run_root / "runtime_context.json").resolve()
    if runtime_marker_path.exists():
        payload = json.loads(runtime_marker_path.read_text(encoding="utf-8-sig"))
        payload["operator_asserted_hooks_available"] = True
        payload["hook_settings_path"] = str(settings_path)
        payload["hook_install_marker"] = "claude-yolo-until-done"
        payload["installed_with_python"] = str(python_exe)
        runtime_marker_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(json.dumps({"settings_path": str(settings_path), "project_dir": str(project_dir)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

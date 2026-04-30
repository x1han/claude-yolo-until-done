#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def normalize_run_root(run_root: str) -> str:
    return Path(run_root).as_posix()


def workflow_markers(settings: dict) -> dict:
    marker_root = settings.setdefault("claudeYoloUntilDone", {})
    if not isinstance(marker_root, dict):
        marker_root = {}
        settings["claudeYoloUntilDone"] = marker_root
    runs = marker_root.setdefault("runs", {})
    if not isinstance(runs, dict):
        runs = {}
        marker_root["runs"] = runs
    return runs


def build_session_start_group(python_exe: Path, bridge_path: Path, run_root: str) -> dict:
    normalized_run_root = normalize_run_root(run_root)
    return {
        "metadata": {
            "workflow": "claude-yolo-until-done",
            "hook_role": "SessionStart",
            "run_root": normalized_run_root,
        },
        "matcher": "startup|resume|compact",
        "hooks": [
            {
                "type": "command",
                "command": f"\"{python_exe}\" \"{bridge_path}\" --event session-start --project-dir \"$CLAUDE_PROJECT_DIR\" --run-root \"{normalized_run_root}\"",
            }
        ],
    }


def build_stop_group(python_exe: Path, bridge_path: Path, run_root: str) -> dict:
    normalized_run_root = normalize_run_root(run_root)
    return {
        "metadata": {
            "workflow": "claude-yolo-until-done",
            "hook_role": "Stop",
            "run_root": normalized_run_root,
        },
        "hooks": [
            {
                "type": "command",
                "command": f"\"{python_exe}\" \"{bridge_path}\" --event stop --project-dir \"$CLAUDE_PROJECT_DIR\" --run-root \"{normalized_run_root}\"",
            }
        ]
    }


def build_session_end_group(python_exe: Path, bridge_path: Path, run_root: str, settings_file: str) -> dict:
    normalized_run_root = normalize_run_root(run_root)
    return {
        "metadata": {
            "workflow": "claude-yolo-until-done",
            "hook_role": "SessionEnd",
            "run_root": normalized_run_root,
        },
        "hooks": [
            {
                "type": "command",
                "command": f"\"{python_exe}\" \"{bridge_path}\" --event session-end --project-dir \"$CLAUDE_PROJECT_DIR\" --run-root \"{normalized_run_root}\" --settings-file \"{settings_file}\"",
            }
        ]
    }


def group_identity(group: dict) -> dict:
    metadata = group.get("metadata")
    if isinstance(metadata, dict) and metadata.get("workflow") == "claude-yolo-until-done":
        return {
            "workflow": metadata.get("workflow"),
            "hook_role": metadata.get("hook_role"),
            "run_root": metadata.get("run_root"),
        }
    return group


def upsert_event_hooks(settings: dict, event_name: str, matcher_group: dict) -> None:
    hooks_root = settings.setdefault("hooks", {})
    event_list = hooks_root.setdefault(event_name, [])
    new_key = json.dumps(group_identity(matcher_group), sort_keys=True, ensure_ascii=True)
    for idx, existing in enumerate(event_list):
        if json.dumps(group_identity(existing), sort_keys=True, ensure_ascii=True) == new_key:
            event_list[idx] = matcher_group
            return
    event_list.append(matcher_group)


def remove_event_hooks(settings: dict, event_name: str, matcher_group: dict) -> None:
    hooks_root = settings.get("hooks", {})
    event_list = hooks_root.get(event_name, [])
    target_key = json.dumps(group_identity(matcher_group), sort_keys=True, ensure_ascii=True)
    kept = [group for group in event_list if json.dumps(group_identity(group), sort_keys=True, ensure_ascii=True) != target_key]
    if kept:
        hooks_root[event_name] = kept
    elif event_name in hooks_root:
        del hooks_root[event_name]
    if not hooks_root and "hooks" in settings:
        del settings["hooks"]


def install_hook_set(settings_path: Path, python_exe: Path, bridge_path: Path, run_root: str, settings_file: str) -> dict:
    settings = load_json(settings_path)
    normalized_run_root = normalize_run_root(run_root)
    upsert_event_hooks(settings, "SessionStart", build_session_start_group(python_exe, bridge_path, normalized_run_root))
    upsert_event_hooks(settings, "Stop", build_stop_group(python_exe, bridge_path, normalized_run_root))
    upsert_event_hooks(settings, "SessionEnd", build_session_end_group(python_exe, bridge_path, normalized_run_root, settings_file))
    workflow_markers(settings)[normalized_run_root] = {
        "workflow": "claude-yolo-until-done",
        "run_root": normalized_run_root,
        "bridge_path": str(bridge_path),
        "settings_file": settings_file,
        "installed_with_python": str(python_exe),
    }
    write_json(settings_path, settings)
    return settings


def uninstall_hook_set(settings_path: Path, python_exe: Path, bridge_path: Path, run_root: str, settings_file: str) -> dict:
    settings = load_json(settings_path)
    normalized_run_root = normalize_run_root(run_root)
    marker_root = settings.get("claudeYoloUntilDone", {})
    marker_runs = marker_root.get("runs", {}) if isinstance(marker_root, dict) else {}
    marker = marker_runs.get(normalized_run_root, {}) if isinstance(marker_runs, dict) else {}
    marker_settings_file = str(marker.get("settings_file", settings_file))
    remove_event_hooks(settings, "SessionStart", build_session_start_group(python_exe, bridge_path, normalized_run_root))
    remove_event_hooks(settings, "Stop", build_stop_group(python_exe, bridge_path, normalized_run_root))
    remove_event_hooks(settings, "SessionEnd", build_session_end_group(python_exe, bridge_path, normalized_run_root, marker_settings_file))
    if isinstance(marker_runs, dict) and normalized_run_root in marker_runs:
        del marker_runs[normalized_run_root]
    if isinstance(marker_root, dict) and not marker_root.get("runs"):
        del settings["claudeYoloUntilDone"]
    write_json(settings_path, settings)
    return settings


def main() -> int:
    print("This module is intended to be imported, not executed directly.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

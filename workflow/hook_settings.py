#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from lifecycle import compute_certification_hash


@contextmanager
def settings_lock(path: Path):
    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    write_json_if_changed(path, payload)


def write_json_if_changed(path: Path, payload: dict) -> None:
    rendered = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False)
    temp_path = Path(temp_file.name)
    try:
        with temp_file:
            temp_file.write(rendered)
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


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
            "hook_namespace": "claude-yolo",
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
            "hook_namespace": "claude-yolo",
        },
        "hooks": [
            {
                "type": "command",
                "command": f"\"{python_exe}\" \"{bridge_path}\" --event stop --project-dir \"$CLAUDE_PROJECT_DIR\" --run-root \"{normalized_run_root}\"",
            }
        ],
    }


def build_user_prompt_submit_group(python_exe: Path, bridge_path: Path, run_root: str) -> dict:
    normalized_run_root = normalize_run_root(run_root)
    return {
        "metadata": {
            "workflow": "claude-yolo-until-done",
            "hook_role": "UserPromptSubmit",
            "run_root": normalized_run_root,
            "hook_namespace": "claude-yolo",
        },
        "hooks": [
            {
                "type": "command",
                "command": f"\"{python_exe}\" \"{bridge_path}\" --event user-prompt-submit --project-dir \"$CLAUDE_PROJECT_DIR\" --run-root \"{normalized_run_root}\"",
            }
        ],
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


def prune_workflow_hooks_for_run_root(settings: dict, run_root: str, allowed_roles: set[str]) -> None:
    hooks_root = settings.get("hooks", {})
    if not isinstance(hooks_root, dict):
        return
    empty_events: list[str] = []
    for event_name, event_list in hooks_root.items():
        if not isinstance(event_list, list):
            continue
        kept = []
        for group in event_list:
            metadata = group.get("metadata") if isinstance(group, dict) else None
            if not isinstance(metadata, dict):
                kept.append(group)
                continue
            if metadata.get("workflow") != "claude-yolo-until-done":
                kept.append(group)
                continue
            if metadata.get("run_root") != run_root:
                kept.append(group)
                continue
            if metadata.get("hook_role") in allowed_roles:
                kept.append(group)
        if kept:
            hooks_root[event_name] = kept
        else:
            empty_events.append(event_name)
    for event_name in empty_events:
        del hooks_root[event_name]
    if not hooks_root and "hooks" in settings:
        del settings["hooks"]



def installed_hook_groups(settings: dict, run_root: str) -> list[dict]:
    hooks_root = settings.get("hooks", {})
    if not isinstance(hooks_root, dict):
        return []
    groups: list[dict] = []
    for event_name in sorted(hooks_root):
        event_list = hooks_root.get(event_name)
        if not isinstance(event_list, list):
            continue
        for group in event_list:
            metadata = group.get("metadata") if isinstance(group, dict) else None
            if not isinstance(metadata, dict):
                continue
            if metadata.get("workflow") != "claude-yolo-until-done":
                continue
            if metadata.get("run_root") != run_root:
                continue
            groups.append({"event": event_name, "group": group})
    return groups



def hook_config_hash(groups: list[dict]) -> str:
    return compute_certification_hash(groups)



def installed_hook_config_hash(settings: dict, run_root: str) -> str:
    return hook_config_hash(installed_hook_groups(settings, run_root))


def install_hook_set(settings_path: Path, python_exe: Path, bridge_path: Path, run_root: str) -> dict:
    with settings_lock(settings_path):
        settings = load_json(settings_path)
        normalized_run_root = normalize_run_root(run_root)
        prune_workflow_hooks_for_run_root(settings, normalized_run_root, {"SessionStart", "Stop", "UserPromptSubmit"})
        upsert_event_hooks(settings, "SessionStart", build_session_start_group(python_exe, bridge_path, normalized_run_root))
        upsert_event_hooks(settings, "Stop", build_stop_group(python_exe, bridge_path, normalized_run_root))
        upsert_event_hooks(
            settings,
            "UserPromptSubmit",
            build_user_prompt_submit_group(python_exe, bridge_path, normalized_run_root),
        )
        workflow_markers(settings)[normalized_run_root] = {
            "workflow": "claude-yolo-until-done",
            "run_root": normalized_run_root,
        }
        write_json_if_changed(settings_path, settings)
        return settings


def uninstall_hook_set(settings_path: Path, python_exe: Path, bridge_path: Path, run_root: str) -> dict:
    with settings_lock(settings_path):
        settings = load_json(settings_path)
        normalized_run_root = normalize_run_root(run_root)
        marker_root = settings.get("claudeYoloUntilDone", {})
        marker_runs = marker_root.get("runs", {}) if isinstance(marker_root, dict) else {}
        remove_event_hooks(settings, "SessionStart", build_session_start_group(python_exe, bridge_path, normalized_run_root))
        remove_event_hooks(settings, "Stop", build_stop_group(python_exe, bridge_path, normalized_run_root))
        remove_event_hooks(
            settings,
            "UserPromptSubmit",
            build_user_prompt_submit_group(python_exe, bridge_path, normalized_run_root),
        )
        if isinstance(marker_runs, dict) and normalized_run_root in marker_runs:
            del marker_runs[normalized_run_root]
        if isinstance(marker_root, dict) and not marker_root.get("runs") and "claudeYoloUntilDone" in settings:
            del settings["claudeYoloUntilDone"]
        write_json_if_changed(settings_path, settings)
        return settings


def main() -> int:
    print("This module is intended to be imported, not executed directly.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

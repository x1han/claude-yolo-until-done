#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from bootstrap import bootstrap_run
from hook_settings import install_hook_set
from state import load_json, load_state, serialize_path, state_path, trace_path


ACTIVE_ENTRYPOINT = "cli"
HEADLESS_ENTRYPOINT = "print"


def read_process_chain() -> str:
    override = os.environ.get("CLAUDE_YOLO_PROCESS_CHAIN")
    if override is not None:
        return override
    try:
        result = subprocess.run(
            ["ps", "-o", "pid,ppid,args", "-p", str(os.getpid()), str(os.getppid())],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def verify_runtime() -> dict:
    entrypoint = os.environ.get("CLAUDE_CODE_ENTRYPOINT", "")
    if entrypoint == HEADLESS_ENTRYPOINT:
        raise SystemExit(
            "Unsupported headless claude -p runtime: Stop-hook blocking cannot keep an unfinished claude-yolo run alive in print mode. "
            "Use an interactive Claude Code session instead."
        )
    if entrypoint and entrypoint != ACTIVE_ENTRYPOINT:
        raise SystemExit(f"Unsupported Claude Code entrypoint: {entrypoint}")

    process_chain = read_process_chain()
    if "--dangerously-skip-permissions" not in process_chain:
        raise SystemExit("Could not positively verify --dangerously-skip-permissions for the current Claude Code session.")

    return {
        "entrypoint": entrypoint or ACTIVE_ENTRYPOINT,
        "process_chain": process_chain,
    }


def classify_run(run_root: Path) -> str:
    has_state = state_path(run_root).exists()
    has_trace = trace_path(run_root).exists()
    if has_state and has_trace:
        return "continue_run"
    if not has_state and not has_trace:
        return "new_run"
    raise SystemExit("Mixed run bundle state detected; state.json and trace.md must either both exist or both be absent.")


def load_current_checklist_task(checklist_path: Path, state: dict) -> dict:
    checklist = load_json(checklist_path)
    tasks = checklist.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise SystemExit(f"Invalid checklist artifact: {checklist_path}")

    current_task_id = state.get("task_id")
    for task in tasks:
        if isinstance(task, dict) and task.get("task_id") == current_task_id:
            return task

    raise SystemExit(f"Continue-run mismatch: could not find current task {current_task_id!r} in {checklist_path}")


def validate_continue_run_paths(state: dict, project_dir: Path, spec_path: Path, plan_path: Path) -> None:
    expected_spec_path = state.get("spec_path")
    expected_plan_path = state.get("plan_path")
    actual_spec_path = serialize_path(spec_path, project_dir)
    actual_plan_path = serialize_path(plan_path, project_dir)
    if expected_spec_path != actual_spec_path:
        raise SystemExit(
            "Continue-run mismatch: --spec does not match existing run bundle "
            f"(state spec_path={expected_spec_path!r}, provided={actual_spec_path!r})"
        )
    if expected_plan_path != actual_plan_path:
        raise SystemExit(
            "Continue-run mismatch: --plan does not match existing run bundle "
            f"(state plan_path={expected_plan_path!r}, provided={actual_plan_path!r})"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify and prepare a claude-yolo-until-done run before execution.")
    parser.add_argument("--project-dir", required=True, help="Target project directory")
    parser.add_argument("--spec", required=True, help="Approved spec path")
    parser.add_argument("--plan", required=True, help="Approved implementation plan path")
    parser.add_argument("--run-root", default=".yolo", help="Run root relative to the project directory")
    parser.add_argument("--settings-file", default=".claude/settings.local.json", help="Settings file path relative to the project directory")
    parser.add_argument("--goal", required=True, help="Run goal")
    parser.add_argument(
        "--success-criterion",
        action="append",
        dest="success_criteria",
        default=[],
        help="Success criterion for this run; repeat to provide multiple entries",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    spec_path = Path(args.spec).resolve()
    plan_path = Path(args.plan).resolve()
    run_root = (project_dir / args.run_root).resolve()
    settings_path = (project_dir / args.settings_file).resolve()
    bridge_path = Path(__file__).resolve().parent / "claude_hook_bridge.py"
    python_exe = Path(sys.executable).resolve()

    if not spec_path.exists():
        raise SystemExit(f"Spec not found: {spec_path}")
    if not plan_path.exists():
        raise SystemExit(f"Plan not found: {plan_path}")

    runtime = verify_runtime()
    classification = classify_run(run_root)

    if classification == "new_run":
        bootstrap_summary = bootstrap_run(
            spec_path=spec_path,
            plan_path=plan_path,
            run_root=run_root,
            goal=args.goal,
            success_criteria=args.success_criteria,
            repo_root=project_dir,
        )
        install_hook_set(settings_path, python_exe, bridge_path, args.run_root)
        payload = {
            "classification": classification,
            "action": "bootstrapped_and_installed",
            "run_root": bootstrap_summary["run_root"],
            "state_path": bootstrap_summary["state_path"],
            "trace_path": bootstrap_summary["trace_path"],
            "checklist_path": bootstrap_summary["checklist_path"],
            "runtime_entrypoint": runtime["entrypoint"],
        }
        print(json.dumps(payload, ensure_ascii=True))
        return 0

    checklist_path = run_root / "watcher_checklist.json"
    if not checklist_path.exists():
        raise SystemExit(f"Missing checklist artifact: {checklist_path}")

    state = load_state(run_root)
    validate_continue_run_paths(state, project_dir, spec_path, plan_path)
    current_checklist_task = load_current_checklist_task(checklist_path, state)
    if state.get("task_title") != current_checklist_task.get("task_title"):
        raise SystemExit(
            f"Continue-run mismatch: state task_title does not match current task in {checklist_path}"
        )
    if state.get("task_inputs") != current_checklist_task:
        raise SystemExit(
            f"Continue-run mismatch: state task_inputs do not match current task in {checklist_path}"
        )
    install_hook_set(settings_path, python_exe, bridge_path, args.run_root)
    payload = {
        "classification": classification,
        "action": "validated_and_installed",
        "run_root": str(run_root),
        "state_status": state.get("status"),
        "owner": state.get("owner"),
        "next_action": state.get("next_action"),
        "runtime_entrypoint": runtime["entrypoint"],
    }
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

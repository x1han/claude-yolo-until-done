#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from bootstrap import bootstrap_run, fail_if_unsupported_headless_mode
from checklist import build_checklist_from_state
from hook_settings import install_hook_set, installed_hook_config_hash, load_json as load_settings_json
from orchestrator import recover_dispatch_for_resume
from state import append_trace_event, build_current_task_view, build_loop_state, detect_dialogue_language, load_json, load_state, serialize_path, state_path, trace_path, transition_state, write_json
from validate_grill_docs import GrillDocsError, ensure_ready_for_execution


ACTIVE_ENTRYPOINT = "cli"
HEADLESS_ENTRYPOINT = "print"


def read_process_chain() -> str:
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
    fail_if_unsupported_headless_mode()
    entrypoint = os.environ.get("CLAUDE_CODE_ENTRYPOINT", "")
    if entrypoint and entrypoint != ACTIVE_ENTRYPOINT:
        raise SystemExit(f"Unsupported Claude Code entrypoint: {entrypoint}")

    process_chain = read_process_chain()
    skip_permissions_verified = "--dangerously-skip-permissions" in process_chain

    return {
        "entrypoint": entrypoint or ACTIVE_ENTRYPOINT,
        "process_chain": process_chain,
        "skip_permissions_verified": skip_permissions_verified,
        "warnings": [] if skip_permissions_verified else ["Could not positively verify --dangerously-skip-permissions for the current Claude Code session."],
    }


def classify_run(run_root: Path) -> str:
    has_state = state_path(run_root).exists()
    has_trace = trace_path(run_root).exists()
    if has_state:
        return "continue_run"
    if has_trace:
        raise SystemExit("Mixed run bundle state detected; trace.md exists without authoritative state.json.")
    return "new_run"


def require_state_version(state: dict) -> int:
    state_version = state.get("state_version")
    if not isinstance(state_version, int) or state_version < 1:
        raise SystemExit("Continue-run state is missing valid positive integer state_version.")
    return state_version


def validate_authoritative_task_state(state: dict) -> None:
    require_state_version(state)
    task_inputs = state.get("task_inputs")
    if not isinstance(task_inputs, dict) or not task_inputs:
        raise SystemExit("Continue-run state is missing task_inputs needed to validate watcher_checklist.json")

    task_id = str(state.get("task_id", "")).strip()
    task_title = str(state.get("task_title", "")).strip()
    input_task_id = str(task_inputs.get("task_id", "")).strip()
    input_task_title = str(task_inputs.get("task_title", "")).strip()

    if not task_id:
        raise SystemExit("Continue-run state is missing non-empty task_id needed to validate watcher_checklist.json")
    if not task_title:
        raise SystemExit("Continue-run state is missing non-empty task_title needed to validate watcher_checklist.json")
    if not input_task_id:
        raise SystemExit("Continue-run state is missing non-empty task_inputs.task_id needed to validate watcher_checklist.json")
    if not input_task_title:
        raise SystemExit("Continue-run state is missing non-empty task_inputs.task_title needed to validate watcher_checklist.json")
    if task_id != input_task_id:
        raise SystemExit("Continue-run mismatch: state task_id does not match task_inputs.task_id")
    if task_title != input_task_title:
        raise SystemExit("Continue-run mismatch: state task_title does not match task_inputs.task_title")



def load_current_checklist_task(checklist_path: Path, state: dict) -> dict:
    validate_authoritative_task_state(state)
    expected_current_task = build_current_task_view(state)
    expected_checklist = build_checklist_from_state(state)
    if not checklist_path.exists():
        write_json(checklist_path, expected_checklist)
        return expected_current_task

    checklist = load_json(checklist_path)
    if checklist != expected_checklist:
        write_json(checklist_path, expected_checklist)
        return expected_current_task

    return checklist.get("current_task", {})


def validate_grill_storm_bundle_if_present(project_dir: Path, spec_path: Path, plan_path: Path) -> None:
    docs_root = (project_dir / "docs").resolve()
    if spec_path != (docs_root / "spec.md").resolve() or plan_path != (docs_root / "plan.md").resolve():
        return
    try:
        ensure_ready_for_execution(project_dir, "docs")
    except GrillDocsError as error:
        raise SystemExit(f"grill-storm planning docs are not execution-ready: {error}") from error



def default_grill_storm_paths(project_dir: Path) -> tuple[Path, Path]:
    docs_root = project_dir / "docs"
    return (docs_root / "spec.md").resolve(), (docs_root / "plan.md").resolve()



def resolve_planning_paths(project_dir: Path, spec_arg: str | None, plan_arg: str | None) -> tuple[Path, Path, str]:
    if bool(spec_arg) != bool(plan_arg):
        raise SystemExit("--spec and --plan must be provided together, or both omitted to use default grill-storm docs.")
    if spec_arg and plan_arg:
        return Path(spec_arg).resolve(), Path(plan_arg).resolve(), "explicit"
    spec_path, plan_path = default_grill_storm_paths(project_dir)
    return spec_path, plan_path, "grill-storm"



def grill_storm_status_text(project_dir: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "grill_storm.py"), "--status", "--project-dir", str(project_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    text = (result.stdout or result.stderr).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    status = payload.get("status")
    if status in {"human_dialogue", "human_spec_review", "human_plan_review"}:
        return text + "\nmain session must ask the human and record approval with workflow/human_approvals.py before execution."
    return text



def require_planning_inputs_ready(project_dir: Path, spec_path: Path, plan_path: Path, planning_source: str) -> None:
    if planning_source == "grill-storm" and (not spec_path.exists() or not plan_path.exists()):
        raise SystemExit(
            "grill-storm planning docs are not initialized; run "
            "workflow/init_grill_docs.py --project-dir <project> --request <request> before execution."
        )

    if not spec_path.exists():
        raise SystemExit(f"Spec not found: {spec_path}")
    if not plan_path.exists():
        raise SystemExit(f"Plan not found: {plan_path}")

    try:
        validate_grill_storm_bundle_if_present(project_dir, spec_path, plan_path)
    except SystemExit as error:
        if planning_source != "grill-storm":
            raise
        status = grill_storm_status_text(project_dir)
        detail = str(error)
        if status:
            detail = f"{detail}\ngrill-storm status: {status}"
        raise SystemExit(detail) from error



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



def validate_continue_run_mode(state: dict, requested_mode: str, requested_loop: dict) -> None:
    existing_mode = str(state.get("mode", "acyclic")).strip() or "acyclic"
    if existing_mode != requested_mode:
        raise SystemExit(
            "Continue-run mismatch: --mode does not match existing run bundle "
            f"(state mode={existing_mode!r}, provided={requested_mode!r})"
        )

    existing_loop = state.get("loop")
    if not isinstance(existing_loop, dict):
        existing_loop = build_loop_state("acyclic") if existing_mode == "acyclic" else {}
    comparable_existing = {
        "enabled": existing_loop.get("enabled"),
        "max_iterations": existing_loop.get("max_iterations"),
        "stop_on_convergence": existing_loop.get("stop_on_convergence"),
    }
    comparable_requested = {
        "enabled": requested_loop.get("enabled"),
        "max_iterations": requested_loop.get("max_iterations"),
        "stop_on_convergence": requested_loop.get("stop_on_convergence"),
    }
    if comparable_existing != comparable_requested:
        raise SystemExit(
            "Continue-run mismatch: loop policy does not match existing run bundle "
            f"(state loop={comparable_existing!r}, provided={comparable_requested!r})"
        )



def persist_hook_config_hash(run_root: Path, hook_hash: str, state: dict | None = None) -> dict:
    current_state = load_state(run_root) if state is None else state
    if str(current_state.get("hook_config_hash", "")).strip() == hook_hash:
        return current_state

    def apply_transition(authoritative_state: dict, _: str) -> None:
        authoritative_state["hook_config_hash"] = hook_hash

    return transition_state(
        run_root,
        actor="preflight",
        action="persist_hook_config_hash",
        expected_version=require_state_version(current_state),
        apply_transition=apply_transition,
    )



def validate_installed_hook_config(settings_path: Path, run_root_arg: str, state: dict) -> None:
    settings = load_settings_json(settings_path)
    expected_hash = str(state.get("hook_config_hash", "")).strip()
    if not expected_hash:
        raise SystemExit("Continue-run state is missing hook_config_hash; hook integrity cannot be verified.")
    actual_hash = installed_hook_config_hash(settings, run_root_arg)
    if actual_hash != expected_hash:
        raise SystemExit(
            "Continue-run hook_config_hash mismatch: installed hooks for this run root no longer match state.json."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify and prepare a claude-yolo-until-done run before execution.")
    parser.add_argument("--project-dir", required=True, help="Target project directory")
    parser.add_argument("--spec", help="Approved spec path; omit with --plan to use default grill-storm docs")
    parser.add_argument("--plan", help="Approved implementation plan path; omit with --spec to use default grill-storm docs")
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
    parser.add_argument("--mode", choices=("acyclic", "loop"), default="acyclic", help="Execution mode; defaults to acyclic")
    parser.add_argument("--dialogue-language", default="", help="Explicit human dialogue language override, such as en or zh-CN")
    parser.add_argument("--latest-user-request", default="", help="Latest substantive user request for human dialogue language detection")
    parser.add_argument("--loop-max-iterations", type=int, default=None, help="Stop loop mode after this many iterations")
    parser.add_argument(
        "--loop-stop-on-convergence",
        action="store_true",
        help="Stop loop mode when convergence is reported",
    )
    args = parser.parse_args()
    try:
        requested_loop = build_loop_state(args.mode, args.loop_max_iterations, args.loop_stop_on_convergence)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    project_dir = Path(args.project_dir).resolve()
    spec_path, plan_path, planning_source = resolve_planning_paths(project_dir, args.spec, args.plan)
    run_root = (project_dir / args.run_root).resolve()
    settings_path = (project_dir / args.settings_file).resolve()
    bridge_path = Path(__file__).resolve().parent / "claude_hook_bridge.py"
    python_exe = Path(sys.executable).resolve()

    require_planning_inputs_ready(project_dir, spec_path, plan_path, planning_source)

    runtime = verify_runtime()
    classification = classify_run(run_root)
    try:
        dialogue_language = detect_dialogue_language(args.dialogue_language, args.latest_user_request)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    if classification == "new_run":
        bootstrap_summary = bootstrap_run(
            spec_path=spec_path,
            plan_path=plan_path,
            run_root=run_root,
            goal=args.goal,
            success_criteria=args.success_criteria,
            repo_root=project_dir,
            mode=args.mode,
            loop_max_iterations=args.loop_max_iterations,
            loop_stop_on_convergence=args.loop_stop_on_convergence,
            dialogue_language=dialogue_language,
        )
        settings = install_hook_set(settings_path, python_exe, bridge_path, args.run_root)
        persist_hook_config_hash(run_root, installed_hook_config_hash(settings, args.run_root))
        payload = {
            "classification": classification,
            "action": "bootstrapped_and_installed",
            "run_root": bootstrap_summary["run_root"],
            "state_path": bootstrap_summary["state_path"],
            "trace_path": bootstrap_summary["trace_path"],
            "checklist_path": bootstrap_summary["checklist_path"],
            "runtime_entrypoint": runtime["entrypoint"],
            "skip_permissions_verified": runtime["skip_permissions_verified"],
            "runtime_warnings": runtime["warnings"],
            "mode": args.mode,
            "loop": requested_loop,
            "dialogue_language": dialogue_language,
        }
        print(json.dumps(payload, ensure_ascii=True))
        return 0

    checklist_path = run_root / "watcher_checklist.json"
    state = load_state(run_root)
    expected_version = require_state_version(state)
    validate_continue_run_paths(state, project_dir, spec_path, plan_path)
    validate_continue_run_mode(state, args.mode, requested_loop)
    if args.dialogue_language:
        requested_language = dialogue_language.get("language", "")
        existing_language = state.get("dialogue_language") if isinstance(state.get("dialogue_language"), dict) else {}
        if requested_language != existing_language.get("language"):
            raise SystemExit(
                "Continue-run mismatch: --dialogue-language does not match existing run bundle "
                f"(state language={existing_language.get('language')!r}, provided={requested_language!r})"
            )
    validate_installed_hook_config(settings_path, args.run_root, state)
    current_checklist_task = load_current_checklist_task(checklist_path, state)
    if build_current_task_view(state) != current_checklist_task:
        raise SystemExit(
            f"Continue-run mismatch: state current task does not match current task in {checklist_path}"
        )
    settings = install_hook_set(settings_path, python_exe, bridge_path, args.run_root)
    installed_hook_hash = installed_hook_config_hash(settings, args.run_root)
    dispatch_recovery: dict[str, object] = {"result": "unchanged", "reason": "no continue-run mutation needed"}
    hook_hash_changed = str(state.get("hook_config_hash", "")).strip() != installed_hook_hash
    needs_dispatch_recovery = recover_dispatch_for_resume(dict(state)).get("result") != "unchanged"
    if hook_hash_changed or needs_dispatch_recovery:
        def apply_transition(current_state: dict, timestamp: str) -> None:
            nonlocal dispatch_recovery
            if hook_hash_changed:
                current_state["hook_config_hash"] = installed_hook_hash
            dispatch_recovery = recover_dispatch_for_resume(current_state, now=timestamp)

        state = transition_state(
            run_root,
            actor="preflight",
            action="continue_run_recovery",
            expected_version=expected_version,
            apply_transition=apply_transition,
        )
    if dispatch_recovery["result"] != "unchanged":
        append_trace_event(
            run_root,
            f"preflight recovered expired dispatch claim: result={dispatch_recovery['result']}; "
            f"owner={dispatch_recovery.get('expired_owner', '')}; role={dispatch_recovery.get('role', '')}; "
            f"action={dispatch_recovery.get('action', '')}",
        )
    payload = {
        "classification": classification,
        "action": "validated_and_installed",
        "run_root": str(run_root),
        "state_status": state.get("status"),
        "owner": state.get("owner"),
        "next_action": state.get("next_action"),
        "runtime_entrypoint": runtime["entrypoint"],
        "skip_permissions_verified": runtime["skip_permissions_verified"],
        "runtime_warnings": runtime["warnings"],
        "dispatch_recovery": dispatch_recovery,
    }
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

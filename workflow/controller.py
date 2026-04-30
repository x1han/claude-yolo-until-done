#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_STAGES = (
    {"id": "stage-01", "hook_stage": 1, "next_action": "validate runtime and bundle", "complete_checkoffs": ["runtime-ready", "runtime-context-recorded", "bundle-ready"]},
    {"id": "stage-02", "hook_stage": 2, "next_action": "load run state and claim exactly one next action", "complete_checkoffs": []},
    {"id": "stage-03", "hook_stage": 3, "next_action": "execute current fix loop and rerun required verification", "complete_checkoffs": ["current-gate-verified", "report-updated"]},
    {"id": "stage-04", "hook_stage": 4, "next_action": "classify blockers and continue unless human-blocked is justified", "complete_checkoffs": []},
    {"id": "stage-05", "hook_stage": 5, "next_action": "run final acceptance and certify completion", "complete_checkoffs": ["completion-certified"]},
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def gate_map(gates_payload: dict) -> dict[str, dict]:
    return {gate["id"]: gate for gate in gates_payload.get("gates", []) if isinstance(gate, dict) and "id" in gate}


def checkoff_map(checkoffs_payload: dict) -> dict[str, dict]:
    return {checkoff["id"]: checkoff for checkoff in checkoffs_payload.get("checkoffs", []) if isinstance(checkoff, dict) and "id" in checkoff}


def stage_definitions(run_root: Path) -> list[dict]:
    manifest_path = run_root / "workflow_manifest.json"
    if manifest_path.exists():
        payload = load_json(manifest_path)
        stages = payload.get("stages")
        if isinstance(stages, list) and stages:
            return stages
    return list(DEFAULT_STAGES)


def stage_sequence(run_root: Path) -> tuple[str, ...]:
    return tuple(stage["id"] for stage in stage_definitions(run_root))


def stage_map(run_root: Path) -> dict[str, dict]:
    return {stage["id"]: stage for stage in stage_definitions(run_root)}


def next_action_map(run_root: Path) -> dict[str, str]:
    return {stage["id"]: stage.get("next_action", stage["id"]) for stage in stage_definitions(run_root)}


def checkoff_completion_map(run_root: Path) -> dict[str, list[str]]:
    return {stage["id"]: list(stage.get("complete_checkoffs", [])) for stage in stage_definitions(run_root)}


def stage_hook_number(run_root: Path, stage_name: str) -> int:
    stage = stage_map(run_root).get(stage_name)
    if not isinstance(stage, dict):
        raise KeyError(f"Unknown stage id: {stage_name}")
    hook_stage = stage.get("hook_stage")
    if not isinstance(hook_stage, int):
        raise ValueError(f"Stage {stage_name} missing integer hook_stage")
    return hook_stage


def stage_name_for_hook(run_root: Path, hook_stage: int) -> str:
    for stage in stage_definitions(run_root):
        if stage.get("hook_stage") == hook_stage:
            return stage["id"]
    return f"stage-{hook_stage:02d}"


def set_gate_passed(gates_payload: dict, gate_id: str, passed: bool) -> None:
    for gate in gates_payload.get("gates", []):
        if gate.get("id") == gate_id:
            gate["passed"] = passed
            return


def set_checkoff_complete(checkoffs_payload: dict, checkoff_id: str, complete: bool) -> None:
    for checkoff in checkoffs_payload.get("checkoffs", []):
        if checkoff.get("id") == checkoff_id:
            checkoff["complete"] = complete
            return


def infer_current_stage(gates_payload: dict, run_root: Path) -> str:
    gates = gate_map(gates_payload)
    sequence = stage_sequence(run_root)
    for stage_name in sequence:
        if not gates.get(stage_name, {}).get("passed", False):
            return stage_name
    return sequence[-1]


def next_stage_name(stage_name: str, run_root: Path) -> str:
    sequence = stage_sequence(run_root)
    try:
        idx = sequence.index(stage_name)
    except ValueError:
        return stage_name
    if idx >= len(sequence) - 1:
        return stage_name
    return sequence[idx + 1]


def sync_checkoffs_for_stage(checkoffs_payload: dict, stage_name: str, passed: bool, run_root: Path) -> None:
    if not passed:
        return
    for checkoff_id in checkoff_completion_map(run_root).get(stage_name, []):
        set_checkoff_complete(checkoffs_payload, checkoff_id, True)


def checkoff_completion_ready(checkoffs_payload: dict) -> bool:
    checkoffs = checkoff_map(checkoffs_payload)
    return all(bool(item.get("complete")) for item in checkoffs.values())


def run_hook(controller_dir: Path, run_root: Path, stage_number: int) -> tuple[int, Path]:
    script = controller_dir.parent / "hooks" / "run_gate.py"
    cmd = [sys.executable, str(script), "--stage", str(stage_number), "--run-root", str(run_root)]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.stdout.strip():
        report_path = Path(completed.stdout.strip().splitlines()[-1])
    else:
        report_path = run_root / "hooks" / f"gate_{stage_number:02d}_report.json"
    return completed.returncode, report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Advance and validate a claude-yolo-until-done run bundle.")
    parser.add_argument("--run-root", default="artifacts/yolo", help="Path to the yolo run bundle root")
    parser.add_argument("--stage", type=int, help="Optional explicit stage number to validate")
    parser.add_argument("--write-status", action="store_true", help="Write controller_status.json under the run root")
    args = parser.parse_args()

    controller_dir = Path(__file__).resolve().parent
    run_root = Path(args.run_root).resolve()
    run_state_path = run_root / "run_state.json"
    gates_path = run_root / "gates.json"
    checkoffs_path = run_root / "checkoffs.json"

    run_state = load_json(run_state_path)
    gates_payload = load_json(gates_path)
    checkoffs_payload = load_json(checkoffs_path)

    if args.stage is not None:
        stage_number = args.stage
        stage_name = stage_name_for_hook(run_root, stage_number)
    else:
        stage_name = infer_current_stage(gates_payload, run_root)
        stage_number = stage_hook_number(run_root, stage_name)

    exit_code, report_path = run_hook(controller_dir, run_root, stage_number)
    hook_report = load_json(report_path) if report_path.exists() else {"passed": False, "failures": [{"name": "missing_hook_report", "detail": str(report_path)}]}
    passed = bool(hook_report.get("passed"))

    set_gate_passed(gates_payload, stage_name, passed)
    sync_checkoffs_for_stage(checkoffs_payload, stage_name, passed, run_root)
    next_actions = next_action_map(run_root)
    current_visible_stage = stage_name
    if passed and stage_name != stage_sequence(run_root)[-1]:
        current_visible_stage = next_stage_name(stage_name, run_root)
    run_state["current_stage"] = current_visible_stage
    run_state["next_action"] = next_actions[current_visible_stage]
    run_state["updated_at"] = utc_now()
    run_state["completion_ready"] = stage_name == stage_sequence(run_root)[-1] and passed and checkoff_completion_ready(checkoffs_payload)
    if stage_name == stage_sequence(run_root)[-1] and passed:
        run_state["workflow_active"] = False
        run_state["stop_forbidden"] = False
        run_state["lifecycle_state"] = "completed"

    write_json(gates_path, gates_payload)
    write_json(run_state_path, run_state)
    write_json(checkoffs_path, checkoffs_payload)

    status = {
        "stage": stage_name,
        "current_stage": run_state["current_stage"],
        "passed": passed,
        "report_path": str(report_path),
        "updated_at": utc_now(),
        "next_action": run_state["next_action"],
        "completion_ready": run_state["completion_ready"],
    }

    if args.write_status:
        write_json(run_root / "controller_status.json", status)

    print(json.dumps(status, ensure_ascii=True))
    return 0 if exit_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

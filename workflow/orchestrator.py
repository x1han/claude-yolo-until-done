from __future__ import annotations

from pathlib import Path

from state import append_trace_event, utc_now, write_state


DISPATCHED_STATUS = "dispatched"
IDLE_STATUS = "idle"


def _find_next_checklist_task(checklist: dict | None, current_task_id: str) -> dict | None:
    tasks = checklist.get("tasks", []) if isinstance(checklist, dict) else []
    for index, task in enumerate(tasks):
        if not isinstance(task, dict) or task.get("task_id") != current_task_id:
            continue
        next_index = index + 1
        if next_index >= len(tasks) or not isinstance(tasks[next_index], dict):
            return None
        return tasks[next_index]
    return None


def resume_after_human(state: dict, guidance: str, checklist: dict | None = None) -> dict:
    current_task_id = state["task_id"]
    notes = list(state.get("task_handoff_notes", []))
    notes.append(guidance)

    resumed = dict(state)
    resumed.update(
        {
            "gate_attempt": 0,
            "gate_reason": "",
            "owner": "worker",
            "next_action": "worker_update",
            "dispatch_status": IDLE_STATUS,
            "last_dispatch": {},
            "worker_request": "",
            "worker_question": "",
            "verification_command": "",
            "verification_result": "",
            "blocked_for_human": False,
            "human_handoff": {},
            "requested_role": "worker",
            "task_handoff_notes": notes,
        }
    )
    next_task = _find_next_checklist_task(checklist, current_task_id)
    if next_task is not None:
        next_task_id = next_task["task_id"]
        resumed["task_id"] = next_task_id
        resumed["gate_id"] = f"gate-{next_task_id}"
        resumed["task_title"] = next_task.get("task_title", resumed.get("task_title", ""))
        resumed["task_inputs"] = dict(next_task)
        return resumed

    if checklist is None:
        prefix, number = current_task_id.rsplit("-", 1)
        next_task_id = f"{prefix}-{int(number) + 1:03d}"
        resumed["task_id"] = next_task_id
        resumed["gate_id"] = f"gate-{next_task_id}"

    return resumed


def build_task_packet(state: dict, role: str) -> dict:
    inputs = dict(state.get("task_inputs", {}))
    return {
        "role": role,
        "task_id": state.get("task_id", ""),
        "task_title": state.get("task_title", ""),
        "task_goal": state.get("task_goal", ""),
        "task_scope": list(state.get("task_scope", [])),
        "plan_task_text": inputs.get("plan_task_text", ""),
        "spec_excerpt": inputs.get("spec_excerpt", ""),
        "checklist_items": list(inputs.get("checklist_items", [])),
        "task_inputs": inputs,
        "task_handoff_notes": list(state.get("task_handoff_notes", [])),
        "worker_request": state.get("worker_request", ""),
        "worker_question": state.get("worker_question", ""),
        "human_handoff": dict(state.get("human_handoff", {})),
        "gate_id": state["gate_id"],
        "gate_attempt": state["gate_attempt"],
        "gate_max_attempts": state["gate_max_attempts"],
        "gate_reason": state.get("gate_reason", ""),
        "verification_command": state.get("verification_command", ""),
        "verification_result": state.get("verification_result", ""),
    }


def next_step(state: dict) -> dict:
    if state.get("blocked_for_human"):
        role = "human"
    elif state.get("worker_request") == "need_helper":
        role = "helper"
    else:
        role = state.get("requested_role", "worker")

    return {
        "role": role,
        "gate_attempt": state.get("gate_attempt", 0),
    }


def mark_dispatch_pending(state: dict, requested_role: str) -> None:
    state["requested_role"] = requested_role
    state["dispatch_status"] = IDLE_STATUS
    state["last_dispatch"] = {}


def orchestrate(run_root: Path, state: dict) -> dict:
    if state.get("dispatch_status") != IDLE_STATUS:
        return {"result": "no_op", "reason": f"dispatch_status={state.get('dispatch_status', '')}"}

    decision = next_step(state)
    role = decision["role"]
    packet = build_task_packet(state, role)
    dispatch = {
        "role": role,
        "task_id": state.get("task_id", ""),
        "gate_id": state.get("gate_id", ""),
        "next_action": state.get("next_action", ""),
        "dispatched_at": utc_now(),
        "task_packet": packet,
    }
    state["dispatch_status"] = DISPATCHED_STATUS
    state["last_dispatch"] = dispatch
    write_state(run_root, state)
    append_trace_event(
        run_root,
        f"orchestrator dispatch: role={role}; task_id={dispatch['task_id']}; next_action={dispatch['next_action']}",
    )
    return {"result": "dispatched", **dispatch}

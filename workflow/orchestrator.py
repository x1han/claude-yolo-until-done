from __future__ import annotations


def _increment_task_id(task_id: str) -> str:
    prefix, number = task_id.rsplit("-", 1)
    return f"{prefix}-{int(number) + 1:03d}"


def resume_after_human(state: dict, guidance: str) -> dict:
    next_task_id = _increment_task_id(state["task_id"])
    notes = list(state.get("task_handoff_notes", []))
    notes.append(guidance)

    resumed = dict(state)
    resumed.update(
        {
            "task_id": next_task_id,
            "gate_id": f"gate-{next_task_id}",
            "gate_attempt": 0,
            "gate_reason": "",
            "owner": "worker",
            "next_action": "worker_update",
            "dispatch_status": "idle",
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
    return resumed


def build_task_packet(state: dict, role: str) -> dict:
    inputs = dict(state.get("task_inputs", {}))
    return {
        "role": role,
        "task_id": state["task_id"],
        "task_title": state["task_title"],
        "task_goal": state["task_goal"],
        "task_scope": list(state.get("task_scope", [])),
        "plan_task_text": inputs.get("plan_task_text", ""),
        "spec_excerpt": inputs.get("spec_excerpt", ""),
        "checklist_items": list(inputs.get("checklist_items", [])),
        "gate_id": state["gate_id"],
        "gate_attempt": state["gate_attempt"],
        "gate_max_attempts": state["gate_max_attempts"],
        "gate_reason": state.get("gate_reason", ""),
        "task_handoff_notes": list(state.get("task_handoff_notes", [])),
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

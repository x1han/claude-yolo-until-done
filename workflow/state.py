from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


STATE_FILE_NAME = "state.json"
TRACE_FILE_NAME = "trace.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def serialize_path(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = repo_root.resolve()
    try:
        return str(resolved_path.relative_to(resolved_root))
    except ValueError:
        return str(resolved_path)


def apply_orchestration_defaults(state: dict) -> None:
    task_id = state.get("task_id") or "task-001"
    state["task_id"] = task_id
    state.setdefault("gate_id", f"gate-{task_id}")
    state.setdefault("gate_attempt", 0)
    state.setdefault("gate_max_attempts", 5)
    state.setdefault("requested_role", "worker")
    state.setdefault("dispatch_status", "idle")
    state.setdefault("last_dispatch", {})
    state.setdefault("worker_request", "")
    state.setdefault("worker_question", "")
    state.setdefault("human_handoff", {})
    state.setdefault("task_handoff_notes", [])
    state.setdefault("task_scope", [])
    state.setdefault("task_goal", state.get("goal", ""))
    state.setdefault("blocked_for_human", False)
    state.setdefault("allow_need_human", True)



def build_state(
    template_path: Path,
    goal: str,
    success_criteria: list[str],
    plan_path: Path,
    spec_path: Path,
    repo_root: Path,
) -> dict:
    state = load_json(template_path)
    state["goal"] = goal
    state["success_criteria"] = success_criteria
    state["status"] = "active"
    state["worker_claim"] = ""
    state["files_changed"] = []
    state["verification_command"] = ""
    state["verification_result"] = ""
    state["submitted_at"] = ""
    state["review"] = {}
    state["reviewed_at"] = ""
    state["owner"] = "worker"
    state["next_action"] = "worker_update"
    state["cleanup_required"] = False
    apply_orchestration_defaults(state)
    state["plan_path"] = serialize_path(plan_path, repo_root)
    state["spec_path"] = serialize_path(spec_path, repo_root)
    state["updated_at"] = utc_now()
    return state


def build_trace(template_path: Path, goal: str, success_criteria: list[str]) -> str:
    template = template_path.read_text(encoding="utf-8")
    bullets = "\n".join(f"- {criterion}" for criterion in success_criteria)
    return template.format(goal=goal, success_criteria=bullets, timestamp=utc_now())


def state_path(run_root: Path) -> Path:
    return run_root / STATE_FILE_NAME


def trace_path(run_root: Path) -> Path:
    return run_root / TRACE_FILE_NAME


def load_state(run_root: Path) -> dict:
    return load_json(state_path(run_root))


def write_state(run_root: Path, payload: dict) -> None:
    write_json(state_path(run_root), payload)


def format_trace_value(value: str | list[str]) -> str:
    if isinstance(value, list):
        return "; ".join(value) if value else "none"
    return value


def append_trace_event(run_root: Path, line: str) -> None:
    path = trace_path(run_root)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    newline = "" if existing.endswith("\n") or not existing else "\n"
    path.write_text(f"{existing}{newline}- {utc_now()} {line}\n", encoding="utf-8")

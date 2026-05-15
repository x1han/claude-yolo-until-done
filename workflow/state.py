from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import fcntl


LOCK_FILE_NAME = ".state.lock"
STATE_FILE_NAME = "state.json"
TRACE_FILE_NAME = "trace.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8")
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def write_json(path: Path, payload: dict) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def write_text(path: Path, text: str) -> None:
    atomic_write_text(path, text)


def serialize_path(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = repo_root.resolve()
    try:
        return str(resolved_path.relative_to(resolved_root))
    except ValueError:
        return str(resolved_path)


def build_current_task_view(state: dict) -> dict:
    return {
        "task_id": state.get("task_id", ""),
        "task_title": state.get("task_title", ""),
        "task_inputs": state.get("task_inputs", {}),
    }


def sync_current_task_view(state: dict) -> None:
    state["current_task"] = build_current_task_view(state)


def sync_task_derived_fields(state: dict) -> None:
    task_id = state.get("task_id") or "task-001"
    state["task_id"] = task_id
    state.setdefault("gate_id", f"gate-{task_id}")
    if not state.get("task_goal"):
        state["task_goal"] = state.get("goal", "")
    sync_current_task_view(state)


def build_resume_target(state: dict) -> dict:
    role = state.get("requested_role") or state.get("owner") or "worker"
    action = state.get("next_action", "")
    if not isinstance(role, str) or not role.strip():
        return {}
    if not isinstance(action, str) or not action.strip() or action == "human_handoff":
        return {}
    return {"role": role, "action": action}


def apply_orchestration_defaults(state: dict) -> None:
    task_id = state.get("task_id") or "task-001"
    state["task_id"] = task_id
    state.setdefault("state_version", 1)
    state.setdefault("task_title", "")
    state.setdefault("task_inputs", {})
    state.setdefault("next_action", "worker_update")
    state.setdefault("requested_role", "worker")
    state.setdefault("dispatch_status", "pending")
    state.setdefault("dispatch_intent", {"role": "worker", "action": "worker_update"})
    state.setdefault("dispatch_claim", {})
    state.setdefault("dispatch_generation", 0)
    state.setdefault("supervision", {
        "last_token_io_at": "",
        "last_progress_at": "",
        "stall_timeout_seconds": 600,
        "retry_limit": 3,
        "retry_count": 0,
        "last_recovery_at": "",
        "last_recovery_reason": "",
    })
    state.setdefault("last_transition_id", "")
    state.setdefault("last_transition_actor", "")
    state.setdefault("hook_config_hash", "")
    state.setdefault("task_packet_hash", "")
    state.setdefault("certification_hash", "")
    state.setdefault("certification", {})
    state.setdefault("retry_budget", {"worker": 0, "helper": 0, "backoff_until": ""})
    state.setdefault("gate_attempt", 0)
    state.setdefault("gate_max_attempts", 5)
    state.setdefault("last_dispatch", {})
    state.setdefault("worker_request", "")
    state.setdefault("worker_question", "")
    state.setdefault("human_handoff", {})
    state.setdefault("resume_target", {})
    state.setdefault("task_handoff_notes", [])
    state.setdefault("task_scope", [])
    state.setdefault("blocked_for_human", False)
    state.setdefault("allow_need_human", True)
    state.setdefault("dialogue_language", default_dialogue_language())
    sync_task_derived_fields(state)



VALID_MODES = {"acyclic", "loop"}


def default_dialogue_language() -> dict:
    return {
        "source": "default",
        "language": "en",
        "confidence": 0.0,
    }


def normalize_dialogue_language(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {"zh", "zh-cn", "zh-hans", "chinese", "中文", "汉语", "漢語"}:
        return "zh-CN"
    if normalized in {"en", "en-us", "en-gb", "english"}:
        return "en"
    return ""


def detect_dialogue_language(explicit_override: str = "", latest_user_request: str = "") -> dict:
    if explicit_override.strip():
        explicit_language = normalize_dialogue_language(explicit_override)
        if not explicit_language:
            raise ValueError(f"Unsupported dialogue language: {explicit_override}")
        return {
            "source": "explicit",
            "language": explicit_language,
            "confidence": 1.0,
        }

    request = latest_user_request.strip()
    if request:
        cjk_count = sum(1 for char in request if "一" <= char <= "鿿")
        ascii_letter_count = sum(1 for char in request if char.isascii() and char.isalpha())
        if cjk_count > 0 and cjk_count >= ascii_letter_count / 2:
            return {
                "source": "latest_user_request",
                "language": "zh-CN",
                "confidence": 0.8,
            }
        if ascii_letter_count > 0:
            return {
                "source": "latest_user_request",
                "language": "en",
                "confidence": 0.8,
            }

    return default_dialogue_language()


def default_loop_state() -> dict:
    return {
        "enabled": False,
        "iteration": 1,
        "max_iterations": None,
        "stop_on_convergence": False,
        "converged": False,
        "stop_reason": "",
        "iteration_evidence": [],
        "latest_iteration_evidence": {},
        "acceleration_review": {},
    }


def build_loop_state(mode: str, max_iterations: int | None = None, stop_on_convergence: bool = False) -> dict:
    if mode not in VALID_MODES:
        raise ValueError(f"Unsupported execution mode: {mode}")
    if mode == "acyclic":
        if max_iterations is not None or stop_on_convergence:
            raise ValueError("Loop stop policy is only valid when mode is loop.")
        return default_loop_state()
    if max_iterations is None and not stop_on_convergence:
        raise ValueError("Loop mode requires --loop-max-iterations, --loop-stop-on-convergence, or both.")
    if max_iterations is None and stop_on_convergence:
        max_iterations = 10
    if max_iterations is not None and max_iterations < 1:
        raise ValueError("Loop max_iterations must be a positive integer.")
    payload = default_loop_state()
    payload["enabled"] = True
    payload["max_iterations"] = max_iterations
    payload["stop_on_convergence"] = stop_on_convergence
    return payload


def build_state(
    template_path: Path,
    goal: str,
    success_criteria: list[str],
    plan_path: Path,
    spec_path: Path,
    repo_root: Path,
    mode: str = "acyclic",
    loop_max_iterations: int | None = None,
    loop_stop_on_convergence: bool = False,
    dialogue_language: dict | None = None,
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
    state["mode"] = mode
    state["loop"] = build_loop_state(mode, loop_max_iterations, loop_stop_on_convergence)
    if dialogue_language is not None:
        state["dialogue_language"] = dialogue_language
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


def lock_path(run_root: Path) -> Path:
    return run_root / LOCK_FILE_NAME


def state_path(run_root: Path) -> Path:
    return run_root / STATE_FILE_NAME


def trace_path(run_root: Path) -> Path:
    return run_root / TRACE_FILE_NAME


@contextmanager
def hold_run_lock(run_root: Path) -> Iterator[None]:
    path = lock_path(run_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_state(run_root: Path) -> dict:
    return load_json(state_path(run_root))


def write_state(run_root: Path, payload: dict) -> None:
    write_json(state_path(run_root), payload)


class StaleStateVersionError(RuntimeError):
    def __init__(self, expected_version: int, actual_version: int) -> None:
        super().__init__(f"Stale state version: expected {expected_version}, found {actual_version}.")
        self.expected_version = expected_version
        self.actual_version = actual_version


def transition_state(
    run_root: Path,
    *,
    actor: str,
    action: str,
    expected_version: int,
    apply_transition: Callable[[dict, str], None],
    progress_transition: Callable[[dict, str], None] | None = None,
) -> dict:
    with hold_run_lock(run_root):
        state = load_state(run_root)
        actual_version = state.get("state_version", 1)
        if expected_version != actual_version:
            raise StaleStateVersionError(expected_version, actual_version)

        timestamp = utc_now()
        apply_transition(state, timestamp)
        if progress_transition is not None:
            progress_transition(state, timestamp)

        next_version = actual_version + 1
        state["state_version"] = next_version
        state["last_transition_actor"] = actor
        state["last_transition_id"] = f"{actor}:{action}:{next_version}"
        state["updated_at"] = timestamp
        write_state(run_root, state)
        return state


def format_trace_value(value: str | list[str]) -> str:
    if isinstance(value, list):
        return "; ".join(value) if value else "none"
    return value


def append_trace_event(run_root: Path, line: str) -> None:
    path = trace_path(run_root)
    with hold_run_lock(run_root):
        with path.open("a+", encoding="utf-8") as handle:
            handle.seek(0, os.SEEK_END)
            has_content = handle.tell() > 0
            if has_content:
                handle.seek(handle.tell() - 1)
                if handle.read(1) != "\n":
                    handle.seek(0, os.SEEK_END)
                    handle.write("\n")
                else:
                    handle.seek(0, os.SEEK_END)
            handle.write(f"- {utc_now()} {line}\n")

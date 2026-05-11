from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from state import atomic_write_text, utc_now

AGENT_SESSIONS_FILE_NAME = "agent_sessions.json"
AGENTS_DIR_NAME = "agents"
ROLE_NAMES = ("worker", "watcher", "helper", "interviewer", "planner")
SESSION_STATUSES = {"", "active", "replaced", "failed"}


def agent_sessions_path(run_root: Path) -> Path:
    return run_root / AGENT_SESSIONS_FILE_NAME


def agents_dir(run_root: Path) -> Path:
    return run_root / AGENTS_DIR_NAME


def require_role(role: str) -> None:
    if role not in ROLE_NAMES:
        raise ValueError(f"Unsupported role agent: {role}")


def agent_log_path(run_root: Path, role: str) -> Path:
    require_role(role)
    return agents_dir(run_root) / f"{role}-log.md"


def agent_summary_path(run_root: Path, role: str) -> Path:
    require_role(role)
    return agents_dir(run_root) / f"{role}-summary.md"


def relative_agent_log_path(role: str) -> str:
    require_role(role)
    return f"{AGENTS_DIR_NAME}/{role}-log.md"


def relative_agent_summary_path(role: str) -> str:
    require_role(role)
    return f"{AGENTS_DIR_NAME}/{role}-summary.md"


def default_role_session(role: str) -> dict:
    require_role(role)
    return {
        "agent_id": "",
        "generation": 0,
        "status": "",
        "created_at": "",
        "last_seen_at": "",
        "log_path": relative_agent_log_path(role),
        "summary_path": relative_agent_summary_path(role),
        "last_dispatch_owner": "",
        "replacement_reason": "",
    }


def default_agent_sessions() -> dict:
    return {
        "version": 1,
        "roles": {role: default_role_session(role) for role in ROLE_NAMES},
    }


def validate_agent_sessions(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("agent_sessions.json is malformed: root must be object")
    if payload.get("version") != 1:
        raise ValueError("agent_sessions.json is malformed: version must be 1")
    roles = payload.get("roles")
    if not isinstance(roles, dict):
        raise ValueError("agent_sessions.json is malformed: roles must be object")
    for role in ROLE_NAMES:
        session = roles.get(role)
        if not isinstance(session, dict):
            roles[role] = default_role_session(role)
            continue
        status = session.get("status", "")
        generation = session.get("generation", 0)
        if status not in SESSION_STATUSES:
            raise ValueError(f"agent_sessions.json is malformed: invalid status for {role}")
        if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
            raise ValueError(f"agent_sessions.json is malformed: invalid generation for {role}")
        merged = default_role_session(role)
        merged.update(session)
        roles[role] = merged
    return payload


def write_agent_sessions(run_root: Path, payload: dict) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    atomic_write_text(agent_sessions_path(run_root), json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def load_agent_sessions(run_root: Path) -> dict:
    path = agent_sessions_path(run_root)
    if not path.exists():
        payload = default_agent_sessions()
        write_agent_sessions(run_root, payload)
        ensure_agent_logs(run_root)
        return payload
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError("agent_sessions.json is malformed: invalid JSON") from exc
    return validate_agent_sessions(payload)


def ensure_agent_logs(run_root: Path) -> None:
    agents_dir(run_root).mkdir(parents=True, exist_ok=True)
    for role in ROLE_NAMES:
        log_path = agent_log_path(run_root, role)
        if not log_path.exists():
            atomic_write_text(log_path, f"# {role} log\n")
        summary_path = agent_summary_path(run_root, role)
        if not summary_path.exists():
            atomic_write_text(summary_path, f"# {role} summary\n")


def ensure_agent_session_files(run_root: Path) -> dict:
    payload = load_agent_sessions(run_root)
    ensure_agent_logs(run_root)
    write_agent_sessions(run_root, payload)
    return payload


def timestamp() -> str:
    return utc_now()


def new_agent_id(role: str, generation: int) -> str:
    require_role(role)
    return f"{role}-{generation}-{uuid4().hex}"


def resolve_role_session(run_root: Path, role: str, dispatch_owner: str, now: str | None = None) -> dict:
    require_role(role)
    observed_at = now or timestamp()
    payload = load_agent_sessions(run_root)
    ensure_agent_logs(run_root)
    session = payload["roles"][role]
    if session.get("status") == "active" and session.get("agent_id"):
        action = "reuse"
    else:
        session["generation"] = int(session.get("generation", 0)) + 1
        session["agent_id"] = new_agent_id(role, session["generation"])
        session["status"] = "active"
        session["created_at"] = observed_at
        session["replacement_reason"] = ""
        action = "create"
    session["last_seen_at"] = observed_at
    session["last_dispatch_owner"] = dispatch_owner
    write_agent_sessions(run_root, payload)
    append_role_log_entry(
        run_root,
        role,
        f"dispatch {dispatch_owner}",
        actions=["Dispatch received."],
        observations=[f"Session action: {action}.", f"Generation: {session['generation']}.", f"Agent: {session['agent_id']}"],
        result=["Role session ready."],
        next_steps=["Continue assigned role work."],
        now=observed_at,
    )
    return {"role": role, "action": action, **session}


def replace_role_session(run_root: Path, role: str, dispatch_owner: str, reason: str, now: str | None = None) -> dict:
    require_role(role)
    observed_at = now or timestamp()
    payload = load_agent_sessions(run_root)
    ensure_agent_logs(run_root)
    session = payload["roles"][role]
    old_generation = int(session.get("generation", 0))
    session["status"] = "replaced"
    session["replacement_reason"] = reason
    replacement = default_role_session(role)
    replacement["generation"] = old_generation + 1
    replacement["agent_id"] = new_agent_id(role, replacement["generation"])
    replacement["status"] = "active"
    replacement["created_at"] = observed_at
    replacement["last_seen_at"] = observed_at
    replacement["last_dispatch_owner"] = dispatch_owner
    replacement["replacement_reason"] = reason
    payload["roles"][role] = replacement
    write_agent_sessions(run_root, payload)
    append_role_log_entry(
        run_root,
        role,
        f"replacement generation {replacement['generation']}",
        actions=["Previous agent session unavailable.", "Created replacement session."],
        observations=["Recovered from `state.json`.", "Recovered from `trace.md`.", f"Recovered from `{relative_agent_log_path(role)}`.", f"Recovered from `{relative_agent_summary_path(role)}`."],
        result=[f"Replacement active for {dispatch_owner}.", f"Reason: {reason}"],
        next_steps=["Resume current dispatch from durable context."],
        now=observed_at,
    )
    return {"role": role, "action": "replace", **replacement}


def append_role_log_entry(
    run_root: Path,
    role: str,
    title: str,
    *,
    hypothesis: list[str] | None = None,
    actions: list[str] | None = None,
    observations: list[str] | None = None,
    result: list[str] | None = None,
    next_steps: list[str] | None = None,
    now: str | None = None,
) -> None:
    require_role(role)
    ensure_agent_logs(run_root)
    observed_at = now or timestamp()
    blocks = [f"## {observed_at} {title}", ""]
    for heading, items in (
        ("Hypothesis", hypothesis or []),
        ("Actions", actions or []),
        ("Observations", observations or []),
        ("Result", result or []),
        ("Next", next_steps or []),
    ):
        if not items:
            continue
        blocks.append(f"{heading}:")
        blocks.extend(f"- {item}" for item in items)
        blocks.append("")
    path = agent_log_path(run_root, role)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(blocks).rstrip() + "\n\n")


def tail_text(path: Path, max_chars: int = 12000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8-sig")
    return text[-max_chars:]


def build_replacement_prompt_context(run_root: Path, role: str, reason: str) -> dict:
    require_role(role)
    return {
        "role": role,
        "replacement_reason": reason,
        "state_json": tail_text(run_root / "state.json"),
        "trace_tail": tail_text(run_root / "trace.md"),
        "role_log_tail": tail_text(agent_log_path(run_root, role)),
        "role_summary": tail_text(agent_summary_path(run_root, role)),
    }

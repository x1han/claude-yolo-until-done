from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from state import atomic_write_text, utc_now

AGENT_SESSIONS_FILE_NAME = "agent_sessions.json"
PLANNING_ROUNDS_FILE_NAME = "planning_rounds.json"
AGENTS_DIR_NAME = "agents"
ROLE_NAMES = ("worker", "watcher", "helper", "muse", "logos")
PLANNING_ROLE_NAMES = ("muse", "logos")
SESSION_ACTION_CREATE = "create"
SESSION_ACTION_REPLACE = "replace"
CONTINUITY_MODEL_PROJECT_MEMORY = "project_memory"
MEMORY_SCOPE_PROJECT = "project"
SESSION_ACTIONS = {SESSION_ACTION_CREATE, SESSION_ACTION_REPLACE}
SESSION_STATUSES = {"", "active", "replaced", "failed"}
PLANNING_ROUND_STATUSES = {"completed", "blocked", "failed"}
ROLE_MEMORY_TEMPLATE = """# {role} memory

## Role Conventions

## Project Conventions

## Risky Areas

## Reliable Verification

## Recurring Issues
"""


def agent_sessions_path(run_root: Path) -> Path:
    return run_root / AGENT_SESSIONS_FILE_NAME


def planning_rounds_path(run_root: Path) -> Path:
    return run_root / PLANNING_ROUNDS_FILE_NAME


def agents_dir(run_root: Path) -> Path:
    return run_root / AGENTS_DIR_NAME


def require_role(role: str) -> None:
    if role not in ROLE_NAMES:
        raise ValueError(f"Unsupported role agent: {role}")


def require_planning_role(role: str) -> None:
    if role not in PLANNING_ROLE_NAMES:
        raise ValueError(f"Unsupported planning role agent: {role}")


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
        "role_invocation_id": "",
        "last_runtime_agent_id": "",
        "generation": 0,
        "status": "",
        "continuity_model": CONTINUITY_MODEL_PROJECT_MEMORY,
        "memory_scope": MEMORY_SCOPE_PROJECT,
        "memory_path": f".claude/agent-memory/{role}/MEMORY.md",
        "role_log_path": relative_agent_log_path(role),
        "summary_path": relative_agent_summary_path(role),
        "created_at": "",
        "last_seen_at": "",
        "last_dispatch_owner": "",
        "replacement_reason": "",
    }


def default_agent_sessions() -> dict:
    return {
        "version": 2,
        "roles": {role: default_role_session(role) for role in ROLE_NAMES},
    }


def normalize_role_session(role: str, session: dict) -> dict:
    merged = default_role_session(role)
    legacy_agent_id = session.get("agent_id", "")
    merged.update({key: value for key, value in session.items() if key != "agent_id"})
    if not merged.get("role_invocation_id"):
        role_session_id = merged.get("role_session_id", "")
        if isinstance(role_session_id, str) and role_session_id:
            merged["role_invocation_id"] = role_session_id
        elif isinstance(legacy_agent_id, str):
            merged["role_invocation_id"] = legacy_agent_id
    if not merged.get("last_runtime_agent_id"):
        runtime_agent_id = merged.get("runtime_agent_id", "")
        if isinstance(runtime_agent_id, str):
            merged["last_runtime_agent_id"] = runtime_agent_id
    merged.pop("role_session_id", None)
    merged.pop("runtime_agent_id", None)
    merged["continuity_model"] = CONTINUITY_MODEL_PROJECT_MEMORY
    merged["memory_scope"] = MEMORY_SCOPE_PROJECT
    merged["memory_path"] = f".claude/agent-memory/{role}/MEMORY.md"
    if "log_path" in merged and "role_log_path" not in merged:
        merged["role_log_path"] = merged["log_path"]
    merged.pop("log_path", None)
    return merged


def validate_agent_sessions(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("agent_sessions.json is malformed: root must be object")
    if payload.get("version") not in {1, 2}:
        raise ValueError("agent_sessions.json is malformed: version must be 1 or 2")
    if payload.get("version") == 1:
        payload["version"] = 2
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
        roles[role] = normalize_role_session(role, session)
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


def project_role_memory_path(project_root: Path, role: str) -> Path:
    require_role(role)
    return project_root / ".claude" / "agent-memory" / role / "MEMORY.md"


def ensure_project_role_memory_files(project_root: Path) -> None:
    for role in ROLE_NAMES:
        memory_path = project_role_memory_path(project_root, role)
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        if not memory_path.exists():
            atomic_write_text(memory_path, ROLE_MEMORY_TEMPLATE.format(role=role))


def ensure_agent_session_files(run_root: Path) -> dict:
    payload = load_agent_sessions(run_root)
    ensure_agent_logs(run_root)
    write_agent_sessions(run_root, payload)
    return payload


def load_planning_rounds(run_root: Path) -> list[dict]:
    path = planning_rounds_path(run_root)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError("planning_rounds.json is malformed: invalid JSON") from exc
    if not isinstance(payload, list):
        raise ValueError("planning_rounds.json is malformed: root must be array")
    return payload


def write_planning_rounds(run_root: Path, payload: list[dict]) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    atomic_write_text(planning_rounds_path(run_root), json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def append_planning_round(run_root: Path, record: dict, now: str | None = None) -> dict:
    role = str(record.get("role", ""))
    require_planning_role(role)
    status = str(record.get("status", ""))
    if status not in PLANNING_ROUND_STATUSES:
        raise ValueError(f"Invalid planning round status: {status}")
    round_number = record.get("round")
    if not isinstance(round_number, int) or isinstance(round_number, bool) or round_number < 1:
        raise ValueError("Invalid planning round number")
    docs_touched = record.get("docs_touched", [])
    decisions_recorded = record.get("decisions_recorded", [])
    questions_added = record.get("questions_added", [])
    for field_name, value in (
        ("docs_touched", docs_touched),
        ("decisions_recorded", decisions_recorded),
        ("questions_added", questions_added),
    ):
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"Invalid planning round {field_name}")
    summary = str(record.get("summary", "")).strip()
    if not summary:
        raise ValueError("Invalid planning round summary")
    observed_at = now or timestamp()
    persisted = {
        "recorded_at": observed_at,
        "role": role,
        "round": round_number,
        "status": status,
        "docs_touched": docs_touched,
        "summary": summary,
        "decisions_recorded": decisions_recorded,
        "questions_added": questions_added,
        "next_recommendation": str(record.get("next_recommendation", "")).strip(),
    }
    rounds = load_planning_rounds(run_root)
    rounds.append(persisted)
    write_planning_rounds(run_root, rounds)
    append_role_log_entry(
        run_root,
        role,
        f"planning round {round_number}",
        actions=[f"Status: {status}"],
        observations=[summary],
        result=[f"Docs touched: {', '.join(docs_touched) if docs_touched else 'none'}"],
        next_steps=[persisted["next_recommendation"]] if persisted["next_recommendation"] else [],
        now=observed_at,
    )
    return persisted


def timestamp() -> str:
    return utc_now()


def new_agent_id(role: str, generation: int) -> str:
    require_role(role)
    return f"{role}-{generation}-{uuid4().hex}"


def dispatch_runtime_contract(action: str, role_invocation_id: str, last_runtime_agent_id: str = "") -> dict:
    if action not in SESSION_ACTIONS:
        raise ValueError(f"Unsupported agent session action: {action}")
    return {
        "tool": "Agent",
        "action": SESSION_ACTION_CREATE,
        "agent_id": "",
        "role_invocation_id": role_invocation_id,
        "last_runtime_agent_id": last_runtime_agent_id,
        "continuity_model": CONTINUITY_MODEL_PROJECT_MEMORY,
        "memory_scope": MEMORY_SCOPE_PROJECT,
        "replacement_allowed": False,
        "replacement_instruction": "Only replace this role agent through explicit replacement flow after the stored agent is unavailable.",
    }


def resolve_role_session(run_root: Path, role: str, dispatch_owner: str, now: str | None = None) -> dict:
    require_role(role)
    observed_at = now or timestamp()
    payload = load_agent_sessions(run_root)
    ensure_agent_logs(run_root)
    session = payload["roles"][role]
    if session.get("status") == "active" and session.get("role_invocation_id"):
        action = SESSION_ACTION_CREATE
    else:
        session["generation"] = int(session.get("generation", 0)) + 1
        session["role_invocation_id"] = new_agent_id(role, session["generation"])
        session["last_runtime_agent_id"] = ""
        session["status"] = "active"
        session["created_at"] = observed_at
        session["replacement_reason"] = ""
        action = SESSION_ACTION_CREATE
    session["last_seen_at"] = observed_at
    session["last_dispatch_owner"] = dispatch_owner
    runtime = dispatch_runtime_contract(action, session["role_invocation_id"], session.get("last_runtime_agent_id", ""))
    write_agent_sessions(run_root, payload)
    append_role_log_entry(
        run_root,
        role,
        f"dispatch {dispatch_owner}",
        actions=["Dispatch received."],
        observations=[
            f"Session action: {action}.",
            f"Generation: {session['generation']}.",
            f"Role invocation: {session['role_invocation_id']}.",
            f"Continuity model: {session['continuity_model']}.",
            f"Project memory: {session['memory_path']}.",
            f"Role log: {session['role_log_path']}.",
            f"Last runtime agent: {session.get('last_runtime_agent_id', '') or 'not recorded'}.",
        ],
        result=["Role session ready."],
        next_steps=["Continue assigned role work."],
        now=observed_at,
    )
    return {"role": role, "action": action, **session, "runtime": runtime}


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
    replacement["role_invocation_id"] = new_agent_id(role, replacement["generation"])
    replacement["last_runtime_agent_id"] = ""
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
    return {"role": role, "action": SESSION_ACTION_REPLACE, **replacement, "runtime": dispatch_runtime_contract(SESSION_ACTION_REPLACE, replacement["role_invocation_id"], "")}


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


def record_runtime_agent_id(*args, **kwargs):
    raise ValueError("runtime agent ids are audit-only in project_memory continuity")


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

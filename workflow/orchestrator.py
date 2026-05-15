from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from agent_sessions import resolve_role_session
from state import append_trace_event, build_resume_target, state_path, transition_state, utc_now, write_state


CLAIMED_STATUS = "claimed"
COMPLETED_STATUS = "completed"
DISPATCHED_STATUS = "dispatched"
IDLE_STATUS = "idle"
PENDING_STATUS = "pending"
RUNNING_STATUS = "running"
TIMED_OUT_STATUS = "timed_out"
ABANDONED_STATUS = "abandoned"
LIVE_CLAIM_STATUSES = {CLAIMED_STATUS, RUNNING_STATUS}
TERMINAL_CLAIM_STATUSES = {COMPLETED_STATUS, TIMED_OUT_STATUS, ABANDONED_STATUS}
DEFAULT_STALL_TIMEOUT_SECONDS = 600
DEFAULT_RETRY_LIMIT = 3
TRUE_HUMAN_HANDOFF_REASONS = {"stop_gate_limit", "worker_stalled_retry_limit", "worker_stall_supervision_invalid"}


def dispatch_role(state: dict) -> str:
    intent = state.get("dispatch_intent") if isinstance(state.get("dispatch_intent"), dict) else {}
    role = intent.get("role") if isinstance(intent.get("role"), str) and intent.get("role") else state.get("requested_role", "worker")
    return role if isinstance(role, str) and role else "worker"


def dispatch_generation(state: dict) -> int:
    raw_generation = state.get("dispatch_generation", 0)
    try:
        generation = int(raw_generation)
    except (TypeError, ValueError):
        return 0
    return generation if generation >= 0 else 0


def dispatch_consumer_id(state: dict, role: str | None = None, generation: int | None = None) -> str:
    consumer_role = role or dispatch_role(state)
    gate_id = state.get("gate_id") or state.get("task_id") or "task"
    if not isinstance(gate_id, str) or not gate_id.strip():
        gate_id = "task"
    resolved_generation = generation if generation is not None else dispatch_generation(state)
    if resolved_generation <= 0:
        resolved_generation = 1
    return f"{consumer_role}:{gate_id}:{resolved_generation}"


def next_dispatch_consumer_id(state: dict, role: str | None = None) -> str:
    return dispatch_consumer_id(state, role=role, generation=dispatch_generation(state) + 1)


def default_consumer_id(state: dict) -> str:
    if state.get("dispatch_status") == PENDING_STATUS:
        return next_dispatch_consumer_id(state)
    return dispatch_consumer_id(state)


def valid_resume_target(target: object) -> bool:
    if not isinstance(target, dict):
        return False
    role = target.get("role")
    action = target.get("action")
    return isinstance(role, str) and bool(role.strip()) and isinstance(action, str) and bool(action.strip())


def resume_after_human(state: dict, guidance: str) -> dict:
    notes = list(state.get("task_handoff_notes", []))
    notes.append(guidance)

    target = state.get("resume_target") if isinstance(state.get("resume_target"), dict) else {}
    role = target.get("role") if isinstance(target.get("role"), str) and target.get("role") else "worker"
    action = target.get("action") if isinstance(target.get("action"), str) and target.get("action") else "worker_update"
    supervision = dict(state.get("supervision") if isinstance(state.get("supervision"), dict) else {})
    supervision.setdefault("last_token_io_at", "")
    supervision.setdefault("last_progress_at", "")
    supervision.setdefault("stall_timeout_seconds", DEFAULT_STALL_TIMEOUT_SECONDS)
    supervision.setdefault("retry_limit", DEFAULT_RETRY_LIMIT)
    supervision["retry_count"] = 0
    supervision["last_recovery_reason"] = ""

    resumed = dict(state)
    resumed.update(
        {
            "gate_attempt": 0,
            "gate_reason": "",
            "owner": role,
            "next_action": action,
            "dispatch_status": PENDING_STATUS,
            "dispatch_intent": {"role": role, "action": action},
            "dispatch_claim": {},
            "last_dispatch": {},
            "worker_request": "",
            "worker_question": "",
            "verification_command": "",
            "verification_result": "",
            "blocked_for_human": False,
            "human_handoff": {},
            "resume_target": {},
            "requested_role": role,
            "task_handoff_notes": notes,
            "supervision": supervision,
        }
    )
    return resumed


def build_loop_contract(state: dict) -> dict:
    loop = state.get("loop") if isinstance(state.get("loop"), dict) else {}
    if state.get("mode", "acyclic") != "loop" or not loop.get("enabled"):
        return {}
    return {
        "mode": "loop",
        "iteration": loop.get("iteration"),
        "max_iterations": loop.get("max_iterations"),
        "stop_on_convergence": loop.get("stop_on_convergence"),
        "converged": loop.get("converged"),
        "instruction": "In loop mode, execute the complete approved spec/plan for this iteration from current evidence; do not pre-plan future loop iterations or treat parsed plan sections as separate loop iterations.",
    }


def build_task_packet(state: dict, role: str) -> dict:
    inputs = dict(state.get("task_inputs", {}))
    packet = {
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
    loop_contract = build_loop_contract(state)
    if loop_contract:
        packet["loop_contract"] = loop_contract
    return packet


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


def parse_timestamp(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def is_dispatch_claim_live(state: dict, now: str | None = None) -> bool:
    dispatch_status = state.get("dispatch_status")
    if dispatch_status not in LIVE_CLAIM_STATUSES:
        return False

    claim = dict(state.get("dispatch_claim", {}))
    owner = claim.get("owner")
    if not owner:
        return False

    lease_expires_at = parse_timestamp(claim.get("lease_expires_at"))
    if lease_expires_at is None:
        return False

    observed_at = parse_timestamp(now) or parse_timestamp(utc_now())
    if observed_at is None:
        return False
    return lease_expires_at > observed_at


def mark_dispatch_pending(state: dict, requested_role: str, *, preserve_last_dispatch: bool = False) -> None:
    state["requested_role"] = requested_role
    state["dispatch_status"] = PENDING_STATUS
    state["dispatch_intent"] = {
        "role": requested_role,
        "action": state.get("next_action", "worker_update"),
    }
    state["dispatch_claim"] = {}
    if not preserve_last_dispatch:
        state["last_dispatch"] = {}


def claim_dispatch(state: dict, consumer_id: str, now: str | None = None, lease_seconds: int = 120) -> dict:
    claim = dict(state.get("dispatch_claim", {}))
    observed_at = parse_timestamp(now) or parse_timestamp(utc_now())
    if observed_at is None:
        raise ValueError("Unable to resolve claim timestamp.")

    if is_dispatch_claim_live(state, now=observed_at.isoformat()):
        owner = claim.get("owner", "")
        if owner == consumer_id:
            return {"result": "claimed", "owner": owner, "lease_expires_at": claim.get("lease_expires_at", "")}
        return {"result": "rejected", "owner": owner, "lease_expires_at": claim.get("lease_expires_at", "")}

    intent = dict(state.get("dispatch_intent", {}))
    if not intent:
        return {"result": "missing_intent"}

    role = dispatch_role(state)
    expected_owner = next_dispatch_consumer_id(state, role=role)
    if consumer_id != expected_owner:
        return {"result": "rejected", "owner": expected_owner, "reason": "dispatch owner does not match next generation"}

    generation = dispatch_generation(state) + 1
    claimed_at = observed_at.isoformat()
    lease_expires_at = (observed_at + timedelta(seconds=lease_seconds)).isoformat()
    state["dispatch_generation"] = generation
    state["dispatch_status"] = CLAIMED_STATUS
    state["dispatch_claim"] = {
        "owner": expected_owner,
        "claimed_at": claimed_at,
        "lease_expires_at": lease_expires_at,
    }
    state["requested_role"] = role
    return {"result": "claimed", "owner": expected_owner, "claimed_at": claimed_at, "lease_expires_at": lease_expires_at}


def dispatch_requires_intent(state: dict) -> bool:
    return state.get("dispatch_status") in {PENDING_STATUS, CLAIMED_STATUS, RUNNING_STATUS} and not bool(state.get("dispatch_intent"))


def build_dispatch_record(state: dict, run_root: Path | None = None, dispatched_at: str | None = None) -> dict:
    intent = dict(state.get("dispatch_intent", {}))
    role = dispatch_role(state)
    claim = state.get("dispatch_claim") if isinstance(state.get("dispatch_claim"), dict) else {}
    dispatch_owner = claim.get("owner", dispatch_consumer_id(state, role=role))
    agent_session = None
    if run_root is not None and role != "human":
        agent_session = resolve_role_session(run_root, role, dispatch_owner, now=dispatched_at)
    return {
        "role": role,
        "task_id": state.get("task_id", ""),
        "gate_id": state.get("gate_id", ""),
        "dispatch_owner": dispatch_owner,
        "next_action": intent.get("action", state.get("next_action", "")),
        "dispatched_at": dispatched_at or utc_now(),
        "task_packet": build_task_packet(state, role),
        "agent_session": agent_session or {},
    }


def dispatch_record_matches_state(dispatch: dict, state: dict) -> bool:
    if not dispatch:
        return False
    intent = dict(state.get("dispatch_intent", {}))
    if dispatch.get("task_id") != state.get("task_id"):
        return False
    if dispatch.get("gate_id") != state.get("gate_id"):
        return False
    if dispatch.get("role") != dispatch_role(state):
        return False
    if dispatch.get("next_action") != intent.get("action", state.get("next_action", "")):
        return False
    return isinstance(dispatch.get("task_packet"), dict)


def replay_dispatch_record(state: dict, dispatched_at: str) -> dict | None:
    dispatch = dict(state.get("last_dispatch", {}))
    if not dispatch_record_matches_state(dispatch, state):
        return None
    replayed = dict(dispatch)
    replayed["dispatch_owner"] = dict(state.get("dispatch_claim", {})).get("owner", replayed.get("dispatch_owner", ""))
    replayed["dispatched_at"] = dispatched_at
    return replayed


def ensure_dispatch_agent_session(dispatch: dict, run_root: Path | None, dispatched_at: str) -> dict:
    if run_root is None or dispatch.get("role") == "human":
        return dispatch
    agent_session = dispatch.get("agent_session")
    if isinstance(agent_session, dict) and agent_session and agent_session.get("continuity_model") == "project_memory":
        return dispatch
    if isinstance(agent_session, dict) and agent_session:
        action = str(agent_session.get("action", ""))
        role_invocation_id = str(agent_session.get("role_invocation_id") or agent_session.get("role_session_id") or agent_session.get("agent_id") or "")
        last_runtime_agent_id = str(agent_session.get("last_runtime_agent_id") or agent_session.get("runtime_agent_id") or "")
        if action and role_invocation_id:
            enriched = dict(dispatch)
            normalized_session = dict(agent_session)
            normalized_session.pop("agent_id", None)
            normalized_session.pop("role_session_id", None)
            normalized_session.pop("runtime_agent_id", None)
            normalized_session.pop("runtime", None)
            normalized_session["role_invocation_id"] = role_invocation_id
            normalized_session["last_runtime_agent_id"] = last_runtime_agent_id
            normalized_session["continuity_model"] = "project_memory"
            normalized_session["memory_scope"] = "project"
            normalized_session["memory_path"] = f".claude/agent-memory/{dispatch['role']}/MEMORY.md"
            normalized_session["role_log_path"] = f"agents/{dispatch['role']}-log.md"
            normalized_session.setdefault("summary_path", f"agents/{dispatch['role']}-summary.md")
            enriched["agent_session"] = normalized_session
            return enriched
        return dispatch
    enriched = dict(dispatch)
    enriched["agent_session"] = resolve_role_session(run_root, dispatch["role"], dispatch.get("dispatch_owner", ""), now=dispatched_at)
    return enriched


def transition_dispatch_terminal(state: dict, status: str, timestamp: str, reason: str) -> None:
    claim = dict(state.get("dispatch_claim", {}))
    claim["terminal_reason"] = reason
    if status == TIMED_OUT_STATUS:
        claim["timed_out_at"] = timestamp
    elif status == ABANDONED_STATUS:
        claim["abandoned_at"] = timestamp
    state["dispatch_claim"] = claim
    state["dispatch_status"] = status


def recover_dispatch_for_resume(state: dict, now: str | None = None) -> dict:
    dispatch_status = state.get("dispatch_status", IDLE_STATUS)
    if dispatch_status not in LIVE_CLAIM_STATUSES | {TIMED_OUT_STATUS, ABANDONED_STATUS}:
        return {"result": "unchanged", "reason": f"dispatch_status={dispatch_status}"}

    timestamp = now or utc_now()
    if dispatch_status in LIVE_CLAIM_STATUSES and is_dispatch_claim_live(state, now=timestamp):
        return {"result": "unchanged", "reason": "dispatch claim lease still live"}

    claim = dict(state.get("dispatch_claim", {}))
    owner = claim.get("owner", "")
    if dispatch_requires_intent(state):
        transition_dispatch_terminal(state, ABANDONED_STATUS, timestamp, "expired dispatch claim is missing dispatch_intent")
        return {
            "result": "abandoned",
            "expired_owner": owner,
            "reason": "expired dispatch claim is missing dispatch_intent",
        }

    intent = dict(state.get("dispatch_intent", {}))
    role = intent.get("role", state.get("requested_role", "worker"))
    action = intent.get("action", state.get("next_action", "worker_update"))
    mark_dispatch_pending(state, role)
    state["dispatch_intent"] = {"role": role, "action": action}
    return {
        "result": "requeued",
        "expired_owner": owner,
        "role": role,
        "action": action,
        "reason": "expired dispatch claim recovered for continue-run",
    }


def supervision_state(state: dict) -> dict:
    supervision = state.get("supervision")
    return supervision if isinstance(supervision, dict) else {}


def supervision_timeout_seconds(state: dict) -> int | None:
    raw_timeout = supervision_state(state).get("stall_timeout_seconds", DEFAULT_STALL_TIMEOUT_SECONDS)
    try:
        timeout_seconds = int(raw_timeout)
    except (TypeError, ValueError):
        return None
    return timeout_seconds if timeout_seconds > 0 else None


def latest_heartbeat_at(state: dict) -> datetime | None:
    supervision = supervision_state(state)
    token_io = parse_timestamp(supervision.get("last_token_io_at"))
    progress = parse_timestamp(supervision.get("last_progress_at"))
    values = [value for value in (token_io, progress) if value is not None]
    return max(values) if values else None


def worker_stall_reason(state: dict, now: str | None = None) -> str | None:
    if state.get("status") != "active":
        return None
    if state.get("owner") != "worker":
        return None
    if state.get("blocked_for_human"):
        return None
    if state.get("dispatch_status") not in LIVE_CLAIM_STATUSES:
        return None
    if is_dispatch_claim_live(state, now=now):
        return None
    supervision = state.get("supervision")
    if not isinstance(supervision, dict):
        return "missing_supervision"
    timeout_seconds = supervision_timeout_seconds(state)
    if timeout_seconds is None:
        return "invalid_supervision"
    heartbeat_at = latest_heartbeat_at(state)
    if heartbeat_at is None:
        return "missing_heartbeat"
    observed_at = parse_timestamp(now) or parse_timestamp(utc_now())
    if observed_at is None:
        return "invalid_observed_time"
    if (observed_at - heartbeat_at).total_seconds() < timeout_seconds:
        return None
    return "worker_stalled"


def block_for_stall_problem(state: dict, timestamp: str, reason: str) -> dict:
    target = state.get("resume_target") if valid_resume_target(state.get("resume_target")) else build_resume_target(state)
    if valid_resume_target(target):
        state["resume_target"] = target
    else:
        state["resume_target"] = {}
    state["blocked_for_human"] = True
    state["owner"] = "human"
    state["next_action"] = "human_handoff"
    state["requested_role"] = "human"
    handoff = dict(state.get("human_handoff") if isinstance(state.get("human_handoff"), dict) else {})
    handoff["reason"] = reason
    state["human_handoff"] = handoff
    transition_dispatch_terminal(state, ABANDONED_STATUS, timestamp, reason)
    supervision = dict(supervision_state(state))
    supervision.setdefault("last_token_io_at", "")
    supervision.setdefault("last_progress_at", "")
    supervision.setdefault("stall_timeout_seconds", DEFAULT_STALL_TIMEOUT_SECONDS)
    supervision.setdefault("retry_limit", DEFAULT_RETRY_LIMIT)
    supervision.setdefault("retry_count", 0)
    supervision["last_recovery_at"] = timestamp
    supervision["last_recovery_reason"] = reason
    state["supervision"] = supervision
    return {"result": "blocked_for_human", "reason": reason}


def recover_stalled_worker(state: dict, timestamp: str) -> dict:
    supervision = dict(supervision_state(state))
    supervision.setdefault("last_token_io_at", "")
    supervision.setdefault("last_progress_at", "")
    supervision.setdefault("stall_timeout_seconds", DEFAULT_STALL_TIMEOUT_SECONDS)
    supervision.setdefault("retry_limit", DEFAULT_RETRY_LIMIT)
    retry_count = int(supervision.get("retry_count", 0))
    retry_limit = int(supervision.get("retry_limit", DEFAULT_RETRY_LIMIT))
    if retry_count >= retry_limit:
        return block_for_stall_problem(state, timestamp, "worker_stalled_retry_limit")

    previous_dispatch = dict(state.get("last_dispatch", {}))
    role = dispatch_role(state)
    transition_dispatch_terminal(state, ABANDONED_STATUS, timestamp, "worker_stalled")
    supervision["retry_count"] = retry_count + 1
    supervision["last_recovery_at"] = timestamp
    supervision["last_recovery_reason"] = "worker_stalled"
    state["supervision"] = supervision
    mark_dispatch_pending(state, role, preserve_last_dispatch=dispatch_record_matches_state(previous_dispatch, state))
    state["dispatch_intent"] = {"role": role, "action": state.get("next_action", "worker_update")}
    if not dispatch_record_matches_state(previous_dispatch, state):
        state["last_dispatch"] = {}
    return {"result": "requeued", "reason": "worker_stalled"}


def consume_dispatch(state: dict, consumer_id: str, run_root: Path | None = None, now: str | None = None) -> tuple[dict, bool, bool]:
    timestamp = now or utc_now()
    dispatch_status = state.get("dispatch_status", IDLE_STATUS)
    mutated = False
    trace_required = False

    if dispatch_status == PENDING_STATUS:
        claim = claim_dispatch(state, consumer_id=consumer_id, now=timestamp)
        if claim["result"] != "claimed":
            return claim, mutated, trace_required
        dispatch = replay_dispatch_record(state, dispatched_at=timestamp) or build_dispatch_record(state, run_root=run_root, dispatched_at=timestamp)
        dispatch = ensure_dispatch_agent_session(dispatch, run_root, timestamp)
        state["dispatch_status"] = RUNNING_STATUS
        state["last_dispatch"] = dispatch
        return {"result": "dispatched", **dispatch}, True, True

    if dispatch_status in LIVE_CLAIM_STATUSES:
        claim = dict(state.get("dispatch_claim", {}))
        owner = claim.get("owner", "")
        if is_dispatch_claim_live(state, now=timestamp):
            if owner != consumer_id:
                return {
                    "result": "rejected",
                    "owner": owner,
                    "lease_expires_at": claim.get("lease_expires_at", ""),
                }, mutated, trace_required

            dispatch = dict(state.get("last_dispatch", {}))
            if dispatch:
                original_agent_session = dispatch.get("agent_session")
                dispatch = ensure_dispatch_agent_session(dispatch, run_root, claim.get("claimed_at") or timestamp)
                agent_session_changed = dispatch.get("agent_session") != original_agent_session
                state["last_dispatch"] = dispatch
                return {"result": "dispatched", **dispatch, "replayed": True}, agent_session_changed, trace_required
            if dispatch_requires_intent(state):
                transition_dispatch_terminal(state, ABANDONED_STATUS, timestamp, "live claim is missing dispatch_intent")
                return {
                    "result": "abandoned",
                    "owner": owner,
                    "reason": "live claim is missing dispatch_intent",
                }, True, False

            dispatch = build_dispatch_record(state, run_root=run_root, dispatched_at=claim.get("claimed_at") or timestamp)
            dispatch = ensure_dispatch_agent_session(dispatch, run_root, claim.get("claimed_at") or timestamp)
            state["dispatch_status"] = RUNNING_STATUS
            state["last_dispatch"] = dispatch
            return {"result": "dispatched", **dispatch, "replayed": True}, True, True

        transition_dispatch_terminal(state, TIMED_OUT_STATUS, timestamp, "dispatch claim lease expired")
        return {
            "result": "timed_out",
            "owner": owner,
            "reason": "dispatch claim lease expired",
        }, True, False

    return {"result": "no_op", "reason": f"dispatch_status={dispatch_status}"}, mutated, trace_required


def orchestrate_step(state: dict, consumer_id: str | None = None, run_root: Path | None = None, now: str | None = None) -> tuple[dict, bool, bool]:
    timestamp = now or utc_now()
    stall_reason = worker_stall_reason(state, now=timestamp)
    if stall_reason == "worker_stalled":
        recovery = recover_stalled_worker(state, timestamp)
        if recovery["result"] == "blocked_for_human":
            return recovery, True, False
    elif stall_reason in {"missing_supervision", "invalid_supervision", "missing_heartbeat", "invalid_observed_time"}:
        return block_for_stall_problem(state, timestamp, "worker_stall_supervision_invalid"), True, False

    effective_consumer_id = consumer_id or default_consumer_id(state)
    result, mutated, trace_required = consume_dispatch(state, consumer_id=effective_consumer_id, run_root=run_root, now=timestamp)
    if stall_reason == "worker_stalled":
        return result, True, trace_required
    return result, mutated, trace_required


def orchestrate(run_root: Path, state: dict, consumer_id: str | None = None) -> dict:
    if state_path(run_root).exists() and isinstance(state.get("state_version"), int):
        preview_state = dict(state)
        preview_result, preview_mutated, _preview_trace_required = orchestrate_step(preview_state, consumer_id=consumer_id)
        if preview_result.get("result") != "dispatched":
            if not preview_mutated:
                return preview_result
        elif preview_result.get("replayed") is True and not preview_mutated:
            preview_session = preview_result.get("agent_session")
            missing_session = not preview_session
            missing_runtime = isinstance(preview_session, dict) and "runtime" not in preview_session
            if not missing_session and not missing_runtime:
                return preview_result

        outcome: dict[str, object] = {}

        def apply_transition(current_state: dict, timestamp: str) -> None:
            result, _mutated, trace_required = orchestrate_step(current_state, consumer_id=consumer_id, run_root=run_root, now=timestamp)
            outcome["result"] = result
            outcome["trace_required"] = trace_required

        transition_state(
            run_root,
            actor="orchestrator",
            action="dispatch",
            expected_version=state["state_version"],
            apply_transition=apply_transition,
        )
        result = outcome["result"]
        if outcome.get("trace_required"):
            append_trace_event(
                run_root,
                f"orchestrator dispatch: role={result['role']}; task_id={result['task_id']}; next_action={result['next_action']}",
            )
        return result

    result, mutated, trace_required = orchestrate_step(state, consumer_id=consumer_id, run_root=run_root)
    if result.get("result") != "dispatched":
        if mutated:
            write_state(run_root, state)
        return result

    replayed = result.get("replayed") is True
    if replayed and not mutated:
        return result

    write_state(run_root, state)
    if trace_required:
        append_trace_event(
            run_root,
            f"orchestrator dispatch: role={result['role']}; task_id={result['task_id']}; next_action={result['next_action']}",
        )
    return result

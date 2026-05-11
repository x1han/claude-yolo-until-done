#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestrator import TRUE_HUMAN_HANDOFF_REASONS, orchestrate, resume_after_human
from state import StaleStateVersionError, load_state, transition_state


BOOL_CHOICES = {"true": True, "false": False}


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in BOOL_CHOICES:
        raise argparse.ArgumentTypeError("Expected true or false.")
    return BOOL_CHOICES[normalized]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Persist helper-human handoff guidance for a workflow run.")
    parser.add_argument("--run-root", required=True, help="Path to the run bundle root")
    parser.add_argument("--summary", required=True, help="Human guidance summary for the current task")
    parser.add_argument("--resume-ready", required=True, type=parse_bool, help="Whether the discussion is ready to resume")
    parser.add_argument("--expected-version", required=True, type=int, help="Expected authoritative state version for this handoff update")
    parser.add_argument("--resume-now", action="store_true", help="Explicitly resume the current task now")
    parser.add_argument("--actor", choices=("human", "helper"), default="human", help="Who is providing the handoff outcome")
    parser.add_argument(
        "--helper-outcome",
        choices=("retry", "block_for_human"),
        default="retry",
        help="Helper-specific outcome when --actor helper is used",
    )
    return parser.parse_args()


def fail(message: str) -> int:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def update_human_handoff(state: dict, summary: str, resume_ready: bool, *, actor: str, helper_outcome: str | None = None) -> None:
    existing = state.get("human_handoff") if isinstance(state.get("human_handoff"), dict) else {}
    payload = {
        "summary": summary,
        "resume_ready": resume_ready,
        "actor": actor,
    }
    if helper_outcome is not None:
        payload["helper_outcome"] = helper_outcome
    if isinstance(existing.get("reason"), str) and existing.get("reason"):
        payload["reason"] = existing["reason"]
    state["human_handoff"] = payload



def increment_retry_budget(state: dict, role: str) -> None:
    retry_budget = state.get("retry_budget") if isinstance(state.get("retry_budget"), dict) else {}
    current = retry_budget.get(role, 0)
    try:
        retry_budget[role] = int(current) + 1
    except (TypeError, ValueError):
        retry_budget[role] = 1
    retry_budget.setdefault("worker", 0)
    retry_budget.setdefault("helper", 0)
    retry_budget.setdefault("backoff_until", "")
    state["retry_budget"] = retry_budget



def block_for_human(state: dict, summary: str, *, actor: str, helper_outcome: str | None = None) -> None:
    state["blocked_for_human"] = True
    state["owner"] = "human"
    state["next_action"] = "human_handoff"
    state["requested_role"] = "human"
    update_human_handoff(state, summary, False, actor=actor, helper_outcome=helper_outcome)


def is_true_human_block(state: dict) -> bool:
    if state.get("worker_request") == "need_human":
        return True
    handoff = state.get("human_handoff") if isinstance(state.get("human_handoff"), dict) else {}
    return handoff.get("reason") in TRUE_HUMAN_HANDOFF_REASONS


def has_valid_resume_target(state: dict) -> bool:
    target = state.get("resume_target")
    if not isinstance(target, dict):
        return False
    role = target.get("role")
    action = target.get("action")
    return isinstance(role, str) and bool(role.strip()) and isinstance(action, str) and bool(action.strip())


def main() -> int:
    args = parse_args()
    run_root = Path(args.run_root).resolve()
    state = load_state(run_root)

    require(state.get("allow_need_human") is True, "Human handoff is disabled for this run.")
    handoff = state.get("human_handoff") if isinstance(state.get("human_handoff"), dict) else {}
    waiting_for_human = state.get("worker_request") == "need_human" or handoff.get("reason") in TRUE_HUMAN_HANDOFF_REASONS
    require(waiting_for_human, "Run is not waiting on need_human guidance.")
    require(state.get("blocked_for_human") is True, "Run is not currently blocked for human guidance.")
    require(not args.resume_now or args.resume_ready is True, "Explicit resume requires resume_ready=true.")
    require(
        not (args.actor == "helper" and args.resume_now and is_true_human_block(state)),
        "Helper cannot resume a run that is blocked for human guidance.",
    )
    require(
        not (args.resume_now and is_true_human_block(state) and not has_valid_resume_target(state)),
        "Run is blocked for human guidance but resume_target is missing or invalid; repair the durable run bundle before resuming.",
    )

    def apply_transition(current_state: dict, _: str) -> None:
        if args.actor == "helper":
            increment_retry_budget(current_state, "helper")
            if args.helper_outcome == "block_for_human":
                block_for_human(current_state, args.summary, actor="helper", helper_outcome=args.helper_outcome)
                return

        if args.resume_now:
            resumed = resume_after_human(current_state, args.summary)
            current_state.clear()
            current_state.update(resumed)
            return

        update_human_handoff(
            current_state,
            args.summary,
            args.resume_ready,
            actor=args.actor,
            helper_outcome=args.helper_outcome if args.actor == "helper" else None,
        )

    try:
        state = transition_state(
            run_root,
            actor=args.actor,
            action="resume_now" if args.resume_now else "record_handoff",
            expected_version=args.expected_version,
            apply_transition=apply_transition,
        )
    except StaleStateVersionError as error:
        fail(str(error))

    if args.actor == "helper" and args.helper_outcome == "block_for_human":
        print(json.dumps({"result": "blocked_for_human", "resume_ready": False}, ensure_ascii=True))
        return 0

    if not args.resume_now:
        print(json.dumps({"result": "waiting_for_human", "resume_ready": args.resume_ready}, ensure_ascii=True))
        return 0
    orchestration = orchestrate(run_root, state)
    print(json.dumps({"result": "resumed", "orchestration": orchestration}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

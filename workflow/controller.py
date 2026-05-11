#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lifecycle import (
    ACTIVE_STATUS,
    APPROVED_STATUS,
    NEEDS_REVIEW_STATUS,
    READY_FOR_CLEANUP_STATUS,
    REWORK_REQUIRED_STATUS,
    build_completion_certification,
    clear_completion_certification,
    compute_certification_hash,
)
from loop_scheduler import loop_decision
from orchestrator import IDLE_STATUS, LIVE_CLAIM_STATUSES, PENDING_STATUS, consume_dispatch, default_consumer_id, dispatch_consumer_id, mark_dispatch_pending
from state import StaleStateVersionError, append_trace_event, build_resume_target, format_trace_value, transition_state


ALLOWED_SUBMIT_STATUSES = {ACTIVE_STATUS, REWORK_REQUIRED_STATUS}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update a lightweight claude-yolo-until-done run state.")
    parser.add_argument("--run-root", required=True, help="Path to the run bundle root")
    parser.add_argument("--actor", required=True, choices=("worker", "watcher"))
    parser.add_argument("--action", required=True, choices=("submit", "review", "complete"))
    parser.add_argument("--expected-version", required=True, type=int)

    parser.add_argument("--worker-claim")
    parser.add_argument("--files-changed", nargs="*")
    parser.add_argument("--verification-command")
    parser.add_argument("--verification-result")
    parser.add_argument("--loop-converged", action="store_true")

    parser.add_argument("--verdict", choices=("approve", "rework_required"))
    parser.add_argument("--scope-checked", nargs="*")
    parser.add_argument("--problem", action="append", default=[])
    parser.add_argument("--required-rework", action="append", default=[])
    parser.add_argument("--acceptance-basis", action="append", default=[])
    return parser.parse_args()


def fail(message: str) -> int:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def clear_transient_routing_fields(state: dict) -> None:
    state["blocked_for_human"] = False
    state["human_handoff"] = {}
    state["resume_target"] = {}
    state["worker_request"] = ""
    state["worker_question"] = ""
    state["gate_reason"] = ""



def update_for_helper_request(state: dict, request: str, question: str) -> None:
    require(request in {"need_helper", "need_human"}, f"Unsupported worker request: {request}")
    if request == "need_human":
        require(state.get("allow_need_human", True), "This run forbids need_human escalation.")
        state["resume_target"] = build_resume_target(state)
        state["blocked_for_human"] = True
        state["human_handoff"] = {}
        state["owner"] = "human"
        state["next_action"] = "human_handoff"
        state["gate_reason"] = ""
        mark_dispatch_pending(state, "human")
    else:
        state["blocked_for_human"] = False
        state["human_handoff"] = {}
        state["resume_target"] = {}
        state["owner"] = "worker"
        state["next_action"] = "worker_update"
        state["gate_reason"] = ""
        mark_dispatch_pending(state, "helper")
    state["worker_request"] = request
    state["worker_question"] = question



def require_dispatch_authority(state: dict, role: str, action_label: str) -> None:
    dispatch_status = state.get("dispatch_status", IDLE_STATUS)
    if dispatch_status == PENDING_STATUS:
        intent = state.get("dispatch_intent") if isinstance(state.get("dispatch_intent"), dict) else {}
        pending_role = intent.get("role") if isinstance(intent.get("role"), str) and intent.get("role") else state.get("requested_role", "worker")
        require(pending_role == role, f"{action_label} requires current dispatch authority.")
        return

    require(dispatch_status in LIVE_CLAIM_STATUSES, f"{action_label} requires current dispatch authority.")
    claim = state.get("dispatch_claim") if isinstance(state.get("dispatch_claim"), dict) else {}
    require(claim.get("owner") == dispatch_consumer_id(state, role), f"{action_label} requires current dispatch authority.")



def publish_next_dispatch(state: dict) -> dict | None:
    if state.get("dispatch_status") != PENDING_STATUS:
        return None
    result, _mutated, _trace_required = consume_dispatch(state, consumer_id=default_consumer_id(state))
    require(result.get("result") == "dispatched", f"Unable to publish next dispatch: {result}")
    return result


def update_for_submit(state: dict, args: argparse.Namespace, timestamp: str) -> None:
    require(args.actor == "worker", "Only the worker may submit.")
    require(state.get("status") in ALLOWED_SUBMIT_STATUSES, "Worker submit requires active or rework_required state.")
    require_dispatch_authority(state, "worker", "Worker submit")
    require(args.worker_claim is not None, "--worker-claim is required for submit.")
    require(args.verification_command is not None, "--verification-command is required for submit.")
    require(args.verification_result is not None, "--verification-result is required for submit.")

    clear_completion_certification(state)
    state["status"] = NEEDS_REVIEW_STATUS
    state["owner"] = "watcher"
    state["next_action"] = "watcher_review"
    clear_transient_routing_fields(state)
    mark_dispatch_pending(state, "watcher")
    state["worker_claim"] = args.worker_claim
    state["files_changed"] = list(args.files_changed or [])
    state["verification_command"] = args.verification_command
    state["verification_result"] = args.verification_result
    state["submitted_at"] = timestamp
    loop = state.get("loop")
    if isinstance(loop, dict) and loop.get("enabled"):
        loop["converged"] = bool(args.loop_converged)
    state["review"] = {}
    state["reviewed_at"] = ""


def build_review_payload(args: argparse.Namespace) -> dict:
    return {
        "verdict": args.verdict,
        "scope_checked": list(args.scope_checked or []),
        "problems": list(args.problem),
        "required_rework": list(args.required_rework),
        "acceptance_basis": list(args.acceptance_basis),
    }


def update_for_review(state: dict, args: argparse.Namespace, timestamp: str) -> None:
    require(args.actor == "watcher", "Only the watcher may review.")
    require(state.get("status") == NEEDS_REVIEW_STATUS, "Watcher review requires needs_review state.")
    require_dispatch_authority(state, "watcher", "Watcher review")
    require(args.verdict is not None, "--verdict is required for review.")

    clear_completion_certification(state)
    review = build_review_payload(args)
    if args.verdict == "approve":
        require(not review["required_rework"], "Approved review cannot include required rework.")
        require(review["acceptance_basis"], "Approved review requires at least one acceptance basis.")
        state["status"] = APPROVED_STATUS
        state["owner"] = "watcher"
        state["next_action"] = "watcher_complete"
        clear_transient_routing_fields(state)
        mark_dispatch_pending(state, "watcher")
        review["problems"] = []
    else:
        require(review["problems"], "Rework review requires at least one problem.")
        require(review["required_rework"], "Rework review requires at least one required rework item.")
        state["status"] = REWORK_REQUIRED_STATUS
        state["owner"] = "worker"
        state["next_action"] = "worker_rework"
        clear_transient_routing_fields(state)
        mark_dispatch_pending(state, "worker")
        review["acceptance_basis"] = []

    state["review"] = review
    state["reviewed_at"] = timestamp


def reset_for_next_loop_iteration(state: dict, next_iteration: int) -> None:
    loop = state["loop"]
    loop["iteration"] = next_iteration
    loop["stop_reason"] = ""
    state["status"] = ACTIVE_STATUS
    state["owner"] = "worker"
    state["next_action"] = "worker_update"
    state["cleanup_required"] = False
    state["worker_claim"] = ""
    state["files_changed"] = []
    state["verification_command"] = ""
    state["verification_result"] = ""
    state["submitted_at"] = ""
    state["review"] = {}
    state["reviewed_at"] = ""
    state["gate_attempt"] = 0
    clear_completion_certification(state)
    clear_transient_routing_fields(state)
    mark_dispatch_pending(state, "worker")


def certify_cleanup_ready_state(state: dict, timestamp: str) -> None:
    completion = build_completion_certification(state, timestamp)
    certification = state.get("certification") if isinstance(state.get("certification"), dict) else {}
    certification["completion"] = completion
    state["certification"] = certification
    state["certification_hash"] = compute_certification_hash(completion)


def update_for_complete(state: dict, args: argparse.Namespace, timestamp: str) -> None:
    require(args.actor == "watcher", "Only the watcher may complete.")
    require(state.get("status") == APPROVED_STATUS, "Completion requires an approved review.")
    require_dispatch_authority(state, "watcher", "Watcher complete")
    review = state.get("review", {})
    require(review.get("verdict") == "approve", "Completion requires watcher approval in review state.")

    state["status"] = READY_FOR_CLEANUP_STATUS
    state["owner"] = "watcher"
    state["next_action"] = "complete"
    state["cleanup_required"] = True
    clear_transient_routing_fields(state)
    state["dispatch_status"] = IDLE_STATUS
    state["last_dispatch"] = {}

    decision = loop_decision(state)
    if decision.get("action") == "continue":
        reset_for_next_loop_iteration(state, decision["next_iteration"])
        return

    if decision.get("action") == "stop":
        loop = state.get("loop")
        if isinstance(loop, dict):
            loop["stop_reason"] = decision.get("reason", "")

    certify_cleanup_ready_state(state, timestamp)


def trace_line(args: argparse.Namespace, state: dict) -> str:
    if args.action == "submit":
        files_changed = ", ".join(state.get("files_changed", [])) or "no files listed"
        return f"worker submit: claim={state['worker_claim']}; files_changed={files_changed}; verification={state['verification_result']}"
    if args.action == "review":
        review = state["review"]
        return (
            f"watcher review: {review['verdict']}; "
            f"scope_checked={format_trace_value(review['scope_checked'])}; "
            f"problems={format_trace_value(review['problems'])}; "
            f"required_rework={format_trace_value(review['required_rework'])}; "
            f"acceptance_basis={format_trace_value(review['acceptance_basis'])}"
        )
    return "watcher complete"


def main() -> int:
    args = parse_args()
    run_root = Path(args.run_root).resolve()
    orchestration: dict | None = None

    def progress_transition(current_state: dict, _: str) -> None:
        nonlocal orchestration
        orchestration = publish_next_dispatch(current_state)

    try:
        if args.action == "submit":
            state = transition_state(
                run_root,
                actor=args.actor,
                action=args.action,
                expected_version=args.expected_version,
                apply_transition=lambda current_state, timestamp: update_for_submit(current_state, args, timestamp),
                progress_transition=progress_transition,
            )
        elif args.action == "review":
            state = transition_state(
                run_root,
                actor=args.actor,
                action=args.action,
                expected_version=args.expected_version,
                apply_transition=lambda current_state, timestamp: update_for_review(current_state, args, timestamp),
                progress_transition=progress_transition,
            )
        else:
            state = transition_state(
                run_root,
                actor=args.actor,
                action=args.action,
                expected_version=args.expected_version,
                apply_transition=lambda current_state, timestamp: update_for_complete(current_state, args, timestamp),
                progress_transition=progress_transition,
            )
    except StaleStateVersionError as error:
        fail(str(error))

    append_trace_event(run_root, trace_line(args, state))

    print(
        json.dumps(
            {
                "run_root": str(run_root),
                "status": state["status"],
                "owner": state["owner"],
                "next_action": state["next_action"],
                "dispatch_status": state.get("dispatch_status"),
                "orchestration": orchestration,
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

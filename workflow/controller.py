#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from state import append_trace_event, format_trace_value, load_state, utc_now, write_state


ALLOWED_SUBMIT_STATUSES = {"active", "rework_required"}
APPROVED_STATUS = "approved"
COMPLETE_STATUS = "complete"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update a lightweight claude-yolo-until-done run state.")
    parser.add_argument("--run-root", required=True, help="Path to the run bundle root")
    parser.add_argument("--actor", required=True, choices=("worker", "watcher"))
    parser.add_argument("--action", required=True, choices=("submit", "review", "complete"))

    parser.add_argument("--worker-claim")
    parser.add_argument("--files-changed", nargs="*")
    parser.add_argument("--verification-command")
    parser.add_argument("--verification-result")

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


def update_for_submit(state: dict, args: argparse.Namespace) -> None:
    require(args.actor == "worker", "Only the worker may submit.")
    require(state.get("status") in ALLOWED_SUBMIT_STATUSES, "Worker submit requires active or rework_required state.")
    require(args.worker_claim is not None, "--worker-claim is required for submit.")
    require(args.verification_command is not None, "--verification-command is required for submit.")
    require(args.verification_result is not None, "--verification-result is required for submit.")

    timestamp = utc_now()
    state["status"] = "needs_review"
    state["owner"] = "watcher"
    state["next_action"] = "watcher_review"
    state["worker_claim"] = args.worker_claim
    state["files_changed"] = list(args.files_changed or [])
    state["verification_command"] = args.verification_command
    state["verification_result"] = args.verification_result
    state["submitted_at"] = timestamp
    state["review"] = {}
    state["reviewed_at"] = ""
    state["updated_at"] = timestamp


def build_review_payload(args: argparse.Namespace) -> dict:
    return {
        "verdict": args.verdict,
        "scope_checked": list(args.scope_checked or []),
        "problems": list(args.problem),
        "required_rework": list(args.required_rework),
        "acceptance_basis": list(args.acceptance_basis),
    }


def update_for_review(state: dict, args: argparse.Namespace) -> None:
    require(args.actor == "watcher", "Only the watcher may review.")
    require(state.get("status") == "needs_review", "Watcher review requires needs_review state.")
    require(args.verdict is not None, "--verdict is required for review.")

    review = build_review_payload(args)
    if args.verdict == "approve":
        require(not review["required_rework"], "Approved review cannot include required rework.")
        require(review["acceptance_basis"], "Approved review requires at least one acceptance basis.")
        state["status"] = APPROVED_STATUS
        state["owner"] = "watcher"
        state["next_action"] = "watcher_complete"
        review["problems"] = []
    else:
        require(review["problems"], "Rework review requires at least one problem.")
        require(review["required_rework"], "Rework review requires at least one required rework item.")
        state["status"] = "rework_required"
        state["owner"] = "worker"
        state["next_action"] = "worker_rework"
        review["acceptance_basis"] = []

    timestamp = utc_now()
    state["review"] = review
    state["reviewed_at"] = timestamp
    state["updated_at"] = timestamp


def update_for_complete(state: dict, args: argparse.Namespace) -> None:
    require(args.actor == "watcher", "Only the watcher may complete.")
    require(state.get("status") == APPROVED_STATUS, "Completion requires an approved review.")
    review = state.get("review", {})
    require(review.get("verdict") == "approve", "Completion requires watcher approval in review state.")

    timestamp = utc_now()
    state["status"] = COMPLETE_STATUS
    state["owner"] = "watcher"
    state["next_action"] = "complete"
    state["cleanup_required"] = True
    state["updated_at"] = timestamp


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
    state = load_state(run_root)

    if args.action == "submit":
        update_for_submit(state, args)
    elif args.action == "review":
        update_for_review(state, args)
    else:
        update_for_complete(state, args)

    write_state(run_root, state)
    append_trace_event(run_root, trace_line(args, state))

    print(
        json.dumps(
            {
                "run_root": str(run_root),
                "status": state["status"],
                "owner": state["owner"],
                "next_action": state["next_action"],
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

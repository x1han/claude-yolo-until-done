#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from state import StaleStateVersionError, transition_state


EVENT_TO_FIELD = {
    "token_io": "last_token_io_at",
    "progress": "last_progress_at",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report worker heartbeat activity for a workflow run.")
    parser.add_argument("--run-root", required=True, help="Path to the run bundle root")
    parser.add_argument("--event", required=True, choices=tuple(EVENT_TO_FIELD), help="Worker activity event to report")
    parser.add_argument("--dispatch-owner", required=True, help="Current dispatch owner expected to hold the live lease")
    parser.add_argument("--expected-version", required=True, type=int, help="Expected authoritative state version for this heartbeat update")
    return parser.parse_args()


def fail(message: str) -> int:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def main() -> int:
    args = parse_args()
    run_root = Path(args.run_root).resolve()
    field_name = EVENT_TO_FIELD[args.event]

    def apply_transition(current_state: dict, timestamp: str) -> None:
        claim = current_state.get("dispatch_claim") if isinstance(current_state.get("dispatch_claim"), dict) else {}
        current_owner = claim.get("owner")
        require(
            current_owner == args.dispatch_owner,
            f"Heartbeat update requires current dispatch owner; current dispatch owner is {current_owner!r}.",
        )
        supervision = current_state.get("supervision")
        require(isinstance(supervision, dict), "Run supervision is missing or invalid.")
        updated_supervision = dict(supervision)
        updated_supervision.setdefault("last_token_io_at", "")
        updated_supervision.setdefault("last_progress_at", "")
        updated_supervision.setdefault("stall_timeout_seconds", 600)
        updated_supervision.setdefault("retry_limit", 3)
        updated_supervision.setdefault("retry_count", 0)
        updated_supervision.setdefault("last_recovery_at", "")
        updated_supervision.setdefault("last_recovery_reason", "")
        updated_supervision[field_name] = timestamp
        current_state["supervision"] = updated_supervision

    try:
        state = transition_state(
            run_root,
            actor="worker",
            action=f"report_{args.event}",
            expected_version=args.expected_version,
            apply_transition=apply_transition,
        )
    except StaleStateVersionError as error:
        fail(str(error))

    event_label = "token I/O" if args.event == "token_io" else "progress"
    print(json.dumps({
        "result": "recorded",
        "event": args.event,
        "state_version": state["state_version"],
        "current_state": f"Worker {event_label} heartbeat recorded.",
        "evidence": str(run_root / "state.json"),
        "blocked_on": "",
        "next": "Continue current worker dispatch.",
    }, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

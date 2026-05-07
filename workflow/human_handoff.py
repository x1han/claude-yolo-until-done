#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestrator import orchestrate, resume_after_human
from state import load_state, utc_now, write_state


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
    parser.add_argument("--resume-now", action="store_true", help="Explicitly resume the current task now")
    return parser.parse_args()


def fail(message: str) -> int:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def update_human_handoff(state: dict, summary: str, resume_ready: bool) -> None:
    state["human_handoff"] = {
        "summary": summary,
        "resume_ready": resume_ready,
    }
    state["updated_at"] = utc_now()


def main() -> int:
    args = parse_args()
    run_root = Path(args.run_root).resolve()
    state = load_state(run_root)

    require(state.get("allow_need_human") is True, "Human handoff is disabled for this run.")
    require(state.get("worker_request") == "need_human", "Run is not waiting on need_human guidance.")
    require(state.get("blocked_for_human") is True, "Run is not currently blocked for human guidance.")
    require(not args.resume_now or args.resume_ready is True, "Explicit resume requires resume_ready=true.")

    update_human_handoff(state, args.summary, args.resume_ready)
    write_state(run_root, state)

    if not args.resume_now:
        print(json.dumps({"result": "waiting_for_human", "resume_ready": args.resume_ready}, ensure_ascii=True))
        return 0
    resumed = resume_after_human(state, args.summary)
    resumed["updated_at"] = utc_now()
    write_state(run_root, resumed)
    orchestration = orchestrate(run_root, resumed)
    print(json.dumps({"result": "resumed", "orchestration": orchestration}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

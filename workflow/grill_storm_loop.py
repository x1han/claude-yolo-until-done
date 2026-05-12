#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_sessions import PLANNING_ROLE_NAMES, PLANNING_ROUND_STATUSES, agent_summary_path, append_planning_round, load_planning_rounds, resolve_role_session, tail_text
from grill_storm import status_payload

ROLE_DISPLAY = {"interviewer": "Muse (right-brain divergent intent explorer)", "planner": "Logos (left-brain logical spec/plan architect)"}

REQUIRED_OUTPUT_SCHEMA = {
    "role": "interviewer|planner",
    "round": "integer >= 1",
    "status": "completed|blocked|failed",
    "docs_touched": ["docs/decisions.md"],
    "summary": "short durable handoff summary",
    "decisions_recorded": ["decision text"],
    "questions_added": ["question text"],
    "next_recommendation": "what the peer or orchestrator should do next",
}

DISPATCHABLE_STATUSES = {"needs_internal_round", "needs_spec_authoring", "needs_spec_self_review", "needs_plan_authoring"}


def build_agent_prompt(dispatch: dict) -> str:
    role = dispatch["role"]
    display = ROLE_DISPLAY.get(role, role)
    lines = [
        f"You are the {display} agent in a grill-storm planning loop.",
        f"Round {dispatch['round']}.",
    ]
    if dispatch.get("planning_mode"):
        lines.append(f"Planning mode: {dispatch['planning_mode']}.")
    lines.extend([
        "",
        f"Reason for dispatch: {dispatch['reason']}",
        "",
        "## Docs you must read",
    ])
    for path in dispatch.get("read", []):
        lines.append(f"- {path}")
    lines.append("")
    lines.append("## Docs you may write")
    for path in dispatch.get("write_any_of", []):
        lines.append(f"- {path}")
    lines.append("")
    if dispatch.get("peer_summary"):
        lines.append("## Peer agent's last summary")
        lines.append(dispatch["peer_summary"])
        lines.append("")
    lines.append("## Required output")
    lines.append("Return a JSON object matching this schema:")
    lines.append("```json")
    lines.append(json.dumps(REQUIRED_OUTPUT_SCHEMA, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("After completing your round, write a durable summary to your role summary file so the peer agent can read it next round.")
    return "\n".join(lines)


def next_round_number(run_root: Path | None) -> int:
    if run_root is None:
        return 1
    return len(load_planning_rounds(run_root)) + 1


def peer_role(role: str) -> str:
    return "planner" if role == "interviewer" else "interviewer"


def read_peer_summary(run_root: Path | None, role: str) -> str:
    if run_root is None:
        return ""
    return tail_text(agent_summary_path(run_root, peer_role(role)))


def remap_docs_paths(paths: list[str], docs_dir_arg: str) -> list[str]:
    if docs_dir_arg == "docs":
        return paths
    return [f"{docs_dir_arg.rstrip('/')}/{path.removeprefix('docs/')}" if path.startswith("docs/") else path for path in paths]


def build_dispatch_request(project_dir: Path, status: dict, *, run_root: Path | None, round_number: int, docs_dir_arg: str = "docs") -> dict:
    role = str(status.get("next_actor", ""))
    if role not in PLANNING_ROLE_NAMES:
        raise ValueError(f"Unsupported grill-storm actor: {role}")
    resolved_run_root = run_root.resolve() if run_root is not None else None
    request = {
        "role": role,
        "round": round_number,
        "project_dir": str(project_dir.resolve()),
        "docs_dir": docs_dir_arg,
        "run_root": str(resolved_run_root) if resolved_run_root is not None else "",
        "planning_mode": str(status.get("planning_mode", "")),
        "read": remap_docs_paths(list(status.get("read", [])), docs_dir_arg),
        "write_any_of": remap_docs_paths(list(status.get("write_any_of", [])), docs_dir_arg),
        "reason": str(status.get("reason", "")),
        "peer_summary": read_peer_summary(resolved_run_root, role),
        "required_output_schema": REQUIRED_OUTPUT_SCHEMA,
    }
    if resolved_run_root is not None:
        session = resolve_role_session(resolved_run_root, role, "grill-storm-loop")
        request["session_action"] = session["action"]
        request["agent_id"] = session["agent_id"]
        request["agent_generation"] = session["generation"]
    request["agent_prompt"] = build_agent_prompt(request)
    return request


def require_string_list(payload: dict, field: str) -> list[str]:
    value = payload.get(field, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Malformed round result: {field} must be a string list")
    return value


def validate_round_result(dispatch: dict, result: dict) -> dict:
    role = str(result.get("role", ""))
    if role != dispatch.get("role"):
        raise ValueError("Round result role does not match dispatch request")
    round_number = result.get("round")
    if round_number != dispatch.get("round"):
        raise ValueError("Round result number does not match dispatch request")
    status = str(result.get("status", ""))
    if status not in PLANNING_ROUND_STATUSES:
        raise ValueError(f"Malformed round result status: {status}")
    docs_touched = require_string_list(result, "docs_touched")
    decisions_recorded = require_string_list(result, "decisions_recorded")
    questions_added = require_string_list(result, "questions_added")
    allowed = set(dispatch.get("write_any_of", []))
    disallowed = [path for path in docs_touched if path not in allowed]
    if disallowed:
        raise ValueError(f"Round result touched docs outside allowed write set: {', '.join(disallowed)}")
    if status == "completed" and not docs_touched and not decisions_recorded and not questions_added:
        raise ValueError("Round result completed with no docs, decisions, or questions")
    summary = str(result.get("summary", "")).strip()
    if not summary:
        raise ValueError("Malformed round result: summary is required")
    return {
        "role": role,
        "round": round_number,
        "status": status,
        "docs_touched": docs_touched,
        "summary": summary,
        "decisions_recorded": decisions_recorded,
        "questions_added": questions_added,
        "next_recommendation": str(result.get("next_recommendation", "")).strip(),
    }


def record_round_result(dispatch: dict, result: dict, now: str | None = None) -> dict:
    run_root = str(dispatch.get("run_root", ""))
    if not run_root:
        raise ValueError("Dispatch request has no run_root for round recording")
    validated = validate_round_result(dispatch, result)
    return append_planning_round(Path(run_root), validated, now=now)


def run_planning_step(project_dir: Path, *, run_root: Path | None = None, docs_dir_arg: str = "docs", max_rounds: int = 6) -> dict:
    status = status_payload(project_dir.resolve(), docs_dir_arg)
    if status.get("status") not in DISPATCHABLE_STATUSES:
        return status
    round_number = next_round_number(run_root)
    if round_number > max_rounds:
        return {
            "status": "max_rounds_exceeded",
            "human_allowed": False,
            "round": round_number,
            "max_rounds": max_rounds,
            "reason": "grill-storm internal rounds did not converge",
        }
    dispatch = build_dispatch_request(project_dir, status, run_root=run_root, round_number=round_number, docs_dir_arg=docs_dir_arg)
    return {
        "status": "dispatch_required",
        "human_allowed": False,
        "dispatch_request": dispatch,
        "controller_status": status,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run grill-storm planning loop commands.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    next_parser = subparsers.add_parser("next", help="Emit next planning action or dispatch request")
    next_parser.add_argument("--project-dir", required=True, help="Target project directory")
    next_parser.add_argument("--docs-dir", default="docs", help="Docs directory relative to project directory unless absolute")
    next_parser.add_argument("--run-root", default="", help="Optional run root for planning role logs")
    next_parser.add_argument("--max-rounds", type=int, default=6, help="Maximum internal planning rounds")

    record_parser = subparsers.add_parser("record", help="Record a completed planning agent round")
    record_parser.add_argument("--result-json", required=True, help="JSON object with dispatch_request and round_result")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "next":
            run_root = Path(args.run_root).resolve() if args.run_root else None
            payload = run_planning_step(Path(args.project_dir).resolve(), run_root=run_root, docs_dir_arg=args.docs_dir, max_rounds=args.max_rounds)
        else:
            envelope = json.loads(args.result_json)
            record = record_round_result(envelope["dispatch_request"], envelope["round_result"])
            payload = {"status": "recorded", "record": record}
    except (KeyError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

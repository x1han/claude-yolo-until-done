#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from validate_grill_docs import GrillDocsError, approved_docs_report, blocking_questions, internal_rounds, read_bundle


def status_payload(project_dir: Path, docs_dir_arg: str = "docs") -> dict[str, object]:
    try:
        root, bundle = read_bundle(project_dir, docs_dir_arg)
    except GrillDocsError as error:
        return {
            "status": "needs_init",
            "human_allowed": False,
            "next_actor": "interviewer",
            "reason": str(error),
        }

    report = approved_docs_report(project_dir, docs_dir_arg)
    if report["status"] == "ready_for_execution":
        return {
            "status": "ready_for_execution",
            "human_allowed": False,
            "spec": report["spec"],
            "plan": report["plan"],
            "docs_dir": str(root),
        }

    rounds = internal_rounds(bundle["decisions"])
    if rounds["interviewer"] < 1:
        return {
            "status": "needs_internal_round",
            "next_actor": "interviewer",
            "human_allowed": False,
            "read": ["docs/intent.md", "docs/open-questions.md"],
            "write_any_of": ["docs/intent.md", "docs/open-questions.md", "docs/decisions.md"],
            "reason": "interviewer internal round required before human question",
        }
    if rounds["planner"] < 1:
        return {
            "status": "needs_internal_round",
            "next_actor": "planner",
            "human_allowed": False,
            "read": ["docs/intent.md", "docs/decisions.md", "docs/spec.md"],
            "write_any_of": ["docs/decisions.md", "docs/spec.md", "docs/plan.md"],
            "reason": "planner internal challenge required before human question",
        }

    blockers = blocking_questions(bundle["open_questions"])
    if blockers:
        first = blockers[0]
        return {
            "status": "ask_user",
            "human_allowed": True,
            "question": first["question"],
            "recommended_answer": first["recommended_answer"],
            "blocking_reason": first["raw"],
            "max_questions": 1,
        }

    return {
        "status": "needs_internal_round",
        "next_actor": "planner",
        "human_allowed": False,
        "read": ["docs/intent.md", "docs/decisions.md", "docs/spec.md"],
        "write_any_of": ["docs/decisions.md", "docs/spec.md", "docs/plan.md"],
        "reason": "; ".join(str(error) for error in report["errors"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report next grill-storm planning action.")
    parser.add_argument("--project-dir", required=True, help="Target project directory")
    parser.add_argument("--docs-dir", default="docs", help="Docs directory relative to project directory unless absolute")
    parser.add_argument("--status", action="store_true", help="Print planning status JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.status:
        print("Only --status is supported for grill-storm controller.", file=sys.stderr)
        return 2
    print(json.dumps(status_payload(Path(args.project_dir).resolve(), args.docs_dir), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

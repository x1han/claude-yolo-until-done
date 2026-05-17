#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from human_approvals import verified_human_approval_sources
from validate_grill_docs import GrillDocsError, accepted_decision_count, approved_docs_report, blocking_questions, consensus_items, has_human_intent_approval, has_joint_uncertainty, has_template_only_lines, internal_rounds, plan_quality_errors, read_bundle, status_value


SPEC_REVIEW_READY_SECTIONS = ("## Problem", "## Acceptance Criteria")
SPEC_TEMPLATE_MARKER = "Planning needs hard docs-first contract."
PLAN_TEMPLATE_MARKER = "Implement hard gate."


def artifact_path(docs_dir_arg: str, filename: str) -> str:
    return str(Path(docs_dir_arg) / filename)


def human_review_payload(status: str, artifact_path: str, review_kind: str, summary: str, next_step: str) -> dict[str, object]:
    return {
        "status": status,
        "human_allowed": True,
        "artifact_path": artifact_path,
        "review": f"{review_kind} path: {artifact_path}\nSimple summary: {summary}\n{next_step}",
        "source": artifact_path,
        "max_questions": 1,
    }


def status_payload(project_dir: Path, docs_dir_arg: str = "docs") -> dict[str, object]:
    try:
        root, bundle = read_bundle(project_dir, docs_dir_arg)
    except GrillDocsError as error:
        return {
            "status": "needs_init",
            "human_allowed": False,
            "next_actor": "muse",
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
    if rounds["muse"] < 1:
        return {
            "status": "needs_internal_round",
            "next_actor": "muse",
            "human_allowed": False,
            "read": ["docs/intent.md", "docs/open-questions.md"],
            "write_any_of": ["docs/intent.md", "docs/open-questions.md", "docs/decisions.md"],
            "reason": "muse internal round required before human question",
        }
    if rounds["logos"] < 1:
        return {
            "status": "needs_internal_round",
            "next_actor": "logos",
            "human_allowed": False,
            "read": ["docs/intent.md", "docs/decisions.md", "docs/spec.md"],
            "write_any_of": ["docs/decisions.md", "docs/spec.md", "docs/plan.md"],
            "reason": "logos internal challenge required before human question",
        }

    blockers = blocking_questions(bundle["open_questions"])
    items = consensus_items(bundle["decisions"])
    joint_uncertainty = has_joint_uncertainty(bundle["decisions"])
    verified_sources = verified_human_approval_sources(project_dir)
    if not has_human_intent_approval(bundle["decisions"], verified_sources):
        if items:
            return {
                "status": "human_dialogue",
                "human_allowed": True,
                "dialogue_type": "consensus",
                "items": items,
                "question": "Which consensus direction should grill-storm turn into the spec?",
                "recommended_answer": next((str(item["title"]) for item in items if item.get("recommended")), str(items[0]["title"])),
                "source": "docs/decisions.md",
            }
        if blockers and joint_uncertainty:
            first = blockers[0]
            return {
                "status": "human_dialogue",
                "human_allowed": True,
                "dialogue_type": "joint_uncertainty",
                "items": [],
                "question": first["question"],
                "recommended_answer": first["recommended_answer"],
                "source": "docs/open-questions.md",
                "blocking_reason": first["raw"],
            }
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
            "next_actor": "logos",
            "human_allowed": False,
            "read": ["docs/intent.md", "docs/decisions.md", "docs/spec.md"],
            "write_any_of": ["docs/decisions.md", "docs/spec.md", "docs/plan.md"],
            "reason": "Muse/Logos must record consensus-candidate or joint-uncertainty before spec authoring",
        }

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

    spec_status = status_value(bundle["spec"])
    plan_status = status_value(bundle["plan"])
    spec_self_reviewed = accepted_decision_count(bundle["decisions"], actor="logos", source="spec-self-review") > 0
    human_spec_reviewed = (
        accepted_decision_count(bundle["decisions"], actor="human", source="spec-review") > 0
        and "spec-review" in verified_sources
    )
    human_plan_reviewed = (
        accepted_decision_count(bundle["decisions"], actor="human", source="plan-review") > 0
        and "plan-review" in verified_sources
    )

    if spec_status == "draft" and not spec_self_reviewed:
        spec_ready_for_review = (
            all(section in bundle["spec"] for section in SPEC_REVIEW_READY_SECTIONS)
            and SPEC_TEMPLATE_MARKER not in bundle["spec"]
            and not has_template_only_lines(bundle["spec"])
        )
        if spec_ready_for_review:
            return {
                "status": "needs_spec_self_review",
                "next_actor": "logos",
                "planning_mode": "logos-spec-reviewer",
                "human_allowed": False,
                "read": ["docs/intent.md", "docs/decisions.md", "docs/spec.md"],
                "write_any_of": ["docs/decisions.md", "docs/spec.md"],
                "reason": "Logos must self-review draft spec before human spec review",
            }
        return {
            "status": "needs_spec_authoring",
            "next_actor": "logos",
            "planning_mode": "logos-spec-writer",
            "human_allowed": False,
            "read": ["docs/intent.md", "docs/decisions.md", "docs/open-questions.md"],
            "write_any_of": ["docs/spec.md", "docs/decisions.md"],
            "reason": "human-approved intent exists; Logos must write draft spec",
        }

    if spec_self_reviewed and not human_spec_reviewed and spec_status in {"self-reviewed", "approved"}:
        return human_review_payload(
            "human_spec_review",
            artifact_path(docs_dir_arg, "spec.md"),
            "Spec",
            "Review spec before plan authoring.",
            "Record accepted human decision with Source: spec-review before planning.",
        )

    if spec_status == "approved" and human_spec_reviewed and plan_status == "approved" and not human_plan_reviewed:
        return human_review_payload(
            "human_plan_review",
            artifact_path(docs_dir_arg, "plan.md"),
            "Plan",
            "Review plan before execution.",
            "Record accepted human decision with Source: plan-review before execution.",
        )

    if spec_status == "approved" and human_spec_reviewed and plan_status == "draft" and not human_plan_reviewed:
        if not plan_quality_errors(bundle["plan"]) and PLAN_TEMPLATE_MARKER not in bundle["plan"]:
            return human_review_payload(
                "human_plan_review",
                artifact_path(docs_dir_arg, "plan.md"),
                "Plan",
                "Review plan before execution.",
                "Record accepted human decision with Source: plan-review before execution.",
            )
        return {
            "status": "needs_plan_authoring",
            "next_actor": "logos",
            "planning_mode": "logos-plan-writer",
            "human_allowed": False,
            "read": ["docs/spec.md", "docs/decisions.md", "docs/plan.md"],
            "write_any_of": ["docs/plan.md", "docs/decisions.md"],
            "reason": "human-approved spec exists; Logos must write execution plan",
        }

    return {
        "status": "needs_internal_round",
        "next_actor": "logos",
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

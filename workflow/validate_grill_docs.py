#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from agent_sessions import PLANNING_ROLE_NAMES
from human_approvals import HUMAN_APPROVAL_SOURCES, verified_human_approval_sources

REQUIRED_DOCS = {
    "intent": "intent.md",
    "open_questions": "open-questions.md",
    "decisions": "decisions.md",
    "spec": "spec.md",
    "plan": "plan.md",
}

TEMPLATE_EMPTY_MARKERS = {
    "- ",
    "- [ ] ",
    "1. ",
    "2. ",
    "- Must:",
    "- Should:",
    "- Nice-to-have:",
    "- Decision:",
    "- Reason:",
}


class GrillDocsError(ValueError):
    pass


def docs_dir(project_dir: Path, docs_dir_arg: str = "docs") -> Path:
    candidate = Path(docs_dir_arg)
    if candidate.is_absolute():
        return candidate
    return (project_dir / candidate).resolve()


def read_bundle(project_dir: Path, docs_dir_arg: str = "docs") -> tuple[Path, dict[str, str]]:
    root = docs_dir(project_dir, docs_dir_arg)
    bundle: dict[str, str] = {}
    missing: list[str] = []
    for key, filename in REQUIRED_DOCS.items():
        path = root / filename
        if not path.exists():
            missing.append(filename)
            continue
        bundle[key] = path.read_text(encoding="utf-8")
    if missing:
        raise GrillDocsError(f"missing grill-storm docs: {', '.join(missing)}")
    return root, bundle


def status_value(body: str) -> str:
    match = re.search(r"^Status:\s*(\S+)", body, flags=re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip().lower() if match else ""


def decision_blocks(decisions: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in decisions.splitlines():
        if line.startswith("### "):
            if current:
                blocks.append("\n".join(current))
            current = [line]
            continue
        if current:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def field_value(text: str, field: str, *, bullet: bool = False, normalize: bool = False) -> str:
    prefix = r"^-\s*" if bullet else r"(?:^|\|)\s*(?:- \[ \]\s*)?"
    match = re.search(prefix + re.escape(field) + r":\s*([^|\n]+)", text, flags=re.MULTILINE | re.IGNORECASE)
    value = match.group(1).strip() if match else ""
    return value.lower() if normalize else value


def internal_rounds(decisions: str) -> dict[str, int]:
    rounds = {role: 0 for role in PLANNING_ROLE_NAMES}
    for block in decision_blocks(decisions):
        if field_value(block, "Status", bullet=True, normalize=True) != "accepted":
            continue
        actor = field_value(block, "Actor", bullet=True, normalize=True)
        if actor in rounds:
            rounds[actor] += 1
    return rounds


def accepted_decision_count(decisions: str, *, actor: str, source: str) -> int:
    count = 0
    for block in decision_blocks(decisions):
        if field_value(block, "Status", bullet=True, normalize=True) != "accepted":
            continue
        if field_value(block, "Actor", bullet=True, normalize=True) != actor:
            continue
        if field_value(block, "Source", bullet=True, normalize=True) == source:
            count += 1
    return count


def has_human_intent_approval(decisions: str, verified_sources: set[str]) -> bool:
    return (
        accepted_decision_count(decisions, actor="human", source="consensus") > 0
        and "consensus" in verified_sources
    ) or (
        accepted_decision_count(decisions, actor="human", source="uncertainty") > 0
        and "uncertainty" in verified_sources
    )


def plan_quality_errors(plan: str) -> list[str]:
    errors: list[str] = []
    required_terms = {
        "exact files": "Files:",
        "exact commands": "Run:",
        "expected outputs": "Expected:",
        "verification steps": "Verify:",
        "rollback/safety notes": "## Rollback / Safety",
    }
    for label, needle in required_terms.items():
        if needle not in plan:
            errors.append(f"plan.md is missing {label}")
    forbidden = ("TBD", "TODO", "implement later")
    for marker in forbidden:
        if marker.lower() in plan.lower():
            errors.append(f"plan.md contains forbidden placeholder marker: {marker}")
    return errors


def has_template_only_lines(body: str) -> bool:
    for line in body.splitlines():
        if line.rstrip() in TEMPLATE_EMPTY_MARKERS:
            return True
    return False


def blocking_questions(open_questions: str) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    current_section = ""
    current: dict[str, str] | None = None
    for line in open_questions.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = stripped[3:].strip().lower()
            current = None
            continue
        if stripped.startswith("- [ ]"):
            current = {
                "section": current_section,
                "blocking": field_value(stripped, "Blocking", normalize=True),
                "question": field_value(stripped, "Question"),
                "recommended_answer": field_value(stripped, "Recommended"),
                "raw": stripped,
            }
            if current_section == "high priority" and current["blocking"] == "yes":
                questions.append(current)
            continue
        if current is None or not line.startswith("  "):
            continue
        current["raw"] = f"{current['raw']}\n{stripped}"
        question = field_value(stripped, "Question")
        recommended = field_value(stripped, "Recommended")
        blocking = field_value(stripped, "Blocking", normalize=True)
        if question:
            current["question"] = question
        if recommended:
            current["recommended_answer"] = recommended
        if blocking:
            current["blocking"] = blocking
    return questions


def consensus_items(decisions: str, *, limit: int = 3) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for block in decision_blocks(decisions):
        if field_value(block, "Status", bullet=True, normalize=True) != "accepted":
            continue
        if field_value(block, "Source", bullet=True, normalize=True) != "consensus-candidate":
            continue
        for line in block.splitlines():
            raw = line.strip()
            if not raw.startswith("- Consensus:"):
                continue
            title = field_value(raw, "Consensus", bullet=True)
            summary = field_value(raw, "Summary")
            tradeoffs = field_value(raw, "Tradeoffs")
            recommended = field_value(raw, "Recommended", normalize=True) == "true"
            if title:
                items.append({
                    "title": title,
                    "summary": summary,
                    "tradeoffs": [tradeoffs] if tradeoffs else [],
                    "recommended": recommended,
                })
                if len(items) >= limit:
                    return items
    return items


def has_joint_uncertainty(decisions: str) -> bool:
    return accepted_decision_count(decisions, actor="logos", source="joint-uncertainty") > 0


def human_only_source_errors(decisions: str) -> list[str]:
    errors: list[str] = []
    for block in decision_blocks(decisions):
        source = field_value(block, "Source", bullet=True, normalize=True)
        if source not in HUMAN_APPROVAL_SOURCES:
            continue
        actor = field_value(block, "Actor", bullet=True, normalize=True)
        if actor and actor != "human":
            errors.append(f"decisions.md has human-only source {source} recorded by {actor}")
    return errors


def approved_docs_report(project_dir: Path, docs_dir_arg: str = "docs") -> dict[str, object]:
    root, bundle = read_bundle(project_dir, docs_dir_arg)
    errors: list[str] = []

    if status_value(bundle["spec"]) != "approved":
        errors.append("spec.md is not approved")
    if status_value(bundle["plan"]) != "approved":
        errors.append("plan.md is not approved")

    for key, body in bundle.items():
        if has_template_only_lines(body):
            errors.append(f"{REQUIRED_DOCS[key]} still contains template-only placeholders")

    verified_sources = verified_human_approval_sources(project_dir)
    rounds = internal_rounds(bundle["decisions"])
    if rounds["muse"] < 1:
        errors.append("decisions.md is missing accepted muse internal round")
    if rounds["logos"] < 1:
        errors.append("decisions.md is missing accepted logos internal round")
    errors.extend(human_only_source_errors(bundle["decisions"]))
    if not has_human_intent_approval(bundle["decisions"], verified_sources):
        errors.append("decisions.md is missing verified human consensus or uncertainty resolution")
    if accepted_decision_count(bundle["decisions"], actor="logos", source="spec-self-review") < 1:
        errors.append("decisions.md is missing accepted Logos spec self-review")
    if accepted_decision_count(bundle["decisions"], actor="human", source="spec-review") < 1:
        errors.append("decisions.md is missing accepted human spec review")
    elif "spec-review" not in verified_sources:
        errors.append("human spec review is missing verified main-session approval")
    if accepted_decision_count(bundle["decisions"], actor="human", source="plan-review") < 1:
        errors.append("decisions.md is missing accepted human plan review")
    elif "plan-review" not in verified_sources:
        errors.append("human plan review is missing verified main-session approval")

    blockers = blocking_questions(bundle["open_questions"])
    if blockers:
        errors.append("open-questions.md still contains blocking high-impact questions")
    for blocker in blockers:
        if not blocker["question"]:
            errors.append("open-questions.md has blocking high-impact question without Question field")
        if not blocker["recommended_answer"]:
            errors.append("open-questions.md has blocking high-impact question without Recommended field")

    if "## Acceptance Criteria" not in bundle["spec"]:
        errors.append("spec.md is missing acceptance criteria")
    if "## Steps" not in bundle["plan"]:
        errors.append("plan.md is missing implementation steps")
    errors.extend(plan_quality_errors(bundle["plan"]))

    return {
        "status": "ready_for_execution" if not errors else "blocked",
        "docs_dir": str(root),
        "spec": str(root / "spec.md"),
        "plan": str(root / "plan.md"),
        "errors": errors,
    }


def ensure_ready_for_execution(project_dir: Path, docs_dir_arg: str = "docs") -> dict[str, object]:
    report = approved_docs_report(project_dir, docs_dir_arg)
    if report["errors"]:
        raise GrillDocsError("; ".join(str(error) for error in report["errors"]))
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate grill-storm planning docs before execution.")
    parser.add_argument("--project-dir", required=True, help="Target project directory")
    parser.add_argument("--docs-dir", default="docs", help="Docs directory relative to project directory unless absolute")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = ensure_ready_for_execution(Path(args.project_dir).resolve(), args.docs_dir)
    except GrillDocsError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

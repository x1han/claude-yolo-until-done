#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

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


def actor_decision_count(decisions: str, actor: str) -> int:
    pattern = re.compile(r"^- Status:\s*accepted\s*$[\s\S]*?^- Actor:\s*" + re.escape(actor) + r"\s*$", re.MULTILINE | re.IGNORECASE)
    return len(pattern.findall(decisions))


def internal_rounds(decisions: str) -> dict[str, int]:
    return {
        "interviewer": actor_decision_count(decisions, "interviewer"),
        "planner": actor_decision_count(decisions, "planner"),
    }


def has_template_only_lines(body: str) -> bool:
    for line in body.splitlines():
        if line.rstrip() in TEMPLATE_EMPTY_MARKERS:
            return True
    return False


def blocking_questions(open_questions: str) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    for line in open_questions.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- [ ]"):
            continue
        if "Blocking: yes" not in stripped:
            continue
        question = ""
        recommended = ""
        question_match = re.search(r"Question:\s*([^|]+)", stripped)
        recommended_match = re.search(r"Recommended:\s*(.+)$", stripped)
        if question_match:
            question = question_match.group(1).strip()
        if recommended_match:
            recommended = recommended_match.group(1).strip()
        questions.append({"question": question, "recommended_answer": recommended, "raw": stripped})
    return questions


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

    rounds = internal_rounds(bundle["decisions"])
    if rounds["interviewer"] < 1:
        errors.append("decisions.md is missing accepted interviewer internal round")
    if rounds["planner"] < 1:
        errors.append("decisions.md is missing accepted planner internal round")

    blockers = blocking_questions(bundle["open_questions"])
    if blockers:
        errors.append("open-questions.md still contains blocking high-impact questions")

    if "## Acceptance Criteria" not in bundle["spec"]:
        errors.append("spec.md is missing acceptance criteria")
    if "## Steps" not in bundle["plan"]:
        errors.append("plan.md is missing implementation steps")
    if "Verify:" not in bundle["plan"]:
        errors.append("plan.md is missing verification steps")

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

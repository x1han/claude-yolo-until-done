#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_DOCS_DIR = Path("docs")


def build_intent_template(request: str) -> str:
    return (
        "# Intent\n\n"
        "## Primary Goal\n"
        f"- {request.strip()}\n\n"
        "## Why This Matters\n"
        "- \n\n"
        "## Non-Goals\n"
        "- \n\n"
        "## Constraints\n"
        "- Time:\n"
        "- Tech:\n"
        "- Compatibility:\n"
        "- Budget:\n\n"
        "## Preferences\n"
        "- Prefer:\n"
        "- Avoid:\n\n"
        "## Assumptions\n"
        "- \n\n"
        "## Unknowns\n"
        "- \n"
    )


def build_open_questions_template() -> str:
    return (
        "# Open Questions\n\n"
        "## High Priority\n"
        "- [ ] \n"
        "- [ ] \n\n"
        "## Medium Priority\n"
        "- [ ] \n"
        "- [ ] \n\n"
        "## Low Priority\n"
        "- [ ] \n\n"
        "## Answered Recently\n"
        "- [x] Question:\n"
        "  Answer:\n"
        "  Impact:\n"
    )


def build_decisions_template() -> str:
    return (
        "# Decisions\n\n"
        "## Decision Log\n\n"
        "Record accepted Muse and Logos rounds here. Do not mark template examples accepted.\n\n"
        "### 2026-05-10 - Example decision title\n"
        "- Status: draft\n"
        "- Actor: muse\n"
        "- Decision: Example pending decision text.\n"
        "- Reason: Example pending reason.\n"
        "- Alternatives considered: Example alternatives.\n"
        "- Impact: Example impact.\n"
        "- Revisit when: Example revisit trigger.\n\n"
        "## Source Guide\n"
        "Use source values only inside real decision blocks, never in template examples.\n"
        "Internal sources: consensus-candidate, joint-uncertainty, spec-self-review.\n"
        "Human-only sources: consensus, uncertainty, spec-review, plan-review.\n"
    )


def build_spec_template() -> str:
    return (
        "# Spec\n\n"
        "Status: draft\n\n"
        "## Problem\n"
        "- \n\n"
        "## Users\n"
        "- \n\n"
        "## Desired Outcome\n"
        "- \n\n"
        "## Requirements\n"
        "- Must:\n"
        "- Should:\n"
        "- Nice-to-have:\n\n"
        "## User Flows\n"
        "1. \n"
        "2. \n\n"
        "## Acceptance Criteria\n"
        "- [ ] \n"
        "- [ ] \n\n"
        "## Risks\n"
        "- \n\n"
        "## Out of Scope\n"
        "- \n"
    )


def build_plan_template() -> str:
    return (
        "# Plan\n\n"
        "Status: draft\n\n"
        "## Goal\n"
        "- \n\n"
        "## Steps\n"
        "1. Step:\n"
        "   Verify:\n"
        "2. Step:\n"
        "   Verify:\n"
        "3. Step:\n"
        "   Verify:\n\n"
        "## Dependencies\n"
        "- \n\n"
        "## File/Area Impact\n"
        "- \n\n"
        "## Tests\n"
        "- \n\n"
        "## Rollback / Safety\n"
        "- \n"
    )


DOC_BUILDERS = (
    ("intent", "intent.md", build_intent_template),
    ("open_questions", "open-questions.md", lambda _request: build_open_questions_template()),
    ("decisions", "decisions.md", lambda _request: build_decisions_template()),
    ("spec", "spec.md", lambda _request: build_spec_template()),
    ("plan", "plan.md", lambda _request: build_plan_template()),
)


def resolve_docs_dir(project_dir: Path, docs_dir_arg: str) -> Path:
    candidate = Path(docs_dir_arg)
    if candidate.is_absolute():
        return candidate
    return (project_dir / candidate).resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize grill-storm planning docs bundle.")
    parser.add_argument("--project-dir", required=True, help="Target project directory")
    parser.add_argument("--request", required=True, help="Initial natural-language request for planning bundle")
    parser.add_argument("--docs-dir", default=str(DEFAULT_DOCS_DIR), help="Docs directory relative to the project directory unless absolute")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    docs_dir = resolve_docs_dir(project_dir, args.docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    preserved: list[str] = []
    files: dict[str, str] = {}

    for key, filename, builder in DOC_BUILDERS:
        path = docs_dir / filename
        files[key] = str(path)
        if path.exists():
            preserved.append(key)
            continue
        path.write_text(builder(args.request), encoding="utf-8")
        created.append(key)

    print(json.dumps({"docs_dir": str(docs_dir), "files": files, "created": created, "preserved": preserved}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

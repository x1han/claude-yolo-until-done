from __future__ import annotations

import re
from pathlib import Path


_TASK_HEADING_PATTERN = re.compile(r"^###\s+Task\s+\d+\s*:\s+(.*\S)\s*$")
_TASK_LINE_PATTERN = re.compile(r"^(\d+)\.\s+(.*\S)\s*$")
_TASK_SECTION_PATTERN = re.compile(
    r"^#{1,6}\s+(?:Tasks?|Task\s+List|Implementation\s+Steps|Work\s+Items)\s*$",
    re.IGNORECASE,
)


def extract_first_task(plan_path: Path) -> tuple[str, str]:
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        stripped = line.strip()
        heading_match = _TASK_HEADING_PATTERN.match(stripped)
        if heading_match:
            return stripped, heading_match.group(1)

    in_task_section = False
    for line in lines:
        stripped = line.strip()
        if _TASK_SECTION_PATTERN.match(stripped):
            in_task_section = True
            continue
        if stripped.startswith("#"):
            in_task_section = False
            continue
        if not in_task_section:
            continue
        line_match = _TASK_LINE_PATTERN.match(stripped)
        if line_match:
            return stripped, line_match.group(2)

    raise SystemExit(f"Could not extract first task from plan: {plan_path}")


def build_master_checklist(spec_path: Path, plan_path: Path) -> dict:
    spec_excerpt = spec_path.read_text(encoding="utf-8").strip()
    first_task_line, task_title = extract_first_task(plan_path)

    return {
        "tasks": [
            {
                "task_id": "task-001",
                "task_title": task_title,
                "plan_task_text": first_task_line,
                "spec_excerpt": spec_excerpt,
                "checklist_items": [
                    "match scope",
                    "require fresh verification",
                    "reject drift",
                ],
            }
        ]
    }

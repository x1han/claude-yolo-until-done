from __future__ import annotations

import re
from pathlib import Path

from state import build_current_task_view


_TASK_HEADING_PATTERN = re.compile(r"^###\s+Task\s+\d+\s*:\s+(.*\S)\s*$")
_TASK_LINE_PATTERN = re.compile(r"^(\d+)\.\s+(.*\S)\s*$")
_TASK_SECTION_PATTERN = re.compile(
    r"^#{1,6}\s+(?:Tasks?|Task\s+List|Implementation\s+Steps|Work\s+Items)\s*$",
    re.IGNORECASE,
)


def extract_plan_tasks(plan_path: Path) -> list[tuple[str, str]]:
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    heading_tasks: list[tuple[str, str]] = []
    for line in lines:
        stripped = line.strip()
        heading_match = _TASK_HEADING_PATTERN.match(stripped)
        if heading_match:
            heading_tasks.append((stripped, heading_match.group(1)))
    if heading_tasks:
        return heading_tasks

    section_tasks: list[tuple[str, str]] = []
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
            section_tasks.append((stripped, line_match.group(2)))
    if section_tasks:
        return section_tasks

    raise SystemExit(f"Could not extract any tasks from plan: {plan_path}")


def build_master_checklist(spec_path: Path, plan_path: Path) -> dict:
    spec_excerpt = spec_path.read_text(encoding="utf-8").strip()
    plan_tasks = extract_plan_tasks(plan_path)

    return {
        "tasks": [
            {
                "task_id": f"task-{index:03d}",
                "task_title": task_title,
                "plan_task_text": plan_task_text,
                "spec_excerpt": spec_excerpt,
                "checklist_items": [
                    "match scope",
                    "require fresh verification",
                    "reject drift",
                ],
            }
            for index, (plan_task_text, task_title) in enumerate(plan_tasks, start=1)
        ]
    }


def build_checklist_from_state(state: dict) -> dict:
    current_task = build_current_task_view(state)
    task_inputs = current_task.get("task_inputs")
    if not isinstance(task_inputs, dict) or not task_inputs:
        raise SystemExit("Continue-run state is missing task_inputs needed to rebuild watcher_checklist.json")

    return {
        "current_task": current_task,
        "tasks": [task_inputs],
    }

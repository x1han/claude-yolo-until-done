#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from checklist import build_master_checklist
from state import build_state, build_trace, write_json, write_text


ROOT_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT_DIR / "templates"


def fail_if_unsupported_headless_mode() -> None:
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT") != "print":
        return
    raise SystemExit(
        "Unsupported headless claude -p runtime: Stop-hook blocking cannot keep an unfinished claude-yolo run alive in print mode. "
        "Use an interactive Claude Code session instead."
    )


def bootstrap_run(
    spec_path: Path,
    plan_path: Path,
    run_root: Path,
    goal: str,
    success_criteria: list[str],
    repo_root: Path,
) -> dict:
    fail_if_unsupported_headless_mode()

    if not spec_path.exists():
        raise SystemExit(f"Spec not found: {spec_path}")
    if not plan_path.exists():
        raise SystemExit(f"Plan not found: {plan_path}")

    resolved_run_root = run_root.resolve()
    state = build_state(
        TEMPLATES_DIR / "state-template.json",
        goal=goal,
        success_criteria=success_criteria,
        plan_path=plan_path,
        spec_path=spec_path,
        repo_root=repo_root,
    )
    checklist = build_master_checklist(spec_path, plan_path)
    first_task = checklist["tasks"][0]
    state["task_title"] = first_task["task_title"]
    state["task_inputs"] = dict(first_task)
    trace = build_trace(
        TEMPLATES_DIR / "trace-template.md",
        goal=goal,
        success_criteria=success_criteria,
    )

    state_path = resolved_run_root / "state.json"
    trace_path = resolved_run_root / "trace.md"
    checklist_path = resolved_run_root / "watcher_checklist.json"
    write_json(state_path, state)
    write_text(trace_path, trace)
    write_json(checklist_path, checklist)

    return {
        "run_root": str(resolved_run_root),
        "state_path": str(state_path),
        "trace_path": str(trace_path),
        "checklist_path": str(checklist_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a lightweight claude-yolo-until-done run bundle.")
    parser.add_argument("--spec", required=True, help="Approved spec path")
    parser.add_argument("--plan", required=True, help="Approved implementation plan path")
    parser.add_argument("--run-root", required=True, help="Destination run bundle root")
    parser.add_argument("--goal", required=True, help="Run goal")
    parser.add_argument(
        "--success-criterion",
        action="append",
        dest="success_criteria",
        default=[],
        help="Success criterion for this run; repeat to provide multiple entries",
    )
    args = parser.parse_args()

    summary = bootstrap_run(
        spec_path=Path(args.spec),
        plan_path=Path(args.plan),
        run_root=Path(args.run_root),
        goal=args.goal,
        success_criteria=args.success_criteria,
        repo_root=Path.cwd(),
    )
    print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

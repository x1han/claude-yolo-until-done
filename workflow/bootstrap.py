#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from state import build_state, build_trace


ROOT_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT_DIR / "templates"


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

    spec_path = Path(args.spec)
    plan_path = Path(args.plan)
    run_root = Path(args.run_root).resolve()

    if not spec_path.exists():
        raise SystemExit(f"Spec not found: {spec_path}")
    if not plan_path.exists():
        raise SystemExit(f"Plan not found: {plan_path}")

    state = build_state(
        TEMPLATES_DIR / "state-template.json",
        goal=args.goal,
        success_criteria=args.success_criteria,
        plan_path=plan_path,
        spec_path=spec_path,
        repo_root=Path.cwd(),
    )
    trace = build_trace(
        TEMPLATES_DIR / "trace-template.md",
        goal=args.goal,
        success_criteria=args.success_criteria,
    )

    state_path = run_root / "state.json"
    trace_path = run_root / "trace.md"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    trace_path.write_text(trace, encoding="utf-8")

    summary = {
        "run_root": str(run_root),
        "state_path": str(state_path),
        "trace_path": str(trace_path),
    }
    print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

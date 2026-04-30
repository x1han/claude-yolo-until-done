#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT_DIR / "templates"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def infer_runtime_context(args: argparse.Namespace) -> dict:
    runtime_context = load_json(TEMPLATES_DIR / "runtime-context-template.json")
    runtime_context["operator_asserted_runtime_name"] = "claude-code"
    runtime_context["operator_asserted_hooks_available"] = True
    runtime_context["operator_asserted_dangerously_skip_permissions"] = bool(args.dangerously_skip_permissions)
    runtime_context["operator_asserted_superpowers_installed"] = True
    runtime_context["operator_asserted_bundle_prepared_by_superpowers"] = True
    runtime_context["asserted_by"] = "bootstrap.py"
    runtime_context["recorded_at"] = utc_now()
    runtime_context["notes"] = args.notes or ""
    return runtime_context


def build_run_state(args: argparse.Namespace) -> dict:
    run_state = load_json(TEMPLATES_DIR / "run-state-template.json")
    run_state["plan_path"] = str(args.plan.resolve())
    run_state["spec_path"] = str(args.spec.resolve())
    run_state["lifecycle_state"] = "active"
    run_state["current_stage"] = "stage-01"
    run_state["current_round"] = args.current_round
    run_state["current_target"] = args.current_target
    run_state["current_issue"] = args.current_issue
    run_state["next_action"] = "validate runtime and bundle"
    run_state["verification_target"] = args.verification_target
    run_state["repair_summary"] = ""
    run_state["verification_commands"] = []
    run_state["verification_before_status"] = "not-run"
    run_state["verification_after_status"] = "not-run"
    run_state["verification_passed"] = False
    run_state["verification_evidence_updated_at"] = utc_now()
    run_state["blocker_type"] = ""
    run_state["blocker_evidence"] = ""
    run_state["local_fix_attempted"] = False
    run_state["why_not_locally_fixable"] = ""
    run_state["blocker_recorded_at"] = utc_now()
    run_state["final_verdict"] = ""
    run_state["final_summary"] = ""
    run_state["final_verification_evidence"] = []
    run_state["remaining_non_blockers"] = []
    run_state["completion_reason"] = ""
    run_state["completion_recorded_at"] = utc_now()
    run_state["updated_at"] = utc_now()
    return run_state


def build_gates() -> dict:
    return load_json(TEMPLATES_DIR / "gates-template.json")


def build_checkoffs() -> dict:
    return load_json(TEMPLATES_DIR / "checkoffs-template.json")


def build_workflow_manifest() -> dict:
    return load_json(TEMPLATES_DIR / "workflow-manifest-template.json")


def build_report(args: argparse.Namespace) -> str:
    return "\n".join(
        [
            "# YOLO Run Report",
            "",
            "## Context",
            f"- Spec: {args.spec.resolve()}",
            f"- Plan: {args.plan.resolve()}",
            f"- Current target: {args.current_target}",
            f"- Current issue: {args.current_issue}",
            "",
            "## Timeline",
            f"- Stage started: {utc_now()}",
            "",
            "## Work Log",
            "- Bootstrap bundle initialized from superpowers artifacts.",
            "",
            "## Blockers",
            "- None recorded yet.",
            "- Type:",
            "- Evidence:",
            "- Local fix attempted: false",
            "- Why not locally fixable:",
            "",
            "## Verification",
            f"- Verification target: {args.verification_target}",
            "- Commands:",
            "- Before status: not-run",
            "- After status: not-run",
            "- Passed: false",
            "",
            "## Completion",
            "- Ready to stop: false",
            "- Certifying gate: stage-05",
            "- Final verdict:",
            "- Final summary:",
            "- Final verification evidence:",
            "- Remaining non-blockers:",
            "- Completion reason:",
            "",
        ]
    )


def build_resume(args: argparse.Namespace) -> str:
    return "\n".join(
        [
            "# YOLO Resume",
            "",
            "## Current Position",
            "- Stage: stage-01",
            f"- Round: {args.current_round}",
            f"- Target: {args.current_target}",
            f"- Issue: {args.current_issue}",
            "",
            "## Last Known Failure",
            "- ",
            "",
            "## Last Commit",
            "- ",
            "",
            "## Next Action",
            "- validate runtime and bundle",
            "",
            "## Stop Status",
            "- Human blocked: false",
            "- Blocker type:",
            "- Local fix attempted: false",
            "- Completion ready: false",
            "- Final verdict:",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a claude-yolo-until-done run bundle from superpowers artifacts.")
    parser.add_argument("--spec", required=True, help="Approved superpowers spec path")
    parser.add_argument("--plan", required=True, help="Approved superpowers implementation plan path")
    parser.add_argument("--run-root", default="artifacts/yolo", help="Destination run bundle root")
    parser.add_argument("--current-target", required=True, help="Current execution target")
    parser.add_argument("--current-issue", required=True, help="Current issue or work item")
    parser.add_argument("--verification-target", required=True, help="Current verification target for the first execution loop")
    parser.add_argument("--current-round", default="round-0", help="Initial round label")
    parser.add_argument("--dangerously-skip-permissions", action="store_true", help="Record that Claude Code was launched with --dangerously-skip-permissions")
    parser.add_argument("--notes", help="Optional runtime context note")
    args = parser.parse_args()

    args.spec = Path(args.spec)
    args.plan = Path(args.plan)
    run_root = Path(args.run_root).resolve()

    if not args.spec.exists():
        raise SystemExit(f"Spec not found: {args.spec}")
    if not args.plan.exists():
        raise SystemExit(f"Plan not found: {args.plan}")

    runtime_context = infer_runtime_context(args)
    run_state = build_run_state(args)
    gates = build_gates()
    checkoffs = build_checkoffs()
    workflow_manifest = build_workflow_manifest()
    report_text = build_report(args)
    resume_text = build_resume(args)

    write_json(run_root / "runtime_context.json", runtime_context)
    write_json(run_root / "run_state.json", run_state)
    write_json(run_root / "gates.json", gates)
    write_json(run_root / "checkoffs.json", checkoffs)
    write_json(run_root / "workflow_manifest.json", workflow_manifest)
    write_text(run_root / "report.md", report_text)
    write_text(run_root / "resume.md", resume_text)

    summary = {
        "run_root": str(run_root),
        "spec_path": str(args.spec.resolve()),
        "plan_path": str(args.plan.resolve()),
        "current_stage": "stage-01",
        "next_action": "validate runtime and bundle",
    }
    print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_STATE_FIELDS = (
    "goal",
    "success_criteria",
    "status",
    "task_id",
    "task_title",
    "task_inputs",
    "worker_claim",
    "files_changed",
    "verification_command",
    "verification_result",
    "submitted_at",
    "review",
    "reviewed_at",
    "owner",
    "next_action",
    "cleanup_required",
    "plan_path",
    "spec_path",
    "updated_at",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def base_report(stage: int | str, run_root: Path) -> dict:
    return {
        "stage": stage,
        "passed": True,
        "checked_at": utc_now(),
        "run_root": str(run_root),
        "run_state_path": str(run_root / "state.json"),
        "checks": [],
        "failures": [],
        "warnings": [],
        "unchecked": [],
    }


def add_check(report: dict, name: str, passed: bool, detail: str, *, source: str = "state.json") -> None:
    report["checks"].append({"name": name, "passed": passed, "detail": detail, "source": source})
    if not passed:
        report["passed"] = False
        report["failures"].append({"name": name, "detail": detail, "source": source})


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def state_path(run_root: Path) -> Path:
    return run_root / "state.json"


def trace_path(run_root: Path) -> Path:
    return run_root / "trace.md"


def load_state(run_root: Path) -> dict:
    return load_json(state_path(run_root))


def load_trace_text(run_root: Path) -> str:
    return trace_path(run_root).read_text(encoding="utf-8-sig")


def validate_required_state_fields(report: dict, state: dict) -> bool:
    ok = True
    for field_name in REQUIRED_STATE_FIELDS:
        present = field_name in state
        add_check(report, f"state_field_{field_name}_present", present, f"field={field_name}")
        ok = ok and present
    return ok


def has_non_empty_text(items: object) -> bool:
    return isinstance(items, list) and any(isinstance(item, str) and item.strip() for item in items)


def validate_loop_evidence_base(report: dict, state: dict) -> tuple[dict, dict] | None:
    loop = state.get("loop") if isinstance(state.get("loop"), dict) else {}
    if not loop.get("enabled"):
        return None

    latest = loop.get("latest_iteration_evidence") if isinstance(loop.get("latest_iteration_evidence"), dict) else {}
    acceleration = loop.get("acceleration_review") if isinstance(loop.get("acceleration_review"), dict) else {}
    iteration = loop.get("iteration")
    add_check(report, "loop_latest_iteration_evidence_present", bool(latest), f"latest_iteration_evidence={latest}")
    add_check(report, "loop_latest_iteration_matches_current", latest.get("iteration") == iteration, f"iteration={iteration} latest={latest}")
    add_check(report, "loop_latest_evidence_present", has_non_empty_text(latest.get("evidence")), f"latest_iteration_evidence={latest}")
    add_check(report, "loop_acceleration_review_present", bool(acceleration), f"acceleration_review={acceleration}")
    add_check(report, "loop_acceleration_iteration_matches_current", acceleration.get("iteration") == iteration, f"iteration={iteration} acceleration_review={acceleration}")
    add_check(report, "loop_acceleration_decision_present", acceleration.get("decision") in {"accepted", "defer", "none"}, f"acceleration_review={acceleration}")
    add_check(report, "loop_acceleration_evidence_present", has_non_empty_text(acceleration.get("evidence")), f"acceleration_review={acceleration}")
    add_check(report, "loop_gate_safety_basis_present", has_non_empty_text(acceleration.get("gate_safety_basis")), f"acceleration_review={acceleration}")
    return latest, acceleration

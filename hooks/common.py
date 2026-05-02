from __future__ import annotations

import json
from datetime import datetime, timezone
from os import environ
from pathlib import Path


REQUIRED_SUPERPOWERS_SKILLS = (
    "using-superpowers",
    "brainstorming",
    "writing-plans",
)

REQUIRED_RUN_FILES = (
    "runtime_context.json",
    "run_state.json",
    "gates.json",
    "checkoffs.json",
    "report.md",
    "resume.md",
)

REQUIRED_RUN_STATE_FIELDS = (
    "workflow_name",
    "workflow_active",
    "lifecycle_state",
    "plan_path",
    "spec_path",
    "current_stage",
    "current_round",
    "current_target",
    "current_issue",
    "last_failure",
    "last_commit",
    "next_action",
    "human_blocked",
    "stop_forbidden",
    "completion_ready",
    "completion_gate",
    "verification_target",
    "repair_summary",
    "verification_commands",
    "verification_before_status",
    "verification_after_status",
    "verification_passed",
    "verification_evidence_updated_at",
    "blocker_type",
    "blocker_evidence",
    "local_fix_attempted",
    "why_not_locally_fixable",
    "blocker_recorded_at",
    "final_verdict",
    "final_summary",
    "final_verification_evidence",
    "remaining_non_blockers",
    "completion_reason",
    "completion_recorded_at",
    "updated_at",
)

REQUIRED_RUNTIME_FIELDS = (
    "operator_asserted_runtime_name",
    "operator_asserted_hooks_available",
    "operator_asserted_dangerously_skip_permissions",
    "operator_asserted_superpowers_installed",
    "operator_asserted_bundle_prepared_by_superpowers",
    "asserted_by",
    "recorded_at",
    "notes",
)

REQUIRED_STATE_FIELDS = (
    "goal",
    "success_criteria",
    "status",
    "worker_claim",
    "files_changed",
    "verification_command",
    "verification_result",
    "submitted_at",
    "review",
    "reviewed_at",
    "owner",
    "next_action",
    "plan_path",
    "spec_path",
    "updated_at",
)

ALLOWED_BLOCKER_TYPES = {
    "gui-os-dialog",
    "external-auth-login",
    "runtime-permission-mode",
    "external-service-dependency",
    "upstream-product-decision",
}


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


def add_check(report: dict, name: str, passed: bool, detail: str) -> None:
    report["checks"].append({"name": name, "passed": passed, "detail": detail})
    if not passed:
        report["passed"] = False
        report["failures"].append({"name": name, "detail": detail})


def add_warning(report: dict, name: str, detail: str) -> None:
    report["warnings"].append({"name": name, "detail": detail})


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


def skill_roots() -> list[Path]:
    roots: list[Path] = []
    override = environ.get("CODEX_SKILLS_ROOT")
    if override:
        roots.append(Path(override))
    roots.extend(
        [
            Path.home() / ".codex" / "skills",
            Path.home() / ".claude" / "skills",
            Path.home() / ".codex" / "plugins" / "cache" / "openai-curated" / "superpowers" / "6807e4de" / "skills",
        ]
    )
    unique_roots: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key not in seen:
            seen.add(key)
            unique_roots.append(root)
    return unique_roots


def enforce_superpowers_installed(report: dict) -> bool:
    all_present = True
    for skill_name in REQUIRED_SUPERPOWERS_SKILLS:
        candidate_paths = [root / skill_name / "SKILL.md" for root in skill_roots()]
        installed = any(path.exists() for path in candidate_paths)
        add_check(
            report,
            f"required_skill_{skill_name}_installed",
            installed,
            "Candidate paths: " + ", ".join(str(path) for path in candidate_paths),
        )
        all_present = all_present and installed
    return all_present


def run_file_paths(run_root: Path) -> dict[str, Path]:
    return {name: run_root / name for name in REQUIRED_RUN_FILES}


def validate_required_run_files(report: dict, run_root: Path) -> bool:
    ok = True
    for name, path in run_file_paths(run_root).items():
        exists = path.exists()
        add_check(report, f"required_file_{name}", exists, f"Expected path: {path}")
        ok = ok and exists
    return ok


def validate_required_fields(report: dict, payload: dict, field_names: tuple[str, ...], prefix: str) -> bool:
    ok = True
    for field_name in field_names:
        present = field_name in payload
        add_check(report, f"{prefix}_{field_name}_present", present, f"Field present: {field_name}")
        ok = ok and present
    return ok


def load_run_bundle(run_root: Path) -> dict[str, dict]:
    bundle = {
        "runtime_context": load_json(run_root / "runtime_context.json"),
        "run_state": load_json(run_root / "run_state.json"),
        "gates": load_json(run_root / "gates.json"),
        "checkoffs": load_json(run_root / "checkoffs.json"),
    }
    manifest_path = run_root / "workflow_manifest.json"
    if manifest_path.exists():
        bundle["workflow_manifest"] = load_json(manifest_path)
    return bundle


def gate_map(gates_payload: dict) -> dict[str, dict]:
    return {gate["id"]: gate for gate in gates_payload.get("gates", []) if isinstance(gate, dict) and "id" in gate}


def checkoff_map(checkoffs_payload: dict) -> dict[str, dict]:
    return {item["id"]: item for item in checkoffs_payload.get("checkoffs", []) if isinstance(item, dict) and "id" in item}


def report_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def verification_status_kind(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if text.startswith("failed"):
        return "failed"
    if text.startswith("passed"):
        return "passed"
    if text in {"not-run", "unknown"}:
        return text
    return text


def report_has_verification_markers(run_root: Path, before_kind: str, after_kind: str) -> tuple[bool, list[str]]:
    body = report_text(run_root / "report.md")
    failures: list[str] = []
    if "## Verification" not in body:
        failures.append("missing verification section")
    if f"- Before status: {before_kind}" not in body:
        failures.append(f"missing before status {before_kind}")
    if f"- After status: {after_kind}" not in body:
        failures.append(f"missing after status {after_kind}")
    return len(failures) == 0, failures


def stage_id(value: int) -> str:
    return f"stage-{value:02d}"


def structured_human_blocked_is_valid(run_state: dict) -> tuple[bool, list[str]]:
    blocker_type = str(run_state.get("blocker_type", "")).strip()
    blocker_evidence = str(run_state.get("blocker_evidence", "")).strip()
    why_not_locally_fixable = str(run_state.get("why_not_locally_fixable", "")).strip()
    blocker_recorded_at = str(run_state.get("blocker_recorded_at", "")).strip()
    local_fix_attempted = run_state.get("local_fix_attempted") is True

    failures: list[str] = []
    if blocker_type not in ALLOWED_BLOCKER_TYPES:
        failures.append(f"blocker_type={blocker_type}")
    if not blocker_evidence:
        failures.append("blocker_evidence missing")
    if not local_fix_attempted:
        failures.append(f"local_fix_attempted={run_state.get('local_fix_attempted')}")
    if not why_not_locally_fixable:
        failures.append("why_not_locally_fixable missing")
    if not blocker_recorded_at:
        failures.append("blocker_recorded_at missing")
    return len(failures) == 0, failures


def human_blocked_evidence_is_valid(run_root: Path, run_state: dict) -> tuple[bool, list[str]]:
    valid_blocker, failures = structured_human_blocked_is_valid(run_state)
    if not valid_blocker:
        return False, failures

    report_body = report_text(run_root / "report.md").lower()
    resume_body = report_text(run_root / "resume.md").lower()
    blocker_type = str(run_state.get("blocker_type", "")).strip().lower()

    evidence_failures: list[str] = []
    if "## blockers" not in report_body:
        evidence_failures.append("report missing blockers section")
    if "human blocked" not in resume_body:
        evidence_failures.append("resume missing human blocked marker")
    if f"- type: {blocker_type}" not in report_body:
        evidence_failures.append(f"report missing blocker type {blocker_type}")
    if "- local fix attempted: true" not in report_body:
        evidence_failures.append("report missing local fix attempted true")
    if f"- blocker type: {blocker_type}" not in resume_body:
        evidence_failures.append(f"resume missing blocker type {blocker_type}")
    if "- local fix attempted: true" not in resume_body:
        evidence_failures.append("resume missing local fix attempted true")
    return len(evidence_failures) == 0, evidence_failures

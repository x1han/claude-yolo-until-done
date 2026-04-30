from __future__ import annotations

from pathlib import Path

from common import (
    REQUIRED_RUNTIME_FIELDS,
    REQUIRED_RUN_STATE_FIELDS,
    add_check,
    base_report,
    enforce_superpowers_installed,
    load_run_bundle,
    report_text,
    validate_required_fields,
    validate_required_run_files,
)


def run(run_root: Path) -> dict:
    report = base_report(stage=1, run_root=run_root)
    if not validate_required_run_files(report, run_root):
        return report

    if not enforce_superpowers_installed(report):
        return report

    bundle = load_run_bundle(run_root)
    runtime_context = bundle["runtime_context"]
    run_state = bundle["run_state"]

    validate_required_fields(report, runtime_context, REQUIRED_RUNTIME_FIELDS, "runtime_context")
    validate_required_fields(report, run_state, REQUIRED_RUN_STATE_FIELDS, "run_state")

    add_check(
        report,
        "operator_asserted_runtime_is_claude_code",
        runtime_context.get("operator_asserted_runtime_name") == "claude-code",
        f"operator_asserted_runtime_name={runtime_context.get('operator_asserted_runtime_name')}",
    )
    add_check(
        report,
        "operator_asserted_hooks_available",
        bool(runtime_context.get("operator_asserted_hooks_available")),
        f"operator_asserted_hooks_available={runtime_context.get('operator_asserted_hooks_available')}",
    )
    add_check(
        report,
        "operator_asserted_dangerously_skip_permissions_enabled",
        bool(runtime_context.get("operator_asserted_dangerously_skip_permissions")),
        f"operator_asserted_dangerously_skip_permissions={runtime_context.get('operator_asserted_dangerously_skip_permissions')}",
    )
    add_check(
        report,
        "operator_asserted_superpowers_installed",
        bool(runtime_context.get("operator_asserted_superpowers_installed")),
        f"operator_asserted_superpowers_installed={runtime_context.get('operator_asserted_superpowers_installed')}",
    )
    add_check(
        report,
        "operator_asserted_bundle_prepared_by_superpowers",
        bool(runtime_context.get("operator_asserted_bundle_prepared_by_superpowers")),
        f"operator_asserted_bundle_prepared_by_superpowers={runtime_context.get('operator_asserted_bundle_prepared_by_superpowers')}",
    )
    add_check(report, "runtime_context_asserted_by_present", bool(str(runtime_context.get("asserted_by", "")).strip()), f"asserted_by={runtime_context.get('asserted_by')}")
    hook_settings_path_raw = str(runtime_context.get("hook_settings_path", "")).strip()
    hook_install_marker = str(runtime_context.get("hook_install_marker", "")).strip()
    add_check(report, "hook_install_marker_present", hook_install_marker == "claude-yolo-until-done", f"hook_install_marker={hook_install_marker}")
    add_check(report, "hook_settings_path_present", bool(hook_settings_path_raw), f"hook_settings_path={hook_settings_path_raw}")
    if hook_settings_path_raw:
        hook_settings_path = Path(hook_settings_path_raw)
        add_check(report, "hook_settings_file_exists", hook_settings_path.exists(), f"hook_settings_path={hook_settings_path}")
    add_check(report, "workflow_name_matches", run_state.get("workflow_name") == "claude-yolo-until-done", f"workflow_name={run_state.get('workflow_name')}")
    add_check(report, "workflow_active_true", run_state.get("workflow_active") is True, f"workflow_active={run_state.get('workflow_active')}")
    add_check(report, "lifecycle_state_active", run_state.get("lifecycle_state") == "active", f"lifecycle_state={run_state.get('lifecycle_state')}")
    add_check(report, "stop_forbidden_true", run_state.get("stop_forbidden") is True, f"stop_forbidden={run_state.get('stop_forbidden')}")
    add_check(report, "plan_path_exists", Path(run_state.get("plan_path", "")).exists(), f"plan_path={run_state.get('plan_path')}")
    add_check(report, "spec_path_exists", Path(run_state.get("spec_path", "")).exists(), f"spec_path={run_state.get('spec_path')}")
    add_check(report, "report_has_context_section", "## Context" in report_text(run_root / "report.md"), f"report_path={run_root / 'report.md'}")
    add_check(report, "resume_has_current_position", "## Current Position" in report_text(run_root / "resume.md"), f"resume_path={run_root / 'resume.md'}")
    return report

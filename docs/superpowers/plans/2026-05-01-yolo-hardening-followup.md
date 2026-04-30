# Claude YOLO Hardening Follow-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace brittle text-matching gates with structured state/evidence validation, require real commit/push applicability before final approval, and tighten final consistency checks across `run_state.json`, `report.md`, and `resume.md`.

**Architecture:** Keep `run_state.json` and structured acceptance artifacts as the primary truth source. Add shared helper functions in `hooks/common.py` so stage gates validate normalized structured evidence instead of free-form text snippets. Make stage-05 enforce applicability-aware commit/push approval and semantic consistency between structured state and human-readable mirrors.

**Tech Stack:** Python 3.14 stdlib (`json`, `pathlib`, `tempfile`, `unittest`, `datetime`), markdown run reports, JSON run bundles, Claude Code hook/controller scripts.

---

## File Structure

### Files to modify
- `hooks/common.py` — add shared structured-evidence validators and final-consistency helpers
- `hooks/gate_02.py` — stop relying on exact `resume.md` next-action substring matches
- `hooks/gate_03.py` — validate structured verification evidence instead of exact report text snippets
- `hooks/gate_05.py` — require applicability-aware final approvals and semantic consistency checks
- `workflow/controller.py` — set completion state in a way that supports applicability-aware final acceptance
- `policy/completion-rules.md` — document applicability-aware commit/push approval and structured evidence expectations
- `README.md` — align operator docs with structured evidence and final-approval semantics
- `QUICKSTART.md` — align operator flow with the updated evidence model

### Files to create
- `tests/test_gate_02_resume_sync.py` — regression tests for stage-02 structured resume validation
- `tests/test_gate_03_structured_evidence.py` — regression tests for stage-03 verification evidence handling
- `tests/test_gate_05_final_acceptance.py` — regression tests for stage-05 applicability-aware approvals and semantic consistency

### Files to keep as existing regression coverage
- `tests/test_session_end_cleanup.py`

---

### Task 1: Replace stage-02 text matching with structured resume validation

**Files:**
- Modify: `hooks/common.py`
- Modify: `hooks/gate_02.py`
- Test: `tests/test_gate_02_resume_sync.py`

- [ ] **Step 1: Write the failing stage-02 regression test**

```python
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = SKILL_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from gate_02 import run as run_gate_02


class Gate02ResumeSyncTest(unittest.TestCase):
    def test_stage_02_accepts_semantically_current_resume_without_exact_next_action_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "runtime_context.json").write_text("{}", encoding="utf-8")
            (run_root / "gates.json").write_text(json.dumps({"gates": [{"id": "stage-02", "required": True, "passed": False}, {"id": "stage-05", "required": True, "passed": False}]}), encoding="utf-8")
            (run_root / "checkoffs.json").write_text(json.dumps({"checkoffs": []}), encoding="utf-8")
            (run_root / "report.md").write_text("# report\n", encoding="utf-8")
            (run_root / "resume.md").write_text(
                "# Resume\n\n## Current Position\n- Stage: stage-02\n\n## Next Action\n- continue current stage\n",
                encoding="utf-8",
            )
            plan_path = run_root / "plan.md"
            plan_path.write_text("# plan\n", encoding="utf-8")
            (run_root / "run_state.json").write_text(
                json.dumps(
                    {
                        "current_stage": "stage-02",
                        "next_action": "load run state and claim exactly one next action",
                        "verification_target": "pytest -q",
                        "completion_gate": "stage-05",
                        "plan_path": str(plan_path),
                    }
                ),
                encoding="utf-8",
            )

            report = run_gate_02(run_root)

            checks = {item["name"]: item for item in report["checks"]}
            self.assertTrue(checks["resume_stage_matches_run_state"]["passed"])
            self.assertTrue(checks["resume_has_next_action_section"]["passed"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_gate_02_resume_sync -v`
Expected: FAIL because `gate_02.py` still requires `next_action` to appear verbatim in `resume.md`.

- [ ] **Step 3: Implement shared resume-structure helpers in `hooks/common.py`**

```python
def markdown_section_value(body: str, heading: str) -> str:
    lines = body.splitlines()
    capture = False
    collected: list[str] = []
    for line in lines:
        if line.strip() == heading:
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture:
            collected.append(line)
    return "\n".join(collected).strip()


def resume_stage_matches(run_root: Path, run_state: dict) -> tuple[bool, str]:
    body = report_text(run_root / "resume.md")
    current_position = markdown_section_value(body, "## Current Position")
    expected = f"- Stage: {run_state.get('current_stage')}"
    return expected in current_position, expected


def resume_has_next_action_section(run_root: Path) -> tuple[bool, str]:
    body = report_text(run_root / "resume.md")
    next_action = markdown_section_value(body, "## Next Action")
    return bool(next_action), next_action or ""
```

- [ ] **Step 4: Update `hooks/gate_02.py` to use structure instead of exact phrase matching**

```python
from common import (
    add_check,
    base_report,
    gate_map,
    load_run_bundle,
    resume_has_next_action_section,
    resume_stage_matches,
    stage_id,
    validate_required_run_files,
)

resume_stage_ok, expected_stage = resume_stage_matches(run_root, run_state)
resume_next_action_ok, resume_next_action_detail = resume_has_next_action_section(run_root)

add_check(report, "resume_stage_matches_run_state", resume_stage_ok, f"expected_stage={expected_stage}")
add_check(report, "resume_has_next_action_section", resume_next_action_ok, f"next_action_section={resume_next_action_detail}")
```

- [ ] **Step 5: Re-run the test to verify it passes**

Run: `python -m unittest tests.test_gate_02_resume_sync -v`
Expected: PASS

- [ ] **Step 6: Run the existing test suite to verify no regressions**

Run: `python -m unittest discover -s tests -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add hooks/common.py hooks/gate_02.py tests/test_gate_02_resume_sync.py
git commit -m "fix: use structured resume checks in stage 2"
```

### Task 2: Replace stage-03 report text strictness with structured verification evidence

**Files:**
- Modify: `hooks/common.py`
- Modify: `hooks/gate_03.py`
- Test: `tests/test_gate_03_structured_evidence.py`

- [ ] **Step 1: Write the failing stage-03 regression tests**

```python
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = SKILL_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from gate_03 import run as run_gate_03


class Gate03StructuredEvidenceTest(unittest.TestCase):
    def test_stage_03_accepts_failed_status_with_detail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "acceptance").mkdir()
            (run_root / "runtime_context.json").write_text("{}", encoding="utf-8")
            (run_root / "gates.json").write_text(json.dumps({"gates": []}), encoding="utf-8")
            (run_root / "checkoffs.json").write_text(json.dumps({"checkoffs": []}), encoding="utf-8")
            (run_root / "resume.md").write_text("# Resume\n", encoding="utf-8")
            (run_root / "report.md").write_text("## Verification\n- Before status: failed\n- After status: passed\n", encoding="utf-8")
            (run_root / "acceptance" / "task-01.step-01.json").write_text(json.dumps({"watcher_decision": "approved", "approved_at": "2026-05-01T00:00:00+00:00"}), encoding="utf-8")
            (run_root / "run_state.json").write_text(
                json.dumps(
                    {
                        "current_stage": "stage-03",
                        "current_target": "fixture",
                        "current_task_id": "task-01",
                        "current_step_id": "step-01",
                        "pending_acceptance_path": str(run_root / "acceptance" / "task-01.step-01.json"),
                        "verification_target": "pytest -q",
                        "repair_summary": "fixed it",
                        "verification_commands": ["pytest -q"],
                        "verification_before_status": "failed: AssertionError",
                        "verification_after_status": "passed",
                        "verification_passed": True,
                        "verification_evidence_updated_at": "2026-05-01T00:00:00+00:00",
                        "latest_watcher_decision": "approved",
                        "step_status": "approved",
                    }
                ),
                encoding="utf-8",
            )

            report = run_gate_03(run_root)

            checks = {item["name"]: item for item in report["checks"]}
            self.assertTrue(checks["verification_before_status_recorded"]["passed"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_gate_03_structured_evidence -v`
Expected: FAIL because `gate_03.py` only accepts exact values in `{"failed", "not-run", "unknown"}`.

- [ ] **Step 3: Add normalized structured verification helpers in `hooks/common.py`**

```python
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
```

- [ ] **Step 4: Update `hooks/gate_03.py` to validate normalized status kinds and section presence**

```python
from common import (
    add_check,
    base_report,
    load_run_bundle,
    report_has_verification_markers,
    validate_required_run_files,
    verification_status_kind,
)

before_kind = verification_status_kind(run_state.get("verification_before_status"))
after_kind = verification_status_kind(run_state.get("verification_after_status"))
report_markers_ok, report_marker_failures = report_has_verification_markers(run_root, before_kind, after_kind)

add_check(report, "verification_before_status_recorded", before_kind in {"failed", "not-run", "unknown"}, f"verification_before_status={run_state.get('verification_before_status')}")
add_check(report, "verification_after_status_recorded", after_kind in {"passed", "failed"}, f"verification_after_status={run_state.get('verification_after_status')}")
add_check(report, "report_has_verification_markers", report_markers_ok, f"report_marker_failures={report_marker_failures}")
```

- [ ] **Step 5: Re-run the test to verify it passes**

Run: `python -m unittest tests.test_gate_03_structured_evidence -v`
Expected: PASS

- [ ] **Step 6: Run the full test suite**

Run: `python -m unittest discover -s tests -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add hooks/common.py hooks/gate_03.py tests/test_gate_03_structured_evidence.py
git commit -m "fix: normalize stage 3 verification evidence"
```

### Task 3: Make stage-05 enforce applicability-aware final approval and semantic consistency

**Files:**
- Modify: `hooks/common.py`
- Modify: `hooks/gate_05.py`
- Modify: `workflow/controller.py`
- Modify: `policy/completion-rules.md`
- Modify: `README.md`
- Modify: `QUICKSTART.md`
- Test: `tests/test_gate_05_final_acceptance.py`

- [ ] **Step 1: Write the failing stage-05 regression tests**

```python
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = SKILL_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from gate_05 import run as run_gate_05


class Gate05FinalAcceptanceTest(unittest.TestCase):
    def test_stage_05_rejects_commit_approved_without_commit_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "runtime_context.json").write_text("{}", encoding="utf-8")
            (run_root / "gates.json").write_text(json.dumps({"gates": [{"id": "stage-01", "required": True, "passed": True}, {"id": "stage-05", "required": True, "passed": False}]}), encoding="utf-8")
            (run_root / "checkoffs.json").write_text(json.dumps({"checkoffs": []}), encoding="utf-8")
            (run_root / "report.md").write_text("## Completion\n- Ready to stop: true\n- Final verdict: approved\n- Final summary: done\n- Completion reason: done\n- Remaining non-blockers:\n", encoding="utf-8")
            (run_root / "resume.md").write_text("## Stop Status\n- Completion ready: true\n- Final verdict: approved\n", encoding="utf-8")
            (run_root / "run_state.json").write_text(
                json.dumps(
                    {
                        "current_stage": "stage-05",
                        "completion_ready": True,
                        "final_verdict": "approved",
                        "final_summary": "done",
                        "final_verification_evidence": ["pytest -q"],
                        "remaining_non_blockers": [],
                        "completion_reason": "done",
                        "completion_recorded_at": "2026-05-01T00:00:00+00:00",
                        "last_commit": "not-requested (fixture run)",
                        "commit_approved": True,
                        "push_approved": True,
                        "commit_required": False,
                        "push_required": False,
                    }
                ),
                encoding="utf-8",
            )

            report = run_gate_05(run_root)

            checks = {item["name"]: item for item in report["checks"]}
            self.assertFalse(checks["commit_approval_matches_applicability"]["passed"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_gate_05_final_acceptance -v`
Expected: FAIL because `gate_05.py` currently treats any non-empty `last_commit` and booleans as sufficient.

- [ ] **Step 3: Extend run-state semantics in `workflow/controller.py`**

```python
run_state.setdefault("commit_required", False)
run_state.setdefault("push_required", False)
run_state.setdefault("commit_approved", False)
run_state.setdefault("push_approved", False)
```

Add the defaults before final write-back so existing bundles remain readable and the final gate can reason about applicability explicitly.

- [ ] **Step 4: Add final-approval and semantic-consistency helpers in `hooks/common.py`**

```python
def approval_applicability_matches(run_state: dict, requirement_key: str, approval_key: str) -> tuple[bool, str]:
    required = run_state.get(requirement_key) is True
    approved = run_state.get(approval_key) is True
    if required:
        return approved, f"required={required}; approved={approved}"
    return not approved, f"required={required}; approved={approved}"


def final_report_resume_consistent(run_root: Path, run_state: dict) -> tuple[bool, list[str]]:
    report_body = report_text(run_root / "report.md")
    resume_body = report_text(run_root / "resume.md")
    failures: list[str] = []
    if f"- Final verdict: {run_state.get('final_verdict')}" not in report_body:
        failures.append("report final verdict mismatch")
    if f"- Final summary: {run_state.get('final_summary')}" not in report_body:
        failures.append("report final summary mismatch")
    if "- watcher decision: approved" not in report_body.lower() and run_state.get("latest_watcher_decision") == "approved":
        failures.append("report watcher decision mismatch")
    if f"- Final verdict: {str(run_state.get('final_verdict', '')).lower()}" not in resume_body.lower():
        failures.append("resume final verdict mismatch")
    if f"- Completion ready: {str(run_state.get('completion_ready')).lower()}" not in resume_body and f"- completion ready: {str(run_state.get('completion_ready')).lower()}" not in resume_body.lower():
        failures.append("resume completion ready mismatch")
    return len(failures) == 0, failures
```

- [ ] **Step 5: Update `hooks/gate_05.py` to enforce applicability-aware approvals and semantic consistency**

```python
from common import (
    add_check,
    approval_applicability_matches,
    base_report,
    final_report_resume_consistent,
    gate_map,
    load_run_bundle,
    report_text,
    validate_required_run_files,
)

commit_ok, commit_detail = approval_applicability_matches(run_state, "commit_required", "commit_approved")
push_ok, push_detail = approval_applicability_matches(run_state, "push_required", "push_approved")
consistency_ok, consistency_failures = final_report_resume_consistent(run_root, run_state)

add_check(report, "commit_approval_matches_applicability", commit_ok, commit_detail)
add_check(report, "push_approval_matches_applicability", push_ok, push_detail)
add_check(report, "final_report_resume_consistent", consistency_ok, f"consistency_failures={consistency_failures}")
```

- [ ] **Step 6: Update the completion policy and operator docs**

Add these points:
- commit/push approval is required only when the active scope actually requires those actions
- `report.md` and `resume.md` are human-readable mirrors and must stay semantically aligned with `run_state.json`
- structured state and acceptance artifacts remain the primary completion evidence

- [ ] **Step 7: Re-run the stage-05 regression tests**

Run: `python -m unittest tests.test_gate_05_final_acceptance -v`
Expected: PASS

- [ ] **Step 8: Re-run the full test suite**

Run: `python -m unittest discover -s tests -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add hooks/common.py hooks/gate_05.py workflow/controller.py policy/completion-rules.md README.md QUICKSTART.md tests/test_gate_05_final_acceptance.py
git commit -m "fix: tighten final acceptance evidence rules"
```

---

## Self-Review

- **Spec coverage:** This plan covers the three requested fixes directly: stage-02/03 brittleness, stage-05 applicability-aware approvals, and final consistency across run-state/report/resume.
- **Placeholder scan:** No `TODO`, `TBD`, or undefined “write tests later” steps remain.
- **Type consistency:** The new keys used across tasks are `commit_required`, `push_required`, normalized verification status kinds, and semantic consistency helpers; the same names are used consistently in tests and implementation.

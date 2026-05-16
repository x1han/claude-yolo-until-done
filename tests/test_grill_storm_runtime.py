from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from human_approvals import record_human_approval

GRILL_STORM_PATH = WORKFLOW_DIR / "grill_storm.py"
VALIDATE_GRILL_DOCS_PATH = WORKFLOW_DIR / "validate_grill_docs.py"
PREFLIGHT_PATH = WORKFLOW_DIR / "preflight.py"
INIT_GRILL_DOCS_PATH = WORKFLOW_DIR / "init_grill_docs.py"


class GrillStormRuntimeTest(unittest.TestCase):
    def runtime_env(self, project_dir: Path) -> dict[str, str]:
        env = dict(os.environ)
        env["CLAUDE_CODE_ENTRYPOINT"] = "cli"
        bin_dir = project_dir / ".test-bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        ps_path = bin_dir / "ps"
        ps_path.write_text(
            "#!/usr/bin/env python3\n"
            "print('  PID  PPID ARGS')\n"
            "print('123 1 claude --dangerously-skip-permissions')\n",
            encoding="utf-8",
        )
        ps_path.chmod(0o755)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
        return env

    def human_gate_decisions(self) -> str:
        return "\n\n### 2026-05-12 - Human consensus approval\n- Status: accepted\n- Actor: human\n- Source: consensus\n- Decision: Build approved planning docs.\n\n### 2026-05-12 - Logos spec self-review\n- Status: accepted\n- Actor: logos\n- Source: spec-self-review\n- Decision: Spec passes self-review.\n\n### 2026-05-12 - Human spec review\n- Status: accepted\n- Actor: human\n- Source: spec-review\n- Decision: Spec approved.\n\n### 2026-05-12 - Human plan review\n- Status: accepted\n- Actor: human\n- Source: plan-review\n- Decision: Plan approved.\n"

    def write_human_approvals(self, project_dir: Path, *sources: str) -> None:
        for source in sources:
            record_human_approval(project_dir, source, f"prompt {source}", f"approved {source}")

    def write_docs(
        self,
        project_dir: Path,
        *,
        decisions: str = "",
        open_questions: str = "",
        spec_status: str = "draft",
        plan_status: str = "draft",
    ) -> Path:
        docs_dir = project_dir / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "intent.md").write_text(
            "# Intent\n\n## Primary Goal\n- Build safe planning flow.\n\n## Why This Matters\n- Prevent hidden assumptions.\n\n## Non-Goals\n- Generic multi-agent platform.\n\n## Constraints\n- Time: bounded\n- Tech: local markdown\n- Compatibility: Claude Code\n- Budget: small\n\n## Preferences\n- Prefer: ask late\n- Avoid: chat-only state\n\n## Assumptions\n- Existing docs-first workflow.\n\n## Unknowns\n- None.\n",
            encoding="utf-8",
        )
        (docs_dir / "open-questions.md").write_text(
            open_questions
            or "# Open Questions\n\n## High Priority\n- [ ] Blocking: yes | Question: Which API should own execution gate? | Recommended: preflight validator\n\n## Medium Priority\n- [ ] None.\n\n## Low Priority\n- [ ] None.\n\n## Answered Recently\n- [x] Question: initial scope\n  Answer: first-party grill-storm\n  Impact: no external superpowers dependency\n",
            encoding="utf-8",
        )
        (docs_dir / "decisions.md").write_text(
            decisions or "# Decisions\n\n## Decision Log\n",
            encoding="utf-8",
        )
        (docs_dir / "spec.md").write_text(
            f"# Spec\n\nStatus: {spec_status}\n\n## Problem\n- Planning needs hard docs-first contract.\n\n## Users\n- Claude Code operators.\n\n## Desired Outcome\n- Approved docs before execution.\n\n## Requirements\n- Must: keep docs authoritative.\n- Should: ask human late.\n- Nice-to-have: terse output.\n\n## User Flows\n1. Initialize docs.\n2. Validate docs.\n\n## Acceptance Criteria\n- [x] Docs exist.\n- [x] Plan covers validation.\n\n## Risks\n- Weak gate.\n\n## Out of Scope\n- External skill dependency.\n",
            encoding="utf-8",
        )
        (docs_dir / "plan.md").write_text(
            f"# Plan\n\nStatus: {plan_status}\n\n## Goal\n- Implement hard gate.\n\n## Steps\n1. Step: Add validator.\n   Files: workflow/validate_grill_docs.py\n   Run: python -m unittest tests.test_grill_storm_runtime -v\n   Expected: PASS\n   Verify: Run validator tests.\n2. Step: Wire preflight.\n   Files: workflow/preflight.py\n   Run: python -m unittest tests.test_grill_storm_runtime -v\n   Expected: PASS\n   Verify: Preflight rejects drafts.\n3. Step: Document first-party skill.\n   Files: skills/grill-storm/SKILL.md\n   Run: python -m unittest tests.test_docs_and_templates -v\n   Expected: PASS\n   Verify: Docs test passes.\n\n## Dependencies\n- Local docs.\n\n## File/Area Impact\n- workflow/preflight.py\n\n## Tests\n- python -m unittest tests.test_grill_storm_runtime -v\n\n## Rollback / Safety\n- Remove gate wiring.\n",
            encoding="utf-8",
        )
        return docs_dir

    def test_grill_storm_requires_muse_and_logos_internal_rounds_before_human_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-10 - Muse scope pass\n- Status: accepted\n- Actor: muse\n- Decision: Need preflight gate.\n- Reason: Execution must fail closed.\n- Alternatives considered: docs only.\n- Impact: adds validator.\n- Revisit when: validator too strict.\n",
            )

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "needs_internal_round")
            self.assertEqual(payload["next_actor"], "logos")
            self.assertFalse(payload["human_allowed"])
            self.assertIn("logos", payload["reason"])

    def test_grill_storm_allows_one_human_question_after_two_agent_internal_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-10 - Muse scope pass\n- Status: accepted\n- Actor: muse\n- Decision: Need preflight gate.\n- Reason: Execution must fail closed.\n- Alternatives considered: docs only.\n- Impact: adds validator.\n- Revisit when: validator too strict.\n\n### 2026-05-10 - Logos challenge pass\n- Status: accepted\n- Actor: logos\n- Decision: Keep validator separate from controller.\n- Reason: Planning gate owns authoring readiness.\n- Alternatives considered: controller-only check.\n- Impact: clearer ownership.\n- Revisit when: preflight grows too large.\n" + self.human_gate_decisions(),
            )

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ask_user")
            self.assertTrue(payload["human_allowed"])
            self.assertEqual(payload["question"], "Which API should own execution gate?")
            self.assertEqual(payload["recommended_answer"], "preflight validator")

    def test_validate_grill_docs_rejects_unapproved_spec_and_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(project_dir, spec_status="draft", plan_status="approved")

            result = subprocess.run(
                [sys.executable, str(VALIDATE_GRILL_DOCS_PATH), "--project-dir", str(project_dir)],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("spec.md is not approved", result.stderr)

    def test_grill_storm_parses_multiline_blocking_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                open_questions="# Open Questions\n\n## High Priority\n- [ ] Blocking: yes\n  Question: Which gate owns planning readiness?\n  Recommended: preflight validator\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-10 - Muse scope pass\n- Status: accepted\n- Actor: muse\n- Decision: Need preflight gate.\n\n### 2026-05-10 - Logos challenge pass\n- Status: accepted\n- Actor: logos\n- Decision: Keep validator separate.\n",
            )

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ask_user")
            self.assertEqual(payload["question"], "Which gate owns planning readiness?")
            self.assertEqual(payload["recommended_answer"], "preflight validator")

    def test_grill_storm_ignores_low_priority_blocking_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                open_questions="# Open Questions\n\n## High Priority\n- [ ] None.\n\n## Low Priority\n- [ ] Blocking: yes | Question: Should docs mention color? | Recommended: no\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-10 - Muse scope pass\n- Status: accepted\n- Actor: muse\n- Decision: Need preflight gate.\n\n### 2026-05-10 - Logos challenge pass\n- Status: accepted\n- Actor: logos\n- Decision: Keep validator separate.\n",
            )

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertNotEqual(payload["status"], "ask_user")

    def test_validate_grill_docs_rejects_cross_block_actor_status_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                spec_status="approved",
                plan_status="approved",
                open_questions="# Open Questions\n\n## High Priority\n- [ ] None.\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-10 - Accepted without actor\n- Status: accepted\n- Decision: Missing actor must not satisfy round.\n\n### 2026-05-10 - Draft logos\n- Status: draft\n- Actor: logos\n- Decision: Draft logos must not satisfy round.\n",
            )

            result = subprocess.run(
                [sys.executable, str(VALIDATE_GRILL_DOCS_PATH), "--project-dir", str(project_dir)],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("decisions.md is missing accepted muse internal round", result.stderr)
            self.assertIn("decisions.md is missing accepted logos internal round", result.stderr)

    def test_grill_storm_treats_blocking_field_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                open_questions="# Open Questions\n\n## High Priority\n- [ ] blocking: YES | question: Which gate owns planning readiness? | recommended: preflight validator\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-10 - Muse scope pass\n- Status: accepted\n- Actor: muse\n- Decision: Need preflight gate.\n\n### 2026-05-10 - Logos challenge pass\n- Status: accepted\n- Actor: logos\n- Decision: Keep validator separate.\n",
            )

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ask_user")
            self.assertEqual(payload["question"], "Which gate owns planning readiness?")
            self.assertEqual(payload["recommended_answer"], "preflight validator")

    def test_validate_grill_docs_rejects_empty_blocking_question_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                spec_status="approved",
                plan_status="approved",
                open_questions="# Open Questions\n\n## High Priority\n- [ ] Blocking: yes\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-10 - Muse scope pass\n- Status: accepted\n- Actor: muse\n- Decision: Need preflight gate.\n\n### 2026-05-10 - Logos challenge pass\n- Status: accepted\n- Actor: logos\n- Decision: Keep validator separate.\n",
            )

            result = subprocess.run(
                [sys.executable, str(VALIDATE_GRILL_DOCS_PATH), "--project-dir", str(project_dir)],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("without Question field", result.stderr)
            self.assertIn("without Recommended field", result.stderr)

    def test_grill_storm_requires_verified_spec_review_before_plan_authoring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                spec_status="approved",
                plan_status="draft",
                open_questions="# Open Questions\n\n## High Priority\n- [ ] None.\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-10 - Muse scope pass\n- Status: accepted\n- Actor: muse\n- Decision: Need preflight gate.\n\n### 2026-05-10 - Logos challenge pass\n- Status: accepted\n- Actor: logos\n- Decision: Keep validator separate.\n" + self.human_gate_decisions(),
            )
            self.write_human_approvals(project_dir, 'consensus')

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "human_spec_review")
            self.assertTrue(payload["human_allowed"])

    def test_grill_storm_requires_verified_plan_review_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                spec_status="approved",
                plan_status="approved",
                open_questions="# Open Questions\n\n## High Priority\n- [ ] None.\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-10 - Muse scope pass\n- Status: accepted\n- Actor: muse\n- Decision: Need preflight gate.\n\n### 2026-05-10 - Logos challenge pass\n- Status: accepted\n- Actor: logos\n- Decision: Keep validator separate.\n" + self.human_gate_decisions(),
            )
            self.write_human_approvals(project_dir, 'consensus', 'spec-review')

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "human_plan_review")
            self.assertTrue(payload["human_allowed"])

    def test_validate_grill_docs_accepts_approved_external_brain_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                spec_status="approved",
                plan_status="approved",
                open_questions="# Open Questions\n\n## High Priority\n- [x] Question: gate owner\n  Answer: preflight validator\n  Impact: fail closed before execution\n\n## Medium Priority\n- [ ] None.\n\n## Low Priority\n- [ ] None.\n\n## Answered Recently\n- [x] Question: initial scope\n  Answer: first-party grill-storm\n  Impact: no external superpowers dependency\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-10 - Muse scope pass\n- Status: accepted\n- Actor: muse\n- Decision: Need preflight gate.\n- Reason: Execution must fail closed.\n- Alternatives considered: docs only.\n- Impact: adds validator.\n- Revisit when: validator too strict.\n\n### 2026-05-10 - Logos challenge pass\n- Status: accepted\n- Actor: logos\n- Decision: Keep validator separate from controller.\n- Reason: Planning gate owns authoring readiness.\n- Alternatives considered: controller-only check.\n- Impact: clearer ownership.\n- Revisit when: preflight grows too large.\n" + self.human_gate_decisions(),
            )

            self.write_human_approvals(project_dir, 'consensus', 'spec-review', 'plan-review')

            result = subprocess.run(
                [sys.executable, str(VALIDATE_GRILL_DOCS_PATH), "--project-dir", str(project_dir)],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ready_for_execution")
            self.assertEqual(payload["spec"], str(project_dir / "docs" / "spec.md"))
            self.assertEqual(payload["plan"], str(project_dir / "docs" / "plan.md"))

    def test_preflight_defaults_to_ready_grill_storm_docs_when_spec_plan_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                spec_status="approved",
                plan_status="approved",
                open_questions="# Open Questions\n\n## High Priority\n- [x] Question: review scope\n  Answer: inspect supplied code changes\n  Impact: watcher must review current diff only\n\n## Medium Priority\n- [ ] None.\n\n## Low Priority\n- [ ] None.\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-11 - Muse scope pass\n- Status: accepted\n- Actor: muse\n- Decision: Code review loop should use first-party grill-storm docs.\n\n### 2026-05-11 - Logos challenge pass\n- Status: accepted\n- Actor: logos\n- Decision: Plan contains one repeatable review task with verification.\n" + self.human_gate_decisions(),
            )
            (project_dir / "docs" / "plan.md").write_text(
                "# Plan\n\nStatus: approved\n\n## Steps\n\n### Task 1: Code review iteration\nReview the current code changes.\nFiles: workflow/orchestrator.py\nRun: python -m unittest tests.test_controller_review_flow -v\nExpected: PASS\nVerify: watcher records review evidence for this iteration.\n\n## Rollback / Safety\n- Stop loop before next iteration.\n",
                encoding="utf-8",
            )

            self.write_human_approvals(project_dir, 'consensus', 'spec-review', 'plan-review')

            result = subprocess.run(
                [
                    sys.executable,
                    str(PREFLIGHT_PATH),
                    "--project-dir",
                    str(project_dir),
                    "--run-root",
                    ".yolo",
                    "--goal",
                    "Run five code-review iterations.",
                    "--success-criterion",
                    "five watcher reviews are recorded",
                    "--mode",
                    "loop",
                    "--loop-max-iterations",
                    "5",
                ],
                cwd=SKILL_ROOT,
                capture_output=True,
                text=True,
                check=False,
                env=self.runtime_env(project_dir),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((project_dir / ".yolo" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["spec_path"], "docs/spec.md")
            self.assertEqual(state["plan_path"], "docs/plan.md")
            self.assertEqual(state["mode"], "loop")
            self.assertEqual(state["loop"]["max_iterations"], 5)

    def test_preflight_without_spec_plan_reports_missing_grill_storm_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PREFLIGHT_PATH),
                    "--project-dir",
                    str(project_dir),
                    "--run-root",
                    ".yolo",
                    "--goal",
                    "Run five code-review iterations.",
                    "--success-criterion",
                    "five watcher reviews are recorded",
                ],
                cwd=SKILL_ROOT,
                capture_output=True,
                text=True,
                check=False,
                env=self.runtime_env(project_dir),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["classification"], "planning_needed")
            self.assertEqual(payload["action"], "init_planning")
            self.assertEqual(payload["current_state"], "Default grill-storm planning docs are missing.")
            self.assertIn("workflow/init_grill_docs.py", payload["next"])
            self.assertFalse((project_dir / ".yolo" / "state.json").exists())

    def test_preflight_without_spec_plan_reports_grill_storm_status_for_draft_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            subprocess.run(
                [
                    sys.executable,
                    str(INIT_GRILL_DOCS_PATH),
                    "--project-dir",
                    str(project_dir),
                    "--request",
                    "Run five code-review iterations.",
                ],
                cwd=SKILL_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PREFLIGHT_PATH),
                    "--project-dir",
                    str(project_dir),
                    "--run-root",
                    ".yolo",
                    "--goal",
                    "Run five code-review iterations.",
                    "--success-criterion",
                    "five watcher reviews are recorded",
                ],
                cwd=SKILL_ROOT,
                capture_output=True,
                text=True,
                check=False,
                env=self.runtime_env(project_dir),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["classification"], "planning_needed")
            self.assertEqual(payload["action"], "continue_planning")
            self.assertIn("grill-storm planning docs are not execution-ready", payload["blocked_on"])
            self.assertIn("next_actor", payload["blocked_on"])
            self.assertFalse((project_dir / ".yolo" / "state.json").exists())

    def test_preflight_explicit_default_docs_paths_still_require_grill_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            subprocess.run(
                [
                    sys.executable,
                    str(INIT_GRILL_DOCS_PATH),
                    "--project-dir",
                    str(project_dir),
                    "--request",
                    "Run review.",
                ],
                cwd=SKILL_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PREFLIGHT_PATH),
                    "--project-dir",
                    str(project_dir),
                    "--spec",
                    str(project_dir / "docs" / "spec.md"),
                    "--plan",
                    str(project_dir / "docs" / "plan.md"),
                    "--run-root",
                    ".yolo",
                    "--goal",
                    "Run review.",
                    "--success-criterion",
                    "review passes",
                ],
                cwd=SKILL_ROOT,
                capture_output=True,
                text=True,
                check=False,
                env=self.runtime_env(project_dir),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["classification"], "planning_needed")
            self.assertEqual(payload["action"], "continue_planning")
            self.assertIn("grill-storm planning docs are not execution-ready", payload["blocked_on"])

    def test_preflight_rejects_new_run_when_grill_docs_are_not_execution_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            docs_dir = self.write_docs(project_dir, spec_status="draft", plan_status="draft")
            env = dict(os.environ)
            env["CLAUDE_CODE_ENTRYPOINT"] = "cli"
            bin_dir = project_dir / ".test-bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            ps_path = bin_dir / "ps"
            ps_path.write_text(
                "#!/usr/bin/env python3\n"
                "print('  PID  PPID ARGS')\n"
                "print('123 1 claude --dangerously-skip-permissions')\n",
                encoding="utf-8",
            )
            ps_path.chmod(0o755)
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PREFLIGHT_PATH),
                    "--project-dir",
                    str(project_dir),
                    "--spec",
                    str(docs_dir / "spec.md"),
                    "--plan",
                    str(docs_dir / "plan.md"),
                    "--run-root",
                    ".yolo",
                    "--goal",
                    "Execute only after approved planning docs.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["classification"], "planning_needed")
            self.assertEqual(payload["action"], "continue_planning")
            self.assertIn("grill-storm planning docs are not execution-ready", payload["blocked_on"])

    def test_validate_grill_docs_requires_human_consensus_spec_and_plan_approvals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                spec_status="approved",
                plan_status="approved",
                open_questions="# Open Questions\n\n## High Priority\n- [ ] None.\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Muse\n- Status: accepted\n- Actor: muse\n- Decision: Muse explored intent.\n\n### 2026-05-12 - Logos\n- Status: accepted\n- Actor: logos\n- Decision: Logos converged approach.\n",
            )

            result = subprocess.run(
                [sys.executable, str(VALIDATE_GRILL_DOCS_PATH), "--project-dir", str(project_dir)],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("decisions.md is missing verified human consensus or uncertainty resolution", result.stderr)
            self.assertIn("decisions.md is missing accepted Logos spec self-review", result.stderr)
            self.assertIn("decisions.md is missing accepted human spec review", result.stderr)
            self.assertIn("decisions.md is missing accepted human plan review", result.stderr)

    def test_validate_grill_docs_accepts_human_gated_ready_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                spec_status="approved",
                plan_status="approved",
                open_questions="# Open Questions\n\n## High Priority\n- [ ] None.\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Muse\n- Status: accepted\n- Actor: muse\n- Decision: Muse explored intent.\n\n### 2026-05-12 - Logos\n- Status: accepted\n- Actor: logos\n- Decision: Logos converged approach.\n\n### 2026-05-12 - Human consensus approval\n- Status: accepted\n- Actor: human\n- Source: consensus\n- Decision: Build human-gated planning.\n- Impact: authorizes spec generation.\n\n### 2026-05-12 - Logos spec self-review\n- Status: accepted\n- Actor: logos\n- Source: spec-self-review\n- Decision: Spec has no placeholders, contradictions, scope leaks, or ambiguous acceptance criteria.\n\n### 2026-05-12 - Human spec review\n- Status: accepted\n- Actor: human\n- Source: spec-review\n- Decision: Spec approved.\n\n### 2026-05-12 - Human plan review\n- Status: accepted\n- Actor: human\n- Source: plan-review\n- Decision: Plan approved.\n",
            )
            (project_dir / "docs" / "plan.md").write_text(
                "# Plan\n\nStatus: approved\n\n## Goal\n- Implement human-gated planning.\n\n## Steps\n### Task 1: Add parser\nFiles: workflow/validate_grill_docs.py\nRun: python -m unittest tests.test_grill_storm_runtime -v\nExpected: PASS\nVerify: validator accepts approved bundle.\n\n## Rollback / Safety\n- Revert parser change.\n",
                encoding="utf-8",
            )
            self.write_human_approvals(project_dir, "consensus", "spec-review", "plan-review")

            result = subprocess.run(
                [sys.executable, str(VALIDATE_GRILL_DOCS_PATH), "--project-dir", str(project_dir)],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ready_for_execution")

    def test_grill_storm_rejects_non_human_consensus_source_before_spec_authoring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                open_questions="# Open Questions\n\n## High Priority\n- [ ] None.\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Muse\n- Status: accepted\n- Actor: muse\n- Source: consensus\n- Decision: Wrong source should not bypass human dialogue.\n\n### 2026-05-12 - Logos\n- Status: accepted\n- Actor: logos\n- Source: consensus\n- Decision: Wrong source should not bypass human dialogue.\n",
            )

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "needs_internal_round")
            self.assertIn("consensus-candidate", payload["reason"])

            validation = subprocess.run(
                [sys.executable, str(VALIDATE_GRILL_DOCS_PATH), "--project-dir", str(project_dir)],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(validation.returncode, 0)
            self.assertIn("human-only source consensus recorded by muse", validation.stderr)

    def test_grill_storm_returns_human_dialogue_for_consensus_before_spec_authoring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                open_questions="# Open Questions\n\n## High Priority\n- [ ] None.\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Muse\n- Status: accepted\n- Actor: muse\n- Decision: Muse explored options.\n\n### 2026-05-12 - Logos consensus\n- Status: accepted\n- Actor: logos\n- Source: consensus-candidate\n- Decision: Surface two viable approaches.\n- Consensus: Minimal controller gates | Summary: add state gates only | Tradeoffs: smaller change; less prompt guidance | Recommended: false\n- Consensus: Controller plus prompt modes | Summary: add state gates and Logos modes | Tradeoffs: larger change; clearer behavior | Recommended: true\n",
            )

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "human_dialogue")
            self.assertEqual(payload["dialogue_type"], "consensus")
            self.assertTrue(payload["human_allowed"])
            self.assertEqual(len(payload["items"]), 2)
            self.assertEqual(payload["items"][1]["title"], "Controller plus prompt modes")
            self.assertTrue(payload["items"][1]["recommended"])

    def test_grill_storm_returns_human_dialogue_for_joint_uncertainty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                open_questions="# Open Questions\n\n## High Priority\n- [ ] Blocking: yes | Question: Should spec approval happen before plan authoring? | Recommended: yes, require human spec approval first\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Muse\n- Status: accepted\n- Actor: muse\n- Decision: Muse cannot infer approval order alone.\n\n### 2026-05-12 - Logos uncertainty\n- Status: accepted\n- Actor: logos\n- Source: joint-uncertainty\n- Decision: Both agents need human approval policy.\n",
            )

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "human_dialogue")
            self.assertEqual(payload["dialogue_type"], "joint_uncertainty")
            self.assertEqual(payload["question"], "Should spec approval happen before plan authoring?")
            self.assertEqual(payload["recommended_answer"], "yes, require human spec approval first")

    def test_grill_storm_requests_spec_authoring_after_human_intent_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                open_questions="# Open Questions\n\n## High Priority\n- [ ] None.\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Muse\n- Status: accepted\n- Actor: muse\n- Decision: Muse explored intent.\n\n### 2026-05-12 - Logos\n- Status: accepted\n- Actor: logos\n- Decision: Logos converged approach.\n\n### 2026-05-12 - Human consensus approval\n- Status: accepted\n- Actor: human\n- Source: consensus\n- Decision: Build human-gated planning.\n",
            )

            self.write_human_approvals(project_dir, 'consensus')

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "needs_spec_authoring")
            self.assertEqual(payload["next_actor"], "logos")
            self.assertEqual(payload["planning_mode"], "logos-spec-writer")

    def test_grill_storm_requests_spec_self_review_after_draft_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                spec_status="draft",
                open_questions="# Open Questions\n\n## High Priority\n- [ ] None.\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Muse\n- Status: accepted\n- Actor: muse\n- Decision: Muse explored intent.\n\n### 2026-05-12 - Logos\n- Status: accepted\n- Actor: logos\n- Decision: Logos converged approach.\n\n### 2026-05-12 - Human consensus approval\n- Status: accepted\n- Actor: human\n- Source: consensus\n- Decision: Build human-gated planning.\n",
            )
            (project_dir / "docs" / "spec.md").write_text(
                "# Spec\n\nStatus: draft\n\n## Problem\n- Need human gates.\n\n## Requirements\n- Must require approval.\n\n## Acceptance Criteria\n- [ ] Controller blocks plan before spec approval.\n",
                encoding="utf-8",
            )

            self.write_human_approvals(project_dir, 'consensus')

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "needs_spec_self_review")
            self.assertEqual(payload["planning_mode"], "logos-spec-reviewer")

    def test_grill_storm_requests_human_spec_review_after_self_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                spec_status="self-reviewed",
                open_questions="# Open Questions\n\n## High Priority\n- [ ] None.\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Muse\n- Status: accepted\n- Actor: muse\n- Decision: Muse explored intent.\n\n### 2026-05-12 - Logos\n- Status: accepted\n- Actor: logos\n- Decision: Logos converged approach.\n\n### 2026-05-12 - Human consensus approval\n- Status: accepted\n- Actor: human\n- Source: consensus\n- Decision: Build human-gated planning.\n\n### 2026-05-12 - Logos spec self-review\n- Status: accepted\n- Actor: logos\n- Source: spec-self-review\n- Decision: Spec passes self-review.\n",
            )

            self.write_human_approvals(project_dir, 'consensus')

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "human_spec_review")
            self.assertTrue(payload["human_allowed"])
            self.assertIn("docs/spec.md", payload["review"])

    def test_grill_storm_requests_plan_authoring_after_human_spec_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                spec_status="approved",
                open_questions="# Open Questions\n\n## High Priority\n- [ ] None.\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Muse\n- Status: accepted\n- Actor: muse\n- Decision: Muse explored intent.\n\n### 2026-05-12 - Logos\n- Status: accepted\n- Actor: logos\n- Decision: Logos converged approach.\n\n### 2026-05-12 - Human consensus approval\n- Status: accepted\n- Actor: human\n- Source: consensus\n- Decision: Build human-gated planning.\n\n### 2026-05-12 - Logos spec self-review\n- Status: accepted\n- Actor: logos\n- Source: spec-self-review\n- Decision: Spec passes self-review.\n\n### 2026-05-12 - Human spec review\n- Status: accepted\n- Actor: human\n- Source: spec-review\n- Decision: Spec approved.\n",
            )

            self.write_human_approvals(project_dir, 'consensus', 'spec-review')

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "needs_plan_authoring")
            self.assertEqual(payload["planning_mode"], "logos-plan-writer")

    def test_grill_storm_requests_human_plan_review_after_draft_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                spec_status="approved",
                plan_status="draft",
                open_questions="# Open Questions\n\n## High Priority\n- [ ] None.\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Muse\n- Status: accepted\n- Actor: muse\n- Decision: Muse explored intent.\n\n### 2026-05-12 - Logos\n- Status: accepted\n- Actor: logos\n- Decision: Logos converged approach.\n\n### 2026-05-12 - Human consensus approval\n- Status: accepted\n- Actor: human\n- Source: consensus\n- Decision: Build human-gated planning.\n\n### 2026-05-12 - Logos spec self-review\n- Status: accepted\n- Actor: logos\n- Source: spec-self-review\n- Decision: Spec passes self-review.\n\n### 2026-05-12 - Human spec review\n- Status: accepted\n- Actor: human\n- Source: spec-review\n- Decision: Spec approved.\n",
            )
            (project_dir / "docs" / "plan.md").write_text(
                "# Plan\n\nStatus: draft\n\n## Goal\n- Implement human-gated planning.\n\n## Steps\n### Task 1: Add gates\nFiles: workflow/grill_storm.py\nRun: python -m unittest tests.test_grill_storm_runtime -v\nExpected: PASS\nVerify: staged status works.\n\n## Rollback / Safety\n- Revert controller gates.\n",
                encoding="utf-8",
            )

            self.write_human_approvals(project_dir, 'consensus', 'spec-review')

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_PATH), "--project-dir", str(project_dir), "--status"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "human_plan_review")
            self.assertTrue(payload["human_allowed"])
            self.assertIn("docs/plan.md", payload["review"])


if __name__ == "__main__":
    unittest.main()

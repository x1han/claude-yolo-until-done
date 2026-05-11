from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
GRILL_STORM_PATH = SKILL_ROOT / "workflow" / "grill_storm.py"
VALIDATE_GRILL_DOCS_PATH = SKILL_ROOT / "workflow" / "validate_grill_docs.py"
PREFLIGHT_PATH = SKILL_ROOT / "workflow" / "preflight.py"


class GrillStormRuntimeTest(unittest.TestCase):
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
            or "# Open Questions\n\n## High Priority\n- [ ] Blocking: yes | Question: Which API should own execution gate? | Recommended: preflight validator\n\n## Medium Priority\n- [ ] None.\n\n## Low Priority\n- [ ] None.\n\n## Answered Recently\n- [x] Question: initial scope\n  Answer: built-in grill-storm\n  Impact: no external superpowers dependency\n",
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
            f"# Plan\n\nStatus: {plan_status}\n\n## Goal\n- Implement hard gate.\n\n## Steps\n1. Step: Add validator.\n   Verify: Run validator tests.\n2. Step: Wire preflight.\n   Verify: Preflight rejects drafts.\n3. Step: Document built-in skill.\n   Verify: Docs test passes.\n\n## Dependencies\n- Local docs.\n\n## File/Area Impact\n- workflow/preflight.py\n\n## Tests\n- python -m unittest tests.test_grill_storm_runtime -v\n\n## Rollback / Safety\n- Remove gate wiring.\n",
            encoding="utf-8",
        )
        return docs_dir

    def test_grill_storm_requires_interviewer_and_planner_internal_rounds_before_human_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-10 - Interviewer scope pass\n- Status: accepted\n- Actor: interviewer\n- Decision: Need preflight gate.\n- Reason: Execution must fail closed.\n- Alternatives considered: docs only.\n- Impact: adds validator.\n- Revisit when: validator too strict.\n",
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
            self.assertEqual(payload["next_actor"], "planner")
            self.assertFalse(payload["human_allowed"])
            self.assertIn("planner", payload["reason"])

    def test_grill_storm_allows_one_human_question_after_two_agent_internal_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-10 - Interviewer scope pass\n- Status: accepted\n- Actor: interviewer\n- Decision: Need preflight gate.\n- Reason: Execution must fail closed.\n- Alternatives considered: docs only.\n- Impact: adds validator.\n- Revisit when: validator too strict.\n\n### 2026-05-10 - Planner challenge pass\n- Status: accepted\n- Actor: planner\n- Decision: Keep validator separate from controller.\n- Reason: Planning gate owns authoring readiness.\n- Alternatives considered: controller-only check.\n- Impact: clearer ownership.\n- Revisit when: preflight grows too large.\n",
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

    def test_validate_grill_docs_accepts_approved_external_brain_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(
                project_dir,
                spec_status="approved",
                plan_status="approved",
                open_questions="# Open Questions\n\n## High Priority\n- [x] Question: gate owner\n  Answer: preflight validator\n  Impact: fail closed before execution\n\n## Medium Priority\n- [ ] None.\n\n## Low Priority\n- [ ] None.\n\n## Answered Recently\n- [x] Question: initial scope\n  Answer: built-in grill-storm\n  Impact: no external superpowers dependency\n",
                decisions="# Decisions\n\n## Decision Log\n\n### 2026-05-10 - Interviewer scope pass\n- Status: accepted\n- Actor: interviewer\n- Decision: Need preflight gate.\n- Reason: Execution must fail closed.\n- Alternatives considered: docs only.\n- Impact: adds validator.\n- Revisit when: validator too strict.\n\n### 2026-05-10 - Planner challenge pass\n- Status: accepted\n- Actor: planner\n- Decision: Keep validator separate from controller.\n- Reason: Planning gate owns authoring readiness.\n- Alternatives considered: controller-only check.\n- Impact: clearer ownership.\n- Revisit when: preflight grows too large.\n",
            )

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
            self.assertIn("grill-storm planning docs are not execution-ready", result.stderr)


if __name__ == "__main__":
    unittest.main()

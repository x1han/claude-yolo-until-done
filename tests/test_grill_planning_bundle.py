from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
INIT_GRILL_DOCS_PATH = SKILL_ROOT / "workflow" / "init_grill_docs.py"


class GrillPlanningBundleTest(unittest.TestCase):
    def run_init(self, project_dir: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(INIT_GRILL_DOCS_PATH),
                "--project-dir",
                str(project_dir),
                "--request",
                "Add grill-storm planning before execution.",
                *extra_args,
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_init_grill_docs_writes_default_planning_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            result = self.run_init(project_dir)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            docs_dir = project_dir / "docs"
            self.assertEqual(payload["docs_dir"], str(docs_dir))
            self.assertEqual(
                payload["files"],
                {
                    "intent": str(docs_dir / "intent.md"),
                    "open_questions": str(docs_dir / "open-questions.md"),
                    "decisions": str(docs_dir / "decisions.md"),
                    "spec": str(docs_dir / "spec.md"),
                    "plan": str(docs_dir / "plan.md"),
                },
            )

            intent = (docs_dir / "intent.md").read_text(encoding="utf-8")
            open_questions = (docs_dir / "open-questions.md").read_text(encoding="utf-8")
            decisions = (docs_dir / "decisions.md").read_text(encoding="utf-8")
            spec = (docs_dir / "spec.md").read_text(encoding="utf-8")
            plan = (docs_dir / "plan.md").read_text(encoding="utf-8")

            self.assertIn("# Intent", intent)
            self.assertIn("Add grill-storm planning before execution.", intent)
            self.assertIn("## Why This Matters", intent)
            self.assertIn("# Open Questions", open_questions)
            self.assertIn("## High Priority", open_questions)
            self.assertIn("# Decisions", decisions)
            self.assertIn("## Decision Log", decisions)
            self.assertIn("Status: draft", decisions)
            self.assertNotIn("Status: accepted", decisions)
            self.assertIn("# Spec", spec)
            self.assertIn("Status: draft", spec)
            self.assertIn("## Acceptance Criteria", spec)
            self.assertIn("# Plan", plan)
            self.assertIn("Status: draft", plan)
            self.assertIn("## Steps", plan)
            self.assertIn("Rollback / Safety", plan)

    def test_init_grill_docs_keeps_existing_docs_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            docs_dir = project_dir / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            existing_spec = docs_dir / "spec.md"
            existing_spec.write_text("# Spec\n\nKeep this content.\n", encoding="utf-8")

            result = self.run_init(project_dir)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["created"], ["intent", "open_questions", "decisions", "plan"])
            self.assertEqual(payload["preserved"], ["spec"])
            self.assertEqual(existing_spec.read_text(encoding="utf-8"), "# Spec\n\nKeep this content.\n")


if __name__ == "__main__":
    unittest.main()

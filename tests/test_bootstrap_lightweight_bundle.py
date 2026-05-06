from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = SKILL_ROOT / "workflow" / "bootstrap.py"


class BootstrapLightweightBundleTest(unittest.TestCase):
    def test_bootstrap_rejects_headless_claude_print_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"

            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n", encoding="utf-8")

            env = dict(os.environ)
            env["CLAUDECODE"] = "1"
            env["CLAUDE_CODE_ENTRYPOINT"] = "print"

            result = subprocess.run(
                [
                    sys.executable,
                    str(BOOTSTRAP_PATH),
                    "--spec",
                    str(spec_path),
                    "--plan",
                    str(plan_path),
                    "--run-root",
                    str(run_root),
                    "--goal",
                    "Ship the lightweight run bundle.",
                    "--success-criterion",
                    "state.json captures the authoritative run state.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("headless claude -p", result.stderr.lower())
            self.assertFalse((run_root / "state.json").exists())
            self.assertFalse((run_root / "trace.md").exists())

    def test_bootstrap_writes_only_state_and_trace_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / "artifacts" / "run-001"

            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(BOOTSTRAP_PATH),
                    "--spec",
                    str(spec_path),
                    "--plan",
                    str(plan_path),
                    "--run-root",
                    str(run_root),
                    "--goal",
                    "Ship the lightweight run bundle.",
                    "--success-criterion",
                    "state.json captures the authoritative run state.",
                    "--success-criterion",
                    "trace.md records the bootstrap handoff.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            state_path = run_root / "state.json"
            trace_path = run_root / "trace.md"
            self.assertTrue(state_path.exists())
            self.assertTrue(trace_path.exists())

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["goal"], "Ship the lightweight run bundle.")
            self.assertEqual(
                state["success_criteria"],
                [
                    "state.json captures the authoritative run state.",
                    "trace.md records the bootstrap handoff.",
                ],
            )
            self.assertEqual(state["status"], "active")
            self.assertEqual(state["owner"], "worker")
            self.assertEqual(state["next_action"], "worker_update")
            self.assertFalse(state["cleanup_required"])
            self.assertEqual(state["plan_path"], "plan.md")
            self.assertEqual(state["spec_path"], "spec.md")
            self.assertEqual(state["worker_claim"], "")
            self.assertEqual(state["files_changed"], [])
            self.assertEqual(state["verification_command"], "")
            self.assertEqual(state["verification_result"], "")
            self.assertEqual(state["submitted_at"], "")
            self.assertEqual(state["review"], {})
            self.assertEqual(state["reviewed_at"], "")
            self.assertIn("updated_at", state)

            trace = trace_path.read_text(encoding="utf-8")
            self.assertIn("# Goal", trace)
            self.assertIn("Ship the lightweight run bundle.", trace)
            self.assertIn("## Success Criteria", trace)
            self.assertIn("- state.json captures the authoritative run state.", trace)
            self.assertIn("- trace.md records the bootstrap handoff.", trace)
            self.assertIn("bootstrap", trace.lower())

            for obsolete_name in [
                "runtime_context.json",
                "run_state.json",
                "gates.json",
                "checkoffs.json",
                "workflow_manifest.json",
                "report.md",
                "resume.md",
            ]:
                self.assertFalse((run_root / obsolete_name).exists(), obsolete_name)


if __name__ == "__main__":
    unittest.main()

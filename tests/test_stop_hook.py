from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from claude_hook_bridge import stop


class StopHookTest(unittest.TestCase):
    def test_stop_blocks_incomplete_workflow_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            for status in ("active", "needs_review", "rework_required", "approved"):
                (run_root / "state.json").write_text(
                    json.dumps(
                        {
                            "goal": "Fix it.",
                            "success_criteria": ["It works."],
                            "status": status,
                            "worker_claim": "",
                            "files_changed": [],
                            "verification_command": "",
                            "verification_result": "",
                            "submitted_at": "",
                            "review": {},
                            "reviewed_at": "",
                            "owner": "worker",
                            "next_action": "worker_update",
                            "plan_path": "docs/plan.md",
                            "spec_path": "docs/spec.md",
                            "updated_at": "2026-05-01T00:00:00Z",
                        }
                    ),
                    encoding="utf-8",
                )
                with io.StringIO() as stream, contextlib.redirect_stdout(stream):
                    decision = stop(project_dir, run_root, {})
                    payload = json.loads(stream.getvalue())
                self.assertEqual(decision, 0)
                self.assertEqual(payload["decision"], "block")
                self.assertIn(status, payload["reason"])

    def test_stop_blocks_when_cleanup_is_still_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "complete",
                        "cleanup_required": True,
                        "worker_claim": "Updated src/app.py.",
                        "files_changed": ["src/app.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed: 1 passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {"verdict": "approve", "scope_checked": [], "problems": [], "required_rework": [], "acceptance_basis": ["ok"]},
                        "reviewed_at": "2026-05-01T00:01:00Z",
                        "owner": "watcher",
                        "next_action": "cleanup",
                        "plan_path": "docs/plan.md",
                        "spec_path": "docs/spec.md",
                        "updated_at": "2026-05-01T00:01:00Z",
                    }
                ),
                encoding="utf-8",
            )
            with io.StringIO() as stream, contextlib.redirect_stdout(stream):
                decision = stop(project_dir, run_root, {})
                payload = json.loads(stream.getvalue())
            self.assertEqual(decision, 0)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("cleanup", payload["reason"])

    def test_stop_blocks_invalid_complete_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "complete",
                        "worker_claim": "Updated src/app.py.",
                        "files_changed": ["src/app.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed: 1 passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {"verdict": "rework_required", "scope_checked": [], "problems": ["x"], "required_rework": ["y"], "acceptance_basis": []},
                        "reviewed_at": "2026-05-01T00:01:00Z",
                        "owner": "watcher",
                        "next_action": "complete",
                        "plan_path": "docs/plan.md",
                        "spec_path": "docs/spec.md",
                        "updated_at": "2026-05-01T00:01:00Z",
                    }
                ),
                encoding="utf-8",
            )
            with io.StringIO() as stream, contextlib.redirect_stdout(stream):
                decision = stop(project_dir, run_root, {})
                payload = json.loads(stream.getvalue())
            self.assertEqual(decision, 0)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("completion validation", payload["reason"])


if __name__ == "__main__":
    unittest.main()

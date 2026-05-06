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

from validate_completion import run as validate_completion
from validate_submission import run as validate_submission


class ValidatorsTest(unittest.TestCase):
    def test_submission_validator_rejects_missing_worker_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "needs_review",
                        "worker_claim": "",
                        "files_changed": ["src/app.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed: 1 passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {},
                        "reviewed_at": "",
                        "owner": "watcher",
                        "next_action": "watcher_review",
                        "plan_path": "docs/plan.md",
                        "spec_path": "docs/spec.md",
                        "updated_at": "2026-05-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            (run_root / "trace.md").write_text("- 2026-05-01T00:00:00Z worker submit: claim=Updated src/app.py\n", encoding="utf-8")
            report = validate_submission(run_root)
            self.assertFalse(report["passed"])

    def test_completion_validator_rejects_complete_without_approved_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "complete",
                        "worker_claim": "Updated parser handling.",
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
            (run_root / "trace.md").write_text("- 2026-05-01T00:01:00Z watcher review: rework_required\n", encoding="utf-8")
            report = validate_completion(run_root)
            self.assertFalse(report["passed"])

    def test_completion_validator_accepts_complete_with_approved_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "complete",
                        "worker_claim": "Updated parser handling.",
                        "files_changed": ["src/app.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed: 1 passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {
                            "verdict": "approve",
                            "scope_checked": ["src/app.py"],
                            "problems": [],
                            "required_rework": [],
                            "acceptance_basis": ["verification passed freshly"],
                        },
                        "reviewed_at": "2026-05-01T00:01:00Z",
                        "owner": "watcher",
                        "next_action": "complete",
                        "cleanup_required": True,
                        "plan_path": "docs/plan.md",
                        "spec_path": "docs/spec.md",
                        "updated_at": "2026-05-01T00:01:00Z",
                    }
                ),
                encoding="utf-8",
            )
            (run_root / "trace.md").write_text(
                "- 2026-05-01T00:00:00Z worker submit: claim=Updated parser handling.\n"
                "- 2026-05-01T00:01:00Z watcher review: approve; scope_checked=src/app.py\n"
                "- 2026-05-01T00:02:00Z watcher complete\n",
                encoding="utf-8",
            )
            report = validate_completion(run_root)
            self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()

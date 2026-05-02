from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"
HOOKS_DIR = SKILL_ROOT / "hooks"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from claude_hook_bridge import session_end
from hook_settings import install_hook_set


class SessionEndCleanupTest(unittest.TestCase):
    def test_session_end_removes_hooks_for_completed_run_installed_with_relative_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / "artifacts" / "yolo"
            settings_path = project_dir / ".claude" / "settings.local.json"
            bridge_path = WORKFLOW_DIR / "claude_hook_bridge.py"

            run_root.mkdir(parents=True)
            install_hook_set(settings_path, Path(sys.executable), bridge_path, "artifacts/yolo", ".claude/settings.local.json")
            state = {
                "goal": "Fix it.",
                "success_criteria": ["It works."],
                "status": "complete",
                "worker_claim": "Updated src/app.py.",
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
                "plan_path": "docs/plan.md",
                "spec_path": "docs/spec.md",
                "updated_at": "2026-05-01T00:01:00Z",
            }
            (run_root / "state.json").write_text(json.dumps(state), encoding="utf-8")
            (run_root / "trace.md").write_text(
                "- 2026-05-01T00:00:00Z worker submit: claim=Updated src/app.py.\n"
                "- 2026-05-01T00:01:00Z watcher review: approve; scope_checked=src/app.py\n"
                "- 2026-05-01T00:02:00Z watcher complete\n",
                encoding="utf-8",
            )

            session_end(project_dir, run_root, ".claude/settings.local.json")

            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(settings, {})


if __name__ == "__main__":
    unittest.main()

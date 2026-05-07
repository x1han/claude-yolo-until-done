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

from claude_hook_bridge import build_user_prompt_submit_payload, user_prompt_submit
from hook_settings import install_hook_set


class UserPromptSubmitCleanupGateTest(unittest.TestCase):
    def test_install_includes_user_prompt_submit_and_excludes_session_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            settings_path = project_dir / ".claude" / "settings.local.json"
            bridge_path = SKILL_ROOT / "workflow" / "claude_hook_bridge.py"
            settings = install_hook_set(settings_path, Path(sys.executable), bridge_path, ".yolo")
            hooks = settings["hooks"]
            self.assertIn("UserPromptSubmit", hooks)
            self.assertNotIn("SessionEnd", hooks)

    def test_user_prompt_submit_blocks_with_three_way_choice_when_run_unfinished(self) -> None:
        payload = build_user_prompt_submit_payload({"status": "rework_required", "cleanup_required": False})
        self.assertEqual(payload["decision"], "block")
        self.assertIn("暂停", payload["reason"])
        self.assertIn("取消", payload["reason"])
        self.assertIn("继续 yolo", payload["reason"])

    def test_user_prompt_submit_allows_explicit_continue_choice(self) -> None:
        payload = build_user_prompt_submit_payload(
            {"status": "rework_required", "cleanup_required": False},
            {"prompt": "继续 yolo"},
        )
        self.assertEqual(payload, {})

    def test_user_prompt_submit_blocks_non_exact_continue_phrase(self) -> None:
        payload = build_user_prompt_submit_payload(
            {"status": "rework_required", "cleanup_required": False},
            {"prompt": "继续 yolo。读取 .yolo/state.json 并执行前 3 步。"},
        )
        self.assertEqual(payload["decision"], "block")
        self.assertIn("三选一", payload["reason"])

    def test_user_prompt_submit_blocks_when_cleanup_is_still_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "status": "complete",
                        "cleanup_required": True,
                        "owner": "watcher",
                        "next_action": "cleanup",
                        "requested_role": "worker",
                        "gate_attempt": 0,
                        "gate_max_attempts": 5,
                        "blocked_for_human": False,
                    }
                ),
                encoding="utf-8",
            )
            (run_root / "trace.md").write_text("# trace\n", encoding="utf-8")
            with io.StringIO() as stream, contextlib.redirect_stdout(stream):
                decision = user_prompt_submit(project_dir, run_root, {})
                payload = json.loads(stream.getvalue())
            self.assertEqual(decision, 0)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("继续 yolo", payload["reason"])

    def test_user_prompt_submit_blocks_when_run_bundle_is_damaged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            (run_root / "trace.md").write_text("# trace\n", encoding="utf-8")
            with io.StringIO() as stream, contextlib.redirect_stdout(stream):
                decision = user_prompt_submit(project_dir, run_root, {})
                payload = json.loads(stream.getvalue())
            self.assertEqual(decision, 0)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("state.json is missing", payload["reason"])

    def test_user_prompt_submit_blocks_invalid_complete_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "status": "complete",
                        "cleanup_required": False,
                        "worker_claim": "Updated src/app.py.",
                        "files_changed": ["src/app.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {"verdict": "rework_required", "scope_checked": [], "problems": ["x"], "required_rework": ["y"], "acceptance_basis": []},
                        "reviewed_at": "2026-05-01T00:01:00Z",
                        "owner": "watcher",
                        "next_action": "complete",
                        "requested_role": "worker",
                        "gate_attempt": 0,
                        "gate_max_attempts": 5,
                        "blocked_for_human": False,
                    }
                ),
                encoding="utf-8",
            )
            (run_root / "trace.md").write_text("# trace\n", encoding="utf-8")
            with io.StringIO() as stream, contextlib.redirect_stdout(stream):
                decision = user_prompt_submit(project_dir, run_root, {})
                payload = json.loads(stream.getvalue())
            self.assertEqual(decision, 0)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("completion validation still fails", payload["reason"])

    def test_user_prompt_submit_blocks_complete_bundle_without_cleanup_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "status": "complete",
                        "cleanup_required": False,
                        "worker_claim": "Updated src/app.py.",
                        "files_changed": ["src/app.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {
                            "verdict": "approve",
                            "scope_checked": ["src/app.py"],
                            "problems": [],
                            "required_rework": [],
                            "acceptance_basis": ["ok"],
                        },
                        "reviewed_at": "2026-05-01T00:01:00Z",
                        "owner": "watcher",
                        "next_action": "complete",
                        "requested_role": "worker",
                        "gate_attempt": 0,
                        "gate_max_attempts": 5,
                        "blocked_for_human": False,
                    }
                ),
                encoding="utf-8",
            )
            (run_root / "trace.md").write_text(
                "- 2026-05-01T00:00:00Z worker submit: claim=Updated src/app.py.\n"
                "- 2026-05-01T00:01:00Z watcher review: approve; scope_checked=src/app.py\n"
                "- 2026-05-01T00:02:00Z watcher complete\n",
                encoding="utf-8",
            )
            with io.StringIO() as stream, contextlib.redirect_stdout(stream):
                decision = user_prompt_submit(project_dir, run_root, {})
                payload = json.loads(stream.getvalue())
            self.assertEqual(decision, 0)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("completion validation still fails", payload["reason"])


if __name__ == "__main__":
    unittest.main()

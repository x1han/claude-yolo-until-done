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

    def test_user_prompt_submit_emits_no_prompt_block_payload_for_complete_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "status": "complete",
                        "cleanup_required": False,
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
                raw = stream.getvalue().strip()
            self.assertEqual(decision, 0)
            self.assertEqual(raw, "")


if __name__ == "__main__":
    unittest.main()

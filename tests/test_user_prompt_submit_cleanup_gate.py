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
from lifecycle import build_completion_certification, compute_certification_hash


class UserPromptSubmitCleanupGateTest(unittest.TestCase):
    def completion_certification(self, state: dict | None = None) -> dict:
        source_state = {
            "status": "ready_for_cleanup",
            "cleanup_required": True,
            "owner": "watcher",
            "next_action": "complete",
            "task_id": "task-001",
            "task_title": "Current task",
            "worker_claim": "Updated src/app.py.",
            "files_changed": ["src/app.py"],
            "verification_command": "python -m unittest",
            "verification_result": "passed",
            "submitted_at": "2026-05-08T00:00:00+00:00",
            "reviewed_at": "2026-05-08T00:00:00+00:00",
            "review": {"verdict": "approve", "scope_checked": ["src/app.py"], "problems": [], "required_rework": [], "acceptance_basis": ["ok"]},
        }
        if state is not None:
            source_state.update(state)
        payload = build_completion_certification(source_state, "2026-05-08T00:00:00+00:00")
        return {
            "certification": {"completion": payload},
            "certification_hash": compute_certification_hash(payload),
        }

    def test_install_includes_user_prompt_submit_and_excludes_session_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            settings_path = project_dir / ".claude" / "settings.local.json"
            bridge_path = SKILL_ROOT / "workflow" / "claude_hook_bridge.py"
            settings = install_hook_set(settings_path, Path(sys.executable), bridge_path, ".yolo")
            hooks = settings["hooks"]
            self.assertIn("UserPromptSubmit", hooks)
            self.assertNotIn("SessionEnd", hooks)

    def test_user_prompt_submit_blocks_with_english_three_way_choice_by_default(self) -> None:
        payload = build_user_prompt_submit_payload({"status": "rework_required", "cleanup_required": False})
        self.assertEqual(payload["decision"], "block")
        self.assertIn("I found an active claude-yolo run", payload["reason"])
        self.assertNotIn("To protect", payload["reason"])
        self.assertIn("pause", payload["reason"])
        self.assertIn("cancel", payload["reason"])
        self.assertIn("continue yolo", payload["reason"])

    def test_user_prompt_submit_blocks_with_persisted_chinese_three_way_choice(self) -> None:
        payload = build_user_prompt_submit_payload(
            {
                "status": "rework_required",
                "cleanup_required": False,
                "dialogue_language": {"source": "latest_user_request", "language": "zh-CN", "confidence": 0.8},
            }
        )
        self.assertEqual(payload["decision"], "block")
        self.assertIn("我发现当前项目还有一个 claude-yolo 运行", payload["reason"])
        self.assertNotIn("为了保护", payload["reason"])
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
        self.assertIn("choose the next step", payload["reason"])

    def test_user_prompt_submit_routes_need_human_runs_to_human_helper_mode(self) -> None:
        payload = build_user_prompt_submit_payload(
            {
                "status": "active",
                "cleanup_required": False,
                "allow_need_human": True,
                "blocked_for_human": True,
                "worker_request": "need_human",
                "worker_question": "Need product guidance.",
                "task_id": "task-001",
                "task_title": "Current task",
                "task_inputs": ["step one", "step two"],
            },
            {"prompt": "我们改成只做前两步可以吗？"},
        )
        self.assertEqual(payload["decision"], "human_helper")
        self.assertEqual(payload["mode"], "human_helper")
        self.assertEqual(payload["worker_question"], "Need product guidance.")
        self.assertEqual(payload["task_id"], "task-001")
        self.assertEqual(payload["task_title"], "Current task")
        self.assertEqual(payload["task_inputs"], ["step one", "step two"])

    def test_user_prompt_submit_keeps_three_way_gate_without_need_human(self) -> None:
        payload = build_user_prompt_submit_payload(
            {
                "status": "active",
                "cleanup_required": False,
                "allow_need_human": True,
                "blocked_for_human": False,
                "worker_request": "",
            },
            {"prompt": "帮我看看现在做到哪一步了"},
        )
        self.assertEqual(payload["decision"], "block")
        self.assertIn("choose the next step", payload["reason"])

    def test_user_prompt_submit_keeps_three_way_gate_when_need_human_is_disabled(self) -> None:
        payload = build_user_prompt_submit_payload(
            {
                "status": "active",
                "cleanup_required": False,
                "allow_need_human": False,
                "blocked_for_human": True,
                "worker_request": "need_human",
            },
            {"prompt": "继续讨论一下"},
        )
        self.assertEqual(payload["decision"], "block")
        self.assertIn("choose the next step", payload["reason"])

    def test_user_prompt_submit_keeps_three_way_gate_when_allow_need_human_is_missing(self) -> None:
        payload = build_user_prompt_submit_payload(
            {
                "status": "active",
                "cleanup_required": False,
                "blocked_for_human": True,
                "worker_request": "need_human",
            },
            {"prompt": "继续讨论一下"},
        )
        self.assertEqual(payload["decision"], "block")
        self.assertIn("choose the next step", payload["reason"])

    def test_user_prompt_submit_routes_stop_gate_limit_runs_to_human_helper_mode(self) -> None:
        payload = build_user_prompt_submit_payload(
            {
                "status": "active",
                "cleanup_required": False,
                "allow_need_human": True,
                "blocked_for_human": True,
                "worker_request": "",
                "worker_question": "",
                "human_handoff": {"reason": "stop_gate_limit"},
                "task_id": "task-001",
                "task_title": "Current task",
                "task_inputs": ["step one", "step two"],
            },
            {"prompt": "先缩小范围再继续"},
        )
        self.assertEqual(payload["decision"], "human_helper")
        self.assertEqual(payload["mode"], "human_helper")
        self.assertEqual(payload["task_id"], "task-001")
        self.assertEqual(payload["task_title"], "Current task")

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
                        "state_version": 1,
                        "gate_attempt": 0,
                        "gate_max_attempts": 5,
                        "blocked_for_human": False,
                        **self.completion_certification(),
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
            self.assertIn("continue yolo", payload["reason"])

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

    def test_user_prompt_submit_blocks_ready_for_cleanup_without_completion_certification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "status": "ready_for_cleanup",
                        "cleanup_required": True,
                        "owner": "watcher",
                        "next_action": "complete",
                        "requested_role": "worker",
                        "state_version": 1,
                        "gate_attempt": 0,
                        "gate_max_attempts": 5,
                        "blocked_for_human": False,
                    }
                ),
                encoding="utf-8",
            )
            with io.StringIO() as stream, contextlib.redirect_stdout(stream):
                decision = user_prompt_submit(project_dir, run_root, {})
                payload = json.loads(stream.getvalue())
            self.assertEqual(decision, 0)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("completion certification", payload["reason"])

    def test_user_prompt_submit_blocks_complete_bundle_with_mismatched_certification_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            state = {
                "status": "complete",
                "cleanup_required": False,
                "owner": "watcher",
                "next_action": "complete",
                "requested_role": "worker",
                "state_version": 1,
                "gate_attempt": 0,
                "gate_max_attempts": 5,
                "blocked_for_human": False,
                "certification": {"completion": self.completion_certification()["certification"]["completion"]},
                "certification_hash": "wrong-hash",
            }
            (run_root / "state.json").write_text(json.dumps(state), encoding="utf-8")
            with io.StringIO() as stream, contextlib.redirect_stdout(stream):
                decision = user_prompt_submit(project_dir, run_root, {})
                payload = json.loads(stream.getvalue())
            self.assertEqual(decision, 0)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("certification_hash", payload["reason"])

    def test_user_prompt_submit_blocks_complete_bundle_with_invalid_terminal_cleanup_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            state = {
                "status": "complete",
                "cleanup_required": False,
                "owner": "worker",
                "next_action": "worker_update",
                "requested_role": "worker",
                "state_version": 1,
                "gate_attempt": 0,
                "gate_max_attempts": 5,
                "blocked_for_human": False,
                **self.completion_certification(
                    {
                        "status": "complete",
                        "cleanup_required": False,
                        "owner": "worker",
                        "next_action": "worker_update",
                    }
                ),
            }
            (run_root / "state.json").write_text(json.dumps(state), encoding="utf-8")
            with io.StringIO() as stream, contextlib.redirect_stdout(stream):
                decision = user_prompt_submit(project_dir, run_root, {})
                payload = json.loads(stream.getvalue())
            self.assertEqual(decision, 0)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("terminal cleanup contract", payload["reason"])

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
                        "owner": "watcher",
                        "next_action": "complete",
                        "requested_role": "worker",
                        "state_version": 1,
                        "gate_attempt": 0,
                        "gate_max_attempts": 5,
                        "blocked_for_human": False,
                        **self.completion_certification(),
                    }
                ),
                encoding="utf-8",
            )
            with io.StringIO() as stream, contextlib.redirect_stdout(stream):
                decision = user_prompt_submit(project_dir, run_root, {})
                raw = stream.getvalue().strip()
            self.assertEqual(decision, 0)
            self.assertEqual(raw, "")


if __name__ == "__main__":
    unittest.main()

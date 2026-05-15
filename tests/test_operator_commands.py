from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"
OPERATOR_PATH = WORKFLOW_DIR / "operator_cli.py"

spec = importlib.util.spec_from_file_location("claude_yolo_operator", OPERATOR_PATH)
assert spec and spec.loader
operator_commands = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator_commands)


class OperatorCommandsTest(unittest.TestCase):
    def captured_command(self, argv: list[str]) -> list[str]:
        calls: list[list[str]] = []

        def fake_run(command: list[str], check: bool) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return subprocess.CompletedProcess(command, 0)

        with patch.object(sys, "argv", ["operator_cli.py", *argv]), patch.object(operator_commands.subprocess, "run", side_effect=fake_run):
            self.assertEqual(operator_commands.main(), 0)

        self.assertEqual(len(calls), 1)
        return calls[0]

    def test_worker_submit_wraps_controller_actor_and_action(self) -> None:
        command = self.captured_command(
            [
                "worker-submit",
                "--run-root",
                ".yolo",
                "--expected-version",
                "7",
                "--worker-claim",
                "claim",
                "--files-changed",
                "workflow/controller.py",
                "--verification-command",
                "python -m unittest",
                "--verification-result",
                "passed",
                "--loop-selected-work",
                "operator wrapper",
                "--loop-evidence",
                "wrapper test passed",
                "--acceleration-decision",
                "defer",
                "--acceleration-evidence",
                "no shortcut",
                "--gate-safety-basis",
                "watcher still required",
            ]
        )

        self.assertEqual(command[:2], [sys.executable, str(WORKFLOW_DIR / "controller.py")])
        self.assertIn("--actor", command)
        self.assertIn("worker", command)
        self.assertIn("--action", command)
        self.assertIn("submit", command)
        self.assertIn("--loop-selected-work", command)
        self.assertIn("operator wrapper", command)

    def test_watcher_review_wraps_controller_actor_and_action(self) -> None:
        command = self.captured_command(
            [
                "watcher-review",
                "--run-root",
                ".yolo",
                "--expected-version",
                "8",
                "--verdict",
                "approve",
                "--scope-checked",
                "workflow/operator_cli.py",
                "--acceptance-basis",
                "verified",
            ]
        )

        self.assertEqual(command[:2], [sys.executable, str(WORKFLOW_DIR / "controller.py")])
        self.assertIn("--actor", command)
        self.assertIn("watcher", command)
        self.assertIn("--action", command)
        self.assertIn("review", command)

    def test_watcher_complete_wraps_controller_actor_and_action(self) -> None:
        command = self.captured_command(["watcher-complete", "--run-root", ".yolo", "--expected-version", "9"])

        self.assertEqual(command[:2], [sys.executable, str(WORKFLOW_DIR / "controller.py")])
        self.assertIn("--actor", command)
        self.assertIn("watcher", command)
        self.assertIn("--action", command)
        self.assertIn("complete", command)

    def test_validator_wrappers_call_run_gate(self) -> None:
        submission = self.captured_command(["validate-submission", "--run-root", ".yolo"])
        completion = self.captured_command(["validate-completion", "--run-root", ".yolo"])

        self.assertEqual(submission[:2], [sys.executable, str(SKILL_ROOT / "hooks" / "run_gate.py")])
        self.assertIn("submission", submission)
        self.assertEqual(completion[:2], [sys.executable, str(SKILL_ROOT / "hooks" / "run_gate.py")])
        self.assertIn("completion", completion)

    def test_cleanup_wraps_cleanup_script(self) -> None:
        command = self.captured_command(["cleanup", "--project-dir", ".", "--run-root", ".yolo", "--mode", "pause"])

        self.assertEqual(command[:2], [sys.executable, str(WORKFLOW_DIR / "cleanup_claude_yolo.py")])
        self.assertIn("--project-dir", command)
        self.assertIn("--mode", command)
        self.assertIn("pause", command)

    def test_preflight_forwards_to_preflight_script(self) -> None:
        command = self.captured_command(["preflight", "--project-dir", ".", "--goal", "Ship it"])

        self.assertEqual(command[:2], [sys.executable, str(WORKFLOW_DIR / "preflight.py")])
        self.assertIn("--project-dir", command)
        self.assertIn("--goal", command)


if __name__ == "__main__":
    unittest.main()

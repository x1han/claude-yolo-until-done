from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from cleanup_claude_yolo import main as cleanup_main

CLEANUP_PATH = SKILL_ROOT / "workflow" / "cleanup_claude_yolo.py"
INSTALL_HOOKS_PATH = SKILL_ROOT / "workflow" / "install_claude_hooks.py"


class CleanupClaudeYoloTest(unittest.TestCase):
    def write_valid_complete_bundle(self, run_root: Path) -> None:
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "state.json").write_text(
            json.dumps(
                {
                    "goal": "Fix it.",
                    "success_criteria": ["It works."],
                    "status": "complete",
                    "cleanup_required": True,
                    "worker_claim": "Updated src/app.py.",
                    "files_changed": ["src/app.py"],
                    "verification_command": "python -m unittest",
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
                    "plan_path": "docs/plan.md",
                    "spec_path": "docs/spec.md",
                    "updated_at": "2026-05-01T00:01:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (run_root / "trace.md").write_text(
            "- watcher review: approve\n- watcher complete\n",
            encoding="utf-8",
        )

    def test_pause_removes_only_claude_yolo_hooks_and_keeps_run_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            (run_root / "state.json").write_text('{"status": "rework_required"}\n', encoding="utf-8")
            (run_root / "trace.md").write_text("# trace\n", encoding="utf-8")

            subprocess.run(
                [sys.executable, str(INSTALL_HOOKS_PATH), "--project-dir", str(project_dir), "--run-root", ".yolo"],
                check=True,
                capture_output=True,
                text=True,
            )

            settings_path = project_dir / ".claude" / "settings.local.json"
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            settings.setdefault("hooks", {}).setdefault("Stop", []).append(
                {"metadata": {"workflow": "other"}, "hooks": [{"type": "command", "command": "true"}]}
            )
            settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLEANUP_PATH),
                    "--project-dir",
                    str(project_dir),
                    "--run-root",
                    ".yolo",
                    "--mode",
                    "pause",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((run_root / "state.json").exists())
            self.assertTrue((run_root / "trace.md").exists())
            updated = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertNotIn("claudeYoloUntilDone", updated)
            self.assertEqual(len(updated["hooks"]["Stop"]), 1)
            self.assertEqual(updated["hooks"]["Stop"][0]["metadata"]["workflow"], "other")

    def test_cancel_removes_run_files_and_claude_yolo_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            (run_root / "state.json").write_text('{"status": "rework_required"}\n', encoding="utf-8")
            (run_root / "trace.md").write_text("# trace\n", encoding="utf-8")

            subprocess.run(
                [sys.executable, str(INSTALL_HOOKS_PATH), "--project-dir", str(project_dir), "--run-root", ".yolo"],
                check=True,
                capture_output=True,
                text=True,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLEANUP_PATH),
                    "--project-dir",
                    str(project_dir),
                    "--run-root",
                    ".yolo",
                    "--mode",
                    "cancel",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((run_root / "state.json").exists())
            self.assertFalse((run_root / "trace.md").exists())

    def test_complete_refuses_cleanup_when_completion_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            (run_root / "state.json").write_text('{"status": "complete", "cleanup_required": false}\n', encoding="utf-8")
            (run_root / "trace.md").write_text("# trace\n", encoding="utf-8")

            subprocess.run(
                [sys.executable, str(INSTALL_HOOKS_PATH), "--project-dir", str(project_dir), "--run-root", ".yolo"],
                check=True,
                capture_output=True,
                text=True,
            )

            settings_path = project_dir / ".claude" / "settings.local.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLEANUP_PATH),
                    "--project-dir",
                    str(project_dir),
                    "--run-root",
                    ".yolo",
                    "--mode",
                    "complete",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue((run_root / "state.json").exists())
            self.assertTrue((run_root / "trace.md").exists())
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertIn("claudeYoloUntilDone", settings)
            self.assertIn("completion validation", result.stderr)

    def test_complete_removes_run_files_and_hooks_after_valid_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_valid_complete_bundle(run_root)

            subprocess.run(
                [sys.executable, str(INSTALL_HOOKS_PATH), "--project-dir", str(project_dir), "--run-root", ".yolo"],
                check=True,
                capture_output=True,
                text=True,
            )

            settings_path = project_dir / ".claude" / "settings.local.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLEANUP_PATH),
                    "--project-dir",
                    str(project_dir),
                    "--run-root",
                    ".yolo",
                    "--mode",
                    "complete",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((run_root / "state.json").exists())
            self.assertFalse((run_root / "trace.md").exists())
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertNotIn("claudeYoloUntilDone", settings)

    def test_complete_keeps_hooks_installed_when_run_file_removal_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_valid_complete_bundle(run_root)

            subprocess.run(
                [sys.executable, str(INSTALL_HOOKS_PATH), "--project-dir", str(project_dir), "--run-root", ".yolo"],
                check=True,
                capture_output=True,
                text=True,
            )

            settings_path = project_dir / ".claude" / "settings.local.json"
            argv = [
                "cleanup_claude_yolo.py",
                "--project-dir",
                str(project_dir),
                "--run-root",
                ".yolo",
                "--mode",
                "complete",
            ]
            with patch.object(sys, "argv", argv), patch("cleanup_claude_yolo.remove_run_files", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    cleanup_main()

            self.assertTrue((run_root / "state.json").exists())
            self.assertTrue((run_root / "trace.md").exists())
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertIn("claudeYoloUntilDone", settings)


if __name__ == "__main__":
    unittest.main()

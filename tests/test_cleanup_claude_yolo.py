from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
CLEANUP_PATH = SKILL_ROOT / "workflow" / "cleanup_claude_yolo.py"
INSTALL_HOOKS_PATH = SKILL_ROOT / "workflow" / "install_claude_hooks.py"


class CleanupClaudeYoloTest(unittest.TestCase):
    def test_pause_removes_only_claude_yolo_hooks_and_keeps_run_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            run_root.mkdir(parents=True)
            (run_root / "state.json").write_text('{"status": "rework_required"}\n', encoding="utf-8")
            (run_root / "trace.md").write_text("# trace\n", encoding="utf-8")

            subprocess.run(
                [sys.executable, str(INSTALL_HOOKS_PATH), "--project-dir", str(project_dir), "--run-root", ".yolo"],
                check=False,
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
                check=False,
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


if __name__ == "__main__":
    unittest.main()

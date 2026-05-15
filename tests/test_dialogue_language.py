from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from state import detect_dialogue_language

PREFLIGHT_PATH = SKILL_ROOT / "workflow" / "preflight.py"


class DialogueLanguageTest(unittest.TestCase):
    def runtime_env(self, project_dir: Path) -> dict[str, str]:
        env = dict(os.environ)
        env["CLAUDE_CODE_ENTRYPOINT"] = "cli"
        bin_dir = project_dir / ".test-bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        ps_path = bin_dir / "ps"
        ps_path.write_text(
            "#!/usr/bin/env python3\n"
            "print('  PID  PPID ARGS')\n"
            "print('123 1 claude --dangerously-skip-permissions')\n",
            encoding="utf-8",
        )
        ps_path.chmod(0o755)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
        return env

    def run_preflight(self, project_dir: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
        spec_path = project_dir / "spec.md"
        plan_path = project_dir / "plan.md"
        spec_path.write_text("# Spec\n", encoding="utf-8")
        plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(PREFLIGHT_PATH),
                "--project-dir",
                str(project_dir),
                "--spec",
                str(spec_path),
                "--plan",
                str(plan_path),
                "--run-root",
                ".yolo",
                "--goal",
                "Ship dialogue language handling.",
                *extra_args,
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
            env=self.runtime_env(project_dir),
        )

    def test_detect_dialogue_language_prefers_explicit_override(self) -> None:
        self.assertEqual(
            detect_dialogue_language("en", "请继续") ,
            {"source": "explicit", "language": "en", "confidence": 1.0},
        )
        self.assertEqual(
            detect_dialogue_language("zh-CN", "continue please"),
            {"source": "explicit", "language": "zh-CN", "confidence": 1.0},
        )

    def test_detect_dialogue_language_uses_latest_user_request_then_default(self) -> None:
        self.assertEqual(
            detect_dialogue_language("", "请继续执行这个 loop"),
            {"source": "latest_user_request", "language": "zh-CN", "confidence": 0.8},
        )
        self.assertEqual(
            detect_dialogue_language("", "Please continue this loop"),
            {"source": "latest_user_request", "language": "en", "confidence": 0.8},
        )
        self.assertEqual(
            detect_dialogue_language("", ""),
            {"source": "default", "language": "en", "confidence": 0.0},
        )

    def test_preflight_rejects_unsupported_explicit_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            result = self.run_preflight(project_dir, "--dialogue-language", "zh-Hant")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unsupported dialogue language", result.stderr)

    def test_preflight_persists_latest_user_request_language_for_new_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            result = self.run_preflight(project_dir, "--latest-user-request", "请用中文继续执行")

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            state = json.loads((project_dir / ".yolo" / "state.json").read_text(encoding="utf-8"))
            expected = {"source": "latest_user_request", "language": "zh-CN", "confidence": 0.8}
            self.assertEqual(payload["dialogue_language"], expected)
            self.assertEqual(state["dialogue_language"], expected)
            self.assertIn("dialogue_language", state)
            self.assertIn("language", state["dialogue_language"])

    def test_preflight_rejects_explicit_language_drift_on_continue_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            result = self.run_preflight(project_dir, "--dialogue-language", "zh-CN")
            self.assertEqual(result.returncode, 0, result.stderr)

            drift = self.run_preflight(project_dir, "--dialogue-language", "en")
            self.assertNotEqual(drift.returncode, 0)
            self.assertIn("--dialogue-language does not match existing run bundle", drift.stderr)


if __name__ == "__main__":
    unittest.main()

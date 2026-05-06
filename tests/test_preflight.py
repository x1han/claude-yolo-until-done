from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_PATH = SKILL_ROOT / "workflow" / "preflight.py"
BOOTSTRAP_PATH = SKILL_ROOT / "workflow" / "bootstrap.py"


class PreflightTest(unittest.TestCase):
    def test_preflight_bootstraps_new_run_and_replaces_legacy_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            settings_path = project_dir / ".claude" / "settings.local.json"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n", encoding="utf-8")
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [
                                {
                                    "metadata": {
                                        "workflow": "claude-yolo-until-done",
                                        "hook_role": "SessionStart",
                                        "run_root": ".yolo",
                                        "hook_namespace": "claude-yolo",
                                    },
                                    "matcher": "startup|resume|compact",
                                    "hooks": [{"type": "command", "command": "legacy-start"}],
                                }
                            ],
                            "Stop": [
                                {
                                    "metadata": {
                                        "workflow": "claude-yolo-until-done",
                                        "hook_role": "Stop",
                                        "run_root": ".yolo",
                                        "hook_namespace": "claude-yolo",
                                    },
                                    "hooks": [{"type": "command", "command": "legacy-stop"}],
                                }
                            ],
                            "SessionEnd": [
                                {
                                    "metadata": {
                                        "workflow": "claude-yolo-until-done",
                                        "hook_role": "SessionEnd",
                                        "run_root": ".yolo",
                                        "hook_namespace": "claude-yolo",
                                    },
                                    "matcher": "stop",
                                    "hooks": [{"type": "command", "command": "legacy-end"}],
                                }
                            ],
                        }
                    },
                    indent=2,
                    ensure_ascii=True,
                )
                + "\n",
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["CLAUDE_CODE_ENTRYPOINT"] = "cli"
            env["CLAUDE_YOLO_PROCESS_CHAIN"] = "123 claude --dangerously-skip-permissions"

            result = subprocess.run(
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
                    "Bootstrap new run from approved plan.",
                    "--success-criterion",
                    "state.json is created for the new run.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["classification"], "new_run")
            self.assertEqual(payload["action"], "bootstrapped_and_installed")
            self.assertTrue((project_dir / ".yolo" / "state.json").exists())
            self.assertTrue((project_dir / ".yolo" / "trace.md").exists())

            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(sorted(settings["hooks"].keys()), ["SessionStart", "Stop", "UserPromptSubmit"])
            self.assertNotIn("SessionEnd", settings["hooks"])
            self.assertIn(".yolo", settings["claudeYoloUntilDone"]["runs"])

    def test_preflight_classifies_continue_run_when_bundle_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n", encoding="utf-8")

            bootstrap = subprocess.run(
                [
                    sys.executable,
                    str(BOOTSTRAP_PATH),
                    "--spec",
                    str(spec_path),
                    "--plan",
                    str(plan_path),
                    "--run-root",
                    str(run_root),
                    "--goal",
                    "Resume an existing run.",
                    "--success-criterion",
                    "bundle already exists.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            env = dict(os.environ)
            env["CLAUDE_CODE_ENTRYPOINT"] = "cli"
            env["CLAUDE_YOLO_PROCESS_CHAIN"] = "123 claude --dangerously-skip-permissions"

            result = subprocess.run(
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
                    "Resume an existing run.",
                    "--success-criterion",
                    "bundle already exists.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["classification"], "continue_run")
            self.assertEqual(payload["action"], "validated_and_installed")
            self.assertEqual(payload["state_status"], "active")

    def test_preflight_rejects_mixed_run_bundle_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n", encoding="utf-8")
            run_root.mkdir(parents=True, exist_ok=True)
            (run_root / "state.json").write_text("{}\n", encoding="utf-8")

            env = dict(os.environ)
            env["CLAUDE_CODE_ENTRYPOINT"] = "cli"
            env["CLAUDE_YOLO_PROCESS_CHAIN"] = "123 claude --dangerously-skip-permissions"

            result = subprocess.run(
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
                    "Reject mixed state.",
                    "--success-criterion",
                    "mixed bundle fails closed.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("mixed run bundle state", result.stderr.lower())

    def test_preflight_rejects_runtime_without_skip_permissions_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n", encoding="utf-8")

            env = dict(os.environ)
            env["CLAUDE_CODE_ENTRYPOINT"] = "cli"
            env["CLAUDE_YOLO_PROCESS_CHAIN"] = "123 claude"

            result = subprocess.run(
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
                    "Reject unsupported runtime.",
                    "--success-criterion",
                    "missing permission proof fails closed.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("dangerously-skip-permissions", result.stderr)


if __name__ == "__main__":
    unittest.main()

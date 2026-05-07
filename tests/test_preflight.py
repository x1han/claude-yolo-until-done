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


class ChecklistBootstrapTest(unittest.TestCase):
    def test_bootstrap_writes_master_checklist_and_task_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "spec.md"
            plan_path = root / "plan.md"
            run_root = root / ".yolo"
            spec_path.write_text(
                "# Spec\n\n## Scope\n- Only touch workflow files\n\n## Success Criteria\n- Stop blocks unfinished runs\n",
                encoding="utf-8",
            )
            plan_path.write_text(
                "# Plan\n\n### Task 1: Tighten stop hook\n- Preserve fail-closed behavior.\n\n### Task 2: Add orchestrator routing\n- Route follow-up work correctly.\n",
                encoding="utf-8",
            )

            result = subprocess.run(
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
                    "Ship orchestration.",
                    "--success-criterion",
                    "Stop blocks unfinished runs.",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            checklist = json.loads((run_root / "watcher_checklist.json").read_text(encoding="utf-8"))
            first_task = checklist["tasks"][0]
            second_task = checklist["tasks"][1]

            self.assertEqual(len(checklist["tasks"]), 2)
            self.assertEqual(state["task_title"], first_task["task_title"])
            self.assertEqual(state["task_inputs"], first_task)
            self.assertEqual(state["task_inputs"]["task_title"], "Tighten stop hook")
            self.assertEqual(state["task_inputs"]["plan_task_text"], "### Task 1: Tighten stop hook")
            self.assertEqual(second_task["task_title"], "Add orchestrator routing")
            self.assertEqual(second_task["plan_task_text"], "### Task 2: Add orchestrator routing")
            self.assertIn("Stop blocks unfinished runs", state["task_inputs"]["spec_excerpt"])

    def test_bootstrap_numbered_fallback_uses_task_section_not_earlier_overview_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "spec.md"
            plan_path = root / "plan.md"
            run_root = root / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text(
                "# Plan\n\n## Overview\n1. Gather prerequisites\n\n## Tasks\n1. Tighten stop hook\n2. Add orchestrator routing\n",
                encoding="utf-8",
            )

            result = subprocess.run(
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
                    "Ship orchestration.",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            checklist = json.loads((run_root / "watcher_checklist.json").read_text(encoding="utf-8"))
            self.assertEqual(checklist["tasks"][0]["task_title"], "Tighten stop hook")
            self.assertEqual(checklist["tasks"][0]["plan_task_text"], "1. Tighten stop hook")


class PreflightTest(unittest.TestCase):
    def test_preflight_bootstraps_new_run_and_replaces_legacy_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            settings_path = project_dir / ".claude" / "settings.local.json"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")
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
            self.assertEqual(payload["checklist_path"], str(project_dir / ".yolo" / "watcher_checklist.json"))
            self.assertTrue((project_dir / ".yolo" / "state.json").exists())
            self.assertTrue((project_dir / ".yolo" / "trace.md").exists())
            self.assertTrue((project_dir / ".yolo" / "watcher_checklist.json").exists())

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
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")

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

    def test_preflight_rejects_continue_run_without_checklist_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")

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
            (run_root / "watcher_checklist.json").unlink(missing_ok=True)

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

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("watcher_checklist.json", result.stderr)

    def test_preflight_validates_continue_run_against_current_checklist_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text(
                "# Plan\n\n### Task 1: Keep the run bundle consistent\n\n### Task 2: Advance the durable task state\n",
                encoding="utf-8",
            )

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

            checklist_path = run_root / "watcher_checklist.json"
            checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
            second_task = checklist["tasks"][1]
            state_path = run_root / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["task_id"] = second_task["task_id"]
            state["task_title"] = second_task["task_title"]
            state["task_inputs"] = second_task
            state_path.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

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

    def test_preflight_rejects_continue_run_when_spec_path_mismatches_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            other_spec_path = project_dir / "other-spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            other_spec_path.write_text("# Other spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")

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
                    str(other_spec_path),
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

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--spec", result.stderr)
            self.assertIn("spec_path='spec.md'", result.stderr)
            self.assertIn("provided='other-spec.md'", result.stderr)

    def test_preflight_rejects_mixed_run_bundle_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")
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
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")

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

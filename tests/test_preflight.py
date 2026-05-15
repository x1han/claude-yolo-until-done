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
    def test_bootstrap_writes_whole_plan_execution_unit_and_review_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "spec.md"
            plan_path = root / "plan.md"
            run_root = root / ".yolo"
            spec_path.write_text(
                "# Spec\n\n## Scope\n- Only touch workflow files\n\n## Success Criteria\n- Stop blocks unfinished runs\n",
                encoding="utf-8",
            )
            plan_body = "# Plan\n\n### Task 1: Tighten stop hook\n- Preserve fail-closed behavior.\n\n### Task 2: Add orchestrator routing\n- Route follow-up work correctly.\n"
            plan_path.write_text(plan_body, encoding="utf-8")

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
            execution_unit = checklist["tasks"][0]

            self.assertEqual(len(checklist["tasks"]), 1)
            self.assertEqual(state["task_title"], "Execute approved spec and plan")
            self.assertEqual(state["task_inputs"], execution_unit)
            self.assertEqual(state["task_inputs"]["task_title"], "Execute approved spec and plan")
            self.assertEqual(state["task_inputs"]["plan_task_text"], plan_body.strip())
            self.assertIn("### Task 1: Tighten stop hook", state["task_inputs"]["plan_task_text"])
            self.assertIn("### Task 2: Add orchestrator routing", state["task_inputs"]["plan_task_text"])
            self.assertEqual(checklist["plan_sections"][0]["task_title"], "Tighten stop hook")
            self.assertEqual(checklist["plan_sections"][1]["task_title"], "Add orchestrator routing")
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
            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(checklist["plan_sections"][0]["task_title"], "Tighten stop hook")
            self.assertEqual(checklist["plan_sections"][0]["plan_task_text"], "1. Tighten stop hook")
            self.assertIn("## Tasks", state["task_inputs"]["plan_task_text"])
            self.assertIn("2. Add orchestrator routing", state["task_inputs"]["plan_task_text"])


class PreflightTest(unittest.TestCase):
    def runtime_env(
        self,
        project_dir: Path,
        process_chain: str = "123 claude --dangerously-skip-permissions",
    ) -> dict[str, str]:
        env = dict(os.environ)
        env["CLAUDE_CODE_ENTRYPOINT"] = "cli"
        env.pop("CLAUDE_YOLO_PROCESS_CHAIN", None)
        bin_dir = project_dir / ".test-bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        ps_path = bin_dir / "ps"
        ps_path.write_text(
            "#!/usr/bin/env python3\n"
            "print('  PID  PPID ARGS')\n"
            f"print({'123 1 ' + process_chain!r})\n",
            encoding="utf-8",
        )
        ps_path.chmod(0o755)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
        return env

    def run_preflight(
        self,
        project_dir: Path,
        spec_path: Path,
        plan_path: Path,
        *,
        goal: str,
        success_criteria: list[str] | None = None,
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
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
            goal,
        ]
        for criterion in success_criteria or []:
            command.extend(["--success-criterion", criterion])
        command.extend(extra_args or [])
        return subprocess.run(
            command,
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
            env=self.runtime_env(project_dir) if env is None else env,
        )

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

            env = self.runtime_env(project_dir)

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

            state = json.loads((project_dir / ".yolo" / "state.json").read_text(encoding="utf-8"))
            self.assertTrue(state["hook_config_hash"])
            self.assertEqual(state["state_version"], 2)
            self.assertEqual(state["last_transition_actor"], "preflight")
            self.assertEqual(state["last_transition_id"], "preflight:persist_hook_config_hash:2")

    def test_preflight_defaults_new_run_to_acyclic_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")
            result = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Run once by default.",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((project_dir / ".yolo" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["mode"], "acyclic")
            self.assertEqual(
                state["loop"],
                {
                    "enabled": False,
                    "iteration": 1,
                    "max_iterations": None,
                    "stop_on_convergence": False,
                    "converged": False,
                    "stop_reason": "",
                    "iteration_evidence": [],
                    "latest_iteration_evidence": {},
                    "acceleration_review": {},
                },
            )

    def test_preflight_persists_loop_policy_and_evidence_defaults_for_new_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")
            result = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Run repeatedly until stop policy fires.",
                extra_args=["--mode", "loop", "--loop-max-iterations", "5", "--loop-stop-on-convergence"],
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            state = json.loads((project_dir / ".yolo" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["mode"], "loop")
            self.assertEqual(payload["loop"]["max_iterations"], 5)
            self.assertTrue(payload["loop"]["stop_on_convergence"])
            self.assertEqual(state["mode"], "loop")

    def test_preflight_defaults_convergence_loop_to_ten_iterations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")
            result = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Run repeatedly until convergence.",
                extra_args=["--mode", "loop", "--loop-stop-on-convergence"],
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            state = json.loads((project_dir / ".yolo" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["loop"]["max_iterations"], 10)
            self.assertTrue(payload["loop"]["stop_on_convergence"])
            self.assertEqual(state["loop"]["max_iterations"], 10)
            self.assertEqual(state["loop"]["iteration"], 1)
            self.assertTrue(state["loop"]["stop_on_convergence"])
            self.assertEqual(state["loop"]["stop_reason"], "")
            self.assertEqual(state["loop"]["iteration_evidence"], [])
            self.assertEqual(state["loop"]["latest_iteration_evidence"], {})
            self.assertEqual(state["loop"]["acceleration_review"], {})

    def test_preflight_persists_dialogue_language_defaults_for_new_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")
            result = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Run once with persisted dialogue-language metadata.",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((project_dir / ".yolo" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(
                state["dialogue_language"],
                {
                    "source": "default",
                    "language": "en",
                    "confidence": 0.0,
                },
            )

    def test_preflight_rejects_loop_policy_when_mode_is_acyclic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")
            result = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Invalid acyclic args.",
                extra_args=["--loop-max-iterations", "10"],
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Loop stop policy is only valid when mode is loop", result.stderr)

    def test_preflight_rejects_continue_run_when_mode_mismatches_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")
            first = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Create loop bundle.",
                extra_args=["--mode", "loop", "--loop-max-iterations", "2"],
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            second = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Try wrong mode.",
                extra_args=["--mode", "acyclic"],
            )

            self.assertNotEqual(second.returncode, 0)
            self.assertIn("Continue-run mismatch: --mode does not match existing run bundle", second.stderr)

    def test_preflight_rejects_continue_run_when_loop_policy_mismatches_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")
            first = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Create loop bundle.",
                extra_args=["--mode", "loop", "--loop-max-iterations", "2"],
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            second = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Try wrong loop policy.",
                extra_args=["--mode", "loop", "--loop-max-iterations", "3"],
            )

            self.assertNotEqual(second.returncode, 0)
            self.assertIn("Continue-run mismatch: loop policy does not match existing run bundle", second.stderr)

    def test_preflight_classifies_continue_run_when_bundle_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")

            initial = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
                success_criteria=["bundle already exists."],
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            env = self.runtime_env(project_dir)

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

    def test_preflight_classifies_continue_run_from_state_when_trace_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")

            initial = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
                success_criteria=["bundle already exists."],
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)
            (run_root / "trace.md").unlink(missing_ok=True)

            env = self.runtime_env(project_dir)

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

    def test_continue_run_rebuilds_missing_checklist_from_authoritative_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")

            initial = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
                success_criteria=["bundle already exists."],
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)
            checklist_path = run_root / "watcher_checklist.json"
            checklist_path.unlink(missing_ok=True)

            env = self.runtime_env(project_dir)

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
            rebuilt = json.loads(checklist_path.read_text(encoding="utf-8"))
            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(rebuilt["current_task"]["task_id"], state["task_id"])
            self.assertEqual(rebuilt["current_task"]["task_title"], state["task_title"])
            self.assertEqual(rebuilt["current_task"]["task_inputs"], state["task_inputs"])

    def test_continue_run_rebuilds_stale_checklist_from_authoritative_state(self) -> None:
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

            initial = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
                success_criteria=["bundle already exists."],
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            checklist_path = run_root / "watcher_checklist.json"
            checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
            checklist["current_task"] = {"task_id": "task-999", "task_title": "stale", "task_inputs": {"task_id": "task-999"}}
            checklist["tasks"][0]["task_title"] = "stale"
            checklist_path.write_text(json.dumps(checklist, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

            env = self.runtime_env(project_dir)

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
            rebuilt = json.loads(checklist_path.read_text(encoding="utf-8"))
            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(rebuilt["current_task"]["task_id"], state["task_id"])
            self.assertEqual(rebuilt["current_task"]["task_title"], state["task_title"])
            self.assertEqual(rebuilt["current_task"]["task_inputs"], state["task_inputs"])
            self.assertEqual(rebuilt["tasks"][0], state["task_inputs"])

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

            initial = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
                success_criteria=["bundle already exists."],
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            checklist_path = run_root / "watcher_checklist.json"
            state_path = run_root / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["task_inputs"]["checklist_items"].append("additional continue-run check")
            state_path.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

            env = self.runtime_env(project_dir)

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

            rebuilt = json.loads(checklist_path.read_text(encoding="utf-8"))
            persisted_state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(rebuilt["current_task"]["task_id"], state["task_id"])
            self.assertEqual(rebuilt["current_task"]["task_title"], state["task_title"])
            self.assertEqual(rebuilt["tasks"][0], state["task_inputs"])
            self.assertEqual(persisted_state["task_inputs"], state["task_inputs"])

    def test_preflight_rejects_inconsistent_authoritative_task_state_before_rebuilding_checklist(self) -> None:
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

            initial = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
                success_criteria=["bundle already exists."],
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            checklist_path = run_root / "watcher_checklist.json"
            state_path = run_root / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["task_id"] = "task-999"
            state["task_title"] = "Corrupted task title"
            state_path.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            checklist_path.unlink(missing_ok=True)

            env = self.runtime_env(project_dir)

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
            self.assertIn("state task_id does not match task_inputs.task_id", result.stderr)
            self.assertFalse(checklist_path.exists())

    def test_preflight_rejects_continue_run_when_authoritative_task_fields_are_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")

            initial = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
                success_criteria=["bundle already exists."],
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            state_path = run_root / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["task_id"] = ""
            state["task_inputs"]["task_id"] = ""
            state_path.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

            env = self.runtime_env(project_dir)

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
            self.assertIn("missing non-empty task_id", result.stderr)

    def test_continue_run_rebuilds_checklist_when_extra_stale_tasks_remain(self) -> None:
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

            initial = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
                success_criteria=["bundle already exists."],
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            checklist_path = run_root / "watcher_checklist.json"
            checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            checklist["current_task"] = {
                "task_id": state["task_id"],
                "task_title": state["task_title"],
                "task_inputs": state["task_inputs"],
            }
            checklist["tasks"][0] = state["task_inputs"]
            checklist["tasks"].append(
                {
                    "task_id": "task-999",
                    "task_title": "stale extra task",
                    "plan_task_text": "### Task 999: stale extra task",
                    "spec_excerpt": "# stale",
                    "checklist_items": ["reject drift"],
                }
            )
            checklist_path.write_text(json.dumps(checklist, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

            env = self.runtime_env(project_dir)

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
            rebuilt = json.loads(checklist_path.read_text(encoding="utf-8"))
            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(rebuilt["current_task"]["task_id"], state["task_id"])
            self.assertEqual(rebuilt["tasks"], [state["task_inputs"]])

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

            initial = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
                success_criteria=["bundle already exists."],
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            env = self.runtime_env(project_dir)

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

    def test_preflight_rejects_trace_without_authoritative_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")
            run_root.mkdir(parents=True, exist_ok=True)
            (run_root / "trace.md").write_text("# trace\n", encoding="utf-8")

            env = self.runtime_env(project_dir)

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
            self.assertIn("trace.md exists without authoritative state.json", result.stderr)

    def test_continue_run_requeues_expired_dispatch_claim_after_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")

            initial = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            state_path = run_root / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["requested_role"] = "watcher"
            state["next_action"] = "watcher_review"
            state["dispatch_status"] = "running"
            state["dispatch_intent"] = {"role": "watcher", "action": "watcher_review"}
            state["dispatch_claim"] = {
                "owner": "worker-1",
                "claimed_at": "2026-05-08T00:00:00+00:00",
                "lease_expires_at": "2026-05-08T00:00:01+00:00",
            }
            state["last_dispatch"] = {
                "role": "watcher",
                "task_id": state["task_id"],
                "gate_id": state["gate_id"],
                "next_action": "watcher_review",
                "dispatched_at": "2026-05-08T00:00:00+00:00",
                "task_packet": {"plan_task_text": "### Task 1: Keep the run bundle consistent"},
            }
            state["state_version"] = 4
            state_path.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

            result = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            updated_state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["classification"], "continue_run")
            self.assertEqual(payload["dispatch_recovery"]["result"], "requeued")
            self.assertEqual(payload["dispatch_recovery"]["role"], "watcher")
            self.assertEqual(updated_state["state_version"], 5)
            self.assertEqual(updated_state["last_transition_actor"], "preflight")

            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["requested_role"], "watcher")
            self.assertEqual(persisted["dispatch_status"], "pending")
            self.assertEqual(persisted["dispatch_intent"], {"role": "watcher", "action": "watcher_review"})
            self.assertEqual(persisted["dispatch_claim"], {})
            self.assertEqual(persisted["last_dispatch"], {})
            trace = (run_root / "trace.md").read_text(encoding="utf-8")
            self.assertIn("preflight recovered expired dispatch claim", trace)

    def test_preflight_rejects_continue_run_when_installed_hook_hash_drifted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            settings_path = project_dir / ".claude" / "settings.local.json"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")

            initial = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            env = self.runtime_env(project_dir)

            first_run = subprocess.run(
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
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(first_run.returncode, 0, first_run.stderr)

            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            settings["hooks"]["Stop"][0]["hooks"][0]["command"] = "tampered-stop"
            settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

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
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("hook_config_hash", result.stderr)

    def test_preflight_rejects_continue_run_when_hook_config_hash_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            settings_path = project_dir / ".claude" / "settings.local.json"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")

            initial = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            env = self.runtime_env(project_dir)

            first_run = subprocess.run(
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
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(first_run.returncode, 0, first_run.stderr)

            state_path = run_root / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["hook_config_hash"] = ""
            state_path.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            settings.pop("hooks", None)
            settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

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
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing hook_config_hash", result.stderr)

    def test_preflight_warns_runtime_without_skip_permissions_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")

            env = self.runtime_env(project_dir, "123 claude")

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
                    "Warn about unsupported runtime.",
                    "--success-criterion",
                    "missing permission proof is reported as warning.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["skip_permissions_verified"])
            self.assertIn("dangerously-skip-permissions", payload["runtime_warnings"][0])

    def test_preflight_ignores_spoofed_process_chain_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")

            env = self.runtime_env(project_dir, "123 claude")
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
                    "Ignore spoofed runtime proof.",
                    "--success-criterion",
                    "env override cannot fake permission proof.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["skip_permissions_verified"])
            self.assertIn("dangerously-skip-permissions", payload["runtime_warnings"][0])

    def test_preflight_rejects_continue_run_when_state_version_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Keep the run bundle consistent\n", encoding="utf-8")

            initial = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            state_path = run_root / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state.pop("state_version")
            state_path.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

            result = self.run_preflight(
                project_dir,
                spec_path,
                plan_path,
                goal="Resume an existing run.",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("state_version", result.stderr)

    def test_preflight_explicit_external_spec_plan_still_bootstraps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec = project_dir / "external-spec.md"
            plan = project_dir / "external-plan.md"
            spec.write_text("# Spec\n\nStatus: approved\n\n## Acceptance Criteria\n- Review passes.\n", encoding="utf-8")
            plan.write_text(
                "# Plan\n\nStatus: approved\n\n## Steps\n\n### Task 1: Review changes\nInspect changes.\n\nVerify: reviewer records evidence.\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PREFLIGHT_PATH),
                    "--project-dir",
                    str(project_dir),
                    "--spec",
                    str(spec),
                    "--plan",
                    str(plan),
                    "--run-root",
                    ".yolo",
                    "--goal",
                    "Run review.",
                    "--success-criterion",
                    "review passes",
                ],
                cwd=SKILL_ROOT,
                capture_output=True,
                text=True,
                check=False,
                env=self.runtime_env(project_dir),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((project_dir / ".yolo" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["spec_path"], "external-spec.md")
            self.assertEqual(state["plan_path"], "external-plan.md")

    def test_preflight_rejects_only_spec_without_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec = project_dir / "spec.md"
            spec.write_text("# Spec\n\nStatus: approved\n\n## Acceptance Criteria\n- Review passes.\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(PREFLIGHT_PATH),
                    "--project-dir",
                    str(project_dir),
                    "--spec",
                    str(spec),
                    "--goal",
                    "Run review.",
                    "--success-criterion",
                    "review passes",
                ],
                cwd=SKILL_ROOT,
                capture_output=True,
                text=True,
                check=False,
                env=self.runtime_env(project_dir),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--spec and --plan must be provided together", result.stderr)


if __name__ == "__main__":
    unittest.main()

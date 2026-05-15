from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = SKILL_ROOT / "workflow" / "bootstrap.py"
sys.path.insert(0, str(SKILL_ROOT / "workflow"))

from bootstrap import bootstrap_run


class BootstrapLightweightBundleTest(unittest.TestCase):
    def run_bootstrap(self, *extra_args: str) -> dict:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        project_dir = Path(temp_dir.name)
        spec_path = project_dir / "spec.md"
        plan_path = project_dir / "plan.md"
        run_root = project_dir / "artifacts" / "run-001"

        spec_path.write_text("# Spec\n", encoding="utf-8")
        plan_path.write_text(
            "# Plan\n\n### Task 1: Ship the lightweight run bundle\n\n### Task 2: Verify the full bundle\n",
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
                "Ship the lightweight run bundle.",
                "--success-criterion",
                "state.json captures the authoritative run state.",
                "--success-criterion",
                "trace.md records the bootstrap handoff.",
                *extra_args,
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_bootstrap_rejects_headless_claude_print_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"

            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n", encoding="utf-8")

            env = dict(os.environ)
            env["CLAUDECODE"] = "1"
            env["CLAUDE_CODE_ENTRYPOINT"] = "print"

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
                    "Ship the lightweight run bundle.",
                    "--success-criterion",
                    "state.json captures the authoritative run state.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("headless claude -p", result.stderr.lower())
            self.assertFalse((run_root / "state.json").exists())
            self.assertFalse((run_root / "trace.md").exists())

    def test_bootstrap_run_persists_loop_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Loop\n- Verify: done\n", encoding="utf-8")
            run_root = project_dir / ".yolo"

            bootstrap_run(
                spec_path=spec_path,
                plan_path=plan_path,
                run_root=run_root,
                goal="Loop bootstrap.",
                success_criteria=["Loop policy persisted."],
                repo_root=project_dir,
                mode="loop",
                loop_max_iterations=3,
                loop_stop_on_convergence=True,
            )

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["mode"], "loop")
            self.assertEqual(state["loop"]["max_iterations"], 3)
            self.assertTrue(state["loop"]["stop_on_convergence"])

    def test_bootstrap_defaults_allow_need_human_true(self) -> None:
        result = self.run_bootstrap()
        state = json.loads((Path(result["run_root"]) / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(state["allow_need_human"])

    def test_bootstrap_persists_explicit_no_human_override(self) -> None:
        result = self.run_bootstrap("--disallow-need-human")
        state = json.loads((Path(result["run_root"]) / "state.json").read_text(encoding="utf-8"))
        self.assertFalse(state["allow_need_human"])

    def test_bootstrap_seeds_authoritative_runtime_fields(self) -> None:
        result = self.run_bootstrap()
        state = json.loads((Path(result["run_root"]) / "state.json").read_text(encoding="utf-8"))

        self.assertEqual(state["status"], "active")
        self.assertEqual(state["state_version"], 1)
        self.assertEqual(state["current_task"]["task_id"], state["task_id"])
        self.assertEqual(state["current_task"]["task_title"], state["task_title"])
        self.assertEqual(state["current_task"]["task_inputs"], state["task_inputs"])
        self.assertEqual(state["next_action"], "worker_update")
        self.assertEqual(state["dispatch_status"], "pending")
        self.assertEqual(state["dispatch_intent"], {"role": "worker", "action": "worker_update"})
        self.assertEqual(state["last_transition_id"], "")
        self.assertEqual(state["last_transition_actor"], "")
        self.assertEqual(state["hook_config_hash"], "")
        self.assertEqual(state["task_packet_hash"], "")
        self.assertEqual(state["certification_hash"], "")
        self.assertEqual(state["certification"], {})
        self.assertEqual(state["retry_budget"], {"worker": 0, "helper": 0, "backoff_until": ""})
        self.assertEqual(state["task_goal"], state["goal"])

    def test_bootstrap_writes_agent_session_registry_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"
            spec_path.write_text("# Spec\n", encoding="utf-8")
            plan_path.write_text("# Plan\n\n### Task 1: Ship the lightweight run bundle\n", encoding="utf-8")

            result = bootstrap_run(
                spec_path=spec_path,
                plan_path=plan_path,
                run_root=run_root,
                goal="Ship the lightweight run bundle.",
                success_criteria=["state.json captures the authoritative run state."],
                repo_root=project_dir,
            )

            self.assertEqual(result["run_root"], str(run_root.resolve()))
            registry_path = run_root / "agent_sessions.json"
            self.assertTrue(registry_path.exists())
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(set(registry["roles"]), {"worker", "watcher", "helper", "muse", "logos"})
            for role in registry["roles"]:
                self.assertTrue((run_root / "agents" / f"{role}-log.md").exists())
                self.assertTrue((run_root / "agents" / f"{role}-summary.md").exists())
                memory_path = project_dir / ".claude" / "agent-memory" / role / "MEMORY.md"
                self.assertTrue(memory_path.exists())
                body = memory_path.read_text(encoding="utf-8")
                self.assertIn(f"# {role} memory", body)
                self.assertIn("## Reliable Verification", body)

    def test_bootstrap_writes_lightweight_run_bundle(self) -> None:
        result = self.run_bootstrap()
        run_root = Path(result["run_root"])

        state_path = run_root / "state.json"
        trace_path = run_root / "trace.md"
        checklist_path = run_root / "watcher_checklist.json"
        self.assertTrue(state_path.exists())
        self.assertTrue(trace_path.exists())
        self.assertTrue(checklist_path.exists())

        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["goal"], "Ship the lightweight run bundle.")
        self.assertEqual(
            state["success_criteria"],
            [
                "state.json captures the authoritative run state.",
                "trace.md records the bootstrap handoff.",
            ],
        )
        self.assertEqual(state["status"], "active")
        self.assertEqual(state["owner"], "worker")
        self.assertEqual(state["next_action"], "worker_update")
        self.assertFalse(state["cleanup_required"])
        self.assertTrue(state["allow_need_human"])
        self.assertEqual(state["plan_path"], "plan.md")
        self.assertEqual(state["spec_path"], "spec.md")
        self.assertEqual(state["task_id"], "task-001")
        self.assertEqual(state["task_title"], "Execute approved spec and plan")
        self.assertEqual(state["task_inputs"]["task_id"], "task-001")
        self.assertEqual(state["task_inputs"]["task_title"], "Execute approved spec and plan")
        self.assertIn("### Task 1: Ship the lightweight run bundle", state["task_inputs"]["plan_task_text"])
        self.assertIn("### Task 2: Verify the full bundle", state["task_inputs"]["plan_task_text"])
        self.assertEqual(state["worker_claim"], "")
        self.assertEqual(state["files_changed"], [])
        self.assertEqual(state["verification_command"], "")
        self.assertEqual(state["verification_result"], "")
        self.assertEqual(state["submitted_at"], "")
        self.assertEqual(state["review"], {})
        self.assertEqual(state["reviewed_at"], "")
        self.assertIn("updated_at", state)

        checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
        self.assertEqual(len(checklist["tasks"]), 1)
        self.assertEqual(checklist["tasks"][0]["task_title"], "Execute approved spec and plan")
        self.assertEqual(checklist["plan_sections"][0]["task_title"], "Ship the lightweight run bundle")
        self.assertEqual(checklist["plan_sections"][1]["task_title"], "Verify the full bundle")

        trace = trace_path.read_text(encoding="utf-8")
        self.assertIn("# Goal", trace)
        self.assertIn("Ship the lightweight run bundle.", trace)
        self.assertIn("## Success Criteria", trace)
        self.assertIn("- state.json captures the authoritative run state.", trace)
        self.assertIn("- trace.md records the bootstrap handoff.", trace)
        self.assertIn("bootstrap", trace.lower())

        for obsolete_name in [
            "runtime_context.json",
            "run_state.json",
            "gates.json",
            "checkoffs.json",
            "workflow_manifest.json",
            "report.md",
            "resume.md",
        ]:
            self.assertFalse((run_root / obsolete_name).exists(), obsolete_name)


if __name__ == "__main__":
    unittest.main()

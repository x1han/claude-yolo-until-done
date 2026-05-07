from __future__ import annotations

import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

import human_handoff

HUMAN_HANDOFF_PATH = SKILL_ROOT / "workflow" / "human_handoff.py"


class HumanHandoffCliTest(unittest.TestCase):
    def write_run_state(self, run_root: Path, **overrides: object) -> None:
        state = {
            "status": "active",
            "allow_need_human": True,
            "owner": "human",
            "next_action": "human_handoff",
            "requested_role": "human",
            "dispatch_status": "idle",
            "last_dispatch": {},
            "task_id": "task-001",
            "task_title": "Current task",
            "task_inputs": {"task_id": "task-001", "task_title": "Current task"},
            "task_handoff_notes": [],
            "gate_id": "gate-task-001",
            "gate_attempt": 3,
            "gate_max_attempts": 5,
            "gate_reason": "stop_gate_limit",
            "worker_request": "need_human",
            "worker_question": "Need product guidance.",
            "blocked_for_human": True,
            "human_handoff": {},
            "verification_command": "python -m unittest source.tests.test_human_handoff -v",
            "verification_result": "waiting for guidance",
            "updated_at": "2026-05-08T00:00:00+00:00",
        }
        state.update(overrides)
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "state.json").write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        (run_root / "trace.md").write_text("# trace\n", encoding="utf-8")

    def load_state(self, run_root: Path) -> dict:
        return json.loads((run_root / "state.json").read_text(encoding="utf-8"))

    def run_handoff(self, run_root: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(HUMAN_HANDOFF_PATH),
                "--run-root",
                str(run_root),
                *extra_args,
            ],
            cwd=SKILL_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def run_handoff_expect_failure(self, run_root: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
        result = self.run_handoff(run_root, *extra_args)
        self.assertNotEqual(result.returncode, 0)
        return result

    def test_continue_discussing_persists_summary_without_resuming(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(run_root)

            result = self.run_handoff(
                run_root,
                "--summary",
                "Only update steps 1-2.",
                "--resume-ready",
                "false",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            state = self.load_state(run_root)
            self.assertEqual(payload["result"], "waiting_for_human")
            self.assertFalse(payload["resume_ready"])
            self.assertEqual(state["owner"], "human")
            self.assertTrue(state["blocked_for_human"])
            self.assertEqual(
                state["human_handoff"],
                {"summary": "Only update steps 1-2.", "resume_ready": False},
            )
            self.assertEqual(state["task_handoff_notes"], [])
            self.assertEqual(state["task_id"], "task-001")
            self.assertEqual(state["last_dispatch"], {})

    def test_explicit_resume_appends_summary_and_redispatches_same_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(run_root)

            result = self.run_handoff(
                run_root,
                "--summary",
                "Only update steps 1-2.",
                "--resume-ready",
                "true",
                "--resume-now",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            state = self.load_state(run_root)
            self.assertEqual(payload["result"], "resumed")
            self.assertFalse(state["blocked_for_human"])
            self.assertEqual(state["worker_request"], "")
            self.assertEqual(state["worker_question"], "")
            self.assertEqual(state["owner"], "worker")
            self.assertEqual(state["requested_role"], "worker")
            self.assertEqual(state["task_id"], "task-001")
            self.assertEqual(state["task_inputs"]["task_id"], "task-001")
            self.assertEqual(state["gate_id"], "gate-task-001")
            self.assertEqual(state["gate_attempt"], 0)
            self.assertEqual(state["task_handoff_notes"], ["Only update steps 1-2."])
            self.assertEqual(state["human_handoff"], {})
            self.assertEqual(state["dispatch_status"], "dispatched")
            self.assertEqual(state["last_dispatch"]["role"], "worker")

    def test_invalid_explicit_resume_is_side_effect_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(run_root)
            before = self.load_state(run_root)

            result = self.run_handoff(
                run_root,
                "--summary",
                "Only update steps 1-2.",
                "--resume-ready",
                "false",
                "--resume-now",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Explicit resume requires resume_ready=true.", result.stderr)
            after = self.load_state(run_root)
            self.assertEqual(after, before)

    def test_human_handoff_cli_rejects_runs_that_disable_need_human(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(run_root, allow_need_human=False)

            result = self.run_handoff_expect_failure(
                run_root,
                "--summary",
                "Only update steps 1-2.",
                "--resume-ready",
                "false",
            )

            self.assertIn("Human handoff is disabled for this run.", result.stderr)

    def test_resume_after_human_signature_has_no_checklist_parameter(self) -> None:
        parameters = inspect.signature(human_handoff.resume_after_human).parameters

        self.assertNotIn("checklist", parameters)


if __name__ == "__main__":
    unittest.main()

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
            "state_version": 1,
            "gate_attempt": 3,
            "gate_max_attempts": 5,
            "gate_reason": "stop_gate_limit",
            "worker_request": "need_human",
            "worker_question": "Need product guidance.",
            "blocked_for_human": True,
            "human_handoff": {},
            "resume_target": {"role": "worker", "action": "worker_update"},
            "verification_command": "python -m unittest source.tests.test_human_handoff -v",
            "verification_result": "waiting for guidance",
            "retry_budget": {"worker": 0, "helper": 0, "backoff_until": ""},
            "updated_at": "2026-05-08T00:00:00+00:00",
        }
        state.update(overrides)
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "state.json").write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        (run_root / "trace.md").write_text("# trace\n", encoding="utf-8")

    def load_state(self, run_root: Path) -> dict:
        return json.loads((run_root / "state.json").read_text(encoding="utf-8"))

    def run_handoff(self, run_root: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
        args = list(extra_args)
        if "--expected-version" not in args:
            args.extend(["--expected-version", str(self.load_state(run_root)["state_version"])])
        return subprocess.run(
            [
                sys.executable,
                str(HUMAN_HANDOFF_PATH),
                "--run-root",
                str(run_root),
                *args,
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
                {"summary": "Only update steps 1-2.", "resume_ready": False, "actor": "human"},
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
            self.assertEqual(state["dispatch_status"], "running")
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

    def test_continue_discussing_requires_fresh_expected_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(run_root, state_version=3)
            before = self.load_state(run_root)

            result = self.run_handoff(
                run_root,
                "--summary",
                "Only update steps 1-2.",
                "--resume-ready",
                "false",
                "--expected-version",
                "2",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Stale state version", result.stderr)
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

    def test_human_handoff_cli_accepts_stop_gate_limit_state_without_worker_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(
                run_root,
                worker_request="",
                worker_question="",
                human_handoff={"reason": "stop_gate_limit"},
            )

            result = self.run_handoff(
                run_root,
                "--summary",
                "Resume with a narrower scope.",
                "--resume-ready",
                "true",
                "--resume-now",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            state = self.load_state(run_root)
            self.assertEqual(json.loads(result.stdout)["result"], "resumed")
            self.assertFalse(state["blocked_for_human"])
            self.assertEqual(state["owner"], "worker")
            self.assertEqual(state["dispatch_status"], "running")
            self.assertEqual(state["task_handoff_notes"], ["Resume with a narrower scope."])

    def test_human_handoff_resume_uses_persisted_resume_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(
                run_root,
                worker_request="",
                worker_question="",
                human_handoff={"reason": "stop_gate_limit"},
                resume_target={"role": "worker", "action": "worker_rework"},
            )

            result = self.run_handoff(
                run_root,
                "--summary",
                "Resume only the rework step.",
                "--resume-ready",
                "true",
                "--resume-now",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            state = self.load_state(run_root)
            self.assertEqual(json.loads(result.stdout)["result"], "resumed")
            self.assertEqual(state["owner"], "worker")
            self.assertEqual(state["next_action"], "worker_rework")
            self.assertEqual(state["requested_role"], "worker")
            self.assertEqual(state["last_dispatch"]["next_action"], "worker_rework")

    def test_human_handoff_cli_accepts_worker_stall_retry_limit_state_without_worker_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(
                run_root,
                worker_request="",
                worker_question="",
                human_handoff={"reason": "worker_stalled_retry_limit"},
            )

            result = self.run_handoff(
                run_root,
                "--summary",
                "Resume after worker retry exhaustion.",
                "--resume-ready",
                "true",
                "--resume-now",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            state = self.load_state(run_root)
            self.assertEqual(json.loads(result.stdout)["result"], "resumed")
            self.assertFalse(state["blocked_for_human"])
            self.assertEqual(state["owner"], "worker")
            self.assertEqual(state["dispatch_status"], "running")
            self.assertEqual(state["task_handoff_notes"], ["Resume after worker retry exhaustion."])

    def test_human_handoff_cli_accepts_worker_stall_supervision_invalid_state_without_worker_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(
                run_root,
                worker_request="",
                worker_question="",
                human_handoff={"reason": "worker_stall_supervision_invalid"},
            )

            result = self.run_handoff(
                run_root,
                "--summary",
                "Resume after repairing supervision metadata.",
                "--resume-ready",
                "false",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            state = self.load_state(run_root)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["result"], "waiting_for_human")
            self.assertTrue(state["blocked_for_human"])
            self.assertEqual(state["owner"], "human")
            self.assertEqual(state["human_handoff"]["reason"], "worker_stall_supervision_invalid")
            self.assertEqual(state["human_handoff"]["summary"], "Resume after repairing supervision metadata.")

    def test_true_human_block_resume_rejects_missing_resume_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(
                run_root,
                worker_request="",
                worker_question="",
                human_handoff={"reason": "stop_gate_limit"},
                resume_target={},
            )
            before = self.load_state(run_root)

            result = self.run_handoff(
                run_root,
                "--summary",
                "Resume only the rework step.",
                "--resume-ready",
                "true",
                "--resume-now",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("resume_target", result.stderr)
            after = self.load_state(run_root)
            self.assertEqual(after, before)

    def test_true_human_block_resume_rejects_malformed_resume_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(
                run_root,
                worker_request="",
                worker_question="",
                human_handoff={"reason": "stop_gate_limit"},
                resume_target={"role": "worker", "action": ""},
            )
            before = self.load_state(run_root)

            result = self.run_handoff(
                run_root,
                "--summary",
                "Resume only the rework step.",
                "--resume-ready",
                "true",
                "--resume-now",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("resume_target", result.stderr)
            after = self.load_state(run_root)
            self.assertEqual(after, before)

    def test_helper_cannot_explicitly_resume_true_human_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(run_root)
            before = self.load_state(run_root)

            result = self.run_handoff(
                run_root,
                "--summary",
                "Try only steps 1-2 first.",
                "--resume-ready",
                "true",
                "--resume-now",
                "--actor",
                "helper",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Helper cannot resume a run that is blocked for human guidance.", result.stderr)
            after = self.load_state(run_root)
            self.assertEqual(after, before)

    def test_helper_block_for_human_preserves_stop_gate_limit_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(
                run_root,
                worker_request="",
                worker_question="",
                human_handoff={"reason": "stop_gate_limit"},
            )

            result = self.run_handoff(
                run_root,
                "--summary",
                "I cannot resolve this without a product decision.",
                "--resume-ready",
                "false",
                "--actor",
                "helper",
                "--helper-outcome",
                "block_for_human",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            state = self.load_state(run_root)
            self.assertEqual(payload["result"], "blocked_for_human")
            self.assertEqual(state["retry_budget"]["helper"], 1)
            self.assertTrue(state["blocked_for_human"])
            self.assertEqual(state["owner"], "human")
            self.assertEqual(state["next_action"], "human_handoff")
            self.assertEqual(state["human_handoff"]["reason"], "stop_gate_limit")
            self.assertEqual(state["human_handoff"]["helper_outcome"], "block_for_human")

    def test_resume_after_human_resets_stall_retry_count(self) -> None:
        state = {
            "task_id": "task-001",
            "gate_id": "gate-task-001",
            "blocked_for_human": True,
            "human_handoff": {"reason": "worker_stalled_retry_limit"},
            "requested_role": "human",
            "resume_target": {"role": "worker", "action": "worker_update"},
            "supervision": {
                "last_token_io_at": "",
                "last_progress_at": "",
                "stall_timeout_seconds": 600,
                "retry_limit": 3,
                "retry_count": 3,
                "last_recovery_at": "2026-05-10T00:00:00+00:00",
                "last_recovery_reason": "worker_stalled_retry_limit",
            },
        }

        resumed = human_handoff.resume_after_human(state, "Try again with a narrower scope.")

        self.assertEqual(resumed["supervision"]["retry_count"], 0)
        self.assertEqual(resumed["supervision"]["last_recovery_reason"], "")

    def test_resume_after_human_signature_has_no_checklist_parameter(self) -> None:
        parameters = inspect.signature(human_handoff.resume_after_human).parameters

        self.assertNotIn("checklist", parameters)


if __name__ == "__main__":
    unittest.main()

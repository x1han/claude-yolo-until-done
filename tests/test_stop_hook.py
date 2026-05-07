from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from claude_hook_bridge import stop


class StopHookTest(unittest.TestCase):
    def make_state(self, **overrides: object) -> dict:
        state = {
            "goal": "Fix it.",
            "success_criteria": ["It works."],
            "status": "active",
            "cleanup_required": False,
            "worker_claim": "",
            "files_changed": [],
            "verification_command": "",
            "verification_result": "",
            "submitted_at": "",
            "review": {},
            "reviewed_at": "",
            "owner": "worker",
            "next_action": "worker_update",
            "task_id": "task-001",
            "gate_id": "gate-task-001",
            "gate_attempt": 0,
            "gate_max_attempts": 5,
            "requested_role": "worker",
            "dispatch_status": "idle",
            "blocked_for_human": False,
            "plan_path": "docs/plan.md",
            "spec_path": "docs/spec.md",
            "updated_at": "2026-05-01T00:00:00Z",
        }
        state.update(overrides)
        return state

    def write_run_bundle(
        self,
        run_root: Path,
        *,
        state: dict | None = None,
        write_state_file: bool = True,
        write_trace_file: bool = True,
    ) -> None:
        run_root.mkdir(parents=True, exist_ok=True)
        if write_state_file:
            (run_root / "state.json").write_text(
                json.dumps(state or self.make_state()) + "\n",
                encoding="utf-8",
            )
        if write_trace_file:
            (run_root / "trace.md").write_text("- 2026-05-01T00:00:00Z bootstrap\n", encoding="utf-8")

    def capture_stop(self, project_dir: Path, run_root: Path, hook_input: dict | None = None) -> tuple[int, dict | None]:
        with io.StringIO() as stream, contextlib.redirect_stdout(stream):
            decision = stop(project_dir, run_root, hook_input or {})
            raw = stream.getvalue().strip()
        return decision, json.loads(raw) if raw else None

    def test_stop_allows_when_no_run_root_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            decision, payload = self.capture_stop(project_dir, project_dir / ".yolo")

        self.assertEqual(decision, 0)
        self.assertIsNone(payload)

    def test_stop_blocks_broken_run_root_even_with_stop_hook_active_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(run_root, write_state_file=False)

            decision, payload = self.capture_stop(project_dir, run_root, {"stop_hook_active": True})

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("state.json is missing", payload["reason"])

    def test_stop_hook_active_flag_does_not_bypass_active_run_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(run_root, state=self.make_state(status="active", gate_attempt=0))

            decision, payload = self.capture_stop(project_dir, run_root, {"stop_hook_active": True})
            updated_state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("Workflow status is active", payload["reason"])
        self.assertEqual(payload["orchestration"]["result"], "dispatched")
        self.assertEqual(payload["orchestration"]["role"], "worker")
        self.assertEqual(updated_state["gate_attempt"], 1)
        self.assertEqual(updated_state["dispatch_status"], "dispatched")
        self.assertEqual(updated_state["last_dispatch"]["role"], "worker")

    def test_stop_blocks_incomplete_workflow_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            for status in ("active", "needs_review", "rework_required", "approved"):
                self.write_run_bundle(run_root, state=self.make_state(status=status, gate_attempt=0))

                decision, payload = self.capture_stop(project_dir, run_root)

                self.assertEqual(decision, 0)
                self.assertEqual(payload["decision"], "block")
                self.assertIn(status, payload["reason"])

    def test_stop_persists_gate_attempt_only_for_worker_return_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(run_root, state=self.make_state(gate_attempt=1, gate_max_attempts=3))

            decision, payload = self.capture_stop(project_dir, run_root)
            updated_state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("Worker return stop gate attempt 2/3", payload["reason"])
        self.assertEqual(updated_state["gate_attempt"], 2)
        self.assertEqual(updated_state["gate_reason"], "worker_return_stop_block")
        self.assertFalse(updated_state["blocked_for_human"])
        self.assertEqual(updated_state["owner"], "worker")

    def test_stop_does_not_persist_gate_attempt_for_helper_watcher_or_human_states(self) -> None:
        cases = (
            self.make_state(gate_attempt=2, requested_role="helper", next_action="helper_reply"),
            self.make_state(status="needs_review", gate_attempt=2, owner="watcher", next_action="watcher_review"),
            self.make_state(gate_attempt=2, owner="human", requested_role="human", next_action="human_handoff", blocked_for_human=True),
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            for state in cases:
                self.write_run_bundle(run_root, state=state)

                decision, payload = self.capture_stop(project_dir, run_root)
                updated_state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))

                self.assertEqual(decision, 0)
                self.assertEqual(payload["decision"], "block")
                self.assertEqual(updated_state["gate_attempt"], 2)

    def test_stop_marks_human_handoff_when_worker_return_hits_gate_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(run_root, state=self.make_state(gate_attempt=4, gate_max_attempts=5))

            decision, payload = self.capture_stop(project_dir, run_root)
            updated_state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("requires human handoff", payload["reason"])
        self.assertEqual(payload["orchestration"]["result"], "dispatched")
        self.assertEqual(payload["orchestration"]["role"], "human")
        self.assertEqual(updated_state["gate_attempt"], 5)
        self.assertTrue(updated_state["blocked_for_human"])
        self.assertEqual(updated_state["owner"], "human")
        self.assertEqual(updated_state["next_action"], "human_handoff")
        self.assertEqual(updated_state["requested_role"], "human")
        self.assertEqual(updated_state["dispatch_status"], "dispatched")
        self.assertEqual(updated_state["last_dispatch"]["role"], "human")
        self.assertEqual(updated_state["human_handoff"], {"reason": "stop_gate_limit"})

    def test_stop_blocks_with_human_handoff_reason_after_limit_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    gate_attempt=5,
                    gate_max_attempts=5,
                    owner="human",
                    requested_role="human",
                    next_action="human_handoff",
                    blocked_for_human=True,
                    human_handoff={"reason": "stop_gate_limit"},
                ),
            )

            decision, payload = self.capture_stop(project_dir, run_root)
            updated_state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("stop gate limit", payload["reason"])
        self.assertEqual(updated_state["gate_attempt"], 5)
        self.assertTrue(updated_state["blocked_for_human"])

    def test_stop_blocks_when_gate_counters_are_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(run_root, state=self.make_state(gate_attempt="abc"))

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("gate counters are unreadable", payload["reason"])

    def test_stop_blocks_when_state_is_missing_required_gate_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            broken_state = self.make_state()
            broken_state.pop("requested_role")
            self.write_run_bundle(run_root, state=broken_state)

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("missing required field 'requested_role'", payload["reason"])

    def test_stop_blocks_when_cleanup_is_still_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    status="complete",
                    cleanup_required=True,
                    worker_claim="Updated src/app.py.",
                    files_changed=["src/app.py"],
                    verification_command="pytest -q",
                    verification_result="passed: 1 passed",
                    submitted_at="2026-05-01T00:00:00Z",
                    review={
                        "verdict": "approve",
                        "scope_checked": [],
                        "problems": [],
                        "required_rework": [],
                        "acceptance_basis": ["ok"],
                    },
                    reviewed_at="2026-05-01T00:01:00Z",
                    owner="watcher",
                    next_action="cleanup",
                ),
            )

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("cleanup", payload["reason"])

    def test_stop_blocks_invalid_complete_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    status="complete",
                    worker_claim="Updated src/app.py.",
                    files_changed=["src/app.py"],
                    verification_command="pytest -q",
                    verification_result="passed: 1 passed",
                    submitted_at="2026-05-01T00:00:00Z",
                    review={
                        "verdict": "rework_required",
                        "scope_checked": [],
                        "problems": ["x"],
                        "required_rework": ["y"],
                        "acceptance_basis": [],
                    },
                    reviewed_at="2026-05-01T00:01:00Z",
                    owner="watcher",
                    next_action="complete",
                ),
            )

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("completion validation", payload["reason"])


if __name__ == "__main__":
    unittest.main()

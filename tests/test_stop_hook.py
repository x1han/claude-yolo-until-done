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

from claude_hook_bridge import session_start, stop
from lifecycle import build_completion_certification, compute_certification_hash


class StopHookTest(unittest.TestCase):
    def completion_certification(self, state: dict | None = None) -> dict:
        source_state = self.make_state(
            status="ready_for_cleanup",
            cleanup_required=True,
            owner="watcher",
            next_action="complete",
            review={"verdict": "approve", "scope_checked": ["src/app.py"], "problems": [], "required_rework": [], "acceptance_basis": ["ok"]},
            reviewed_at="2026-05-08T00:00:00+00:00",
            worker_claim="Updated src/app.py.",
            files_changed=["src/app.py"],
            verification_command="python -m unittest",
            verification_result="passed",
            submitted_at="2026-05-08T00:00:00+00:00",
        )
        if state is not None:
            source_state.update(state)
        payload = build_completion_certification(source_state, "2026-05-08T00:00:00+00:00")
        return {
            "certification": {"completion": payload},
            "certification_hash": compute_certification_hash(payload),
        }

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
            "state_version": 1,
            "gate_attempt": 0,
            "gate_max_attempts": 5,
            "requested_role": "worker",
            "dispatch_status": "idle",
            "dispatch_intent": {},
            "dispatch_claim": {},
            "last_dispatch": {},
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

    def capture_session_start(self, project_dir: Path, run_root: Path) -> tuple[int, dict | None]:
        with io.StringIO() as stream, contextlib.redirect_stdout(stream):
            decision = session_start(project_dir, run_root)
            raw = stream.getvalue().strip()
        return decision, json.loads(raw) if raw else None

    def test_stop_allows_when_no_run_root_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            decision, payload = self.capture_stop(project_dir, project_dir / ".yolo")

        self.assertEqual(decision, 0)
        self.assertIsNone(payload)

    def test_session_start_does_not_require_trace_when_state_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(run_root, write_trace_file=False)

            decision, payload = self.capture_session_start(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertIn("hookSpecificOutput", payload)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertNotIn("trace.md is missing", payload["hookSpecificOutput"]["additionalContext"])

    def test_session_start_reports_missing_required_fields_via_hook_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            broken_state = self.make_state()
            broken_state.pop("requested_role")
            self.write_run_bundle(run_root, state=broken_state)

            decision, payload = self.capture_session_start(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertIn("hookSpecificOutput", payload)
        self.assertIn(
            "missing required field 'requested_role'",
            payload["hookSpecificOutput"]["additionalContext"],
        )

    def test_session_start_reports_missing_state_version_via_hook_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            broken_state = self.make_state()
            broken_state.pop("state_version")
            self.write_run_bundle(run_root, state=broken_state)

            decision, payload = self.capture_session_start(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertIn("hookSpecificOutput", payload)
        self.assertIn("state_version", payload["hookSpecificOutput"]["additionalContext"])

    def test_session_start_reports_missing_persisted_completion_certification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    status="ready_for_cleanup",
                    cleanup_required=True,
                    owner="watcher",
                    next_action="complete",
                ),
            )

            decision, payload = self.capture_session_start(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertIn("hookSpecificOutput", payload)
        self.assertIn("completion certification", payload["hookSpecificOutput"]["additionalContext"])

    def test_session_start_uses_persisted_chinese_for_invalid_complete_repair_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    status="complete",
                    cleanup_required=False,
                    certification={},
                    certification_hash="bad",
                    dialogue_language={"source": "latest_user_request", "language": "zh-CN", "confidence": 0.8},
                ),
            )

            decision, payload = self.capture_session_start(project_dir, run_root)

        self.assertEqual(decision, 0)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("恢复前需要先修复", context)
        self.assertIn("Issue:", context)

    def test_stop_blocks_broken_run_root_even_with_stop_hook_active_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(run_root, write_state_file=False)

            decision, payload = self.capture_stop(project_dir, run_root, {"stop_hook_active": True})

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("state.json is missing", payload["reason"])

    def test_stop_hook_active_flag_does_not_bypass_pending_unclaimed_dispatch_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    status="active",
                    gate_attempt=0,
                    dispatch_status="pending",
                    dispatch_intent={"role": "worker", "action": "worker_update"},
                    dispatch_claim={},
                ),
            )

            decision, payload = self.capture_stop(project_dir, run_root, {"stop_hook_active": True})
            updated_state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("Workflow status is active", payload["reason"])
        self.assertNotIn("orchestration", payload)
        self.assertEqual(updated_state["gate_attempt"], 0)
        self.assertEqual(updated_state["dispatch_status"], "pending")
        self.assertEqual(updated_state["dispatch_intent"]["role"], "worker")

    def test_stop_blocks_when_dispatch_intent_is_missing_for_active_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(status="active", dispatch_status="pending", dispatch_intent={}),
            )

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("dispatch_intent", payload["reason"])

    def test_stop_blocks_when_dispatch_intent_fields_are_malformed_for_active_work(self) -> None:
        cases = (
            {"role": "", "action": "worker_update"},
            {"role": "worker", "action": 123},
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            for dispatch_intent in cases:
                self.write_run_bundle(
                    run_root,
                    state=self.make_state(
                        status="active",
                        dispatch_status="pending",
                        dispatch_intent=dispatch_intent,
                    ),
                )

                decision, payload = self.capture_stop(project_dir, run_root)

                self.assertEqual(decision, 0)
                self.assertEqual(payload["decision"], "block")
                self.assertIn("dispatch_intent", payload["reason"])

    def test_stop_blocks_when_live_dispatch_claim_still_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    status="active",
                    dispatch_status="claimed",
                    dispatch_intent={"role": "worker", "action": "worker_update"},
                    dispatch_claim={
                        "owner": "worker-1",
                        "claimed_at": "2026-05-08T00:00:00+00:00",
                        "lease_expires_at": "2999-01-01T00:00:00+00:00",
                    },
                ),
            )

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("live dispatch claim", payload["reason"])
        self.assertNotIn("orchestration", payload)

    def test_stop_blocks_when_claimed_dispatch_claim_shape_is_malformed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    status="active",
                    dispatch_status="claimed",
                    dispatch_intent={"role": "worker", "action": "worker_update"},
                    dispatch_claim={"owner": "worker-1"},
                ),
            )

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("dispatch_claim", payload["reason"])
        self.assertIn("repaired", payload["reason"])

    def test_stop_blocks_when_running_dispatch_lease_is_naive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    status="active",
                    dispatch_status="running",
                    dispatch_intent={"role": "worker", "action": "worker_update"},
                    dispatch_claim={
                        "owner": "worker-1",
                        "claimed_at": "2026-05-08T00:00:00+00:00",
                        "lease_expires_at": "2026-05-08T00:01:00",
                    },
                ),
            )

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("lease_expires_at", payload["reason"])
        self.assertIn("repaired", payload["reason"])

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
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    gate_attempt=1,
                    gate_max_attempts=3,
                    dispatch_status="completed",
                    last_dispatch={"role": "worker", "task_id": "task-001"},
                ),
            )

            decision, payload = self.capture_stop(project_dir, run_root)
            updated_state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("Worker return stop gate attempt 2/3", payload["reason"])
        self.assertEqual(updated_state["gate_attempt"], 2)
        self.assertEqual(updated_state["gate_reason"], "worker_return_stop_block")
        self.assertFalse(updated_state["blocked_for_human"])
        self.assertEqual(updated_state["owner"], "worker")

    def test_stop_persists_gate_attempt_with_new_state_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    state_version=7,
                    gate_attempt=1,
                    gate_max_attempts=3,
                    dispatch_status="completed",
                    last_dispatch={"role": "worker", "task_id": "task-001"},
                ),
            )

            decision, payload = self.capture_stop(project_dir, run_root)
            updated_state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("Worker return stop gate attempt 2/3", payload["reason"])
        self.assertEqual(updated_state["gate_attempt"], 2)
        self.assertEqual(updated_state["state_version"], 8)
        self.assertEqual(updated_state["last_transition_actor"], "stop_hook")

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
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    gate_attempt=4,
                    gate_max_attempts=5,
                    next_action="worker_rework",
                    dispatch_status="completed",
                    last_dispatch={"role": "worker", "task_id": "task-001"},
                ),
            )

            decision, payload = self.capture_stop(project_dir, run_root)
            updated_state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("requires human handoff", payload["reason"])
        self.assertNotIn("orchestration", payload)
        self.assertEqual(updated_state["gate_attempt"], 5)
        self.assertTrue(updated_state["blocked_for_human"])
        self.assertEqual(updated_state["owner"], "human")
        self.assertEqual(updated_state["next_action"], "human_handoff")
        self.assertEqual(updated_state["requested_role"], "human")
        self.assertEqual(updated_state["dispatch_status"], "pending")
        self.assertEqual(updated_state["dispatch_intent"]["role"], "human")
        self.assertEqual(updated_state["resume_target"], {"role": "worker", "action": "worker_rework"})
        self.assertEqual(updated_state["last_dispatch"], {})
        self.assertEqual(updated_state["worker_request"], "need_human")
        self.assertEqual(
            updated_state["worker_question"],
            "Stop gate limit reached; human guidance is required before the run can resume.",
        )
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

    def test_stop_blocks_when_active_state_is_missing_required_dispatch_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            broken_state = self.make_state(status="active")
            broken_state.pop("dispatch_intent")
            self.write_run_bundle(run_root, state=broken_state)

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("missing required dispatch field 'dispatch_intent'", payload["reason"])

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
                    **self.completion_certification(),
                ),
            )

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("cleanup", payload["reason"])

    def test_stop_blocks_ready_for_cleanup_without_persisted_completion_certification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    status="ready_for_cleanup",
                    cleanup_required=True,
                    owner="watcher",
                    next_action="complete",
                ),
            )

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("completion certification", payload["reason"])

    def test_stop_blocks_complete_state_with_mismatched_completion_certification_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    status="complete",
                    cleanup_required=False,
                    owner="watcher",
                    next_action="complete",
                    certification={"completion": self.completion_certification()["certification"]["completion"]},
                    certification_hash="wrong-hash",
                ),
                write_trace_file=False,
            )

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("certification_hash", payload["reason"])

    def test_stop_blocks_complete_state_without_cleanup_ready_state_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            certification = self.completion_certification()
            certification["certification"]["completion"].pop("cleanup_ready_state_hash", None)
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    status="complete",
                    cleanup_required=False,
                    owner="watcher",
                    next_action="complete",
                    **certification,
                ),
            )

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("cleanup-ready state proof", payload["reason"])

    def test_stop_blocks_complete_state_with_invalid_terminal_cleanup_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    status="complete",
                    cleanup_required=False,
                    owner="worker",
                    next_action="worker_update",
                    **self.completion_certification(
                        {
                            "status": "complete",
                            "cleanup_required": False,
                            "owner": "worker",
                            "next_action": "worker_update",
                        }
                    ),
                ),
                write_trace_file=False,
            )

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("terminal cleanup contract", payload["reason"])

    def test_stop_allows_complete_state_with_persisted_completion_certification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.write_run_bundle(
                run_root,
                state=self.make_state(
                    status="complete",
                    cleanup_required=False,
                    owner="watcher",
                    next_action="complete",
                    **self.completion_certification(),
                ),
                write_trace_file=False,
            )

            decision, payload = self.capture_stop(project_dir, run_root)

        self.assertEqual(decision, 0)
        self.assertIsNone(payload)


if __name__ == "__main__":
    unittest.main()

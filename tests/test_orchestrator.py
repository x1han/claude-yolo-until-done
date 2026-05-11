from __future__ import annotations

import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from orchestrator import (
    build_task_packet,
    claim_dispatch,
    is_dispatch_claim_live,
    mark_dispatch_pending,
    next_step,
    orchestrate,
    parse_timestamp,
    recover_dispatch_for_resume,
    resume_after_human,
)
from state import build_state, load_state, write_state


class OrchestratorStateTest(unittest.TestCase):
    def test_build_state_sets_orchestration_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            template_path = project_dir / "state-template.json"
            template_path.write_text("{}\n", encoding="utf-8")

            state = build_state(
                template_path=template_path,
                goal="Ship orchestrator defaults.",
                success_criteria=["State includes orchestration defaults."],
                plan_path=project_dir / "plan.md",
                spec_path=project_dir / "spec.md",
                repo_root=project_dir,
            )

            self.assertEqual(state["task_id"], "task-001")
            self.assertEqual(state["gate_id"], "gate-task-001")
            self.assertEqual(state["gate_attempt"], 0)
            self.assertEqual(state["gate_max_attempts"], 5)
            self.assertEqual(state["requested_role"], "worker")
            self.assertEqual(state["dispatch_status"], "pending")
            self.assertEqual(state["dispatch_generation"], 0)
            self.assertEqual(
                state["supervision"],
                {
                    "last_token_io_at": "",
                    "last_progress_at": "",
                    "stall_timeout_seconds": 600,
                    "retry_limit": 3,
                    "retry_count": 0,
                    "last_recovery_at": "",
                    "last_recovery_reason": "",
                },
            )
            self.assertFalse(state["blocked_for_human"])

    def test_build_state_preserves_template_orchestration_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            template_path = project_dir / "state-template.json"
            template_path.write_text(
                json.dumps(
                    {
                        "task_id": "task-777",
                        "gate_id": "gate-custom",
                        "gate_attempt": 3,
                        "gate_max_attempts": 9,
                        "requested_role": "reviewer",
                        "dispatch_status": "waiting",
                        "blocked_for_human": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            state = build_state(
                template_path=template_path,
                goal="Preserve template orchestration values.",
                success_criteria=["Existing template defaults survive build_state()."],
                plan_path=project_dir / "plan.md",
                spec_path=project_dir / "spec.md",
                repo_root=project_dir,
            )

            self.assertEqual(state["task_id"], "task-777")
            self.assertEqual(state["gate_id"], "gate-custom")
            self.assertEqual(state["gate_attempt"], 3)
            self.assertEqual(state["gate_max_attempts"], 9)
            self.assertEqual(state["requested_role"], "reviewer")
            self.assertEqual(state["dispatch_status"], "waiting")
            self.assertTrue(state["blocked_for_human"])

    def test_state_template_includes_orchestration_defaults(self) -> None:
        template_path = SKILL_ROOT / "templates" / "state-template.json"
        state = json.loads(template_path.read_text(encoding="utf-8"))

        self.assertEqual(state["task_id"], "task-001")
        self.assertEqual(state["gate_id"], "gate-task-001")
        self.assertEqual(state["gate_attempt"], 0)
        self.assertEqual(state["gate_max_attempts"], 5)
        self.assertEqual(state["requested_role"], "worker")
        self.assertEqual(state["dispatch_status"], "pending")
        self.assertEqual(state["dispatch_generation"], 0)
        self.assertEqual(
            state["supervision"],
            {
                "last_token_io_at": "",
                "last_progress_at": "",
                "stall_timeout_seconds": 600,
                "retry_limit": 3,
                "retry_count": 0,
                "last_recovery_at": "",
                "last_recovery_reason": "",
            },
        )
        self.assertFalse(state["blocked_for_human"])


class OrchestratorRoutingTest(unittest.TestCase):
    def test_worker_need_helper_routes_to_helper_without_incrementing_gate(self) -> None:
        state = {
            "task_id": "task-001",
            "task_title": "Implement gate logic",
            "task_goal": "Keep stop fail-closed.",
            "task_scope": ["workflow/claude_hook_bridge.py"],
            "task_inputs": {"plan_task_text": "Implement the stop gate."},
            "task_handoff_notes": [],
            "gate_id": "gate-task-001",
            "gate_attempt": 2,
            "gate_max_attempts": 5,
            "gate_reason": "worker_returned",
            "requested_role": "worker",
            "dispatch_status": "idle",
            "worker_request": "need_helper",
            "worker_question": "Should stop increment on helper return?",
            "verification_command": "python -m unittest source.tests.test_stop_hook -v",
            "verification_result": "",
            "blocked_for_human": False,
        }

        decision = next_step(state)

        self.assertEqual(decision["role"], "helper")
        self.assertEqual(decision["gate_attempt"], 2)

    def test_blocked_for_human_routes_to_human(self) -> None:
        decision = next_step({"blocked_for_human": True, "requested_role": "helper", "gate_attempt": 4})

        self.assertEqual(decision["role"], "human")
        self.assertEqual(decision["gate_attempt"], 4)

    def test_default_state_routes_to_worker(self) -> None:
        decision = next_step({})

        self.assertEqual(decision["role"], "worker")
        self.assertEqual(decision["gate_attempt"], 0)

    def test_build_task_packet_contains_full_task_text_and_spec_excerpt(self) -> None:
        state = {
            "task_id": "task-001",
            "task_title": "Implement gate logic",
            "task_goal": "Keep stop fail-closed.",
            "task_scope": ["workflow/claude_hook_bridge.py"],
            "task_inputs": {
                "plan_task_text": "Task 5 full text goes here.",
                "spec_excerpt": "Stop must never default-pass unfinished work.",
                "checklist_items": ["review fresh verification evidence"],
            },
            "task_handoff_notes": ["watcher requested tighter stop semantics"],
            "gate_id": "gate-task-001",
            "gate_attempt": 1,
            "gate_max_attempts": 5,
            "gate_reason": "worker_returned",
            "verification_command": "python -m unittest source.tests.test_stop_hook -v",
            "verification_result": "",
        }

        packet = build_task_packet(state, role="watcher")

        self.assertEqual(packet["role"], "watcher")
        self.assertEqual(packet["task_id"], "task-001")
        self.assertEqual(packet["plan_task_text"], "Task 5 full text goes here.")
        self.assertEqual(packet["spec_excerpt"], "Stop must never default-pass unfinished work.")
        self.assertEqual(packet["checklist_items"], ["review fresh verification evidence"])
        self.assertEqual(packet["gate_id"], "gate-task-001")
        self.assertEqual(packet["gate_attempt"], 1)
        self.assertEqual(packet["task_handoff_notes"], ["watcher requested tighter stop semantics"])

    def test_build_task_packet_preserves_handoff_context(self) -> None:
        state = {
            "task_id": "task-002",
            "task_title": "Second",
            "task_goal": "Repair it",
            "task_scope": ["workflow/orchestrator.py"],
            "task_inputs": {
                "task_id": "task-002",
                "task_title": "Second",
                "plan_task_text": "2. Second",
                "spec_excerpt": "spec",
                "checklist_items": ["a"],
            },
            "task_handoff_notes": ["Need reviewer guidance"],
            "worker_request": "need_helper",
            "worker_question": "Should helper inspect validators?",
            "human_handoff": {"reason": "stop_gate_limit"},
            "gate_id": "gate-task-002",
            "gate_attempt": 2,
            "gate_max_attempts": 5,
            "gate_reason": "worker_return_stop_block",
            "verification_command": "python -m unittest -v",
            "verification_result": "passed",
        }

        packet = build_task_packet(state, "helper")

        self.assertEqual(packet["worker_request"], "need_helper")
        self.assertEqual(packet["worker_question"], "Should helper inspect validators?")
        self.assertEqual(packet["human_handoff"], {"reason": "stop_gate_limit"})
        self.assertEqual(packet["task_handoff_notes"], ["Need reviewer guidance"])

    def test_resume_after_human_keeps_current_task_and_gate_and_clears_human_block(self) -> None:
        state = {
            "task_id": "task-001",
            "gate_id": "gate-task-001",
            "gate_attempt": 4,
            "dispatch_status": "waiting",
            "worker_request": "need_human",
            "worker_question": "Need approval",
            "gate_reason": "stop_gate_limit",
            "verification_command": "python -m unittest source.tests.test_stop_hook -v",
            "verification_result": "failed before human guidance",
            "blocked_for_human": True,
            "human_handoff": {"question": "Need approval"},
            "requested_role": "human",
            "task_handoff_notes": [],
        }

        resumed = resume_after_human(state, "Proceed with the simpler fix.")

        self.assertEqual(resumed["task_id"], "task-001")
        self.assertEqual(resumed["gate_id"], "gate-task-001")
        self.assertEqual(resumed["gate_attempt"], 0)
        self.assertFalse(resumed["blocked_for_human"])
        self.assertEqual(resumed["human_handoff"], {})
        self.assertEqual(resumed["owner"], "worker")
        self.assertEqual(resumed["next_action"], "worker_update")
        self.assertEqual(resumed["dispatch_status"], "pending")
        self.assertEqual(resumed["worker_request"], "")
        self.assertEqual(resumed["worker_question"], "")
        self.assertEqual(resumed["gate_reason"], "")
        self.assertEqual(resumed["verification_command"], "")
        self.assertEqual(resumed["verification_result"], "")
        self.assertEqual(resumed["requested_role"], "worker")
        self.assertEqual(resumed["task_handoff_notes"], ["Proceed with the simpler fix."])

    def test_resume_after_human_preserves_notes_and_appends_guidance(self) -> None:
        state = {
            "task_id": "task-009",
            "gate_id": "gate-task-009",
            "gate_attempt": 1,
            "blocked_for_human": True,
            "human_handoff": {"question": "Need direction"},
            "requested_role": "human",
            "task_handoff_notes": ["worker exhausted helper path", "watcher asked for narrowed scope"],
        }

        resumed = resume_after_human(state, "Focus only on orchestrator resume state.")

        self.assertEqual(
            resumed["task_handoff_notes"],
            [
                "worker exhausted helper path",
                "watcher asked for narrowed scope",
                "Focus only on orchestrator resume state.",
            ],
        )

    def test_resume_after_human_keeps_current_task_inputs_and_gate(self) -> None:
        state = {
            "task_id": "task-009",
            "task_title": "Current task",
            "task_inputs": {"task_id": "task-009", "task_title": "Current task"},
            "gate_id": "gate-task-009",
            "gate_attempt": 1,
            "blocked_for_human": True,
            "human_handoff": {"question": "Need direction"},
            "requested_role": "human",
            "task_handoff_notes": [],
        }

        resumed = resume_after_human(state, "Proceed on the current task.")

        self.assertEqual(resumed["task_id"], "task-009")
        self.assertEqual(resumed["gate_id"], "gate-task-009")
        self.assertEqual(resumed["task_title"], "Current task")
        self.assertEqual(resumed["task_inputs"], {"task_id": "task-009", "task_title": "Current task"})

    def test_resume_after_human_signature_has_no_checklist_parameter(self) -> None:
        parameters = inspect.signature(resume_after_human).parameters

        self.assertNotIn("checklist", parameters)

    def test_mark_dispatch_pending_resets_dispatch_fields(self) -> None:
        state = {
            "requested_role": "worker",
            "dispatch_status": "claimed",
            "dispatch_intent": {"role": "worker", "action": "worker_update"},
            "dispatch_claim": {"owner": "watcher-1"},
            "last_dispatch": {"role": "worker"},
        }

        mark_dispatch_pending(state, "watcher")

        self.assertEqual(state["requested_role"], "watcher")
        self.assertEqual(state["dispatch_status"], "pending")
        self.assertEqual(state["dispatch_intent"]["role"], "watcher")
        self.assertEqual(state["dispatch_claim"], {})
        self.assertEqual(state["last_dispatch"], {})

    def test_claim_dispatch_marks_single_consumer_ownership(self) -> None:
        state = {
            "task_id": "task-001",
            "gate_id": "gate-task-001",
            "requested_role": "worker",
            "dispatch_status": "pending",
            "dispatch_intent": {"role": "worker", "action": "worker_update"},
            "dispatch_claim": {},
            "dispatch_generation": 0,
        }

        claim = claim_dispatch(state, consumer_id="worker:gate-task-001:1", now="2026-05-08T00:00:00+00:00", lease_seconds=120)

        self.assertEqual(claim["result"], "claimed")
        self.assertEqual(state["dispatch_generation"], 1)
        self.assertEqual(state["dispatch_status"], "claimed")
        self.assertEqual(state["dispatch_claim"]["owner"], "worker:gate-task-001:1")
        self.assertEqual(state["dispatch_claim"]["lease_expires_at"], "2026-05-08T00:02:00+00:00")

    def test_second_live_claimant_is_rejected(self) -> None:
        state = {
            "task_id": "task-001",
            "gate_id": "gate-task-001",
            "requested_role": "worker",
            "dispatch_status": "pending",
            "dispatch_intent": {"role": "worker", "action": "worker_update"},
            "dispatch_claim": {},
            "dispatch_generation": 0,
        }

        first_claim = claim_dispatch(state, consumer_id="worker:gate-task-001:1", now="2026-05-08T00:00:00+00:00", lease_seconds=120)
        second_claim = claim_dispatch(state, consumer_id="worker:gate-task-001:2", now="2026-05-08T00:01:00+00:00", lease_seconds=120)

        self.assertEqual(first_claim["result"], "claimed")
        self.assertEqual(second_claim["result"], "rejected")
        self.assertEqual(second_claim["owner"], "worker:gate-task-001:1")
        self.assertEqual(state["dispatch_status"], "claimed")
        self.assertEqual(state["dispatch_claim"]["owner"], "worker:gate-task-001:1")

    def test_parse_timestamp_rejects_naive_timestamps(self) -> None:
        self.assertIsNone(parse_timestamp("2026-05-08T00:00:00"))

    def test_orchestrate_dispatches_only_from_pending_intent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            state = {
                "task_id": "task-001",
                "task_title": "Implement gate logic",
                "task_goal": "Keep stop fail-closed.",
                "task_scope": ["workflow/claude_hook_bridge.py"],
                "task_inputs": {"plan_task_text": "Task text", "spec_excerpt": "Spec text", "checklist_items": ["check fresh evidence"]},
                "task_handoff_notes": [],
                "gate_id": "gate-task-001",
                "gate_attempt": 1,
                "gate_max_attempts": 5,
                "gate_reason": "worker_returned",
                "requested_role": "watcher",
                "dispatch_status": "pending",
                "dispatch_intent": {"role": "watcher", "action": "watcher_review"},
                "dispatch_claim": {},
                "worker_request": "",
                "verification_command": "python -m unittest source.tests.test_stop_hook -v",
                "verification_result": "passed",
                "blocked_for_human": False,
            }

            result = orchestrate(run_root, state)
            persisted = load_state(run_root)

        self.assertEqual(result["result"], "dispatched")
        self.assertEqual(result["role"], "watcher")
        self.assertEqual(persisted["dispatch_status"], "running")
        self.assertEqual(persisted["dispatch_claim"]["owner"], "watcher:gate-task-001:1")
        self.assertEqual(persisted["last_dispatch"]["role"], "watcher")
        self.assertEqual(persisted["last_dispatch"]["task_packet"]["plan_task_text"], "Task text")

    def test_orchestrate_noops_when_dispatch_is_idle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            state = {
                "task_id": "task-001",
                "requested_role": "worker",
                "dispatch_status": "idle",
                "dispatch_intent": {"role": "worker", "action": "worker_update"},
                "blocked_for_human": False,
            }

            result = orchestrate(run_root, state)

        self.assertEqual(result["result"], "no_op")
        self.assertIn("dispatch_status=idle", result["reason"])

    def test_orchestrate_replays_live_dispatch_for_same_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            state = {
                "task_id": "task-001",
                "task_title": "Implement gate logic",
                "task_goal": "Keep stop fail-closed.",
                "task_scope": ["workflow/orchestrator.py"],
                "task_inputs": {"plan_task_text": "Task text"},
                "task_handoff_notes": [],
                "gate_id": "gate-task-001",
                "gate_attempt": 0,
                "gate_max_attempts": 5,
                "requested_role": "worker",
                "dispatch_status": "running",
                "dispatch_intent": {"role": "worker", "action": "worker_update"},
                "dispatch_claim": {
                    "owner": "worker:gate-task-001:1",
                    "claimed_at": "2026-05-08T00:00:00+00:00",
                    "lease_expires_at": "2999-01-01T00:00:00+00:00",
                },
                "last_dispatch": {
                    "role": "worker",
                    "task_id": "task-001",
                    "gate_id": "gate-task-001",
                    "next_action": "worker_update",
                    "dispatched_at": "2026-05-08T00:00:00+00:00",
                    "task_packet": {"plan_task_text": "Task text"},
                },
            }

            result = orchestrate(run_root, state, consumer_id="worker:gate-task-001:1")

        self.assertEqual(result["result"], "dispatched")
        self.assertTrue(result["replayed"])
        self.assertEqual(result["role"], "worker")

    def test_orchestrate_dispatch_completion_advances_state_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            state = {
                "task_id": "task-001",
                "task_title": "Implement gate logic",
                "task_goal": "Keep stop fail-closed.",
                "task_scope": ["workflow/claude_hook_bridge.py"],
                "task_inputs": {"plan_task_text": "Task text", "spec_excerpt": "Spec text", "checklist_items": ["check fresh evidence"]},
                "task_handoff_notes": [],
                "gate_id": "gate-task-001",
                "gate_attempt": 1,
                "gate_max_attempts": 5,
                "gate_reason": "worker_returned",
                "requested_role": "watcher",
                "dispatch_status": "pending",
                "dispatch_intent": {"role": "watcher", "action": "watcher_review"},
                "dispatch_claim": {},
                "worker_request": "",
                "verification_command": "python -m unittest source.tests.test_stop_hook -v",
                "verification_result": "passed",
                "blocked_for_human": False,
                "state_version": 3,
                "last_transition_actor": "controller",
                "last_transition_id": "controller:review:3",
            }
            write_state(run_root, state)

            result = orchestrate(run_root, dict(state))
            persisted = load_state(run_root)

        self.assertEqual(result["result"], "dispatched")
        self.assertEqual(persisted["dispatch_status"], "running")
        self.assertEqual(persisted["dispatch_claim"]["owner"], "watcher:gate-task-001:1")
        self.assertEqual(persisted["state_version"], 4)
        self.assertEqual(persisted["last_transition_actor"], "orchestrator")

    def test_recover_dispatch_for_resume_requeues_expired_live_claim(self) -> None:
        state = {
            "requested_role": "worker",
            "next_action": "worker_update",
            "dispatch_status": "running",
            "dispatch_intent": {"role": "watcher", "action": "watcher_review"},
            "dispatch_claim": {
                "owner": "worker:gate-task-001:1",
                "claimed_at": "2026-05-08T00:00:00+00:00",
                "lease_expires_at": "2026-05-08T00:00:01+00:00",
            },
            "last_dispatch": {"role": "watcher", "task_id": "task-001"},
        }

        result = recover_dispatch_for_resume(state, now="2026-05-08T00:01:00+00:00")

        self.assertEqual(result["result"], "requeued")
        self.assertEqual(result["expired_owner"], "worker:gate-task-001:1")
        self.assertEqual(result["role"], "watcher")
        self.assertEqual(state["requested_role"], "watcher")
        self.assertEqual(state["dispatch_status"], "pending")
        self.assertEqual(state["dispatch_intent"], {"role": "watcher", "action": "watcher_review"})
        self.assertEqual(state["dispatch_claim"], {})
        self.assertEqual(state["last_dispatch"], {})

    def test_orchestrate_times_out_expired_live_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            state = {
                "task_id": "task-001",
                "requested_role": "worker",
                "dispatch_status": "claimed",
                "dispatch_intent": {"role": "worker", "action": "worker_update"},
                "dispatch_claim": {
                    "owner": "worker:gate-task-001:1",
                    "claimed_at": "2026-05-08T00:00:00+00:00",
                    "lease_expires_at": "2026-05-08T00:00:01+00:00",
                },
                "last_dispatch": {},
            }

            result = orchestrate(run_root, state, consumer_id="worker-2")
            persisted = load_state(run_root)

        self.assertEqual(result["result"], "timed_out")
        self.assertEqual(persisted["dispatch_status"], "timed_out")
        self.assertEqual(persisted["dispatch_claim"]["terminal_reason"], "dispatch claim lease expired")

    def test_recover_dispatch_for_resume_requeues_timed_out_dispatch_with_intent(self) -> None:
        state = {
            "requested_role": "worker",
            "next_action": "worker_update",
            "dispatch_status": "timed_out",
            "dispatch_intent": {"role": "watcher", "action": "watcher_review"},
            "dispatch_claim": {
                "owner": "worker:gate-task-001:1",
                "claimed_at": "2026-05-08T00:00:00+00:00",
                "lease_expires_at": "2026-05-08T00:00:01+00:00",
                "terminal_reason": "dispatch claim lease expired",
                "timed_out_at": "2026-05-08T00:01:00+00:00",
            },
            "last_dispatch": {"role": "watcher", "task_id": "task-001"},
        }

        result = recover_dispatch_for_resume(state, now="2026-05-08T00:02:00+00:00")

        self.assertEqual(result["result"], "requeued")
        self.assertEqual(result["expired_owner"], "worker:gate-task-001:1")
        self.assertEqual(result["role"], "watcher")
        self.assertEqual(result["action"], "watcher_review")
        self.assertEqual(state["requested_role"], "watcher")
        self.assertEqual(state["dispatch_status"], "pending")
        self.assertEqual(state["dispatch_intent"], {"role": "watcher", "action": "watcher_review"})
        self.assertEqual(state["dispatch_claim"], {})
        self.assertEqual(state["last_dispatch"], {})

    def test_recover_dispatch_for_resume_requeues_abandoned_dispatch_with_intent(self) -> None:
        state = {
            "requested_role": "worker",
            "next_action": "worker_update",
            "dispatch_status": "abandoned",
            "dispatch_intent": {"role": "worker", "action": "worker_rework"},
            "dispatch_claim": {
                "owner": "worker:gate-task-001:1",
                "claimed_at": "2026-05-08T00:00:00+00:00",
                "lease_expires_at": "2026-05-08T00:00:01+00:00",
                "terminal_reason": "live claim is missing dispatch_intent",
                "abandoned_at": "2026-05-08T00:01:00+00:00",
            },
            "last_dispatch": {},
        }

        result = recover_dispatch_for_resume(state, now="2026-05-08T00:02:00+00:00")

        self.assertEqual(result["result"], "requeued")
        self.assertEqual(result["expired_owner"], "worker:gate-task-001:1")
        self.assertEqual(result["role"], "worker")
        self.assertEqual(result["action"], "worker_rework")
        self.assertEqual(state["requested_role"], "worker")
        self.assertEqual(state["dispatch_status"], "pending")
        self.assertEqual(state["dispatch_intent"], {"role": "worker", "action": "worker_rework"})
        self.assertEqual(state["dispatch_claim"], {})
        self.assertEqual(state["last_dispatch"], {})

    def test_orchestrate_abandons_live_claim_without_replayable_intent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            state = {
                "task_id": "task-001",
                "requested_role": "worker",
                "dispatch_status": "running",
                "dispatch_intent": {},
                "dispatch_claim": {
                    "owner": "worker:gate-task-001:1",
                    "claimed_at": "2026-05-08T00:00:00+00:00",
                    "lease_expires_at": "2999-01-01T00:00:00+00:00",
                },
                "last_dispatch": {},
            }

            result = orchestrate(run_root, state, consumer_id="worker:gate-task-001:1")
            persisted = load_state(run_root)

        self.assertEqual(result["result"], "abandoned")
        self.assertEqual(persisted["dispatch_status"], "abandoned")
        self.assertEqual(persisted["dispatch_claim"]["terminal_reason"], "live claim is missing dispatch_intent")

    def test_orchestrate_noops_after_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            state = {
                "task_id": "task-001",
                "task_title": "Implement gate logic",
                "task_goal": "Keep stop fail-closed.",
                "task_scope": [],
                "task_inputs": {},
                "task_handoff_notes": [],
                "gate_id": "gate-task-001",
                "gate_attempt": 0,
                "gate_max_attempts": 5,
                "requested_role": "worker",
                "dispatch_status": "dispatched",
                "last_dispatch": {"role": "worker"},
                "blocked_for_human": False,
            }

            result = orchestrate(run_root, state)

        self.assertEqual(result["result"], "no_op")
        self.assertIn("dispatch_status=dispatched", result["reason"])

    def test_orchestrate_does_not_recover_when_lease_is_live_even_if_heartbeat_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            state = {
                "state_version": 1,
                "task_id": "task-001",
                "gate_id": "gate-task-001",
                "status": "active",
                "owner": "worker",
                "next_action": "worker_update",
                "requested_role": "worker",
                "dispatch_status": "running",
                "dispatch_generation": 1,
                "dispatch_intent": {"role": "worker", "action": "worker_update"},
                "dispatch_claim": {
                    "owner": "worker:gate-task-001:1",
                    "claimed_at": "2026-05-10T00:00:00+00:00",
                    "lease_expires_at": "2999-01-01T00:00:00+00:00",
                },
                "last_dispatch": {
                    "role": "worker",
                    "task_id": "task-001",
                    "gate_id": "gate-task-001",
                    "next_action": "worker_update",
                    "dispatched_at": "2026-05-10T00:00:00+00:00",
                    "task_packet": {"task_id": "task-001"},
                },
                "supervision": {
                    "last_token_io_at": "2026-05-10T00:00:00+00:00",
                    "last_progress_at": "",
                    "stall_timeout_seconds": 600,
                    "retry_limit": 3,
                    "retry_count": 0,
                    "last_recovery_at": "",
                    "last_recovery_reason": "",
                },
                "blocked_for_human": False,
                "human_handoff": {},
            }
            write_state(run_root, state)

            result = orchestrate(run_root, dict(state), consumer_id="worker:gate-task-001:1")
            persisted = load_state(run_root)

        self.assertEqual(result["result"], "dispatched")
        self.assertTrue(result["replayed"])
        self.assertEqual(persisted["dispatch_generation"], 1)
        self.assertEqual(persisted["supervision"]["retry_count"], 0)

    def test_orchestrate_recovers_stalled_worker_and_advances_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            state = {
                "state_version": 1,
                "task_id": "task-001",
                "gate_id": "gate-task-001",
                "status": "active",
                "owner": "worker",
                "next_action": "worker_update",
                "requested_role": "worker",
                "dispatch_status": "running",
                "dispatch_generation": 3,
                "dispatch_intent": {"role": "worker", "action": "worker_update"},
                "dispatch_claim": {
                    "owner": "worker:gate-task-001:3",
                    "claimed_at": "2026-05-10T00:00:00+00:00",
                    "lease_expires_at": "2026-05-10T00:02:00+00:00",
                },
                "last_dispatch": {
                    "role": "worker",
                    "task_id": "task-001",
                    "gate_id": "gate-task-001",
                    "next_action": "worker_update",
                    "dispatched_at": "2026-05-10T00:00:00+00:00",
                    "task_packet": {"task_id": "task-001", "plan_task_text": "Task text"},
                },
                "supervision": {
                    "last_token_io_at": "2026-05-10T00:00:00+00:00",
                    "last_progress_at": "",
                    "stall_timeout_seconds": 600,
                    "retry_limit": 3,
                    "retry_count": 0,
                    "last_recovery_at": "",
                    "last_recovery_reason": "",
                },
                "blocked_for_human": False,
                "human_handoff": {},
            }
            write_state(run_root, state)

            result = orchestrate(run_root, dict(state), consumer_id="worker:gate-task-001:4")
            persisted = load_state(run_root)

        self.assertEqual(result["result"], "dispatched")
        self.assertEqual(persisted["dispatch_generation"], 4)
        self.assertEqual(persisted["dispatch_claim"]["owner"], "worker:gate-task-001:4")
        self.assertEqual(persisted["supervision"]["retry_count"], 1)
        self.assertEqual(persisted["supervision"]["last_recovery_reason"], "worker_stalled")

    def test_orchestrate_escalates_after_retry_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            state = {
                "state_version": 1,
                "task_id": "task-001",
                "gate_id": "gate-task-001",
                "status": "active",
                "owner": "worker",
                "next_action": "worker_update",
                "requested_role": "worker",
                "dispatch_status": "running",
                "dispatch_generation": 3,
                "dispatch_intent": {"role": "worker", "action": "worker_update"},
                "dispatch_claim": {
                    "owner": "worker:gate-task-001:3",
                    "claimed_at": "2026-05-10T00:00:00+00:00",
                    "lease_expires_at": "2026-05-10T00:02:00+00:00",
                },
                "last_dispatch": {
                    "role": "worker",
                    "task_id": "task-001",
                    "gate_id": "gate-task-001",
                    "next_action": "worker_update",
                    "dispatched_at": "2026-05-10T00:00:00+00:00",
                    "task_packet": {"task_id": "task-001"},
                },
                "supervision": {
                    "last_token_io_at": "2026-05-10T00:00:00+00:00",
                    "last_progress_at": "",
                    "stall_timeout_seconds": 600,
                    "retry_limit": 3,
                    "retry_count": 3,
                    "last_recovery_at": "",
                    "last_recovery_reason": "",
                },
                "blocked_for_human": False,
                "human_handoff": {},
                "resume_target": {"role": "worker", "action": "worker_update"},
            }
            write_state(run_root, state)

            result = orchestrate(run_root, dict(state))
            persisted = load_state(run_root)

        self.assertEqual(result["result"], "blocked_for_human")
        self.assertTrue(persisted["blocked_for_human"])
        self.assertEqual(persisted["owner"], "human")
        self.assertEqual(persisted["human_handoff"]["reason"], "worker_stalled_retry_limit")


if __name__ == "__main__":
    unittest.main()

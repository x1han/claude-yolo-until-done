from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from orchestrator import build_task_packet, next_step, resume_after_human
from state import build_state


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
            self.assertEqual(state["dispatch_status"], "idle")
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
        self.assertEqual(state["dispatch_status"], "idle")
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

    def test_resume_after_human_creates_new_task_and_gate_and_clears_human_block(self) -> None:
        state = {
            "task_id": "task-001",
            "gate_id": "gate-task-001",
            "gate_attempt": 4,
            "dispatch_status": "waiting",
            "worker_request": "need_helper",
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

        self.assertEqual(resumed["task_id"], "task-002")
        self.assertEqual(resumed["gate_id"], "gate-task-002")
        self.assertEqual(resumed["gate_attempt"], 0)
        self.assertFalse(resumed["blocked_for_human"])
        self.assertEqual(resumed["human_handoff"], {})
        self.assertEqual(resumed["owner"], "worker")
        self.assertEqual(resumed["next_action"], "worker_update")
        self.assertEqual(resumed["dispatch_status"], "idle")
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


if __name__ == "__main__":
    unittest.main()

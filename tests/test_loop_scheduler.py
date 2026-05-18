from __future__ import annotations

import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from workflow import loop_scheduler
from workflow.loop_scheduler import loop_decision


class LoopSchedulerTest(unittest.TestCase):
    def loop_state(self, *, status: str = "complete", iteration: int = 1, max_iterations: int | None = None, stop_on_convergence: bool = False, converged: bool = False) -> dict:
        return {
            "mode": "loop",
            "status": status,
            "loop": {
                "enabled": True,
                "iteration": iteration,
                "max_iterations": max_iterations,
                "stop_on_convergence": stop_on_convergence,
                "converged": converged,
                "stop_reason": "",
            },
            "task_title": "Execute approved spec and plan",
            "task_inputs": {
                "task_id": "task-001",
                "task_title": "Execute approved spec and plan",
                "plan_task_text": "# Plan\n\n### Task 1: First",
                "plan_sections": [
                    {"task_id": "plan-section-001", "task_title": "First", "plan_task_text": "### Task 1: First"},
                ],
            },
        }

    def test_acyclic_mode_never_schedules_loop(self) -> None:
        state = {"mode": "acyclic", "status": "complete", "loop": {"enabled": False, "iteration": 1}}

        self.assertEqual(loop_decision(state), {"action": "not_loop", "reason": "mode is acyclic"})

    def test_loop_mode_with_disabled_loop_is_invalid(self) -> None:
        state = {"mode": "loop", "status": "complete", "loop": {"enabled": False, "iteration": 1}}

        self.assertEqual(loop_decision(state), {"action": "stop", "reason": "invalid_loop_state"})

    def test_loop_unit_guard_accepts_complete_execution_unit(self) -> None:
        state = {
            "mode": "loop",
            "loop": {"enabled": True, "iteration": 2},
            "task_title": "Execute approved spec and plan",
            "task_inputs": {
                "task_id": "task-001",
                "task_title": "Execute approved spec and plan",
                "plan_task_text": "# Plan\n\n### Task 1: First\n\n### Task 2: Second",
                "plan_sections": [
                    {"task_id": "plan-section-001", "task_title": "First", "plan_task_text": "### Task 1: First"},
                    {"task_id": "plan-section-002", "task_title": "Second", "plan_task_text": "### Task 2: Second"},
                ],
            },
        }

        self.assertEqual(loop_scheduler.loop_execution_unit_problem(state), "")

    def test_loop_unit_guard_rejects_plan_section_as_current_unit(self) -> None:
        state = {
            "mode": "loop",
            "loop": {"enabled": True, "iteration": 2},
            "task_title": "First",
            "task_inputs": {
                "task_id": "plan-section-001",
                "task_title": "First",
                "plan_task_text": "### Task 1: First",
                "plan_sections": [
                    {"task_id": "plan-section-001", "task_title": "First", "plan_task_text": "### Task 1: First"},
                ],
            },
        }

        self.assertEqual(loop_scheduler.loop_execution_unit_problem(state), "loop task_inputs points at a plan section instead of the complete approved spec/plan")

    def test_loop_stops_after_fixed_count_of_complete_acyclic_iterations(self) -> None:
        state = self.loop_state(iteration=5, max_iterations=5)

        self.assertEqual(loop_decision(state), {"action": "stop", "reason": "max_iterations"})

    def test_loop_continues_before_max_iterations(self) -> None:
        state = self.loop_state(iteration=4, max_iterations=5)

        self.assertEqual(loop_decision(state), {"action": "continue", "next_iteration": 5})

    def test_loop_stops_on_convergence(self) -> None:
        state = self.loop_state(iteration=2, stop_on_convergence=True, converged=True)

        self.assertEqual(loop_decision(state), {"action": "stop", "reason": "converged"})

    def test_loop_a_plus_b_uses_either_stop(self) -> None:
        state = self.loop_state(iteration=2, max_iterations=10, stop_on_convergence=True, converged=True)

        self.assertEqual(loop_decision(state), {"action": "stop", "reason": "converged"})

    def test_loop_waits_when_acyclic_iteration_not_terminal(self) -> None:
        state = self.loop_state(status="active", iteration=1, max_iterations=2)

        self.assertEqual(loop_decision(state), {"action": "wait", "reason": "iteration not terminal"})

    def test_loop_treats_ready_for_cleanup_as_terminal(self) -> None:
        state = self.loop_state(status="ready_for_cleanup", iteration=1, max_iterations=2)

        self.assertEqual(loop_decision(state), {"action": "continue", "next_iteration": 2})


if __name__ == "__main__":
    unittest.main()

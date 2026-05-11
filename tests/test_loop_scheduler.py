from __future__ import annotations

import unittest

from workflow.loop_scheduler import loop_decision


class LoopSchedulerTest(unittest.TestCase):
    def test_acyclic_mode_never_schedules_loop(self) -> None:
        state = {"mode": "acyclic", "status": "complete", "loop": {"enabled": False, "iteration": 1}}

        self.assertEqual(loop_decision(state), {"action": "not_loop", "reason": "mode is acyclic"})

    def test_loop_disabled_never_schedules_loop(self) -> None:
        state = {"mode": "loop", "status": "complete", "loop": {"enabled": False, "iteration": 1}}

        self.assertEqual(loop_decision(state), {"action": "not_loop", "reason": "loop disabled"})

    def test_loop_stops_at_max_iterations(self) -> None:
        state = {
            "mode": "loop",
            "status": "complete",
            "loop": {
                "enabled": True,
                "iteration": 10,
                "max_iterations": 10,
                "stop_on_convergence": False,
                "converged": False,
                "stop_reason": "",
            },
        }

        self.assertEqual(loop_decision(state), {"action": "stop", "reason": "max_iterations"})

    def test_loop_continues_before_max_iterations(self) -> None:
        state = {
            "mode": "loop",
            "status": "complete",
            "loop": {
                "enabled": True,
                "iteration": 9,
                "max_iterations": 10,
                "stop_on_convergence": False,
                "converged": False,
                "stop_reason": "",
            },
        }

        self.assertEqual(loop_decision(state), {"action": "continue", "next_iteration": 10})

    def test_loop_stops_on_convergence(self) -> None:
        state = {
            "mode": "loop",
            "status": "complete",
            "loop": {
                "enabled": True,
                "iteration": 2,
                "max_iterations": None,
                "stop_on_convergence": True,
                "converged": True,
                "stop_reason": "",
            },
        }

        self.assertEqual(loop_decision(state), {"action": "stop", "reason": "converged"})

    def test_loop_a_plus_b_uses_either_stop(self) -> None:
        state = {
            "mode": "loop",
            "status": "complete",
            "loop": {
                "enabled": True,
                "iteration": 2,
                "max_iterations": 10,
                "stop_on_convergence": True,
                "converged": True,
                "stop_reason": "",
            },
        }

        self.assertEqual(loop_decision(state), {"action": "stop", "reason": "converged"})

    def test_loop_waits_when_acyclic_iteration_not_terminal(self) -> None:
        state = {
            "mode": "loop",
            "status": "active",
            "loop": {
                "enabled": True,
                "iteration": 1,
                "max_iterations": 2,
                "stop_on_convergence": False,
                "converged": False,
                "stop_reason": "",
            },
        }

        self.assertEqual(loop_decision(state), {"action": "wait", "reason": "iteration not terminal"})

    def test_loop_treats_ready_for_cleanup_as_terminal(self) -> None:
        state = {
            "mode": "loop",
            "status": "ready_for_cleanup",
            "loop": {
                "enabled": True,
                "iteration": 1,
                "max_iterations": 2,
                "stop_on_convergence": False,
                "converged": False,
                "stop_reason": "",
            },
        }

        self.assertEqual(loop_decision(state), {"action": "continue", "next_iteration": 2})


if __name__ == "__main__":
    unittest.main()

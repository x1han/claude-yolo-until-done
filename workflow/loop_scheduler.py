#!/usr/bin/env python3
from __future__ import annotations

TERMINAL_ITERATION_STATUSES = {"complete", "ready_for_cleanup"}


def loop_decision(state: dict) -> dict:
    if state.get("mode", "acyclic") != "loop":
        return {"action": "not_loop", "reason": "mode is acyclic"}

    loop = state.get("loop")
    if not isinstance(loop, dict) or not loop.get("enabled"):
        return {"action": "not_loop", "reason": "loop disabled"}

    if state.get("status") not in TERMINAL_ITERATION_STATUSES:
        return {"action": "wait", "reason": "iteration not terminal"}

    if loop.get("stop_on_convergence") and loop.get("converged"):
        return {"action": "stop", "reason": "converged"}

    iteration = loop.get("iteration")
    max_iterations = loop.get("max_iterations")
    if not isinstance(iteration, int) or isinstance(iteration, bool) or iteration < 1:
        return {"action": "stop", "reason": "invalid_loop_state"}
    if max_iterations is not None:
        if not isinstance(max_iterations, int) or isinstance(max_iterations, bool) or max_iterations < 1:
            return {"action": "stop", "reason": "invalid_loop_state"}
        if iteration >= max_iterations:
            return {"action": "stop", "reason": "max_iterations"}

    return {"action": "continue", "next_iteration": iteration + 1}

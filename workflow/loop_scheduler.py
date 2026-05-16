#!/usr/bin/env python3
from __future__ import annotations

TERMINAL_ITERATION_STATUSES = {"complete", "ready_for_cleanup"}
WHOLE_EXECUTION_TITLE = "Execute approved spec and plan"


def loop_execution_unit_problem(state: dict) -> str:
    if state.get("mode", "acyclic") != "loop":
        return ""
    loop = state.get("loop")
    if not isinstance(loop, dict) or not loop.get("enabled"):
        return ""
    task_inputs = state.get("task_inputs")
    if not isinstance(task_inputs, dict) or not task_inputs:
        return "loop task_inputs missing complete approved spec/plan execution unit"
    if task_inputs.get("task_id") != "task-001":
        return "loop task_inputs points at a plan section instead of the complete approved spec/plan"
    if task_inputs.get("task_title") != WHOLE_EXECUTION_TITLE:
        return "loop task_inputs title is not the complete approved spec/plan execution unit"
    if state.get("task_title") and state.get("task_title") != WHOLE_EXECUTION_TITLE:
        return "loop state task_title is not the complete approved spec/plan execution unit"
    plan_text = task_inputs.get("plan_task_text")
    if not isinstance(plan_text, str) or not plan_text.strip():
        return "loop task_inputs missing complete plan text"
    plan_sections = task_inputs.get("plan_sections")
    if isinstance(plan_sections, list):
        for section in plan_sections:
            if not isinstance(section, dict):
                continue
            if task_inputs.get("task_id") == section.get("task_id"):
                return "loop task_inputs points at a plan section instead of the complete approved spec/plan"
    return ""


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

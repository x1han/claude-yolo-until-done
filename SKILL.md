---
name: claude-yolo-until-done
description: Use when running Claude Code with hooks and an existing superpowers-generated execution bundle, and the agent must keep fixing, verifying, and continuing until explicit completion gates pass without repeatedly handing control back to the user.
---
# Claude YOLO Until Done

## Overview
This is a Claude Code only execution skill for high-autonomy fix, verify, and continue workflows.

Core rule: this skill does not create plans. It may run only after `superpowers` has already produced an approved execution bundle with explicit gates, checkoff markers, and completion criteria.

This skill is a fail-closed workflow, not a general coding prompt. If its runtime, inputs, or hooks are incomplete, it must stop instead of improvising.

## Required Operating Mode
- Treat this directory as a multi-file workflow, not a single prompt.
- `superpowers` is mandatory. If it is not installed, this workflow must fail closed and stop.
- Claude Code hooks are mandatory. If hooks are unavailable, this workflow must fail closed and stop.
- `--dangerously-skip-permissions` is mandatory. If it was not enabled for the current Claude Code run, this workflow must fail closed and stop.
- A complete superpowers-generated execution bundle is mandatory. If the bundle is missing or incomplete, this workflow must fail closed and stop.
- This skill may consume a plan, continue a run, repair failures, verify progress, update state, and advance gates.
- This skill may not replace planning, rewrite scope silently, or downgrade gates because the current session is tired, compressed, or blocked.

## Required File Order
Read these files first:
- `policy/required-runtime.md`
- `policy/required-superpowers.md`
- `policy/required-inputs.md`
- `policy/invariants.md`
- `policy/failure-behavior.md`
- `policy/blocker-rules.md`
- `policy/completion-rules.md`
- `policy/hook-contract.md`
- `policy/run-state-contract.md`

Then load only the active stage file(s):
- `stages/01-validate-runtime-and-bundle.md`
- `stages/02-load-state-and-claim-next-step.md`
- `stages/03-execute-fix-loop.md`
- `stages/04-handle-blockers.md`
- `stages/05-final-acceptance.md`

## Required Artifacts
This workflow expects a superpowers-generated run bundle with at least:
- approved spec, typically under `docs/superpowers/specs/`
- approved implementation plan, typically under `docs/superpowers/plans/`
- `<run-root>/runtime_context.json`, with `artifacts/yolo/` as the default example run root
- `<run-root>/run_state.json`
- `<run-root>/gates.json`
- `<run-root>/checkoffs.json`
- `<run-root>/report.md`
- `<run-root>/resume.md`

Use the templates in `templates/` only to define the expected shape of those artifacts. Do not treat template presence as proof that a real run bundle exists.

## Hook Requirement
Use hooks to certify any gate that models commonly rationalize away.

Minimum hook-backed claims should cover:
- runtime and bundle validation
- stage advancement
- blocker classification
- completion readiness

No hook result means no pass claim for the corresponding gate.

## Anti-Bypass Rules
- Do not invent a plan inline.
- Do not continue from a vague request.
- Do not enter YOLO mode before `superpowers` has produced a complete approved execution bundle.
- Do not weaken a gate because context was compressed.
- Do not treat partial progress as completion.
- Do not ask the user what to do next unless a blocker matches the human-blocked whitelist.
- Do not stop after code changes without re-running the required verification step for the current gate.
- Do not treat a local summary, a chat recap, or a stale handoff as a substitute for the current run bundle.

## When Refactoring This Skill
Prefer moving enforceable checks into hooks and run-state validation instead of adding more prose here.

## Operator Docs
For real Claude Code hook installation and session integration, read `README.md`.

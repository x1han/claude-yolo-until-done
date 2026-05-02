---
name: claude-yolo-until-done
description: Use when running Claude Code with hooks and an existing approved spec and plan, and the agent must keep fixing, verifying, and continuing through a lightweight worker/watcher workflow until valid completion.
---
# Claude YOLO Until Done

## Overview
This is a Claude Code only execution workflow for high-autonomy fix, verify, and continue loops.

Core rule: this skill does not create plans. It may run only after `superpowers` has already produced an approved spec and implementation plan.

This skill is a fail-closed workflow, not a general coding prompt. If its runtime, inputs, or hooks are incomplete, it must stop instead of improvising.

## Required Operating Mode
- Treat this directory as a multi-file workflow, not a single prompt.
- `superpowers` is mandatory. If it is not installed, this workflow must fail closed and stop.
- Claude Code hooks are mandatory. If hooks are unavailable, this workflow must fail closed and stop.
- `--dangerously-skip-permissions` is mandatory. If it was not enabled for the current Claude Code run, this workflow must fail closed and stop.
- An approved spec and approved implementation plan are mandatory.
- A lightweight run root is mandatory. If the durable state is missing or incomplete, this workflow must fail closed and stop.
- This skill may consume a plan, continue a run, repair failures, verify progress, update durable state, and advance worker/watcher transitions.
- This skill may not replace planning, rewrite scope silently, or weaken verification because the current session is tired, compressed, or blocked.

## Required File Order
Read these files first:
- `policy/required-runtime.md`
- `policy/required-superpowers.md`
- `policy/required-inputs.md`
- `policy/invariants.md`
- `policy/failure-behavior.md`
- `policy/completion-rules.md`
- `policy/hook-contract.md`
- `policy/run-state-contract.md`

Then work from the current lightweight runtime artifacts on disk.

## Required Artifacts
This workflow expects at least:
- approved spec, typically under `docs/superpowers/specs/`
- approved implementation plan, typically under `docs/superpowers/plans/`
- `<run-root>/state.json`, with `artifacts/yolo/` as the default example run root
- `<run-root>/trace.md`

Use the templates in `templates/` only to define the expected shape of those artifacts. Do not treat template presence as proof that a real run exists.

## Runtime Model
The durable status flow is:
- `active`
- `needs_review`
- `rework_required`
- `approved`
- `complete`

The worker may submit only with fresh verification evidence.

The watcher must review before completion and must record a structured review payload.

`state.json` is authoritative. `trace.md` is supporting audit evidence.

## Hook Requirement
Use hooks to certify claims that are easy to rationalize away.

Minimum hook-backed claims should cover:
- session restore from durable state
- early-stop blocking while work is incomplete
- submission readiness
- completion readiness

No hook output means no pass claim for the corresponding hook-backed decision.

## Anti-Bypass Rules
- Do not invent a plan inline.
- Do not continue from a vague request.
- Do not enter YOLO mode before `superpowers` has produced an approved spec and plan.
- Do not weaken watcher review.
- Do not treat partial progress as completion.
- Do not stop after code changes without re-running the required verification step for the current submission.
- Do not treat a local summary, a chat recap, or a stale handoff as a substitute for the current durable state.

## When Refactoring This Skill
Prefer moving enforceable checks into hooks and lightweight validators instead of adding more prose here.

## Operator Docs
For real Claude Code hook installation and session integration, read `README.md`.

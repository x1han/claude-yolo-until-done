---
name: claude-yolo-until-done
description: Use when turning vague request into stable grill-storm docs and then running Claude Code with hooks through lightweight worker/watcher workflow until valid completion.
---
# Claude YOLO Until Done

## Overview
This is Claude Code only workflow for grill-storm planning and high-autonomy fix, verify, and continue loops.

Core rule: first converge on approved spec and implementation plan through local docs, then execute approved plan through lightweight runtime.

Normal usage is simple: initialize local grill-storm bundle, let `Interviewer` and `Planner` converge on docs, then use `claude-yolo-until-done` to execute approved plan.

This skill is fail-closed workflow, not general coding prompt. If runtime, planning docs, inputs, or hooks are incomplete, it must stop instead of improvising.

## Recommended Usage
- Keep output folder as current working directory unless user names another one.
- Treat `docs/` inside output folder as default planning bundle.
- Treat `.yolo/` inside output folder as default run root.
- If user already provides exact spec and plan paths, use them directly.
- Do not invoke another execution skill for main run.

## Required Operating Mode
- Claude Code hooks are mandatory for execution phase. If hooks are unavailable, this workflow must fail closed and stop.
- `--dangerously-skip-permissions` is mandatory for execution phase. If it was not enabled for current Claude Code run, this workflow must fail closed and stop.
- Interactive Claude Code is mandatory for execution phase. Headless `claude -p` print mode is not supported because Stop-hook blocking cannot keep unfinished claude-yolo run alive there.
- preflight owns startup classification. If approved plan and spec exist but run root does not yet exist, preflight should bootstrap new run with `workflow/bootstrap.py` instead of failing just because `.yolo/` is absent.
- Only continue-run path should fail closed for missing durable state. Once run root already exists, missing or incomplete `state.json` or `trace.md` must block continuation.
- Planning mode should use shared docs as primary context, not chat history.
- Planning mode should use `Interviewer` and `Planner` in turn loop, with one key question at time and ask-late behavior.
- This skill may consume plan, continue run, repair failures, verify progress, update durable state, and advance worker/watcher transitions.
- This skill may not replace planning with hidden assumptions, rewrite scope silently, or weaken verification because current session is tired, compressed, or blocked.

## Startup Contract
- Planning start: initialize `docs/intent.md`, `docs/open-questions.md`, `docs/decisions.md`, `docs/spec.md`, and `docs/plan.md` with `workflow/init_grill_docs.py`.
- Planning loop: `Interviewer` and `Planner` should update at least one planning doc every round, record stable conclusions in `decisions.md`, and ask user only when blocking high-impact gap remains.
- New run default: approved grill-storm docs exist under `docs/spec.md` and `docs/plan.md`, pass `workflow/validate_grill_docs.py`, and `.yolo/` does not yet exist. preflight should bootstrap run root first, then install current local hook set, then continue execution.
- New run override: both `--spec` and `--plan` point to existing approved planning artifacts outside the default grill-storm docs.
- Planning-needed run: if default grill-storm docs are missing or draft, stop before bootstrap and report the planning action needed.
- Continue run: `.yolo/state.json` and `.yolo/trace.md` already exist. preflight should verify them, reinstall current local hook set if needed, and resume from durable state.
- Invalid run: if skill lacks either approved planning artifacts for new run, or coherent durable state for continue-run path, it must fail closed and stop.
- Legacy local hook settings are not blocker for new run. Install step is idempotent and should replace same-run claude-yolo hook groups with current contract.

## Required File Order
Read these files first:
- `policy/required-runtime.md`
- `policy/required-authoring.md`
- `policy/required-inputs.md`
- `policy/invariants.md`
- `policy/failure-behavior.md`
- `policy/completion-rules.md`
- `policy/hook-contract.md`
- `policy/run-state-contract.md`

Then run preflight before ordinary execution continues.

## Required Artifacts
This workflow expects at least:
- `docs/intent.md`
- `docs/open-questions.md`
- `docs/decisions.md`
- approved spec, typically under `docs/spec.md`
- approved implementation plan, typically under `docs/plan.md`
- `<run-root>/state.json`, with `.yolo/` as default example run root
- `<run-root>/trace.md`

When user does not specify output folder, treat current working directory as output folder and keep both `docs/` and `.yolo/` inside it by default.

Use templates in `templates/` only to define expected shape of runtime artifacts. Do not treat template presence as proof that real run exists.

## Planning Model
Planning loop should:
- prefer internal code and docs verification before asking user
- ask at most one user question per round
- include recommended answer or direction with every user question
- keep `spec.md` for stable requirements only
- grow `plan.md` only after spec is stable
- keep confirmed decisions in `decisions.md`
- keep blocking unknowns in `open-questions.md`
- keep agent talk grounded in docs instead of chat-only memory

## Runtime Model
Durable status flow is:
- `active`
- `needs_review`
- `rework_required`
- `approved`
- `ready_for_cleanup`

Worker may submit only with fresh verification evidence.

Watcher must review before completion and must record structured review payload.

Default mode is acyclic. Loop mode is selected only at preflight/bootstrap with `--mode loop` plus `--loop-max-iterations`, `--loop-stop-on-convergence`, or both. A+B uses either stop condition, and continue-run must fail closed on mode/config drift.

`state.json` is authoritative. `trace.md` is supporting audit evidence.

Role agent sessions are per `.yolo/` run. Reuse the same role agent for later dispatches to that role when possible.

`agent_sessions.json` stores role-agent routing metadata. It is not workflow authority. `state.json` remains authoritative.

Each role maintains a role lab notebook in `agents/<role>-log.md`: short caveman-style experimental records with hypothesis, actions, observations, result, and next.

## Hook Requirement
Use hooks to certify claims that are easy to rationalize away.

Minimum hook-backed claims should cover:
- session restore from durable state
- unfinished-work stop blocking
- three-way mounted-run prompt gating
- submission readiness
- completion readiness

No hook output means no pass claim for corresponding hook-backed decision.

## Anti-Bypass Rules
- Do not invent plan inline without updating shared planning docs.
- Do not continue from vague request directly into execution.
- Do not enter YOLO mode before approved spec and plan exist.
- Do not weaken watcher review.
- Do not treat partial progress as completion.
- Do not stop after code changes without re-running required verification step for current submission.
- Do not treat local summary, chat recap, or stale handoff as substitute for current durable state.
- Do not write unconfirmed assumptions as final conclusions.

## When Refactoring This Skill
Prefer moving enforceable execution checks into hooks and lightweight validators instead of adding more prose here. Prefer keeping planning-state rules in shared docs and agent prompts instead of hidden chat conventions.

## Operator Docs
For real Claude Code hook installation and session integration, read `README.md`.

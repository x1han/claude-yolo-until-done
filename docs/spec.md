# Spec

Status: approved

## Problem
- The workflow needs a loop execution mode that repeats one approved convergence plan for a bounded number of iterations without weakening the existing fail-closed acyclic worker/watcher lifecycle.
- Current human-facing UX and machine-facing workflow state are mixed too loosely: operators need clear assistant-like dialogue, while validators and controllers need stable structured records instead of brittle prose parsing.
- Durable workflow artifacts must remain predictable across agents, continuations, and validators even when the human dialogue language is not English.
- Manual worker, watcher, and controller operation paths are currently exposed mainly as Python script invocations with internal role/action details; operators need stable wrapper surfaces that do not require hand-written imports.

## Users
- Claude Code operators who use `claude-yolo-until-done` to plan and execute autonomous repair or convergence runs.
- Muse, Logos, worker, watcher, helper, and controller agents that depend on durable English planning and runtime records.
- Maintainers who validate workflow behavior through tests, hook reports, and state/trace artifacts.

## Desired Outcome
- A human-reviewed implementation can add loop mode as a small extension over the current acyclic execution core: one approved convergence plan is repeated for up to five iterations, each iteration fixes the highest-priority current real bench blocker, verifies the fix, records evidence, and stops early only when convergence is verified.
- Durable specs, plans, checklists, state files, traces, hook reports, validator records, and other machine-readable artifacts stay in English.
- Human-facing prompts, confirmations, status messages, and questions use the detected dialogue language, with explicit override support before inference from the latest substantive user request.
- Gate-critical automation consumes JSON state or validator records, or strict templates where human review remains primary, instead of parsing unconstrained narrative prose.
- Operator-facing commands or script wrappers cover worker, watcher, controller, gate validation, cleanup, and preflight paths using the existing repository command style unless packaging conventions introduce a clearer first-party CLI.
- Human-facing copy explains purpose, current state, needed confirmation, and next step in assistant-like language rather than procedural phrases such as "according to the workflow".
- The same loop searches for system-wide acceleration opportunities, prioritizes high-confidence speedups from current logs/failures, and verifies each speedup without weakening human gates, watcher review, hook validation, cleanup, or audit evidence.

## Requirements
- Must: preserve default acyclic semantics unless `--mode loop` is selected at preflight/bootstrap time.
- Must: require loop mode to include at least one stop policy: `--loop-max-iterations`, `--loop-stop-on-convergence`, or both.
- Must: support the intended candidate run shape of at most five convergence iterations for this request; fewer iterations are valid only when convergence is verified.
- Must: fail closed on continue-run mode or loop policy drift from authoritative `state.json`.
- Must: keep `state.json` authoritative for execution status, owner, next action, mode, loop config, current iteration, convergence flag, latest verification fields, and loop stop reason.
- Must: keep `trace.md` as chronological audit evidence without making it the source of truth over `state.json`.
- Must: keep hook and validator reports machine-readable JSON and include enough loop/state fields to detect tampering or stale completion evidence.
- Must: keep durable workflow artifacts and machine-readable schemas in English regardless of detected dialogue language.
- Must: detect human dialogue language from an explicit override when present; otherwise use the latest substantive user request as the current operator-facing language signal.
- Must: persist detected dialogue language in authoritative run state when it affects future prompts across continuation; trace may mention it only as audit context.
- Must: expose or document stable operator command surfaces for preflight, worker submit, watcher review, watcher complete, submission validation, completion validation, and cleanup without requiring operators to write Python imports.
- Must: verify assistant-like copy through targeted fixtures or snapshot expectations for known bench messages before considering broader tone tooling.
- Should: reuse the existing acyclic worker/watcher/controller lifecycle as the loop iteration body instead of creating a parallel scheduler.
- Should: choose the highest-priority current blocker or acceleration opportunity from current failures/logs at each iteration rather than preassigning all fixes at bootstrap.
- Should: measure acceleration candidates with timing, duplicate-work, manual-step, parser-round, or command-count evidence before treating them as improvements.
- Should: prioritize structured records for gate-critical paths: state transitions, watcher review, submission readiness, completion readiness, and loop iteration evidence.
- Should: keep wrapper names aligned with the current repository convention of direct scripts under `workflow/` and `hooks/` unless a packaging entrypoint is added deliberately.
- Nice-to-have: add a narrow phrase checker later if fixture-based copy tests do not prevent procedural wording regressions.

## User Flows
1. Planning flow:
   - Muse and Logos converge on the loop-mode candidate in English durable docs.
   - The main session asks one human-facing consensus question in the detected dialogue language.
   - Only after verified human consensus may Logos move this draft spec toward human spec review and later plan authoring.
2. New loop run flow:
   - Operator starts from approved `docs/spec.md` and `docs/plan.md`.
   - Operator runs preflight with `--mode loop --loop-max-iterations 5` and optionally `--loop-stop-on-convergence`.
   - Preflight validates approved docs, verifies runtime, bootstraps `.yolo/state.json`, `.yolo/trace.md`, checklist, hooks, and loop config.
   - Worker executes the current iteration plan body, fixes the highest-priority current blocker or acceleration opportunity, verifies, and submits with evidence and convergence status.
   - Watcher reviews the submitted evidence and either requests rework or approves the iteration.
   - Controller completes the iteration, advances to the next iteration when stop policy has not fired, or records a stop reason and prepares cleanup when convergence or max iterations stops the loop.
3. Continue-run flow:
   - Operator resumes with existing `.yolo/state.json` and `.yolo/trace.md`.
   - Preflight validates that supplied mode and loop policy match `state.json`.
   - Runtime resumes from `state.json` owner/next action and keeps dialogue language stable if it was persisted.
4. Human dialogue flow:
   - Workflow prompts and status messages use the detected dialogue language while preserving exact English state names and commands when needed for operator accuracy.
   - Messages explain what happened, why confirmation is needed, and what will happen next.

## Acceptance Criteria
- [ ] Preflight/bootstrap tests cover `--mode loop --loop-max-iterations 5`, optional convergence stop, rejection of loop policy in acyclic mode, and fail-closed continue-run mode/config drift.
- [ ] Controller or scheduler tests prove an approved loop iteration either advances to the next iteration with reset worker/watcher fields or stops with `loop.stop_reason` when convergence or max iterations fires.
- [ ] Completion validator tests prove loop stop reason and loop config are covered by machine-readable certification or equivalent structured evidence and tampering is rejected.
- [ ] State/trace/hook report expectations show `state.json` remains authoritative while `trace.md` records chronological audit entries for each worker submit, watcher review, watcher complete, and loop iteration boundary.
- [ ] Language handling tests prove durable artifacts remain English while human-facing messages use explicit override first and latest substantive user request second.
- [ ] Wrapper or command-surface tests/docs show operators can run preflight, worker submit, watcher review, watcher complete, submission validation, completion validation, and cleanup without writing Python imports.
- [ ] Copy fixtures or snapshots cover known bench phrases, including replacement of procedural wording such as "according to the workflow" with assistant-like text that states purpose, current state, needed confirmation, and next step.
- [ ] Loop evidence includes acceleration review for each iteration, with accepted speedups tied to timing, duplicate-work, manual-step, parser-round, or command-count evidence and rejected speedups documented when unsafe.
- [ ] Grill-storm validation still blocks execution until verified human consensus, human spec review, and human plan review are recorded.

## Risks
- Loop mode could accidentally weaken acyclic fail-closed guarantees if it bypasses watcher review or completion validation; mitigation is to reuse the existing lifecycle and require structured loop stop evidence.
- Language detection could become speculative or overbuilt; mitigation is explicit override first, latest substantive user request second, and no broad localization framework in this slice.
- Wrapper naming could churn if a packaging CLI is introduced later; mitigation is to align initially with the existing script-based command surface and document stable roles/actions.
- Copy verification could become subjective; mitigation is to start with known bench phrases and fixture expectations, not a broad style lint system.
- Acceleration work could tempt unsafe shortcuts; mitigation is to require evidence-backed speedups and preserve human approvals, watcher review, hook-backed validation, cleanup checks, and durable audit records.

## Out of Scope
- Marking this spec or any plan as human-approved before the main session records verified human approval.
- Replacing the worker/watcher lifecycle, watcher review, completion validation, or Claude Code hook requirements.
- Localizing durable specs, plans, checklists, state, trace, hook reports, validator records, policy files, or schemas.
- Building a general internationalization framework beyond dialogue language detection for human-facing workflow messages.
- Splitting the request into five independent acyclic tasks or allowing each loop iteration to invent unrelated scope.
- Designing a full packaging or release CLI unless existing repository conventions already support it.

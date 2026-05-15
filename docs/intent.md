# Intent

## Primary Goal
- Add a loop-mode planning and execution shape for `claude-yolo-until-done` that repeats one approved convergence plan for up to five iterations, fixing the highest-priority real bench blocker each time, verifying after each fix, recording evidence, and stopping early only when convergence is verified.
- Preserve English as the language for durable workflow artifacts: spec, plan, checklist, state, trace, hook reports, validator records, and other machine-readable docs.
- Detect the human dialogue language during preflight from the user conversation language and use that language only for human-facing prompts, confirmations, status messages, and questions.
- Replace brittle parsing of human-readable prose with machine-readable records or strict templates wherever workflow automation currently depends on parsed text.
- Encapsulate worker, watcher, and controller manual operation paths behind stable commands or scripts so operators do not hand-write Python imports.
- Improve human-facing wording so it reads like an assistant explaining purpose, current state, needed confirmation, and next step rather than procedural phrases such as "according to the workflow".
- Find system-wide acceleration opportunities during the same repeated convergence loop, prioritize the highest-confidence speedup each iteration, and verify that acceleration does not weaken approval gates, watcher review, cleanup, or audit evidence.

## Why This Matters
- The current bench failures point to a mismatch between human-facing UX and machine-facing workflow state: prose should serve people, while validators and controllers should consume structured records.
- The real bench also exposed slow planning and operator overhead, so each loop iteration should search for speedups that preserve fail-closed safety.
- Loop mode should make convergence work repeatable without turning one approved plan into ad hoc task splitting.
- Language handling must be predictable: operators can interact naturally in their language, while durable artifacts remain stable for tools, validators, and future agents.
- Manual operational paths should be usable by operators who understand workflow concepts but should not need to remember internal module paths or Python import forms.

## Non-Goals
- Do not change the default acyclic execution semantics except where loop mode reuses existing acyclic steps as one iteration body.
- Do not localize machine-readable docs, policy files, state files, traces, hook reports, or validator payloads.
- Do not implement broad internationalization; this request only needs preflight language detection for human-facing workflow dialogue.
- Do not replace watcher review or completion validation with loop iteration counts.
- Do not use hidden chat assumptions as workflow authority; all stable conclusions must be reflected in planning docs and later in approved spec/plan.

## Constraints
- Time: Plan for a compact, testable implementation that can be executed in repeated convergence iterations without manual replanning between iterations.
- Tech: Align with the fail-closed workflow model, hook-backed claims, `state.json` as authority, `trace.md` as audit evidence, and existing grill-storm docs.
- Compatibility: Continue-run must fail closed on mode/config drift; new loop runs must record loop mode and stop policy at bootstrap/preflight time.
- Budget: Prefer small extensions over rewrites; use machine-readable sidecars or strict templates where they reduce validator/parser brittleness without overbuilding.

## Preferences
- Prefer: One approved convergence plan with loop metadata, structured iteration records, explicit verification evidence, and early-stop convergence criteria.
- Prefer: Human-facing messages that are direct, helpful, and localized to the detected dialogue language while keeping exact workflow state names stable when necessary.
- Prefer: Operator commands that mirror workflow roles and actions, for example controller/worker/watcher entrypoints, rather than import snippets.
- Avoid: Parsing unconstrained narrative Markdown for state transitions, decisions, review payloads, or verification evidence.
- Avoid: Treating loop iteration count as success; convergence must be verified.
- Prefer: Measurable acceleration work that removes avoidable waiting, duplicate parsing, repeated manual commands, or unnecessary planning rounds without bypassing required gates.
- Avoid: Adding speculative localization frameworks or broad UX redesign beyond the four bench problems.
- Avoid: Speedups that skip human approvals, watcher review, hook-backed validation, cleanup checks, or durable evidence.

## Assumptions
- The requested "five repeated convergence iterations" means a maximum of five iterations, not exactly five if verified convergence occurs sooner.
- Each loop iteration should choose the highest-priority current blocker from current failures/logs rather than preassigning all five fixes at bootstrap.
- English durable docs are a hard requirement even when human dialogue is not English.
- Existing acyclic worker/watcher/controller behavior remains the core execution body; loop mode wraps and records repeated passes.

## Internal Consensus Candidate
- Recommended candidate for human review: implement one loop-mode convergence plan repeated up to five iterations, with English durable artifacts, localized human dialogue, structured gate records, stable worker/watcher/controller wrappers, and assistant-like copy.
- This is an internal consensus candidate only; it is not human-approved spec or plan authority.

## Resolved Internally
- Dialogue language detection should prefer an explicit override when available; otherwise use the most recent substantive user request as the current operator-facing language signal.
- Gate-critical parser/validator paths should move first: state transitions, watcher review, submission readiness, completion readiness, and loop iteration evidence.
- Loop iteration evidence should keep `state.json` authoritative for loop mode/config/current iteration/latest verification summary, use `trace.md` for chronological audit entries, and use validator reports for machine-readable checks.
- Machine-readable records should use JSON for state-like and hook/validator records; strict Markdown templates are acceptable only where human review remains primary.
- Human-facing wording verification should start with fixture or snapshot expectations for known bench messages, not a broad style framework.

## Remaining Unknowns
- Human approval is still needed before this candidate can become approved spec/plan scope.
- Logos should inspect existing CLI/package conventions before finalizing exact worker/watcher/controller command names.
- Additional human-facing phrase rewrites should be discovered from known bench messages and nearby fixtures rather than guessed broadly.

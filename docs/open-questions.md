# Open Questions

## High Priority
- [ ] Does the human approve the internal consensus candidate as the basis for spec drafting and plan authoring?
  - Recommended direction: approve the candidate as written: one loop-mode convergence plan repeated up to five iterations, English durable artifacts, localized human dialogue, structured gate records, stable worker/watcher/controller wrappers, and assistant-like copy.
  - Blocking: yes for marking spec/plan approved; no for further internal Logos feasibility narrowing.

## Medium Priority
- [ ] Which exact command names should ship for worker/watcher/controller wrappers after Logos inspects existing CLI/package conventions?
  - Recommended direction: prefer existing CLI style if present; otherwise use role/action subcommands that hide Python imports while preserving direct module entrypoints internally.
  - Blocking: no for human approval of scope; yes before final implementation plan details.

## Low Priority
- [ ] Are there any additional human-facing phrases beyond known procedural examples that should be rewritten in the first implementation slice?
  - Recommended direction: start with known bench messages and exact procedural phrases such as "according to the workflow"; expand only when tests or review reveal nearby copy drift.
  - Blocking: no.

## Answered Recently

## Answered Internally
- [x] Question: Should preflight detect human dialogue language from the most recent user message, the dominant conversation language, or an explicit override when available?
  Answer: Use explicit override first when available; otherwise use the most recent substantive user request as the practical dialogue-language source for current prompts.
  Impact: Spec can define language detection without requiring a broad i18n framework.
- [x] Question: Which parser/validator paths should be converted first to machine-readable records or strict templates?
  Answer: Prioritize gate-critical paths: state transitions, watcher review, submission readiness, completion readiness, and loop iteration evidence.
  Impact: Logos can inventory concrete files while keeping implementation scope focused on workflow advancement gates.
- [x] Question: What minimal loop iteration record belongs in durable artifacts?
  Answer: `state.json` should hold authoritative loop mode/config/current iteration/latest verification summary; `trace.md` should hold chronological audit entries; validator reports should hold machine-readable checks.
  Impact: Plan can avoid duplicating source-of-truth fields while still proving timing and evidence.
- [x] Question: Should human-facing wording rules be enforced by tests, fixture snapshots, a lint-like checker, or reviewer checklist?
  Answer: Start with fixture/snapshot expectations for known bench messages; add a narrow checker only if phrase drift recurs.
  Impact: Keeps the first slice testable without overbuilding a style system.
- [x] Question: Should detected dialogue language be persisted in run state, trace metadata, or both?
  Answer: Persist it in authoritative run state if it affects future prompts; mention it in trace only for audit readability.
  Impact: Future prompts can remain stable across continuation without making trace authoritative.
- [x] Question: Should machine-readable records be JSON, JSONL, YAML, or embedded fenced blocks in Markdown?
  Answer: Use JSON for validator/hook reports and state-like records; use strict Markdown templates only where human review remains primary.
  Impact: Aligns with existing state/hook patterns and reduces parser ambiguity.
- [x] Question: Should loop mode split the work into five independent subtasks?
  Answer: No. The user wants one approved convergence plan repeated for up to five iterations.
  Impact: Spec and plan should model a repeated iteration body with stop policies, not acyclic task fan-out.
- [x] Question: Should machine-readable docs follow detected human dialogue language?
  Answer: No. Durable spec, plan, checklist, state, trace, and machine-readable records stay English.
  Impact: Language detection applies only to human-facing prompts and status dialogue.

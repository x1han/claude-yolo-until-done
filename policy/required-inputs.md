# Required Inputs

Before workflow starts, first classify run type.

## New run

A new run requires all of following:

- one approved spec, typically under `docs/spec.md`
- one approved implementation plan, typically under `docs/plan.md`
- if grill-storm planning is in use, planning bundle under `docs/` should also include `intent.md`, `open-questions.md`, and `decisions.md`
- no existing durable run bundle at `<run-root>/state.json` and `<run-root>/trace.md`

In this branch, preflight should bootstrap run root before ordinary execution continues.

## Continue run

A continue-run requires all of following:

- one approved spec, typically under `docs/spec.md`
- one approved implementation plan, typically under `docs/plan.md`
- `<run-root>/state.json` where default example run root is `.yolo/`
- `<run-root>/trace.md`

Durable run root must identify:

- active goal
- success criteria
- current workflow status
- current owner and next action
- active verification evidence
- current review payload, if review has happened

Do not proceed if files exist but still contain template-only values or unresolved placeholders.
Do not proceed if only one of `state.json` or `trace.md` exists; mixed bundle state must fail closed.

# Required Inputs

Before the workflow starts, first classify the run type.

## New run

A new run requires all of the following:

- one approved spec, typically under `docs/superpowers/specs/`
- one approved implementation plan, typically under `docs/superpowers/plans/`
- no existing durable run bundle at `<run-root>/state.json` and `<run-root>/trace.md`

In this branch, preflight should bootstrap the run root before ordinary execution continues.

## Continue run

A continue-run requires all of the following:

- one approved spec, typically under `docs/superpowers/specs/`
- one approved implementation plan, typically under `docs/superpowers/plans/`
- `<run-root>/state.json` where the default example run root is `.yolo/`
- `<run-root>/trace.md`

The durable run root must identify:

- the active goal
- the success criteria
- the current workflow status
- the current owner and next action
- the active verification evidence
- the current review payload, if review has happened

Do not proceed if files exist but still contain template-only values or unresolved placeholders.
Do not proceed if only one of `state.json` or `trace.md` exists; that mixed bundle state must fail closed.

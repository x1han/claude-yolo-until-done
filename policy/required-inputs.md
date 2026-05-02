# Required Inputs

Before the workflow starts, all of the following must exist and be current:

- one approved spec, typically under `docs/superpowers/specs/`
- one approved implementation plan, typically under `docs/superpowers/plans/`
- `<run-root>/state.json` where the default example run root is `artifacts/yolo/`
- `<run-root>/trace.md`

The durable run root must identify:

- the active goal
- the success criteria
- the current workflow status
- the current owner and next action
- the active verification evidence
- the current review payload, if review has happened

Do not proceed if files exist but still contain template-only values or unresolved placeholders.

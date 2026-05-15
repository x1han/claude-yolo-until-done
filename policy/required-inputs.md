# Required Inputs

Before workflow starts, first classify run type.

## New run

A new run requires all of following:

- default path: approved grill-storm docs under `docs/spec.md` and `docs/plan.md`, plus `docs/intent.md`, `docs/open-questions.md`, and `docs/decisions.md`
- override path: both `--spec` and `--plan` point to existing approved planning artifacts
- no existing durable run bundle at `<run-root>/state.json` and `<run-root>/trace.md`

In this branch, preflight should bootstrap run root before ordinary execution continues.

Default execution mode is acyclic. To repeat the same approved plan, choose loop mode at startup with `--mode loop` and at least one stop policy: `--loop-max-iterations`, `--loop-stop-on-convergence`, or both. Loop mode: repeat the same complete approved spec/plan; fixed loop N means N complete acyclic executions, convergence-only loop uses default max 10, and agents must not pre-plan future loop iterations. A+B uses either stop condition.

## Continue run

A continue-run requires all of following:

- one approved spec, typically under `docs/spec.md`
- one approved implementation plan, typically under `docs/plan.md`
- `<run-root>/state.json` where default example run root is `.yolo/`
- `<run-root>/trace.md`

Continue-run must use the same mode/config already stored in `state.json`; mode/config drift must fail closed before execution resumes.

Durable run root must identify:

- active goal
- success criteria
- current workflow status
- current owner and next action
- active verification evidence
- current review payload, if review has happened

Do not proceed if files exist but still contain template-only values or unresolved placeholders.
Do not proceed if only one of `state.json` or `trace.md` exists; mixed bundle state must fail closed.

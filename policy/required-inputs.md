# Required Inputs

Before workflow starts, first classify run type.

Preflight reports one explicit operator action: `init_planning`, `continue_planning`, `await_human_approval`, `bootstrap_execution`, `resume_execution`, or `repair_state`. Each blocked report includes current state, evidence, blocked-on item, and next safe action.

## New run

A new run requires all of following:

- default path: approved grill-storm docs under `docs/spec.md` and `docs/plan.md`, plus `docs/intent.md`, `docs/open-questions.md`, and `docs/decisions.md`
- override path: both `--spec` and `--plan` point to existing approved, execution-ready planning artifacts; draft or incomplete artifacts return `continue_planning`
- no existing durable run bundle at `<run-root>/state.json` and `<run-root>/trace.md`

In this branch, preflight should bootstrap run root before ordinary execution continues.

Default execution mode is acyclic. To repeat the same approved plan, choose loop mode at startup with `--mode loop` and at least one stop policy: `--loop-max-iterations`, `--loop-stop-on-convergence`, or both. Loop mode repeats the same complete approved spec/plan; fixed loop N means N complete acyclic executions, convergence-only loop uses default max 10, and agents must not pre-plan future loop iterations. A+B uses either stop condition.

Loop mode must keep `task_inputs` pointed at the complete approved spec/plan execution unit: `task-001`, titled `Execute approved spec and plan`, with the complete approved spec/plan text. Parsed plan sections are review context only and must not become loop iterations. The controller derives loop `selected_work` from this authoritative task input; operators and workers do not choose it with CLI text.

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

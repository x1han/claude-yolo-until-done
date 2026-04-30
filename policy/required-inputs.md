# Required Inputs

Before the workflow starts, all of the following must exist and be current:

- one approved spec, typically under `docs/superpowers/specs/`
- one approved implementation plan, typically under `docs/superpowers/plans/`
- `<run-root>/runtime_context.json` where the default example run root is `artifacts/yolo/`
- `<run-root>/run_state.json`
- `<run-root>/gates.json`
- `<run-root>/checkoffs.json`
- `<run-root>/report.md`
- `<run-root>/resume.md`

The run bundle must identify:

- the runtime and permission mode used for the current Claude Code run
- the active plan path
- the current stage
- the current target or issue
- the active verification target
- the completion gates
- the human-blocked whitelist

Do not proceed if files exist but still contain template-only values or unresolved placeholders.

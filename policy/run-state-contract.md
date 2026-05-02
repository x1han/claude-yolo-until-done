# Run State Contract

`<run-root>/state.json` is the authoritative execution state for this workflow.

`<run-root>/trace.md` is secondary operator-facing context. It records the activity trail, but when `trace.md` and `state.json` disagree, `state.json` wins.

## Required `state.json` fields

It must always contain at least:

- `goal`
- `success_criteria`
- `status`
- `worker_claim`
- `files_changed`
- `verification_command`
- `verification_result`
- `submitted_at`
- `review`
- `reviewed_at`
- `owner`
- `next_action`
- `plan_path`
- `spec_path`
- `updated_at`

## Rules

- update `state.json` after every material execution step
- use repository-relative examples and paths when documenting or templating workflow state
- never rely on memory when `state.json` disagrees with memory
- if `state.json` is missing a required field, fail closed and stop
- `trace.md` may summarize or elaborate, but it does not override `state.json`

# Run State Contract

`<run-root>/state.json` is the authoritative execution state for this workflow.

`<run-root>/trace.md` is secondary operator-facing context. It records the activity trail, but when `trace.md` and `state.json` disagree, `state.json` wins.

## Role agent session files

`agent_sessions.json` is per `.yolo/` run and stores role-agent routing metadata only.

Role dispatch metadata includes `agent_id` and runtime routing. `create` creates the role agent once for that generation. `reuse` must resume/send to exactly the stored `agent_id`; it must not create a fresh role agent. Replacement is explicit only and creates a new generation.

Each role lab notebook lives under `agents/<role>-log.md`. It preserves concise operational context for later continuation or explicit replacement.

These files do not override `state.json`. If they are missing, runtime may recreate them. If malformed, runtime fails closed or repairs without mutating workflow state.

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
- `cleanup_required`
- `plan_path`
- `spec_path`
- `updated_at`

## Rules

- update `state.json` after every material execution step
- use repository-relative examples and paths when documenting or templating workflow state
- never rely on memory when `state.json` disagrees with memory
- if `state.json` is missing a required field, fail closed and stop
- `trace.md` may summarize or elaborate, but it does not override `state.json`

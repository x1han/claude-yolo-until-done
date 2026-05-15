# Run State Contract

`<run-root>/state.json` is the authoritative execution state for this workflow.

`<run-root>/trace.md` is secondary operator-facing context. It records the activity trail, but when `trace.md` and `state.json` disagree, `state.json` wins.

## Role-agent routing metadata

`agent_sessions.json` is per `.yolo/` run and stores role-agent routing metadata only. It is not workflow authority; `state.json` remains authoritative for task status, owner, gates, dispatch status, and completion.

Each role session has:
- `role_invocation_id`: workflow-generated role/generation audit id.
- `last_runtime_agent_id`: last observed Agent tool id for audit trail.
- `generation`: explicit replacement lineage.
- `continuity_model: project_memory`.
- project memory path under `.claude/agent-memory/<role>/MEMORY.md`.
- role log and summary paths under `.yolo/agents/`.

`session_action=create` means create fresh Agent subagent for that turn. Continuity comes from project memory, role log, role summary, and shared docs/state, not exact hidden runtime-agent reuse. `last_runtime_agent_id` is audit-only in this model. Replacement is explicit only.

Each role lab notebook lives under `agents/<role>-log.md`. It preserves concise operational context for later continuation or explicit replacement. Create fresh Agent subagent for this turn, then hydrate from durable context before work.

These files do not override `state.json`. If they are missing, runtime may recreate them. If malformed, runtime fails closed or repairs without mutating workflow state.

## Execution unit

`task_inputs` is one authoritative execution unit for the run. It contains the complete approved spec/plan that worker and watcher use for the acyclic lifecycle. Parsed plan headings may appear as derived review context, but they are not schedulable runtime tasks.

Acyclic mode executes this unit once. Loop mode: repeat the same complete approved spec/plan as the acyclic execution unit; fixed loop N means N complete acyclic executions. Convergence-only loop uses default max 10. Each iteration rereads current state and evidence, then executes the complete unit again or stops by policy. Agents and operators must not pre-plan future loop iterations or treat parsed plan sections as loop slices; do not pre-plan future loop iterations.

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

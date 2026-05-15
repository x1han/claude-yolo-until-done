# Persistent Memory Role Agents Design

## Problem

`claude-yolo-until-done` currently models role continuity as exact runtime Agent reuse by `runtime_agent_id`. Real5 proved this contract is not executable in the current Claude Code tool surface: the workflow can record an Agent tool `agentId`, but this environment does not expose a callable send/resume-by-agent-id tool. Creating a fresh Agent as fallback would violate the exact-reuse contract and hide the failure.

Claude Code subagent persistent memory provides a supported alternative: each role invocation can be a fresh subagent while role continuity comes from project memory, run-scoped role logs, and shared planning/workflow docs.

## Goals

- Replace exact live-subagent reuse with official Claude Code subagent project memory continuity.
- Keep roles durable across fresh invocations: Muse, Logos, Worker, Watcher, Helper.
- Preserve auditability through `.yolo/` role logs, `state.json`, `trace.md`, and dispatch metadata.
- Stop promising unsupported `resume_by_agent_id` behavior.
- Fail closed when required memory/log/state files are unavailable or malformed.
- Keep `state.json` as workflow authority; role registry remains routing/audit metadata only.

## Non-goals

- Do not use Agent Teams; user does not want separate Claude Code sessions.
- Do not implement or depend on unavailable `SendMessage`/subagent-resume tool APIs.
- Do not create fresh agents while claiming exact live reuse.
- Do not move workflow authority into role memory or agent registry.
- Do not store task-specific chatter, full diffs, secrets, or transient logs in long-term memory.

## Architecture

The workflow becomes a Persistent Role Agents model, not Persistent Live Agents.

Each role invocation is a fresh Claude Code subagent. Continuity comes from three durable layers:

1. Claude Code project memory: `.claude/agent-memory/<role>/MEMORY.md`
2. Run role log: `.yolo/agents/<role>-log.md` and summary file
3. Shared workflow docs/state: `docs/*.md`, `.yolo/state.json`, `.yolo/trace.md`

The main session dispatches a fresh Agent for each role turn. The dispatch prompt requires the role to load its memory, read its run log, read the assigned docs/state, do the role work, update the run log, and update memory only with durable learnings.

## Role agent definitions

All shipped role definitions must use Claude Code subagent project memory:

```yaml
memory: project
```

Affected role files:

- `.claude/agents/muse.md`
- `.claude/agents/logos.md`
- `.claude/agents/worker.md`
- `.claude/agents/watcher.md`
- `.claude/agents/helper.md`

Each role prompt must state:

- Read relevant project memory before work.
- Read the run role log before work.
- Read dispatch-required docs/state before work.
- Update role log after work.
- Update memory only with durable project or role learnings.
- Keep `MEMORY.md` concise and curated.
- Do not store secrets, full diffs, task chatter, or unverified guesses.

Role-specific write authority:

- Muse/Logos may update planning docs and their own memory; they must not edit shipped code.
- Worker may edit shipped code when task packet authorizes it and may update own memory.
- Watcher reviews and writes review/log/memory artifacts; it must not fix source code during review.
- Helper follows its task packet and records only durable learnings in own memory.

## Memory files

Bootstrap or installation must ensure these files exist:

```text
.claude/agent-memory/muse/MEMORY.md
.claude/agent-memory/logos/MEMORY.md
.claude/agent-memory/worker/MEMORY.md
.claude/agent-memory/watcher/MEMORY.md
.claude/agent-memory/helper/MEMORY.md
```

Default `MEMORY.md` shape:

```markdown
# <role> memory

## Role Conventions

## Project Conventions

## Risky Areas

## Reliable Verification

## Recurring Issues
```

Claude Code injects only the beginning of `MEMORY.md`, so each memory file should stay under 200 lines where practical. Detailed durable notes may live in focused files in the same role memory directory, but `MEMORY.md` must remain the index.

## Registry schema

Keep `.yolo/agent_sessions.json` for now to avoid a broad migration. Its meaning changes from live-session routing to role invocation audit metadata.

Version 2 role entry:

```json
{
  "role_invocation_id": "logos-3-...",
  "last_runtime_agent_id": "ae6d68f...",
  "generation": 3,
  "status": "active",
  "continuity_model": "project_memory",
  "memory_scope": "project",
  "memory_path": ".claude/agent-memory/logos/MEMORY.md",
  "role_log_path": ".yolo/agents/logos-log.md",
  "summary_path": ".yolo/agents/logos-summary.md",
  "created_at": "...",
  "last_seen_at": "...",
  "last_dispatch_owner": "grill-storm-loop"
}
```

`last_runtime_agent_id` is audit evidence only. It is never a required resume handle and never controls dispatch.

Migration from current schema:

- `role_session_id` becomes `role_invocation_id`.
- `runtime_agent_id` becomes `last_runtime_agent_id`.
- `agent_runtime`, `resume_by_agent_id`, and `must_resume_exact_agent_id` are removed from new dispatch payloads.
- Missing memory files are initialized; malformed registry still fails closed.

## Dispatch contract

New dispatch payload uses project-memory continuity:

```json
{
  "dispatch_action": "create",
  "continuity_model": "project_memory",
  "role_invocation_id": "logos-3-...",
  "last_runtime_agent_id": "ae6d68f...",
  "memory": {
    "scope": "project",
    "path": ".claude/agent-memory/logos/MEMORY.md",
    "required": true
  },
  "role_log": ".yolo/agents/logos-log.md",
  "summary_path": ".yolo/agents/logos-summary.md",
  "docs_mailbox": [
    "docs/intent.md",
    "docs/open-questions.md",
    "docs/decisions.md"
  ]
}
```

Rules:

- Every role turn dispatches a fresh Agent.
- The fresh Agent must use memory/log/docs for continuity.
- If required memory/log files cannot be created/read/written, dispatch fails closed.
- Runtime Agent ids are recorded after completion only for audit.
- No dispatch emits `resume_by_agent_id` or `must_resume_exact_agent_id`.

## Real bench acceptance

A real bench passes this contract only when:

- All five role definitions include `memory: project`.
- All five memory directories and `MEMORY.md` files exist.
- Muse/Logos can complete multiple planning rounds with fresh subagents.
- Dispatch prompts include memory path, role log path, and docs mailbox.
- Role logs grow after each role turn.
- Agent memory updates only with durable learnings.
- Human approval gates remain real and visible in the main session.
- No fake human approval appears in docs.
- No code path claims exact live subagent reuse.

## Testing

Required tests:

- Docs/templates test asserts all role files include `memory: project`.
- Agent session tests cover version 2 registry creation and old schema migration.
- Agent session tests assert `last_runtime_agent_id` is audit-only.
- Grill-storm loop tests assert dispatch payload uses `dispatch_action=create` and `continuity_model=project_memory`.
- Grill-storm loop tests assert prompt includes memory, role log, and docs mailbox instructions.
- Orchestrator tests assert worker/watcher/helper dispatch uses project-memory continuity.
- Negative tests assert no dispatch contains `resume_by_agent_id`, `must_resume_exact_agent_id`, or required exact runtime agent id.
- Docs tests assert README, SKILL, and policy describe project-memory continuity rather than exact live reuse.

## Rollback and safety

This change removes an unsupported runtime guarantee. If future Claude Code exposes stable subagent resume-by-id, a later design can add a separate `continuity_model=live_agent_resume` path with capability checks. Until then, `project_memory` is the only supported continuity model.

`state.json` remains authoritative. If memory or registry conflicts with `state.json`, `state.json` wins.

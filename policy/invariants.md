# Invariants

These rules apply at every stage:

- the current plan remains the source of truth for scope
- `run_state.json` remains the source of truth for execution position
- completion requires explicit gates, not intuition
- the agent must continue by default
- the agent may stop only for an approved human-blocked condition or a verified completion state
- after a fix, the workflow must return to the relevant verification target for the current gate
- new blockers must be classified using `blocker-rules.md`, not informal judgment
- reports, checkoffs, and run state must reflect the current run, not stale summaries

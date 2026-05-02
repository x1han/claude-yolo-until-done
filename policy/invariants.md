# Invariants

These rules apply at every step:

- the current approved plan remains the source of truth for scope
- `state.json` remains the source of truth for execution position
- `trace.md` is supporting audit evidence and must not contradict `state.json`
- completion requires explicit watcher approval and validator evidence, not intuition
- the agent must continue by default
- the agent may stop only for a verified completion state
- after a fix, the workflow must return to the relevant verification target

# Stage 2: Load State And Claim Next Step

Goal: resume from disk state instead of chat memory.

Required actions:

- load `<run-root>/run_state.json`, using `artifacts/yolo/` only as the default example
- load the active plan path referenced by the run state
- load the active gate and checkoff files
- identify the current stage, current target, and next action
- update `resume.md` if the last recorded state is stale or unclear

Pass condition:
- the stage 2 hook confirms the run state is internally consistent and names exactly one next action

Fail condition:
- the run state is missing fields
- the plan path no longer exists
- the next action is ambiguous

# Stage 4: Handle Blockers

Goal: prevent fake blockers from escaping the execution loop.

Required actions:

- classify every blocker against `policy/blocker-rules.md`
- reject any blocker that is still locally fixable
- record structured blocker evidence in `run_state.json`, including:
  - `blocker_type`
  - `blocker_evidence`
  - `local_fix_attempted`
  - `why_not_locally_fixable`
  - `blocker_recorded_at`
- record all blockers in `report.md`
- update `run_state.json` and `resume.md`

Pass condition:
- the stage 4 hook confirms either:
  - the blocker is not human-blocked and the workflow should continue, or
  - the blocker matches the whitelist and the run may pause

No informal blocker claim is valid without state updates and a matching rule.

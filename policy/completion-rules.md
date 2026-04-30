# Completion Rules

This workflow may stop only when completion is positively verified.

Minimum completion conditions:

- every required plan gate passed
- every required verification target for the active scope passed
- every required checkoff marker is complete
- `run_state.json` marks `completion_ready` as true
- `run_state.json` records concrete completion evidence, including:
  - `final_verdict`
  - `final_summary`
  - `final_verification_evidence`
  - `remaining_non_blockers`
  - `completion_reason`
  - `completion_recorded_at`
- the corresponding completion hook passed
- `report.md` and `resume.md` reflect the final state of the run

The workflow may not stop just because:

- code was changed
- one test passed
- one issue was fixed
- the agent produced a convincing summary
- the remaining work feels small

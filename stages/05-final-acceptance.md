# Stage 5: Final Acceptance

Goal: stop only when the workflow is truly done.

Required actions:

- verify all required gates passed
- verify all required checkoff markers are complete
- verify `completion_ready` is true in `run_state.json`
- record concrete completion evidence in `run_state.json`, including:
  - `final_verdict`
  - `final_summary`
  - `final_verification_evidence`
  - `remaining_non_blockers`
  - `completion_reason`
  - `completion_recorded_at`
- verify `report.md` and `resume.md` match the final state

Pass condition:
- the stage 5 hook passes and explicitly certifies completion readiness

Fail condition:
- any required gate, checkoff, report field, or completion flag is missing or stale

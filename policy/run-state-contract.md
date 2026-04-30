# Run State Contract

`<run-root>/run_state.json` is the authoritative execution state for this workflow. The default example run root in this skill is `artifacts/yolo/`.

`<run-root>/runtime_context.json` is the stage-1 runtime assertion bundle recorded at bootstrap. It is not independent proof; stage 1 must re-validate what it can and fail closed when positive verification is unavailable.

It must always contain at least:

- `workflow_name`
- `workflow_active`
- `lifecycle_state`
- `plan_path`
- `spec_path`
- `current_stage`
- `current_round`
- `current_target`
- `current_issue`
- `last_failure`
- `last_commit`
- `next_action`
- `human_blocked`
- `stop_forbidden`
- `completion_ready`
- `completion_gate`
- `verification_target`
- `repair_summary`
- `verification_commands`
- `verification_before_status`
- `verification_after_status`
- `verification_passed`
- `verification_evidence_updated_at`
- `blocker_type`
- `blocker_evidence`
- `local_fix_attempted`
- `why_not_locally_fixable`
- `blocker_recorded_at`
- `final_verdict`
- `final_summary`
- `final_verification_evidence`
- `remaining_non_blockers`
- `completion_reason`
- `completion_recorded_at`
- `updated_at`

## Rules
- update this file after every material execution step
- never rely on memory when this file disagrees with memory
- if the file is missing a required field, fail closed and stop
- if the file shows `workflow_active` as false, do not continue the run
- allowed lifecycle states are `active`, `paused`, `deactivated`, and `completed`

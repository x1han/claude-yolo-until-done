# Stage 3: Execute Fix Loop

Goal: keep fixing, verifying, and continuing without handing control back to the user.

Loop rules:

- perform the current planned action
- if a bug is found and is locally fixable, fix it directly
- after a fix, run the required verification for the current gate
- update `report.md` and `run_state.json`
- record concrete repair evidence in `run_state.json`, including:
  - `repair_summary`
  - `verification_commands`
  - `verification_before_status`
  - `verification_after_status`
  - `verification_passed`
  - `verification_evidence_updated_at`
- if the gate passes, advance only to the next allowed step
- let the controller mark gate and checkoff side effects only after the verification evidence passes
- if the gate fails, stay in diagnosis, repair, and re-verification

Do not stop after:

- editing code
- writing a summary
- seeing one passing test
- opening a new thread of work that is still locally fixable

Pass condition:
- the stage 3 hook confirms the current gate's verification target passed, the repair evidence is concrete, and state was updated correctly

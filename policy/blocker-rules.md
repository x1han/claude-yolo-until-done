# Blocker Rules

The workflow must continue by default. It may hand control back to the user only when the blocker positively matches the human-blocked whitelist.

## Allowed Human-Blocked Conditions
- GUI or OS permission dialogs the agent cannot operate around
- external account login or human authentication the agent cannot lawfully complete
- repository or environment permissions that remain unavailable without changing the Claude Code launch mode
- external services, dependencies, or infrastructure that are unavailable and cannot be fixed from the current repository or machine
- a clearly verified out-of-scope upstream or product decision that this repository cannot resolve locally

## Not Allowed As Human Blockers
- context compression
- uncertainty about the next plan step when the run bundle exists
- a new bug that can be fixed locally
- a failed test that has not yet been investigated
- fatigue, complexity, or long task length
- missing courage to continue

## Required Blocker Handling
Before classifying a blocker as human-blocked:

- verify the current stage and next action from `run_state.json`
- verify the blocker is not locally fixable
- record structured blocker evidence in `run_state.json`, including:
  - `blocker_type`
  - `blocker_evidence`
  - `local_fix_attempted`
  - `why_not_locally_fixable`
  - `blocker_recorded_at`
- record the blocker in `report.md`
- update `run_state.json`
- update `resume.md`
- produce or refresh the relevant hook result if a blocker hook exists

If the blocker does not match the whitelist, continue the workflow.

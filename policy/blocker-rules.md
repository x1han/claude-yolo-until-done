# Blocker Rules

The workflow must continue by default. It should hand control back to the user only when the blocker truly cannot be resolved from the current repository or machine.

## Allowed Human-Blocked Conditions
- GUI or OS permission dialogs the agent cannot operate around
- external account login or human authentication the agent cannot lawfully complete
- repository or environment permissions that remain unavailable without changing the Claude Code launch mode
- external services, dependencies, or infrastructure that are unavailable and cannot be fixed from the current repository or machine
- a clearly verified out-of-scope upstream or product decision that this repository cannot resolve locally

## Not Allowed As Human Blockers
- context compression
- uncertainty about the next plan step when durable workflow state exists
- a new bug that can be fixed locally
- a failed test that has not yet been investigated
- fatigue, complexity, or long task length

## Required Blocker Handling
Before classifying a blocker as human-blocked:

- verify the current status and next action from `state.json`
- verify the blocker is not locally fixable
- record the blocker clearly in `trace.md`
- keep the durable state honest about what is blocked and why

If the blocker does not match the whitelist, continue the workflow.

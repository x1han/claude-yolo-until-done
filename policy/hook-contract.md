# Hook Contract

Hooks exist to turn common execution rationalizations into executable pass or fail decisions.

## Shared Rules
- a hook must read the current durable workflow state, not stale chat summaries
- a hook may only certify the invariants it actually checks
- a hook must fail closed if the required durable state cannot be verified

## Minimum Hook Coverage
- `SessionStart`: restore context from `state.json`
- `Stop`: block stopping while the workflow is incomplete or cleanup is still required
- `UserPromptSubmit`: force an explicit pause/cancel/continue choice while a mounted run is unfinished or still awaiting cleanup
- `submission`: validate a worker submission before watcher review proceeds
- `completion`: validate final completion before hooks may be cleaned up

## Lifecycle Hooks
`SessionStart`, `Stop`, and `UserPromptSubmit` are Claude Code lifecycle hooks. They communicate through hook stdout payloads instead of validator report files, and a blocking decision may still return exit code `0` because Claude reads the JSON decision payload.

## Validator Hooks
The `submission` and `completion` validators should write a machine-readable artifact under `<run-root>/hooks/` where the default example run root is `.yolo/`.

Each validator report should contain:

- `stage`
- `passed`
- `checked_at`
- `run_root`
- `run_state_path`
- `checks`
- `failures`
- `warnings`
- `unchecked`

Validator exit codes:
- `0`: all checked invariants passed
- `1`: one or more checked invariants failed
- `2`: invocation or environment error

## Lifecycle Note
SessionEnd is disabled in this version. Cleanup is owned by explicit complete-time cleanup plus the `UserPromptSubmit` gate when a mounted run still needs operator choice.

## Non-Negotiable
No hook output means no pass claim for that hook-backed decision.

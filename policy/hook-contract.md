# Hook Contract

Hooks exist to turn common execution rationalizations into executable pass or fail decisions.

## Rules
- a hook must read the current durable workflow state, not stale chat summaries
- a hook must emit a machine-readable artifact under `<run-root>/hooks/` where the default example run root is `artifacts/yolo/`
- a hook must exit non-zero on failure
- a hook may only certify the invariants it actually checks
- a hook must fail closed if the required durable state cannot be verified

## Minimum Hook Coverage
- `SessionStart`: restore context from `state.json`
- `Stop`: block stopping while the workflow is incomplete
- `submission`: validate a worker submission before watcher review proceeds
- `completion`: validate final completion before hooks may be cleaned up

## Standard Output
Each validator should write a JSON report containing:

- `stage`
- `passed`
- `checked_at`
- `run_root`
- `run_state_path`
- `checks`
- `failures`
- `warnings`
- `unchecked`

## Standard Exit Codes
- `0`: all checked invariants passed
- `1`: one or more checked invariants failed
- `2`: invocation or environment error

## Non-Negotiable
No hook output means no pass claim for that hook-backed decision.

# Required Runtime

This workflow may run only when all of the following are true:

- the active agent runtime is Claude Code
- Claude Code hooks are available in the current session
- `--dangerously-skip-permissions` is recommended for autonomous execution; preflight reports whether it can verify this flag
- the session is interactive Claude Code, not headless `claude -p` print mode
- the current task is an execution task, not a planning task
- the repository or worktree is acceptable for autonomous edits and test execution
- the installed local hooks and durable workflow files can be positively verified

If mandatory runtime requirements cannot be positively verified, fail closed and stop. Missing `--dangerously-skip-permissions` proof is advisory and must be reported as runtime warning, not used as a hard stop.

This workflow does not promise equivalent behavior in non-Claude runtimes or in headless `claude -p` print mode.

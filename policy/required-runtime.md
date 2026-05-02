# Required Runtime

This workflow may run only when all of the following are true:

- the active agent runtime is Claude Code
- Claude Code hooks are available in the current session
- the session was started with `--dangerously-skip-permissions`
- the current task is an execution task, not a planning task
- the repository or worktree is acceptable for autonomous edits and test execution
- the installed local hooks and durable workflow files can be positively verified

If any runtime requirement cannot be positively verified, fail closed and stop.

This workflow does not promise equivalent behavior in non-Claude runtimes.

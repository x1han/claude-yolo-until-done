# Required Runtime

This workflow may run only when all of the following are true:

- the active agent runtime is Claude Code
- Claude Code hooks are available in the current session
- the session was started with `--dangerously-skip-permissions`
- the current task is an execution task, not a planning task
- the repository or worktree is acceptable for autonomous edits and test execution
- bootstrap-time runtime assertions are treated as operator-provided metadata, not independent proof
- stage 1 should positively verify locally observable runtime artifacts such as project hook settings and hook-install markers when available

If any runtime requirement cannot be positively verified, fail closed and stop.

This workflow does not promise equivalent behavior in Codex, ChatGPT, Copilot CLI, or any non-Claude runtime.

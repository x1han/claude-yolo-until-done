# Stage 1: Validate Runtime And Bundle

Goal: prove that this session is allowed to run the workflow.

Required checks:

- confirm the bootstrap bundle recorded operator assertions about Claude Code runtime, hooks, and `--dangerously-skip-permissions`
- re-validate those runtime requirements where the workflow can positively do so
- confirm `superpowers` is installed
- confirm the required run bundle exists and is current

Pass condition:
- the stage 1 hook passes

Fail condition:
- any runtime dependency, superpowers dependency, or bundle artifact cannot be positively verified

If this stage fails, stop instead of improvising.

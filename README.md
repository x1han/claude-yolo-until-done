# Claude YOLO Until Done

`claude-yolo-until-done` is a Claude Code only execution workflow for continuing a superpowers-generated plan until explicit gates pass.

For the shortest operator path, see [QUICKSTART.md](QUICKSTART.md).

This skill is not a general-purpose prompt. It assumes:

- `superpowers` is installed
- an approved spec and plan already exist
- a run bundle exists under a chosen run root, with `artifacts/yolo/` as the default example
- Claude Code is launched with `--dangerously-skip-permissions`
- Claude Code hooks are available

If those prerequisites are not true, the workflow is designed to fail closed.

## What The Hook Integration Does

The recommended Claude Code integration uses three project-local hooks:

- `SessionStart`: injects a reminder to reload active workflow context from `<run-root>/run_state.json` after startup, resume, or compaction
- `Stop`: blocks Claude from stopping while the workflow is still active unless a structured, verified `human_blocked` record is already present
- `SessionEnd`: removes the project-local yolo hooks after a completed run so later non-yolo sessions in the same repo are not burdened by them

This keeps the workflow from silently degrading after resume or compaction and reduces the chance that Claude exits early with a nice summary instead of finishing the loop. Incomplete runs intentionally keep the hooks installed until the run is completed or you manually uninstall them.

## Why Project-Local Hooks

Use project-local hooks in `.claude/settings.local.json`, not global hooks in `~/.claude/settings.json`.

That keeps the behavior scoped to one repository and avoids changing unrelated Claude Code sessions. This matches Claude Code's documented hook locations and scopes: project-local settings apply to a single project and are not shared by default, while global settings affect every project.

## Recommended Runtime Pattern

1. Use `superpowers:brainstorming` and `superpowers:writing-plans` first.
2. Bootstrap the run bundle from the approved spec and plan.
3. Install the local Claude hooks for the target project.
4. Launch Claude Code in that project with `--dangerously-skip-permissions`.
5. Activate `claude-yolo-until-done` and continue the run until the gates pass.

## Step 1: Bootstrap The Run Bundle

From the project root:

```powershell
python <skill-repo>\workflow\bootstrap.py `
  --spec <target-project>\docs\superpowers\specs\2026-04-29-example-spec.md `
  --plan <target-project>\docs\superpowers\plans\2026-04-29-example-plan.md `
  --run-root <target-project>\artifacts\yolo `
  --current-target "core e2e fix loop" `
  --current-issue "#123 flaky save flow" `
  --verification-target "pytest tests/e2e/test_save_flow.py -q" `
  --dangerously-skip-permissions
```

This creates:

- `<run-root>/runtime_context.json`
- `<run-root>/run_state.json`
- `<run-root>/gates.json`
- `<run-root>/checkoffs.json`
- `<run-root>/report.md`
- `<run-root>/resume.md`

## Step 2: Install The Claude Code Hooks

Use the helper installer:

```powershell
python <skill-repo>\workflow\install_claude_hooks.py `
  --project-dir <target-project> `
  --run-root artifacts/yolo
```

That writes or updates:

- `<target-project>\.claude\settings.local.json`

It installs a minimal hook set:

- `SessionStart` for `startup|resume|compact`
- `Stop` for all turns
- `SessionEnd` for cleanup after completed runs

The generated commands call:

- `workflow/claude_hook_bridge.py --event session-start`
- `workflow/claude_hook_bridge.py --event stop`
- `workflow/claude_hook_bridge.py --event session-end`

If you prefer manual setup, use [templates/claude-settings-local.example.json](templates/claude-settings-local.example.json) as the starting point.

## Hook Cleanup Lifecycle

The hooks installed by this workflow are project-local, so they do not affect unrelated repositories. But they do remain in the current repository until removed.

This workflow now handles that in two ways:

- automatic cleanup on `SessionEnd` when `completion_ready: true` and `workflow_active: false`, or when the run has been explicitly deactivated
- explicit manual cleanup with:

```powershell
python <skill-repo>\workflow\uninstall_claude_hooks.py `
  --project-dir <target-project> `
  --run-root artifacts/yolo
```

Use the manual cleanup command if:

- the session ended unexpectedly
- the auto cleanup hook did not run
- you want to disable the yolo hooks before the next session

## Step 3: Launch Claude Code Correctly

Open Claude Code in the project and include `--dangerously-skip-permissions`.

Example:

```powershell
claude --dangerously-skip-permissions
```

This workflow assumes permission prompts are not interrupting the loop. If Claude Code is started without that flag, the skill's own runtime contract says it should fail closed rather than pretend uninterrupted autonomy is still possible.

## Step 4: Activate The Workflow In Session

When the session starts, the `SessionStart` hook injects a reminder based on `<run-root>/run_state.json` if that file still shows `workflow_active: true`. The reminder is intentionally conservative: Claude should reload and re-validate the bundle on disk rather than trust the injected note by itself.

Then use the skill in the project session and continue from the current bundle:

- load `<run-root>/run_state.json` such as `artifacts/yolo/run_state.json`
- follow the current stage
- update the run bundle after material changes
- use the local gates and controller

Useful commands:

```powershell
python <skill-repo>\workflow\controller.py --run-root <target-project>\artifacts\yolo --write-status
python <skill-repo>\hooks\run_gate.py --stage 3 --run-root <target-project>\artifacts\yolo
```

## What The Stop Hook Actually Enforces

The `Stop` hook bridge blocks stopping when all of these are true:

- `<run-root>/run_state.json` exists
- `workflow_active` is `true`
- `lifecycle_state` is not `paused` or `deactivated`
- there is no valid structured `human_blocked` record with an allowed blocker type, evidence, local fix attempt, and non-local-fixable reason

If that happens, the hook returns a blocking decision and tells Claude to reload the run bundle and continue the current stage.

The bridge also checks `stop_hook_active` from Claude Code's hook input and exits early when it is already inside a stop-hook continuation path, which avoids the infinite-loop failure mode called out in the Claude Code hooks guide.

## What The SessionEnd Hook Cleans Up

The `SessionEnd` bridge removes the `SessionStart`, `Stop`, and `SessionEnd` hook entries that were installed for this workflow, but only when:

- `<run-root>/run_state.json` exists
- `completion_ready` is `true`
- `workflow_active` is `false`

This means:

- completed yolo runs clean up after themselves
- paused runs do not lose their hooks
- abandoned or incomplete runs keep their guardrails until you explicitly uninstall them

## Pause Or Deactivate A Run

If you need to do non-yolo work in the same repo, use the lifecycle helper instead of hand-editing `run_state.json`:

```powershell
python <skill-repo>\workflow\set_lifecycle_state.py `
  --run-root <target-project>\artifacts\yolo `
  --state paused `
  --reason "Temporary non-yolo work in the same repo"
```

Supported lifecycle states:

- `active`: the workflow is running and stop remains guarded
- `paused`: the workflow is intentionally suspended; stop is allowed and hooks stay installed
- `deactivated`: the workflow is intentionally shut down; stop is allowed and `SessionEnd` may remove the hooks

## Recommended Scope And Safety

Use `.claude/settings.local.json` for this workflow unless you explicitly want to commit the behavior for the whole project.

Do not install these hooks globally unless every project on the machine should inherit the same stop-blocking behavior.

Because Claude Code hooks run automatically with your current credentials, review hook scripts before enabling them. This workflow intentionally keeps the default integration small and local:

- one local settings file
- one bridge script
- one run bundle directory

## Troubleshooting

### Claude still stops early

Check:

- Claude Code was started with `--dangerously-skip-permissions`
- `.claude/settings.local.json` contains the `Stop` hook
- `<run-root>/run_state.json` still has `workflow_active: true`
- `completion_ready` was not flipped early
- `human_blocked` was not set without evidence

### Resume or compaction loses the workflow context

Check:

- `.claude/settings.local.json` contains the `SessionStart` hook
- the matcher still includes `resume|compact`
- `<run-root>/run_state.json` exists and is current

### Other projects are affected

Move the hook config out of `~/.claude/settings.json` and into the project's `.claude/settings.local.json`.

## Relevant Claude Code Docs

- Hooks can be configured in `~/.claude/settings.json`, `.claude/settings.json`, or `.claude/settings.local.json`, and the local project settings file is project-scoped rather than global: [Hooks reference](https://code.claude.com/docs/en/hooks)
- Claude Code recommends using `CLAUDE_PROJECT_DIR` to reference project-relative hook scripts: [Hooks guide](https://code.claude.com/docs/en/hooks-guide)
- `Stop` hooks can block Claude from stopping by returning `decision: "block"` with a `reason`: [Hooks reference](https://code.claude.com/docs/en/hooks)
- The hooks guide explicitly warns that a Stop hook should check `stop_hook_active` to avoid looping forever: [Hooks guide](https://code.claude.com/docs/en/hooks-guide)

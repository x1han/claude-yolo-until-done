# Quickstart

This is the shortest practical path for using `claude-yolo-until-done` in a real Claude Code session.

## 1. Finish Planning First

Do not start here unless `superpowers` has already produced:

- an approved spec
- an approved implementation plan
- explicit gates or checkoffs

This skill is execution-only. It does not replace planning.

## 2. Bootstrap The Run Bundle

From the target project:

```powershell
python <skill-repo>\workflow\bootstrap.py `
  --spec <target-project>\docs\superpowers\specs\2026-04-29-example-spec.md `
  --plan <target-project>\docs\superpowers\plans\2026-04-29-example-plan.md `
  --run-root <target-project>\artifacts\yolo `
  --current-target "core e2e flow" `
  --current-issue "#123 save flow regression" `
  --verification-target "pytest tests/e2e/test_save_flow.py -q" `
  --dangerously-skip-permissions
```

## 3. Install Project-Local Claude Hooks

```powershell
python <skill-repo>\workflow\install_claude_hooks.py `
  --project-dir <target-project> `
  --run-root artifacts/yolo
```

This writes `.claude/settings.local.json` in the target repo.
The example above uses the default run root `artifacts/yolo`; a different run root is allowed if you keep it consistent across bootstrap, hooks, and controller commands.

## 4. Launch Claude Code Correctly

Start Claude Code in the target repo with:

```powershell
claude --dangerously-skip-permissions
```

Without that flag, this workflow should fail closed.

## 5. Continue The Workflow

Inside Claude Code:

- activate `claude-yolo-until-done`
- reload `<run-root>/run_state.json`, typically `artifacts/yolo/run_state.json`
- continue from `current_stage`
- keep updating the run bundle after material steps

Useful commands:

```powershell
python <skill-repo>\workflow\controller.py --run-root <target-project>\artifacts\yolo --write-status
python <skill-repo>\hooks\run_gate.py --stage 3 --run-root <target-project>\artifacts\yolo
```

## 6. Let The Hooks Guard The Session

The installed hooks do three things:

- `SessionStart`: restore workflow context after startup, resume, or compaction
- `Stop`: block early stopping unless a structured human-blocked record is valid
- `SessionEnd`: remove the local yolo hooks after a completed run

## 7. If Cleanup Does Not Happen Automatically

Run:

```powershell
python <skill-repo>\workflow\uninstall_claude_hooks.py `
  --project-dir <target-project> `
  --run-root artifacts/yolo
```

## 8. If You Need To Pause The Run

```powershell
python <skill-repo>\workflow\set_lifecycle_state.py `
  --run-root <target-project>\artifacts\yolo `
  --state paused `
  --reason "Temporary non-yolo work in the same repo"
```

Use `--state deactivated` if you want the next `SessionEnd` cleanup to remove the project-local hooks.

## Daily Checklist

- plan exists
- run bundle exists
- hooks installed locally
- Claude launched with `--dangerously-skip-permissions`
- `workflow_active` remains true until done
- `completion_ready` only flips at final acceptance
- incomplete runs keep hooks installed until completion or manual uninstall

# Quickstart

This is the shortest practical path for using `claude-yolo-until-done` as a lightweight worker+watcher loop.

## 1. Finish Planning First

Do not start here unless `superpowers` has already produced:

- an approved spec
- an approved implementation plan

This workflow is execution-only.

## 2. Bootstrap The Run Root

From the target project:

```bash
python <skill-repo>/workflow/bootstrap.py \
  --spec <target-project>/docs/superpowers/specs/approved-spec.md \
  --plan <target-project>/docs/superpowers/plans/approved-plan.md \
  --run-root <target-project>/artifacts/yolo \
  --goal "Fix the requested problem and verify it." \
  --success-criterion "The requested files are updated exactly as required." \
  --success-criterion "The verification command passes freshly." \
  --success-criterion "The workflow reaches valid completion."
```

## 3. Install Project-Local Hooks

```bash
python <skill-repo>/workflow/install_claude_hooks.py \
  --project-dir <target-project> \
  --run-root artifacts/yolo
```

This writes `.claude/settings.local.json` in the target repository.

## 4. Launch Claude Code Correctly

```bash
claude --dangerously-skip-permissions
```

Without that flag, this workflow should fail closed.

## 5. Continue The Workflow

Inside Claude Code:

- activate `claude-yolo-until-done`
- reload `<run-root>/state.json`, usually `artifacts/yolo/state.json`
- follow `status`, `owner`, and `next_action`
- keep updating the run root after material steps

Useful commands:

```bash
python <skill-repo>/workflow/controller.py --run-root <target-project>/artifacts/yolo --actor worker --action submit ...
python <skill-repo>/workflow/controller.py --run-root <target-project>/artifacts/yolo --actor watcher --action review ...
python <skill-repo>/workflow/controller.py --run-root <target-project>/artifacts/yolo --actor watcher --action complete
python <skill-repo>/hooks/run_gate.py --validator submission --run-root <target-project>/artifacts/yolo
python <skill-repo>/hooks/run_gate.py --validator completion --run-root <target-project>/artifacts/yolo
```

## 6. Let The Hooks Guard The Session

The installed hooks do three things:

- `SessionStart`: restore workflow context after startup, resume, or compaction
- `Stop`: block early stopping while the workflow is incomplete
- `SessionEnd`: remove the local yolo hooks after a valid completed run

## 7. If Cleanup Does Not Happen Automatically

```bash
python <skill-repo>/workflow/uninstall_claude_hooks.py \
  --project-dir <target-project> \
  --run-root artifacts/yolo
```

## Daily Checklist

- approved spec exists
- approved plan exists
- `state.json` and `trace.md` exist
- hooks are installed locally
- Claude was launched with `--dangerously-skip-permissions`
- incomplete runs keep hooks installed
- only a valid completed run cleans hooks automatically

# Quickstart

This is the shortest practical path for using `claude-yolo-until-done` as a lightweight worker+watcher loop.

## 1. Finish Planning First

Do not start here unless `superpowers` has already produced:

- an approved spec
- an approved implementation plan

This workflow is execution-only.

## 2. Choose The Output Folder

The output folder defaults to the current working directory.

`.yolo/` lives inside that output folder. If you want a different location, choose that folder first and run the workflow there, or pass explicit paths that point into it.

## 3. Bootstrap The Run Root

From the output folder:

```bash
python <skill-repo>/workflow/bootstrap.py \
  --spec <output-folder>/docs/superpowers/specs/approved-spec.md \
  --plan <output-folder>/docs/superpowers/plans/approved-plan.md \
  --run-root <output-folder>/.yolo \
  --goal "Fix the requested problem and verify it." \
  --success-criterion "The requested files are updated exactly as required." \
  --success-criterion "The verification command passes freshly." \
  --success-criterion "The workflow reaches valid completion."
```

## 4. Run Preflight On Skill Load

When the skill is loaded, run preflight first:

- verify the approved spec and plan paths exist
- classify the run as new-run or continue-run
- bootstrap `.yolo/state.json` and `.yolo/trace.md` when the run is new
- verify `.yolo/state.json` and `.yolo/trace.md` only when the run is a continue-run
- install the current local claude-yolo hook set without treating legacy same-run hook groups as a blocker
- offer a narrow repair path before ordinary execution continues

The output should stay brief, but the checks should be strict.

## 5. Install Project-Local Hooks

```bash
python <skill-repo>/workflow/install_claude_hooks.py \
  --project-dir <output-folder> \
  --run-root .yolo
```

This writes `.claude/settings.local.json` in the output folder.

## 6. Launch Claude Code Correctly

```bash
claude --dangerously-skip-permissions
```

Without that flag, this workflow should fail closed.

Do not start claude-yolo from headless `claude -p` print mode. The workflow depends on interactive stop/resume behavior that current print mode does not preserve.

## 7. Continue The Workflow

Inside Claude Code, the normal usage is simple: use `claude-yolo-until-done` to execute the approved plan.

If needed, also name the exact spec path, plan path, or output folder, but no extra execution skill should be required.

Keep the session aligned with the durable run state:

- activate `claude-yolo-until-done`
- run preflight first
- reload `<run-root>/state.json`, usually `.yolo/state.json`
- follow `status`, `owner`, and `next_action`
- keep updating the run root after material steps

Useful commands:

```bash
python <skill-repo>/workflow/controller.py --run-root <output-folder>/.yolo --actor worker --action submit ...
python <skill-repo>/workflow/controller.py --run-root <output-folder>/.yolo --actor watcher --action review ...
python <skill-repo>/workflow/controller.py --run-root <output-folder>/.yolo --actor watcher --action complete
python <skill-repo>/workflow/cleanup_claude_yolo.py --project-dir <output-folder> --run-root .yolo --mode pause
python <skill-repo>/workflow/cleanup_claude_yolo.py --project-dir <output-folder> --run-root .yolo --mode cancel
python <skill-repo>/workflow/cleanup_claude_yolo.py --project-dir <output-folder> --run-root .yolo --mode complete
python <skill-repo>/hooks/run_gate.py --validator submission --run-root <output-folder>/.yolo
python <skill-repo>/hooks/run_gate.py --validator completion --run-root <output-folder>/.yolo
```

## 8. Let The Hooks Guard The Session

The installed hooks do three things:

- `SessionStart`: restore workflow context after startup, resume, or compaction
- `Stop`: block early stopping while the workflow is incomplete or cleanup is still required
- `UserPromptSubmit`: force exactly one choice while claude-yolo remains mounted — 暂停, 取消, or 继续 yolo

## Daily Checklist

- approved spec exists
- approved plan exists
- `.yolo/state.json` and `.yolo/trace.md` exist
- hooks are installed locally
- Claude was launched with `--dangerously-skip-permissions`
- incomplete runs keep hooks installed
- completion triggers explicit cleanup instead of relying on session shutdown

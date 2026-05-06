# Claude YOLO Until Done

`claude-yolo-until-done` is a lightweight Claude Code worker+watcher execution workflow.

It is for the phase after planning is already done. The intended path is simple: use `superpowers` to produce an approved spec and plan first, then tell Claude Code to use `claude-yolo-until-done` to execute the approved plan.

The workflow assumes an approved spec and plan already exist, then drives a small durable loop:

- bootstrap a run root with `state.json` and `trace.md`
- let the worker make a concrete submission with fresh verification evidence
- require the watcher to review before completion
- use hooks to block early stopping and force explicit cleanup choices while the workflow stays mounted

For the shortest operator path, see [QUICKSTART.md](QUICKSTART.md).

## Preconditions

Use this workflow only when all of the following are true:

- `superpowers` is installed
- an approved spec already exists
- an approved implementation plan already exists
- Claude Code hooks are available
- Claude Code is launched with `--dangerously-skip-permissions`
- the session is interactive Claude Code, not headless `claude -p` print mode

If those assumptions are not true, the workflow should fail closed.

## Output Folder And Run Root

The output folder defaults to the current working directory unless you explicitly choose another location.

`.yolo/` lives inside that output folder and is the default run-root model for this workflow.

## Runtime Shape

The lightweight runtime keeps two durable artifacts under a chosen run root, with `.yolo/` as the default example:

- `state.json` — authoritative workflow state
- `trace.md` — append-only human-readable activity trail

The runtime status model is intentionally small:

- `active`
- `needs_review`
- `rework_required`
- `approved`
- `complete`

## Hook Model

The recommended integration installs three project-local Claude Code hooks in `.claude/settings.local.json`:

- `SessionStart` — reminds Claude to reload `state.json` after startup, resume, or compaction
- `Stop` — blocks stopping while the workflow is still incomplete or cleanup is still required
- `UserPromptSubmit` — blocks ordinary new prompts until the user chooses to pause, cancel, or continue yolo

Primary cleanup happens at `complete`. If the run is still mounted afterward, `UserPromptSubmit` is the backup gate that forces an explicit decision before ordinary continuation.

This keeps the workflow scoped to one repository and avoids affecting unrelated projects.

## Bootstrap

From the target project root:

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

That creates:

- `<run-root>/state.json`
- `<run-root>/trace.md`

## Install Hooks

```bash
python <skill-repo>/workflow/install_claude_hooks.py \
  --project-dir <output-folder> \
  --run-root .yolo
```

This writes or updates `<output-folder>/.claude/settings.local.json`.

## Continue The Workflow

Launch interactive Claude Code in the output folder with:

```bash
claude --dangerously-skip-permissions
```

Do not use headless `claude -p` print mode for claude-yolo runs. In print mode, a blocked Stop hook can still end the process before the unfinished run continues, so bootstrap must fail closed instead.

Then tell Claude to use `claude-yolo-until-done` to execute the approved plan, optionally naming the plan path and output folder if you are not using the defaults.

The main commands are:

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

## What The Guards Enforce

The stop hook blocks while the workflow is still in progress, including `active`, `needs_review`, `rework_required`, and `approved`.

The submission validator checks that the worker submission is complete and that `trace.md` contains the worker submit event.

The completion validator checks that:

- `state.json` says the workflow is `complete`
- the watcher review verdict is `approve`
- submission evidence is still present
- `trace.md` contains both watcher review and watcher completion entries

The controller also marks `cleanup_required` at completion so the run cannot silently drift into ordinary session use without explicit cleanup.

## Manual Cleanup

If you need to detach claude-yolo manually, use the shared cleanup script:

```bash
python <skill-repo>/workflow/cleanup_claude_yolo.py \
  --project-dir <output-folder> \
  --run-root .yolo \
  --mode pause
```

Use `pause` to preserve `state.json` and `trace.md`, `cancel` to remove them, and `complete` to perform post-completion cleanup.

## Scope

This version is designed to be reliable and simple in a single active run root. It does not attempt to coordinate multiple concurrent Claude sessions sharing the same workflow state.

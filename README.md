# Claude YOLO Until Done

`claude-yolo-until-done` is a lightweight Claude Code worker+watcher execution workflow.

It is for the phase after planning is already done. The workflow assumes an approved spec and plan already exist, then drives a small durable loop:

- bootstrap a run root with `state.json` and `trace.md`
- let the worker make a concrete submission with fresh verification evidence
- require the watcher to review before completion
- use hooks to block early stopping and to clean up local hooks after a valid completion

For the shortest operator path, see [QUICKSTART.md](QUICKSTART.md).

## Preconditions

Use this workflow only when all of the following are true:

- `superpowers` is installed
- an approved spec already exists
- an approved implementation plan already exists
- Claude Code hooks are available
- Claude Code is launched with `--dangerously-skip-permissions`

If those assumptions are not true, the workflow should fail closed.

## Runtime Shape

The lightweight runtime keeps two durable artifacts under a chosen run root, with `artifacts/yolo/` as the default example:

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
- `Stop` — blocks stopping while the workflow is still incomplete
- `SessionEnd` — removes the local yolo hooks after a valid completed run

This keeps the workflow scoped to one repository and avoids affecting unrelated projects.

## Bootstrap

From the target project root:

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

That creates:

- `<run-root>/state.json`
- `<run-root>/trace.md`

## Install Hooks

```bash
python <skill-repo>/workflow/install_claude_hooks.py \
  --project-dir <target-project> \
  --run-root artifacts/yolo
```

This writes or updates `<target-project>/.claude/settings.local.json`.

## Continue The Workflow

Launch Claude Code in the target repository with:

```bash
claude --dangerously-skip-permissions
```

Then use the workflow in session and continue from the durable state on disk.

The main commands are:

```bash
python <skill-repo>/workflow/controller.py --run-root <target-project>/artifacts/yolo --actor worker --action submit ...
python <skill-repo>/workflow/controller.py --run-root <target-project>/artifacts/yolo --actor watcher --action review ...
python <skill-repo>/workflow/controller.py --run-root <target-project>/artifacts/yolo --actor watcher --action complete
python <skill-repo>/hooks/run_gate.py --validator submission --run-root <target-project>/artifacts/yolo
python <skill-repo>/hooks/run_gate.py --validator completion --run-root <target-project>/artifacts/yolo
```

## What The Guards Enforce

The stop hook blocks while the workflow is still in progress, including `active`, `needs_review`, `rework_required`, and `approved`.

The submission validator checks that the worker submission is complete and that `trace.md` contains the worker submit event.

The completion validator checks that:

- `state.json` says the workflow is `complete`
- the watcher review verdict is `approve`
- submission evidence is still present
- `trace.md` contains both watcher review and watcher completion entries

Only then may `SessionEnd` remove the local hooks automatically.

## Manual Cleanup

If a finished run is not cleaned up automatically, remove the local hooks manually:

```bash
python <skill-repo>/workflow/uninstall_claude_hooks.py \
  --project-dir <target-project> \
  --run-root artifacts/yolo
```

## Scope

This version is designed to be reliable and simple in a single active run root. It does not attempt to coordinate multiple concurrent Claude sessions sharing the same workflow state.

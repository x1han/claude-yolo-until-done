# Quickstart

This is shortest practical path for using `claude-yolo-until-done` as grill-storm planning flow plus lightweight worker+watcher loop.

## 1. Initialize Grill-Storm Docs

From target project root:

```bash
python <skill-repo>/workflow/init_grill_docs.py \
  --project-dir <output-folder> \
  --request "Describe work to plan."
```

That creates `docs/intent.md`, `docs/open-questions.md`, `docs/decisions.md`, `docs/spec.md`, and `docs/plan.md`.

## 2. Finish Planning First

Do not start execution until grill-storm loop has produced:

- approved spec
- approved implementation plan

This workflow still keeps execution and planning separate.

Preflight reports one explicit operator action: `init_planning`, `continue_planning`, `await_human_approval`, `bootstrap_execution`, `resume_execution`, or `repair_state`. Each blocked report includes current state, evidence, blocked-on item, and next safe action.

## 3. Run Preflight

From output folder:

```bash
python <skill-repo>/workflow/preflight.py \
  --project-dir <output-folder> \
  --run-root .yolo \
  --goal "Fix requested problem and verify it." \
  --success-criterion "Requested files are updated exactly as required." \
  --success-criterion "Verification command passes freshly." \
  --success-criterion "Workflow reaches valid completion."
```

Default is acyclic mode: execute the approved spec/plan once. Loop mode: repeat the same complete approved spec/plan as the acyclic execution unit. fixed loop N means N complete acyclic executions; convergence-only loop uses default max 10. do not pre-plan future loop iterations.

Loop mode must keep `task_inputs` pointed at the complete approved spec/plan execution unit; parsed plan sections are review context only and must not become loop iterations.

For loop mode, preflight with a stop policy:

```bash
python <skill-repo>/workflow/preflight.py \
  --project-dir <output-folder> \
  --run-root .yolo \
  --goal "Improve until loop policy stops." \
  --success-criterion "Each iteration is reviewed before the next starts." \
  --mode loop \
  --loop-max-iterations 10 \
  --loop-stop-on-convergence
```

`--loop-max-iterations` is stop policy A, `--loop-stop-on-convergence` is stop policy B, and A+B uses either stop condition. On continue-run, preflight rejects mode/config drift from existing `state.json`.

## 4. Continue From Preflight Result

When skill is loaded, run preflight first:

- verify approved spec and plan paths exist
- classify run as new-run or continue-run
- bootstrap `.yolo/state.json` and `.yolo/trace.md` when run is new
- verify `.yolo/state.json` and `.yolo/trace.md` only when run is continue-run
- install current local claude-yolo hook set without treating legacy same-run hook groups as blocker
- offer narrow repair path before ordinary execution continues

Output should stay brief, but checks should be strict.

## 5. Install Project-Local Hooks

```bash
python <skill-repo>/workflow/install_claude_hooks.py \
  --project-dir <output-folder> \
  --run-root .yolo
```

This writes `.claude/settings.local.json` in output folder.

## 6. Launch Claude Code Correctly

```bash
claude --dangerously-skip-permissions
```

Without that flag, preflight reports a runtime warning and autonomy may be weaker.

Do not start claude-yolo from headless `claude -p` print mode. Workflow depends on interactive stop/resume behavior that current print mode does not preserve.

## 7. Continue Workflow

Inside Claude Code, normal usage is simple: use `claude-yolo-until-done` to execute approved plan.

If needed, also name exact spec path, plan path, or output folder, but no extra execution skill should be required.

Keep session aligned with durable run state:

- activate `claude-yolo-until-done`
- run preflight first
- reload `<run-root>/state.json`, usually `.yolo/state.json`
- follow `status`, `owner`, and `next_action`
- keep updating run root after material steps

Useful commands:

```bash
python <skill-repo>/workflow/operator_cli.py worker-submit --run-root <output-folder>/.yolo ...
python <skill-repo>/workflow/operator_cli.py watcher-review --run-root <output-folder>/.yolo ...
python <skill-repo>/workflow/operator_cli.py watcher-complete --run-root <output-folder>/.yolo ...
python <skill-repo>/workflow/operator_cli.py cleanup --project-dir <output-folder> --run-root .yolo --mode pause
python <skill-repo>/workflow/operator_cli.py cleanup --project-dir <output-folder> --run-root .yolo --mode cancel
python <skill-repo>/workflow/operator_cli.py cleanup --project-dir <output-folder> --run-root .yolo --mode complete
python <skill-repo>/workflow/operator_cli.py validate-submission --run-root <output-folder>/.yolo
python <skill-repo>/workflow/operator_cli.py validate-completion --run-root <output-folder>/.yolo
```

## 8. Let Hooks Guard Session

Installed hooks do three things:

- `SessionStart`: restore workflow context after startup, resume, or compaction
- `Stop`: block early stopping while workflow is incomplete or cleanup is still required
- `UserPromptSubmit`: force exactly one choice while claude-yolo remains mounted — 暂停, 取消, or 继续 yolo

## Daily Checklist

- approved spec exists
- approved plan exists
- `.yolo/state.json` and `.yolo/trace.md` exist
- hooks are installed locally
- Claude was launched with `--dangerously-skip-permissions`
- incomplete runs keep hooks installed
- completion triggers explicit cleanup instead of relying on session shutdown

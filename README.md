# Claude YOLO Until Done

`claude-yolo-until-done` is a lightweight Claude Code workflow with built-in grill-storm authoring and worker+watcher execution.

Project no longer depends on `superpowers` installation. Intended path is simple: use built-in `grill-storm` to converge on approved spec and plan first, then tell Claude Code to use `claude-yolo-until-done` to execute approved plan.

Workflow has two phases:

- planning: use two built-in agents to converge on `docs/intent.md`, `docs/open-questions.md`, `docs/decisions.md`, `docs/spec.md`, and `docs/plan.md`
- execution: bootstrap run root with `state.json` and `trace.md`, then drive worker/watcher loop until cleanup is explicit

For shortest operator path, see [QUICKSTART.md](QUICKSTART.md).

## Preconditions

Use this workflow only when all of following are true:

- approved grill-storm docs exist under `docs/spec.md` and `docs/plan.md`, or both `--spec` and `--plan` name existing approved artifacts
- approved implementation plan is execution-ready
- Claude Code hooks are available for execution phase
- Claude Code is preferably launched with `--dangerously-skip-permissions` for autonomous execution; preflight reports a warning if it cannot verify the flag
- session is interactive Claude Code, not headless `claude -p` print mode

If assumptions are not true, workflow should fail closed.

## Grill-Storm Planning Bundle

First-party planning bundle lives under `docs/` in target project:

- `intent.md`
- `open-questions.md`
- `decisions.md`
- `spec.md`
- `plan.md`

These 5 files are external brain. Agent talk should not rely only on chat history.

Use built-in grill-storm authoring flow:

- combines `grill-me` style gap finding with brainstorming-style internal challenge before asking user
- `Muse` reads `intent.md` and `open-questions.md`
- `Logos` reads `intent.md`, `decisions.md`, and `spec.md`
- after each round, update intent, open questions, decisions, spec, or plan instead of relying on memory
- converge in one or two high-quality internal rounds by requiring candidates, critique, evidence, rejected alternatives, and a human review packet
- return `human_dialogue` when agents reach consensus or `joint_uncertainty`
- require human-approved spec before plan authoring and human-approved plan before execution

Use `intent.md`, `open-questions.md`, and `decisions.md` as primary working state. `spec.md` should hold stable requirements only. `plan.md` should become execution-ready only after spec is stable.

High-quality autonomy comes from constrained artifacts and validation, not long agent chatter. Muse should produce 2-3 candidate directions with tradeoffs and falsifiers; Logos should critique those candidates, select one recommendation, or name one blocking uncertainty. By default, two internal rounds is the limit before the main session prints a concise human review packet. Local research notes live at `../workflow/reference/autonomous-debate-patterns.md`.

Initialize bundle from target project root:

```bash
python <skill-repo>/workflow/init_grill_docs.py \
  --project-dir <output-folder> \
  --request "Describe work to plan."
```

## Output Folder And Run Root

Output folder defaults to current working directory unless you explicitly choose another location.

`.yolo/` lives inside output folder and is default run-root model for this workflow.

## Runtime Shape

Lightweight runtime keeps two durable artifacts under chosen run root, with `.yolo/` as default example:

- `state.json` — authoritative workflow state
- `trace.md` — append-only human-readable activity trail
- `agent_sessions.json` — per `.yolo/` run role-agent routing metadata
- `agents/<role>-log.md` — role lab notebook for durable agent context

Runtime status model is intentionally small:

- `active`
- `needs_review`
- `rework_required`
- `approved`
- `ready_for_cleanup`

## Preflight And Bootstrap

Default new-run startup uses built-in grill-storm docs under `<project>/docs/`. Run `workflow/init_grill_docs.py` when those docs do not exist, iterate with `workflow/grill_storm.py --status` until `docs/spec.md` and `docs/plan.md` are approved, then run `workflow/preflight.py` without `--spec/--plan` to execute the default docs.

Existing approved spec/plan files are still supported by passing both `--spec` and `--plan`.

From target project root:

```bash
python <skill-repo>/workflow/preflight.py \
  --project-dir <output-folder> \
  --goal "Fix requested problem and verify it." \
  --success-criterion "Requested files are updated exactly as required." \
  --success-criterion "Verification command passes freshly." \
  --success-criterion "Workflow reaches valid completion."
```

That creates:

- `<run-root>/state.json`
- `<run-root>/trace.md`

Default execution mode is acyclic: one approved plan run reaches cleanup. Loop mode repeats the same acyclic core until one stop policy fires:

```bash
python <skill-repo>/workflow/preflight.py \
  --project-dir <output-folder> \
  --goal "Improve until loop policy stops." \
  --success-criterion "Each iteration is reviewed before the next starts." \
  --mode loop \
  --loop-max-iterations 10 \
  --loop-stop-on-convergence
```

`--loop-max-iterations` is stop policy A, `--loop-stop-on-convergence` is stop policy B, and A+B uses either stop condition. For continue-run, supplied mode/config must match existing `state.json` or preflight fails closed.

## Install Hooks

```bash
python <skill-repo>/workflow/install_claude_hooks.py \
  --project-dir <output-folder> \
  --run-root .yolo
```

This writes or updates `<output-folder>/.claude/settings.local.json`.

## Continue Workflow

Launch interactive Claude Code in output folder with:

```bash
claude --dangerously-skip-permissions
```

Do not use headless `claude -p` print mode for claude-yolo runs. In print mode, blocked Stop hook can still end process before unfinished run continues, so bootstrap must fail closed instead.

Then tell Claude Code to use `claude-yolo-until-done` to execute approved plan, optionally naming plan path and output folder if you are not using defaults.

Main commands are:

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

## Persistent Role Agents

Role agents are scoped per `.yolo/` run. Each role should be created once per run and then continued for later dispatches to that same role.

`agent_sessions.json` stores routing metadata only. It does not replace `state.json` and does not decide workflow status.

Dispatch payloads include `session_action`, `agent_id`, and runtime routing metadata. `session_action: create` means create the role agent once for that generation. `session_action: reuse` means resume/send to exactly that existing `agent_id`; do not create a fresh role agent with new context. Replacement is explicit only and creates a new generation through the replacement flow.

```json
{
  "session_action": "reuse",
  "agent_id": "logos-1-example",
  "agent_runtime": {
    "tool": "Agent",
    "action": "resume_by_agent_id",
    "agent_id": "logos-1-example",
    "must_resume_exact_agent_id": true
  }
}
```

Each role keeps a role lab notebook at `agents/<role>-log.md`. Entries are concise experimental records: hypothesis, actions, observations, result, next. Summaries are compression cache only; the notebook is primary durable context.

## Hook Model

Recommended integration installs three project-local Claude Code hooks in `.claude/settings.local.json`:

- `SessionStart`
- `Stop`
- `UserPromptSubmit`

Primary cleanup happens at `complete`. If run is still mounted afterward, `UserPromptSubmit` is backup gate that forces explicit decision before ordinary continuation.

## What Guards Enforce

Stop hook blocks while workflow is still in progress, including `active`, `needs_review`, `rework_required`, and `approved`.

Submission validator checks that worker submission is complete and that `trace.md` contains worker submit event.

Completion validator checks that:

- `state.json` says workflow is `ready_for_cleanup`
- watcher review verdict is `approve`
- submission evidence is still present
- `trace.md` contains both watcher review and watcher completion entries

Controller also marks `cleanup_required` at completion so run cannot silently drift into ordinary session use without explicit cleanup.

## Manual Cleanup

If you need to detach claude-yolo manually, use shared cleanup script:

```bash
python <skill-repo>/workflow/cleanup_claude_yolo.py \
  --project-dir <output-folder> \
  --run-root .yolo \
  --mode pause
```

Use `pause` to preserve `state.json` and `trace.md`, `cancel` to remove them, and `complete` to perform post-completion cleanup.

## Scope

This version is designed to be reliable and simple in single active run root. It does not attempt to coordinate multiple concurrent Claude sessions sharing same workflow state. It also does not turn planning phase into generic multi-agent platform.

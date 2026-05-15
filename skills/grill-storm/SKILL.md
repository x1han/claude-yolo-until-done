---
name: grill-storm
description: Use when turning vague work into approved docs/spec.md and docs/plan.md with Muse/Logos planning before claude-yolo-until-done execution.
---
# Grill-Storm

## Overview
Grill-storm is the first-party planning skill for `claude-yolo-until-done`.

It initializes a local planning bundle, runs Muse/Logos internal planning rounds through shared docs, asks the user late, and stops only when spec and plan have explicit human approval.

This skill owns planning only. Use `claude-yolo-until-done` after approval to execute the plan with hooks, worker, and watcher.

## Planning Bundle
Default bundle lives in the selected output folder under `docs/`:

- `docs/intent.md`
- `docs/open-questions.md`
- `docs/decisions.md`
- `docs/spec.md`
- `docs/plan.md`

These files are generated project artifacts, not shipped repo state.

## Required Runtime
Run from the installed `claude-yolo-until-done` skill repository:

```bash
python workflow/init_grill_docs.py \
  --project-dir <output-folder> \
  --request "Describe work to plan."
```

Then advance the planning loop:

```bash
python workflow/grill_storm_loop.py next \
  --project-dir <output-folder> \
  --run-root <output-folder>/.yolo
```

When `dispatch_required` is returned, launch the requested `Muse` or `Logos` agent using the emitted prompt and durable context, then record the structured result:

```bash
python workflow/grill_storm_loop.py record \
  --project-dir <output-folder> \
  --run-root <output-folder>/.yolo \
  --result-json '<json>'
```

`workflow/grill_storm.py --status` is status-only. `workflow/grill_storm_loop.py` owns planning-loop advancement.

## Agent Responsibilities
Muse is right-brain exploration:

- generate 1-3 adjacent but divergent possibilities
- surface constraints, unknowns, and falsifiers
- ask at most one key question
- include a recommended answer or direction
- never write final spec or plan

Logos is left-brain convergence:

- critique Muse candidates
- turn stable agreement into spec and plan structure
- record accepted decisions and rejected alternatives
- require human-approved spec before plan authoring
- require human-approved plan before execution
- never mark spec or plan approved without human approval

## Human Gate
Ask the user only after Muse and Logos have recorded accepted internal rounds, or when both agree there is one blocking uncertainty.

Human-facing output should include:

- concise consensus
- recommended answer or direction
- one question when needed
- explicit approval request for spec or plan review

## Validation
Before execution, validate planning docs:

```bash
python workflow/validate_grill_docs.py --project-dir <output-folder>
```

Execution may start only after:

- `docs/spec.md` has human-approved status/source
- `docs/plan.md` has human-approved status/source
- `workflow/validate_grill_docs.py` passes

## Relationship To claude-yolo-until-done
`grill-storm` prepares approved planning artifacts.

`claude-yolo-until-done` consumes those artifacts, bootstraps `.yolo/`, installs hooks, and runs worker/watcher execution to valid cleanup.

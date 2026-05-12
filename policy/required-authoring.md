# Required Authoring Contract

This workflow no longer depends on `superpowers` to produce initial spec and plan.

Built-in authoring flow is called `grill-storm`.

Before execution starts, authoring flow must have already produced:

- stable `intent.md`
- stable `open-questions.md`, with blocking unknowns clearly marked
- stable `decisions.md`
- approved `spec.md`
- approved `plan.md`

Current first-party grill-storm path should:

- use local Markdown files as primary state
- use Muse/`Interviewer` and Logos/`Planner` in turn loop; status routing is not itself agent launch
- let Muse infer intent from sparse user wording and propose 1-3 adjacent divergent expansions before Logos evaluates feasibility
- combine internal grilling with brainstorming-style alternatives, tradeoffs, recommendation, and spec self-review before asking user
- prefer internal verification before asking user
- return `human_dialogue` when agents reach consensus or `joint_uncertainty`
- ask user only when blocking, high-impact gap remains
- require human-approved spec before plan authoring
- require human-approved plan before execution
- never write unconfirmed assumptions as final conclusions

## Two-agent planning loop

`workflow/grill_storm.py --status` is status-only. `workflow/grill_storm_loop.py` owns planning-loop advancement and emits dispatch requests. Main Claude Code runtime must satisfy those requests by launching the matching Muse/`Interviewer` or Logos/`Planner` Agent and recording the structured result.

The agents communicate through the docs mailbox: intent, open questions, decisions, spec, plan, and role summaries. A planning conclusion is not durable until it is written there.

Execution should not start until approved spec and plan exist and match intended scope.

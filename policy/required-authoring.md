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
- use `Interviewer` and `Planner` in turn loop
- combine internal grilling with brainstorming-style challenge before asking user
- prefer internal verification before asking user
- ask user only when blocking, high-impact gap remains
- never write unconfirmed assumptions as final conclusions

Execution should not start until approved spec and plan exist and match intended scope.

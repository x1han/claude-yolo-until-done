# Decisions

## Decision Log

### 2026-05-14 - Loop mode repeats one convergence plan
- Status: accepted
- Actor: muse
- Source: consensus-candidate
- Consensus: Loop-mode convergence bundle | Summary: Implement one loop-mode convergence plan repeated up to five iterations with English durable artifacts, localized human dialogue, structured gate records, stable worker/watcher/controller wrappers, assistant-like copy, and evidence-backed acceleration review each iteration. | Tradeoffs: Gives the implementation a cohesive target and keeps machine state stable, but still requires human review before approved spec/plan status and needs Logos to verify exact parser paths, command names, and safe acceleration evidence. | Recommended: true
- Decision: Model loop mode as one approved convergence plan repeated for up to five iterations, with each iteration reading current failures/logs, fixing the highest-priority blocker, verifying, recording timing/evidence, and stopping early only on verified convergence.
- Reason: Internal Muse/Logos direction interprets the request as loop semantics rather than acyclic task splitting; human approval is still required before spec/plan approval.
- Alternatives considered: Split the four bench problems into separate acyclic tasks; require all five iterations even after convergence; let each iteration invent new scope.
- Impact: Spec and plan should define an iteration body, stop policy, and evidence requirements instead of a fixed task list.
- Revisit when: A future request asks for parallel task fan-out or independent worker assignments.

### 2026-05-14 - Logos feasibility accepts consensus candidate
- Status: accepted
- Actor: logos
- Source: consensus-candidate
- Consensus: Loop-mode convergence bundle | Summary: Feasibility review supports one loop-mode convergence plan repeated up to five iterations, with English durable artifacts, localized human dialogue, structured gate records, stable worker/watcher/controller wrappers, assistant-like copy, and evidence-backed acceleration review each iteration. | Tradeoffs: Existing preflight/controller/validator code already supports much of the loop-state skeleton, so this is feasible as an incremental slice; remaining implementation must add dialogue-language persistence/copy fixtures, stable wrapper ergonomics, and safe acceleration evidence without marking anything human-approved. | Recommended: true
- Decision: Keep the internal consensus candidate and draft the spec around a small loop-mode extension over the current acyclic runtime.
- Reason: `workflow/preflight.py`, `workflow/bootstrap.py`, `workflow/state.py`, `workflow/controller.py`, `workflow/loop_scheduler.py`, and validator tests already show loop config, mode drift checks, iteration reset, stop reasons, and loop completion certification are concrete enough to plan against.
- Alternatives considered: Treat loop mode as five independent tasks; postpone spec until wrapper command names are fully finalized; make trace Markdown authoritative for iteration evidence.
- Impact: Spec should be self-contained but remain draft; plan authoring should wait for verified human consensus and human spec review.
- Revisit when: Human rejects the consensus candidate or maintainers choose a package-level CLI that replaces direct script commands.

### 2026-05-14 - Durable workflow artifacts stay English
- Status: accepted
- Actor: muse
- Source: consensus-candidate
- Decision: Keep spec, plan, checklist, state, trace, hook reports, validator reports, and other machine-readable workflow records in English even when the user dialogue language is different.
- Reason: English durable artifacts reduce parser instability, improve cross-agent continuity, and match the user's stated requirement; human approval is still required before spec/plan approval.
- Alternatives considered: Fully localize all artifacts; localize Markdown but keep JSON English; leave language choice implicit.
- Impact: Language detection must affect only human-facing prompts/status/confirmation text, not durable machine-readable state.
- Revisit when: The project deliberately designs a full localization layer for docs and machine-readable schemas.

### 2026-05-14 - Prefer structured records over prose parsing for workflow gates
- Status: accepted
- Actor: muse
- Source: consensus-candidate
- Decision: Parser and validator paths that gate workflow advancement should consume machine-readable records or strict templates, not unconstrained human-readable prose.
- Reason: The bench problem identifies brittleness from parsing prose; fail-closed workflow gates need stable inputs; human approval is still required before spec/plan approval.
- Alternatives considered: Improve ad hoc regexes over narrative Markdown; ask operators to write prose more carefully.
- Impact: Implementation planning should inventory brittle parser paths and prioritize gate-critical conversions first.
- Revisit when: A parser path is demonstrably non-critical and cheaper to stabilize with a strict template.

### 2026-05-14 - Operator manual paths should be wrapped
- Status: accepted
- Actor: muse
- Source: consensus-candidate
- Decision: Worker, watcher, and controller manual operations should be exposed through stable commands or scripts rather than requiring operators to hand-write Python imports.
- Reason: Manual operation is part of the product UX; import snippets leak implementation details and are error-prone; human approval is still required before spec/plan approval.
- Alternatives considered: Document current Python imports more clearly; provide only examples in docs.
- Impact: Plan should include operator-facing wrappers and docs/tests for the real manual paths.
- Revisit when: The CLI surface is redesigned globally.

### 2026-05-14 - Human-facing copy should speak as an assistant
- Status: accepted
- Actor: muse
- Source: consensus-candidate
- Decision: Human-facing workflow messages should explain purpose, current state, needed confirmation, and next step in natural assistant language, avoiding procedural phrasing such as "according to the workflow".
- Reason: The user requested friendlier wording and the workflow should communicate intent rather than internal bureaucracy; human approval is still required before spec/plan approval.
- Alternatives considered: Leave existing procedural text; only patch the single quoted phrase.
- Impact: Plan should include targeted copy updates and verification fixtures for known bench messages.
- Revisit when: Broader tone/style guidelines are introduced.

## Internal Consensus Candidates
Consensus: Loop-mode convergence bundle | Summary: Implement one loop-mode convergence plan repeated up to five iterations with English durable artifacts, localized human dialogue, structured gate records, stable worker/watcher/controller wrappers, assistant-like copy, and evidence-backed acceleration review each iteration. | Tradeoffs: Gives the implementation a cohesive target and keeps machine state stable, but still requires human review before approved spec/plan status and needs Logos to verify exact parser paths, command names, and safe acceleration evidence. | Recommended: true | Source: internal-consensus-candidate

## Source Guide
Use these source values in real decision blocks when applicable; keep examples draft until accepted.
- Source: consensus
- Source: uncertainty
- Source: spec-self-review
- Source: spec-review
- Source: plan-review


### 2026-05-14T08:00:12.879115+00:00 - Human consensus approval
- Status: accepted
- Actor: human
- Source: consensus
- Decision: ok. Approved consensus: Loop-mode convergence bundle.
- Approval-ID: human-045e30fe1629456186a3170dbfd721f0

### 2026-05-14 - Logos spec self-review accepts draft spec
- Status: accepted
- Actor: logos
- Source: spec-self-review
- Decision: Logos self-review accepts `docs/spec.md` as adequate for the approved Loop-mode convergence bundle and marks it self-reviewed, not human-approved.
- Reason: The spec covers English durable artifacts, localized human dialogue, structured gate records, stable worker/watcher/controller wrappers, assistant-like copy, loop semantics up to five iterations, per-iteration evidence-backed acceleration review, and fail-closed safety without broadening scope beyond the approved consensus.
- Alternatives considered: Patch additional speculative CLI details before plan authoring; leave status as draft despite complete consensus coverage; mark the spec human-approved from internal review.
- Impact: `docs/spec.md` may proceed to human spec review, while plan authoring remains blocked until human spec approval is recorded.
- Revisit when: Human spec review requests changes or implementation evidence invalidates a spec assumption.


### 2026-05-14T08:28:13.346239+00:00 - Human spec review
- Status: accepted
- Actor: human
- Source: spec-review
- Decision: ok. Approved spec as displayed in session.
- Approval-ID: human-ac6909b5456c477b98d32da0ba79e80e

### 2026-05-14 - Logos plan self-review accepts repeated convergence-loop draft
- Status: accepted
- Actor: logos
- Source: plan-self-review
- Decision: Logos authored `docs/plan.md` as a self-reviewed implementation plan for one repeated convergence loop, not five independent acyclic tasks.
- Reason: Human consensus and human spec review approve the Loop-mode convergence bundle; the plan covers English durable artifacts, localized human dialogue, structured gate records, stable worker/watcher/controller wrappers, assistant-like copy, and per-iteration evidence-backed acceleration review while preserving fail-closed gates.
- Alternatives considered: Split implementation into five preassigned tasks; mark the plan human-approved from internal review; defer wrapper and acceleration details until execution.
- Impact: Main orchestrator may present `docs/plan.md` for human plan review, but execution remains blocked until verified `Source: plan-review` is recorded by the human/main session.
- Revisit when: Human plan review requests changes or implementation evidence shows a listed file/test target is no longer the minimal safe surface.


### 2026-05-14T08:51:52.447534+00:00 - Human plan review
- Status: accepted
- Actor: human
- Source: plan-review
- Decision: ok. Approved plan as displayed in session.
- Approval-ID: human-b19f64aac719403aa645b18ebf42df28

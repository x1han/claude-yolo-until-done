# Plan

## Loop-Mode Convergence Implementation Plan

Status: approved

> **For agentic workers:** Execute this plan with the `claude-yolo-until-done` runtime, not by splitting it into five independent acyclic tasks. The same iteration body below repeats until either verified convergence stops the loop or iteration 5 completes.

## Goal
- Add a compact loop-mode convergence slice that repeats one approved worker/watcher/controller iteration up to 5 times, keeps durable workflow artifacts in English, localizes only human-facing dialogue, replaces gate-critical prose parsing with structured records or strict templates, wraps manual operator paths, improves assistant-facing copy, and reviews acceleration evidence each iteration without bypassing gates.

## Architecture
- Preserve the existing acyclic execution core in `workflow/preflight.py`, `workflow/bootstrap.py`, `workflow/controller.py`, `workflow/state.py`, `workflow/loop_scheduler.py`, `hooks/validate_submission.py`, and `hooks/validate_completion.py`; loop mode wraps that core and records iteration evidence instead of creating a second scheduler.
- Keep `state.json` authoritative for mode/config/current iteration/dialogue language/latest verification/convergence/stop reason, keep `trace.md` chronological and English, and keep validator or hook reports as JSON under `<run-root>/hooks/`.
- Add stable operator-facing script surfaces that delegate to current modules so operators run role/action commands rather than writing imports, while preserving direct Python module entrypoints for tests and maintainers.

## Dependencies
- Approved spec: `/datf/hanxi/software/claude-yolo-until-done/repo/docs/spec.md`.
- Existing loop skeleton and tests in `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/state.py`, `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/preflight.py`, `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/controller.py`, `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/loop_scheduler.py`, `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/lifecycle.py`, `/datf/hanxi/software/claude-yolo-until-done/repo/hooks/run_gate.py`, `/datf/hanxi/software/claude-yolo-until-done/repo/hooks/validate_submission.py`, and `/datf/hanxi/software/claude-yolo-until-done/repo/hooks/validate_completion.py`.
- Human approval records already exist at `<run-root>/human_approvals.json` via `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/human_approvals.py`; reuse this structured pattern for any new gate evidence.

## File/Area Impact

Files:
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/state.py`
  - Add or extend focused helpers for `dialogue_language` and per-iteration `loop.iteration_evidence` / `loop.acceleration_review` defaults.
  - Keep JSON output `ensure_ascii=True` for durable English/machine records.
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/preflight.py`
  - Accept an explicit dialogue-language override if current CLI conventions allow adding a flag; otherwise isolate detection in a helper callable by preflight.
  - Persist detected dialogue language into authoritative state on new runs and reject continue-run drift only if an explicit override conflicts with existing state.
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/bootstrap.py`
  - Thread dialogue-language and loop evidence defaults into initial `state.json`.
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/controller.py`
  - Extend worker submit inputs with strict JSON or repeated CLI fields for iteration evidence and acceleration review.
  - Record iteration boundary evidence before reset and never skip watcher review or completion certification.
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/loop_scheduler.py`
  - Keep stop decisions simple; add validation only if controller needs to reject missing loop evidence before continuing/stopping.
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/lifecycle.py`
  - Include loop stop reason, dialogue language, and iteration evidence hashes in completion certification if they affect final completion integrity.
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/claude_hook_bridge.py`
  - Replace procedural/hard-coded prompt-gate copy with assistant-like wording and route localized human-facing strings through a small helper.
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/human_handoff.py`
  - Ensure human-facing handoff messages use persisted dialogue language when presented by hooks or wrappers; keep stored summaries English unless they are explicit human-provided answers.
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/hooks/validate_submission.py`
  - Validate machine-readable worker submission evidence, including loop iteration evidence and acceleration review when mode is loop.
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/hooks/validate_completion.py`
  - Validate loop stop reason, loop config, and completion certification hash coverage.
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/hooks/run_gate.py`
  - Preserve existing validator dispatch; only update help text if wrapper docs need clearer command names.
- Create or modify wrapper entrypoints under `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/` only if no existing script can provide the stable surface.
  - Preferred minimal wrapper: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/yolo.py` with subcommands for `preflight`, `worker submit`, `watcher review`, `watcher complete`, `validate submission`, `validate completion`, and `cleanup` that delegate to existing modules.
  - Do not add packaging metadata or a global console script in this slice unless an existing packaging file already defines entrypoints.
- Modify docs only where operator command surfaces are documented:
  - `/datf/hanxi/software/claude-yolo-until-done/repo/README.md`
  - `/datf/hanxi/software/claude-yolo-until-done/repo/QUICKSTART.md`
  - `/datf/hanxi/software/claude-yolo-until-done/repo/SKILL.md`
  - Policy files under `/datf/hanxi/software/claude-yolo-until-done/repo/policy/` only when runtime contract text must match implemented behavior.
- Modify tests:
  - `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_preflight.py`
  - `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_controller_review_flow.py`
  - `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_loop_scheduler.py`
  - `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_validators.py`
  - `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_stop_hook.py`
  - `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_user_prompt_submit_cleanup_gate.py`
  - `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_docs_and_templates.py`
  - Add a focused test file such as `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_dialogue_language.py` or `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_operator_wrappers.py` only if the behavior does not fit the existing files.

## Repeated Loop Shape
- Configure the run with `--mode loop --loop-max-iterations 5 --loop-stop-on-convergence` for this request.
- Do not create five tasks. Repeat this single iteration body:
  1. Read authoritative `state.json`, current failure/log evidence, validator reports, and current tests.
  2. Select the highest-priority current blocker or safe acceleration opportunity from fresh evidence.
  3. Write the smallest failing test or fixture for that blocker/opportunity.
  4. Implement the minimal change.
  5. Run the targeted command for the changed area.
  6. Record worker submission evidence, including acceleration review evidence and whether convergence is verified.
  7. Run submission validation.
  8. Watcher reviews evidence and either requires rework or approves.
  9. Watcher completes the iteration; controller either resets for the next iteration or records `loop.stop_reason` as `converged` or `max_iterations`.
- Continue to the next iteration only after watcher approval and controller completion. Stop early only when convergence is positively verified and recorded.

## Steps

### Task 1: Baseline loop-mode run contract and state schema

Files:
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/state.py`
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/bootstrap.py`
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/preflight.py`
- Test: `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_preflight.py`

- [ ] Step 1: Add failing tests for loop max 5 and dialogue-language persistence.
  Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_preflight.PreflightTest -v`
  Expected: FAIL before implementation with assertions showing `state.json` lacks persisted dialogue-language metadata or loop evidence defaults.
  Verify: Failure is limited to the new assertions; existing loop max/config tests still show their previous behavior.

- [ ] Step 2: Implement minimal state defaults.
  - Add a small `dialogue_language` structure to initial state, for example `{"source": "explicit|latest_user|default", "language": "en", "confidence": "explicit|inferred|default"}`.
  - Add loop evidence defaults under the existing `loop` object, for example `iteration_evidence: []`, `latest_iteration_evidence: {}`, and `acceleration_review: {}`.
  - Keep durable field names and enum values in English.
  Verify: The state helper still rejects loop stop policy in acyclic mode and still requires a positive stop policy in loop mode.

- [ ] Step 3: Thread state defaults through bootstrap/preflight.
  Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_preflight.PreflightTest.test_preflight_bootstraps_new_run_and_replaces_legacy_hooks -v`
  Expected: PASS and produced JSON includes `classification: new_run`, `action: bootstrapped_and_installed`, `mode: loop` only when loop mode was requested, and state contains dialogue-language defaults.
  Verify: Continue-run mode/config drift tests still fail closed when requested mode or loop policy differs from `state.json`.

### Task 2: Dialogue language detection for human-facing copy only

Files:
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/preflight.py`
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/claude_hook_bridge.py`
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/human_handoff.py`
- Test: `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_user_prompt_submit_cleanup_gate.py`
- Test: `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_stop_hook.py`
- Test: add `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_dialogue_language.py` if no existing file cleanly owns language helper tests.

- [ ] Step 1: Write language tests.
  Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_dialogue_language tests.test_user_prompt_submit_cleanup_gate -v`
  Expected: FAIL before implementation because explicit override and latest-substantive-user fallback are not yet implemented or hook copy ignores persisted language.
  Verify: Tests assert durable state keys remain English and only human-facing hook payload text changes language.

- [ ] Step 2: Implement a narrow language helper.
  - Prefer explicit override when available.
  - Otherwise infer only from a supplied/latest substantive user request string.
  - Fall back to English if evidence is empty or ambiguous.
  - Do not add a general i18n framework.
  Verify: Helper tests cover explicit English, explicit Chinese, inferred latest substantive Chinese, inferred latest substantive English, and fallback English.

- [ ] Step 3: Use persisted language in hook-facing messages.
  Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_stop_hook tests.test_user_prompt_submit_cleanup_gate -v`
  Expected: PASS with assistant-like block reasons in the persisted dialogue language where tests provide non-English state.
  Verify: JSON payload keys remain English; only message values are localized.

### Task 3: Structured records for gate-critical parser and validator paths

Files:
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/controller.py`
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/hooks/validate_submission.py`
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/hooks/validate_completion.py`
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/lifecycle.py`
- Test: `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_controller_review_flow.py`
- Test: `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_validators.py`

- [ ] Step 1: Add failing validator tests for structured loop evidence.
  Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_validators.ValidatorsTest -v`
  Expected: FAIL before implementation when loop-mode submission lacks iteration evidence or acceleration review, and when completion certification omits loop stop evidence.
  Verify: Existing acyclic validator tests continue to exercise the original required fields.

- [ ] Step 2: Extend worker submit data without parsing narrative prose.
  - Accept either strict JSON file/path input or explicit repeated CLI fields for `loop_iteration`, `blocker_evidence`, `verification_evidence`, `acceleration_candidate`, `acceleration_evidence`, `acceleration_decision`, and `gate_safety_basis`.
  - Store accepted evidence in `state.json` under English keys.
  - Append a short English trace line for audit readability, but never make trace the source of truth.
  Verify: Controller tests prove state has structured loop evidence after worker submit.

- [ ] Step 3: Certify structured loop stop and completion state.
  Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_controller_review_flow tests.test_validators -v`
  Expected: PASS; tampering with loop config, stop reason, or evidence after certification causes completion validator failure.
  Verify: Completion validator reports JSON under `<run-root>/hooks/completion_report.json` and includes failed check names when evidence is stale or missing.

### Task 4: Controller iteration boundaries and acceleration review each iteration

Files:
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/controller.py`
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/loop_scheduler.py`
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/state.py`
- Test: `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_controller_review_flow.py`
- Test: `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_loop_scheduler.py`

- [ ] Step 1: Add failing tests for per-iteration acceleration review.
  Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_controller_review_flow.ControllerReviewFlowTest tests.test_loop_scheduler.LoopSchedulerTest -v`
  Expected: FAIL before implementation if a loop iteration can continue without acceleration review evidence or if evidence is lost during reset.
  Verify: Tests cover both `loop.stop_reason=converged` and `loop.stop_reason=max_iterations`.

- [ ] Step 2: Preserve reviewed iteration evidence before reset.
  - When watcher completes an approved loop iteration and `loop_decision` returns `continue`, copy the current iteration evidence into `loop.iteration_evidence` before clearing transient worker/watcher fields.
  - Keep `worker_claim`, `verification_command`, `verification_result`, `review`, and `reviewed_at` reset for the next iteration exactly as current tests expect.
  Verify: Existing reset assertions in `test_loop_complete_schedules_next_worker_iteration_before_max_iterations` still pass, and new assertions show historical iteration evidence remains available.

- [ ] Step 3: Enforce speedup safety.
  Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_controller_review_flow tests.test_validators -v`
  Expected: PASS; unsafe speedups are accepted only as rejected candidates with a safety reason, and accepted speedups require timing/duplicate-work/manual-step/parser-round/command-count evidence plus gate-safety basis.
  Verify: No test allows speedup evidence to replace watcher review, completion validation, cleanup, or human approval.

### Task 5: Stable operator wrapper paths

Files:
- Create or modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/yolo.py`
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/README.md`
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/QUICKSTART.md`
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/SKILL.md`
- Test: add `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_operator_wrappers.py`
- Test: `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_docs_and_templates.py`

- [ ] Step 1: Add wrapper command tests.
  Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_operator_wrappers -v`
  Expected: FAIL before implementation because the wrapper entrypoint does not exist.
  Verify: Tests call wrapper commands as subprocesses and assert they delegate to existing preflight/controller/run_gate/cleanup behavior.

- [ ] Step 2: Implement the smallest wrapper.
  - Provide stable commands such as:
    - `python workflow/yolo.py preflight --project-dir <output-folder> ...`
    - `python workflow/yolo.py worker submit --run-root <output-folder>/.yolo ...`
    - `python workflow/yolo.py watcher review --run-root <output-folder>/.yolo ...`
    - `python workflow/yolo.py watcher complete --run-root <output-folder>/.yolo ...`
    - `python workflow/yolo.py validate submission --run-root <output-folder>/.yolo`
    - `python workflow/yolo.py validate completion --run-root <output-folder>/.yolo`
    - `python workflow/yolo.py cleanup --project-dir <output-folder> --run-root .yolo --mode complete`
  - Delegate to current modules rather than duplicating state transition logic.
  Verify: Wrapper tests prove operators do not need Python import snippets.

- [ ] Step 3: Update operator docs.
  Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_docs_and_templates.DocsAndTemplatesTest -v`
  Expected: PASS; docs mention wrapper commands and no longer rely on hand-written import examples for normal operation.
  Verify: Direct legacy script examples may remain as maintainer fallback, but normal operator path uses wrapper commands.

### Task 6: Assistant-like human-facing copy fixtures

Files:
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/claude_hook_bridge.py`
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/grill_storm.py`
- Modify: `/datf/hanxi/software/claude-yolo-until-done/repo/workflow/preflight.py`
- Modify docs only if messages are documented: `/datf/hanxi/software/claude-yolo-until-done/repo/README.md`, `/datf/hanxi/software/claude-yolo-until-done/repo/QUICKSTART.md`, `/datf/hanxi/software/claude-yolo-until-done/repo/SKILL.md`
- Test: `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_stop_hook.py`
- Test: `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_user_prompt_submit_cleanup_gate.py`
- Test: `/datf/hanxi/software/claude-yolo-until-done/repo/tests/test_grill_storm_runtime.py`

- [ ] Step 1: Add copy fixture assertions.
  Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_stop_hook tests.test_user_prompt_submit_cleanup_gate tests.test_grill_storm_runtime -v`
  Expected: FAIL before implementation for known procedural wording or hard-coded prompt copy.
  Verify: Assertions require messages to state purpose, current state, needed confirmation, and next step.

- [ ] Step 2: Replace narrow procedural phrases.
  - Replace wording like `according to the workflow` or bureaucratic gate phrasing with assistant-like language.
  - Keep exact state names, command names, and JSON keys unchanged for operator accuracy.
  Verify: Copy tests pass in English and localized cases covered by Task 2.

### Task 7: Final targeted verification and grill-storm gate check

Files:
- Verify all modified files from Tasks 1-6.
- No production code changes outside listed files unless a targeted test proves the file is in the same workflow path.

- [ ] Step 1: Run targeted test bundle.
  Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_preflight tests.test_controller_review_flow tests.test_loop_scheduler tests.test_validators tests.test_stop_hook tests.test_user_prompt_submit_cleanup_gate tests.test_docs_and_templates tests.test_grill_storm_runtime -v`
  Expected: PASS with all targeted tests successful.
  Verify: Failures, if any, map to one of the accepted scope items and are fixed before continuing.

- [ ] Step 2: Validate grill-storm docs still block until plan review.
  Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python workflow/grill_storm.py --status --project-dir /datf/hanxi/software/claude-yolo-until-done/repo`
  Expected: Before human plan-review is recorded, JSON status is `human_plan_review` with `human_allowed: true`; after main-session plan-review is recorded, status may become `ready_for_execution`.
  Verify: Execution is not started from this plan until `docs/decisions.md` and `.yolo/human_approvals.json` include verified human `Source: plan-review`.

- [ ] Step 3: Run validator or smoke preflight in a temporary run root after plan approval.
  Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python workflow/preflight.py --project-dir /datf/hanxi/software/claude-yolo-until-done/repo --run-root .yolo-loop-smoke --goal "Validate loop-mode convergence run shape." --success-criterion "Loop mode uses one repeated iteration body." --success-criterion "Worker and watcher gates remain required." --mode loop --loop-max-iterations 5 --loop-stop-on-convergence`
  Expected: PASS only after plan approval; output JSON includes `classification: new_run`, `action: bootstrapped_and_installed`, `mode: loop`, and loop config with `max_iterations: 5` and `stop_on_convergence: true`.
  Verify: Remove the temporary `.yolo-loop-smoke` bundle after inspection unless the operator explicitly wants to keep it.

## Tests
- Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_preflight -v`
  Expected: PASS; loop preflight, bootstrap, continue-run drift, and dialogue-language state tests pass.
  Verify: New loop mode still requires a stop policy and rejects stop policy flags in acyclic mode.
- Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_controller_review_flow tests.test_loop_scheduler -v`
  Expected: PASS; worker submit, watcher review, watcher complete, iteration reset, convergence stop, max-iteration stop, and acceleration evidence retention pass.
  Verify: No path advances to the next iteration without watcher approval.
- Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_validators -v`
  Expected: PASS; submission and completion validators reject missing/stale structured evidence and accept valid loop certification.
  Verify: Validator artifacts remain JSON under `<run-root>/hooks/`.
- Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_stop_hook tests.test_user_prompt_submit_cleanup_gate -v`
  Expected: PASS; lifecycle hooks still block unfinished work and use assistant-like localized copy where applicable.
  Verify: Stop-hook blocking remains fail-closed for broken durable state.
- Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python -m unittest tests.test_docs_and_templates tests.test_grill_storm_runtime tests.test_grill_storm_loop -v`
  Expected: PASS; docs, planning gates, human approval gates, and wrapper documentation stay coherent.
  Verify: Grill-storm validation still requires human consensus, human spec review, and human plan review before execution.

## Expected Outputs
- `state.json` for a loop run contains English machine keys for `mode`, `loop.enabled`, `loop.iteration`, `loop.max_iterations`, `loop.stop_on_convergence`, `loop.converged`, `loop.stop_reason`, persisted `dialogue_language`, and structured per-iteration evidence.
- `trace.md` remains English chronological audit text and records worker submit, watcher review, watcher complete, and loop iteration boundary events.
- `<run-root>/hooks/submission_report.json` and `<run-root>/hooks/completion_report.json` remain machine-readable JSON and include pass/fail checks for loop evidence and certification.
- Operator docs show stable wrapper commands for preflight, worker submit, watcher review, watcher complete, submission validation, completion validation, and cleanup.
- Human-facing hook/status messages read like an assistant explaining purpose, current state, needed confirmation, and next step.

## Verification Steps
1. Confirm this plan is not marked approved until human plan review is recorded.
   Run: `cd /datf/hanxi/software/claude-yolo-until-done/repo && python workflow/grill_storm.py --status --project-dir /datf/hanxi/software/claude-yolo-until-done/repo`
   Expected: `human_plan_review` before main-session plan approval, then `ready_for_execution` only after verified plan review.
   Verify: `.yolo/human_approvals.json` contains `recorded_by: main-session` for `source: plan-review` before execution starts.
2. Run targeted unit tests listed in `## Tests`.
   Expected: PASS for all targeted files.
   Verify: Any failure is fixed or explicitly recorded as rework before watcher approval.
3. Run a temporary loop preflight smoke only after plan review.
   Expected: JSON shows loop config with `max_iterations: 5` and `stop_on_convergence: true`.
   Verify: Continue-run with mismatched mode/config fails closed.
4. Run submission and completion validators on a test run root that includes loop evidence.
   Expected: `hooks/run_gate.py --validator submission` and `hooks/run_gate.py --validator completion` return 0 for valid evidence and 1 for tampered evidence.
   Verify: Reports name failed checks when evidence is missing or stale.

## Rollback / Safety
- Preserve acyclic behavior: if `--mode loop` is not selected, state defaults, controller transitions, validators, hooks, and docs must behave as they did before except for narrowly improved copy that does not change state semantics.
- Do not bypass human consensus, human spec review, human plan review, watcher review, submission validation, completion validation, cleanup, or hook-backed stop/prompt gates for speed.
- If a loop change breaks acyclic tests, revert the smallest related change in the touched file and rerun the targeted test before continuing.
- If wrapper commands fail, keep direct script paths documented as maintainer fallback while repairing the wrapper; do not remove existing direct entrypoints.
- If language detection is ambiguous, fall back to English rather than guessing; durable artifacts remain English in all cases.
- If acceleration evidence is weak or safety is uncertain, record the speedup as rejected for that iteration and continue with gate-preserving correctness work.
- Before risky git actions during execution, verify the repository layer with `pwd`, `git rev-parse --show-toplevel`, `git rev-parse --git-common-dir`, and `git branch --show-current` from `/datf/hanxi/software/claude-yolo-until-done/repo`.

# Exact Runtime Agent ID Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route every role-agent reuse to the actual Claude Code Agent runtime `agentId` captured after first create dispatch, while preserving a separate logical role session id for audit.

**Architecture:** `workflow/agent_sessions.py` remains the single owner of role-agent routing metadata. It will split logical `session_id` from captured `runtime_agent_id`, fail closed when reuse lacks a runtime id, and expose one recorder for the main session/operator to persist the actual Agent tool id. Grill-storm and runtime orchestrator dispatches consume the same normalized contract.

**Tech Stack:** Python 3 standard library, `unittest`, existing `state.atomic_write_text`, GitNexus MCP for impact/change checks.

---

## File structure

- Modify `workflow/agent_sessions.py`
  - Own schema migration from old `agent_id` to `session_id`.
  - Add `runtime_agent_id` to role session records.
  - Add `record_runtime_agent_id(run_root, role, session_id, runtime_agent_id, now=None)`.
  - Make reuse fail closed when `runtime_agent_id` is absent.
  - Make `dispatch_runtime_contract()` accept `session_id` and `runtime_agent_id` separately.

- Modify `workflow/grill_storm_loop.py`
  - Emit `session_id`, `runtime_agent_id`, and runtime routing in planning dispatches.
  - Update prompt text so create says runtime id must be recorded after Agent creation, and reuse says exact runtime id must be resumed.

- Modify `workflow/orchestrator.py`
  - Normalize legacy/replayed dispatch `agent_session` using new contract fields.
  - Preserve shared behavior for worker/watcher/helper.

- Modify `tests/test_agent_sessions.py`
  - Cover schema defaults, legacy migration, runtime id recording, fail-closed reuse, replacement reset.

- Modify `tests/test_grill_storm_loop.py`
  - Cover planning create/reuse payloads with both ids.

- Modify `tests/test_orchestrator.py`
  - Cover worker create/reuse payloads and legacy normalization.

- Modify `tests/test_docs_and_templates.py`, `README.md`, `SKILL.md`, `policy/run-state-contract.md`
  - Document `session_id` vs `runtime_agent_id`, exact resume behavior, and no fresh-agent fallback.

---

### Task 1: Update agent session schema tests first

**Files:**
- Modify: `tests/test_agent_sessions.py:14-110`
- Test: `tests/test_agent_sessions.py`

- [ ] **Step 1: Import the new recorder in the test file**

Add `record_runtime_agent_id` to the import list from `agent_sessions`:

```python
from agent_sessions import (
    ROLE_NAMES,
    agent_log_path,
    agent_sessions_path,
    append_planning_round,
    append_role_log_entry,
    build_replacement_prompt_context,
    ensure_agent_session_files,
    load_agent_sessions,
    load_planning_rounds,
    record_runtime_agent_id,
    replace_role_session,
    resolve_role_session,
)
```

- [ ] **Step 2: Update default registry expectations**

Replace the per-role assertions in `test_ensure_agent_session_files_writes_registry_and_role_logs` with:

```python
for role in ROLE_NAMES:
    session = registry["roles"][role]
    self.assertEqual(session["session_id"], "")
    self.assertEqual(session["runtime_agent_id"], "")
    self.assertEqual(session["generation"], 0)
    self.assertEqual(session["status"], "")
    self.assertEqual(session["log_path"], f"agents/{role}-log.md")
    self.assertEqual(session["summary_path"], f"agents/{role}-summary.md")
    self.assertTrue(agent_log_path(run_root, role).exists())
```

- [ ] **Step 3: Replace create/reuse test with runtime capture contract**

Replace `test_resolve_role_session_creates_then_reuses_same_agent_id` with:

```python
def test_resolve_role_session_requires_runtime_id_before_reuse(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / ".yolo"

        first = resolve_role_session(run_root, "worker", "worker:gate-task-001:1", now="2026-05-11T00:00:00+00:00")

        self.assertEqual(first["action"], "create")
        self.assertTrue(first["session_id"].startswith("worker-1-"))
        self.assertEqual(first["runtime_agent_id"], "")
        self.assertEqual(first["runtime"]["action"], "create")
        self.assertEqual(first["runtime"]["session_id"], first["session_id"])
        self.assertEqual(first["runtime"]["agent_id"], "")

        with self.assertRaises(ValueError) as raised:
            resolve_role_session(run_root, "worker", "worker:gate-task-001:2", now="2026-05-11T00:01:00+00:00")

        self.assertIn("runtime_agent_id is missing", str(raised.exception))
```

- [ ] **Step 4: Add runtime id recorder test**

Add this test after the missing-runtime-id test:

```python
def test_record_runtime_agent_id_enables_exact_reuse(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / ".yolo"
        first = resolve_role_session(run_root, "worker", "worker:gate-task-001:1", now="2026-05-11T00:00:00+00:00")

        updated = record_runtime_agent_id(
            run_root,
            "worker",
            first["session_id"],
            "actual-runtime-worker-123",
            now="2026-05-11T00:00:30+00:00",
        )
        second = resolve_role_session(run_root, "worker", "worker:gate-task-001:2", now="2026-05-11T00:01:00+00:00")

        self.assertEqual(updated["runtime_agent_id"], "actual-runtime-worker-123")
        self.assertEqual(second["action"], "reuse")
        self.assertEqual(second["session_id"], first["session_id"])
        self.assertEqual(second["runtime_agent_id"], "actual-runtime-worker-123")
        self.assertEqual(second["runtime"]["action"], "resume_by_agent_id")
        self.assertEqual(second["runtime"]["agent_id"], "actual-runtime-worker-123")
        self.assertEqual(second["runtime"]["session_id"], first["session_id"])
        self.assertTrue(second["runtime"]["must_resume_exact_agent_id"])
        registry = load_agent_sessions(run_root)
        self.assertEqual(registry["roles"]["worker"]["last_dispatch_owner"], "worker:gate-task-001:2")
```

- [ ] **Step 5: Add recorder mismatch test**

Add this test after the recorder success test:

```python
def test_record_runtime_agent_id_rejects_wrong_session_id(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / ".yolo"
        resolve_role_session(run_root, "worker", "worker:gate-task-001:1", now="2026-05-11T00:00:00+00:00")

        with self.assertRaises(ValueError) as raised:
            record_runtime_agent_id(run_root, "worker", "worker-1-wrong", "actual-runtime-worker-123")

        self.assertIn("session_id does not match", str(raised.exception))
```

- [ ] **Step 6: Update separate-role assertions**

In `test_resolve_role_session_keeps_roles_separate`, replace `agent_id` assertions with:

```python
self.assertNotEqual(worker["session_id"], watcher["session_id"])
self.assertEqual(worker["role"], "worker")
self.assertEqual(watcher["role"], "watcher")
```

- [ ] **Step 7: Update replacement test assertions**

In `test_replace_role_session_marks_generation_and_notebook`, replace id assertions with:

```python
self.assertEqual(replacement["action"], "replace")
self.assertEqual(replacement["generation"], 2)
self.assertNotEqual(replacement["session_id"], original["session_id"])
self.assertEqual(replacement["runtime_agent_id"], "")
self.assertEqual(replacement["runtime"]["action"], "create")
self.assertEqual(replacement["runtime"]["session_id"], replacement["session_id"])
self.assertEqual(replacement["runtime"]["agent_id"], "")
self.assertFalse(replacement["runtime"]["replacement_allowed"])
```

- [ ] **Step 8: Add legacy registry migration test**

Add this test before the malformed registry test:

```python
def test_load_agent_sessions_migrates_legacy_agent_id_to_session_id(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / ".yolo"
        run_root.mkdir()
        agent_sessions_path(run_root).write_text(
            json.dumps(
                {
                    "version": 1,
                    "roles": {
                        role: {
                            "agent_id": "worker-1-legacy" if role == "worker" else "",
                            "generation": 1 if role == "worker" else 0,
                            "status": "active" if role == "worker" else "",
                            "created_at": "2026-05-11T00:00:00+00:00" if role == "worker" else "",
                            "last_seen_at": "2026-05-11T00:00:00+00:00" if role == "worker" else "",
                            "log_path": f"agents/{role}-log.md",
                            "summary_path": f"agents/{role}-summary.md",
                            "last_dispatch_owner": "worker:gate-task-001:1" if role == "worker" else "",
                            "replacement_reason": "",
                        }
                        for role in ROLE_NAMES
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        registry = load_agent_sessions(run_root)

        self.assertEqual(registry["roles"]["worker"]["session_id"], "worker-1-legacy")
        self.assertEqual(registry["roles"]["worker"]["runtime_agent_id"], "")
        self.assertNotIn("agent_id", registry["roles"]["worker"])
```

- [ ] **Step 9: Run tests and verify failures**

Run:

```bash
cd /datf/hanxi/software/claude-yolo-until-done/repo && python3 -m unittest tests.test_agent_sessions -v
```

Expected: fails because `record_runtime_agent_id`, `session_id`, and `runtime_agent_id` are not implemented yet.

---

### Task 2: Implement agent session schema and runtime id recorder

**Files:**
- Modify: `workflow/agent_sessions.py:66-300`
- Test: `tests/test_agent_sessions.py`

- [ ] **Step 1: Replace default role session shape**

Change `default_role_session()` to:

```python
def default_role_session(role: str) -> dict:
    require_role(role)
    return {
        "session_id": "",
        "runtime_agent_id": "",
        "generation": 0,
        "status": "",
        "created_at": "",
        "last_seen_at": "",
        "log_path": relative_agent_log_path(role),
        "summary_path": relative_agent_summary_path(role),
        "last_dispatch_owner": "",
        "replacement_reason": "",
    }
```

- [ ] **Step 2: Add legacy normalization helper**

Add this helper above `validate_agent_sessions()`:

```python
def normalize_role_session(role: str, session: dict) -> dict:
    merged = default_role_session(role)
    legacy_agent_id = session.get("agent_id", "")
    merged.update({key: value for key, value in session.items() if key != "agent_id"})
    if not merged.get("session_id") and isinstance(legacy_agent_id, str):
        merged["session_id"] = legacy_agent_id
    return merged
```

- [ ] **Step 3: Use normalization during validation**

Replace these lines in `validate_agent_sessions()`:

```python
merged = default_role_session(role)
merged.update(session)
roles[role] = merged
```

with:

```python
roles[role] = normalize_role_session(role, session)
```

- [ ] **Step 4: Replace runtime contract function**

Replace `dispatch_runtime_contract()` with:

```python
def dispatch_runtime_contract(action: str, session_id: str, runtime_agent_id: str = "") -> dict:
    if action not in SESSION_ACTIONS:
        raise ValueError(f"Unsupported agent session action: {action}")
    if action == SESSION_ACTION_REUSE and not runtime_agent_id:
        raise ValueError(f"Cannot reuse role agent session {session_id}: runtime_agent_id is missing")
    return {
        "tool": "Agent",
        "action": RUNTIME_ACTION_RESUME_BY_AGENT_ID if action == SESSION_ACTION_REUSE else RUNTIME_ACTION_CREATE,
        "agent_id": runtime_agent_id if action == SESSION_ACTION_REUSE else "",
        "session_id": session_id,
        "must_resume_exact_agent_id": action == SESSION_ACTION_REUSE,
        "replacement_allowed": False,
        "replacement_instruction": "Only replace this role agent through explicit replacement flow after the stored agent is unavailable.",
    }
```

- [ ] **Step 5: Update `resolve_role_session()` to use `session_id`**

Replace body section from active check through return with:

```python
session = payload["roles"][role]
if session.get("status") == "active" and session.get("session_id"):
    action = SESSION_ACTION_REUSE
else:
    session["generation"] = int(session.get("generation", 0)) + 1
    session["session_id"] = new_agent_id(role, session["generation"])
    session["runtime_agent_id"] = ""
    session["status"] = "active"
    session["created_at"] = observed_at
    session["replacement_reason"] = ""
    action = SESSION_ACTION_CREATE
session["last_seen_at"] = observed_at
session["last_dispatch_owner"] = dispatch_owner
runtime = dispatch_runtime_contract(action, session["session_id"], session.get("runtime_agent_id", ""))
write_agent_sessions(run_root, payload)
append_role_log_entry(
    run_root,
    role,
    f"dispatch {dispatch_owner}",
    actions=["Dispatch received."],
    observations=[f"Session action: {action}.", f"Generation: {session['generation']}.", f"Session: {session['session_id']}.", f"Runtime agent: {session.get('runtime_agent_id', '') or 'not recorded'}"],
    result=["Role session ready."],
    next_steps=["Continue assigned role work."],
    now=observed_at,
)
return {"role": role, "action": action, **session, "runtime": runtime}
```

- [ ] **Step 6: Add runtime id recorder**

Add this function after `resolve_role_session()`:

```python
def record_runtime_agent_id(run_root: Path, role: str, session_id: str, runtime_agent_id: str, now: str | None = None) -> dict:
    require_role(role)
    clean_session_id = session_id.strip()
    clean_runtime_agent_id = runtime_agent_id.strip()
    if not clean_session_id:
        raise ValueError("session_id is required")
    if not clean_runtime_agent_id:
        raise ValueError("runtime_agent_id is required")
    observed_at = now or timestamp()
    payload = load_agent_sessions(run_root)
    ensure_agent_logs(run_root)
    session = payload["roles"][role]
    if session.get("session_id") != clean_session_id:
        raise ValueError(f"Cannot record runtime_agent_id for {role}: session_id does not match active session")
    if session.get("status") != "active":
        raise ValueError(f"Cannot record runtime_agent_id for {role}: session is not active")
    session["runtime_agent_id"] = clean_runtime_agent_id
    session["last_seen_at"] = observed_at
    write_agent_sessions(run_root, payload)
    append_role_log_entry(
        run_root,
        role,
        "runtime agent id recorded",
        actions=["Recorded Agent tool runtime id."],
        observations=[f"Session: {clean_session_id}.", f"Runtime agent: {clean_runtime_agent_id}."],
        result=["Exact resume routing ready."],
        now=observed_at,
    )
    return {"role": role, **session, "runtime": dispatch_runtime_contract(SESSION_ACTION_REUSE, clean_session_id, clean_runtime_agent_id)}
```

- [ ] **Step 7: Update replacement to clear runtime id**

In `replace_role_session()`, replace:

```python
replacement["agent_id"] = new_agent_id(role, replacement["generation"])
```

with:

```python
replacement["session_id"] = new_agent_id(role, replacement["generation"])
replacement["runtime_agent_id"] = ""
```

Then replace return line with:

```python
return {"role": role, "action": SESSION_ACTION_REPLACE, **replacement, "runtime": dispatch_runtime_contract(SESSION_ACTION_REPLACE, replacement["session_id"], "")}
```

- [ ] **Step 8: Run tests**

Run:

```bash
cd /datf/hanxi/software/claude-yolo-until-done/repo && python3 -m unittest tests.test_agent_sessions -v
```

Expected: `tests.test_agent_sessions` passes.

---

### Task 3: Update grill-storm planning dispatch contract

**Files:**
- Modify: `workflow/grill_storm_loop.py:28-128`
- Modify: `tests/test_grill_storm_loop.py:35-128`
- Test: `tests/test_grill_storm_loop.py`

- [ ] **Step 1: Update create dispatch test expectations**

In `test_planning_step_requests_muse_first`, replace id assertions with:

```python
self.assertEqual(dispatch["session_action"], "create")
self.assertTrue(dispatch["session_id"].startswith("muse-1-"))
self.assertEqual(dispatch["runtime_agent_id"], "")
self.assertEqual(dispatch["agent_generation"], 1)
self.assertEqual(dispatch["agent_runtime"]["action"], "create")
self.assertEqual(dispatch["agent_runtime"]["session_id"], dispatch["session_id"])
self.assertEqual(dispatch["agent_runtime"]["agent_id"], "")
```

- [ ] **Step 2: Update persistent session test to capture logical id**

In `test_persistent_session_reused_across_rounds`, replace:

```python
agent_id_1 = dispatch1["agent_id"]
```

with:

```python
session_id_1 = dispatch1["session_id"]
```

Replace registry assertion with:

```python
self.assertEqual(sessions["roles"]["muse"]["session_id"], session_id_1)
self.assertEqual(sessions["roles"]["muse"]["generation"], 1)
self.assertEqual(sessions["roles"]["muse"]["status"], "active")
self.assertEqual(sessions["roles"]["logos"]["generation"], 1)
self.assertEqual(sessions["roles"]["logos"]["status"], "active")
```

- [ ] **Step 3: Update reuse test to record runtime id first**

Add import:

```python
from agent_sessions import load_agent_sessions, record_runtime_agent_id
```

In `test_planning_dispatch_reuse_instructs_exact_agent_id_resume`, replace setup after first dispatch with:

```python
session_id = first["session_id"]
record_runtime_agent_id(run_root, "muse", session_id, "actual-runtime-muse-123")
```

Replace assertions with:

```python
self.assertEqual(dispatch["session_action"], "reuse")
self.assertEqual(dispatch["session_id"], session_id)
self.assertEqual(dispatch["runtime_agent_id"], "actual-runtime-muse-123")
self.assertEqual(dispatch["agent_runtime"]["action"], "resume_by_agent_id")
self.assertEqual(dispatch["agent_runtime"]["agent_id"], "actual-runtime-muse-123")
self.assertEqual(dispatch["agent_runtime"]["session_id"], session_id)
self.assertTrue(dispatch["agent_runtime"]["must_resume_exact_agent_id"])
self.assertIn(session_id, dispatch["agent_prompt"])
self.assertIn("actual-runtime-muse-123", dispatch["agent_prompt"])
self.assertIn("Do not create a fresh muse agent", dispatch["agent_prompt"])
```

- [ ] **Step 4: Add fail-closed planning reuse test**

Add this test after the reuse test:

```python
def test_planning_dispatch_reuse_fails_without_runtime_agent_id(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp)
        self.write_docs(project_dir)
        run_root = project_dir / ".yolo"
        run_planning_step(project_dir, run_root=run_root)

        with self.assertRaises(ValueError) as raised:
            build_dispatch_request(
                project_dir,
                {
                    "status": "needs_internal_round",
                    "next_actor": "muse",
                    "planning_mode": "internal_round",
                    "read": ["docs/intent.md"],
                    "write_any_of": ["docs/decisions.md"],
                    "reason": "same role again",
                },
                run_root=run_root,
                round_number=2,
            )

        self.assertIn("runtime_agent_id is missing", str(raised.exception))
```

- [ ] **Step 5: Update dispatch payload construction**

In `build_dispatch_request()`, replace session fields with:

```python
request["session_action"] = session["action"]
request["session_id"] = session["session_id"]
request["runtime_agent_id"] = session.get("runtime_agent_id", "")
request["agent_generation"] = session["generation"]
request["agent_runtime"] = session["runtime"]
```

- [ ] **Step 6: Update prompt routing text**

In `build_agent_prompt()`, replace routing lines with:

```python
lines.extend([
    "",
    "## Agent session routing",
    f"- session_action: {dispatch.get('session_action', '')}",
    f"- session_id: {dispatch.get('session_id', '')}",
    f"- runtime_agent_id: {dispatch.get('runtime_agent_id', '')}",
    f"- agent_generation: {dispatch.get('agent_generation', '')}",
])
```

Replace create/reuse instruction block with:

```python
if agent_runtime.get("action") == RUNTIME_ACTION_RESUME_BY_AGENT_ID:
    lines.append(f"- Runtime must resume/send to exactly this runtime_agent_id. Do not create a fresh {role} agent unless explicit replacement has been requested.")
else:
    lines.append(f"- Runtime may create this {role} agent for the recorded session_id. After creation, record the actual Agent tool agentId before any reuse dispatch.")
```

- [ ] **Step 7: Run tests**

Run:

```bash
cd /datf/hanxi/software/claude-yolo-until-done/repo && python3 -m unittest tests.test_agent_sessions tests.test_grill_storm_loop -v
```

Expected: both test modules pass.

---

### Task 4: Update orchestrator dispatch contract

**Files:**
- Modify: `workflow/orchestrator.py:278-296`
- Modify: `tests/test_orchestrator.py:624-758`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Update orchestrator test imports**

At top of `tests/test_orchestrator.py`, add `record_runtime_agent_id` to existing `agent_sessions` import. Final import should include:

```python
from agent_sessions import load_agent_sessions, record_runtime_agent_id
```

If the import is already multi-line, add only `record_runtime_agent_id` inside it.

- [ ] **Step 2: Update first-dispatch worker assertions**

In `test_orchestrate_creates_worker_agent_session_on_first_dispatch`, replace id assertions with:

```python
self.assertEqual(result["agent_session"]["role"], "worker")
self.assertEqual(result["agent_session"]["action"], "create")
self.assertEqual(result["agent_session"]["generation"], 1)
self.assertTrue(result["agent_session"]["session_id"].startswith("worker-1-"))
self.assertEqual(result["agent_session"]["runtime_agent_id"], "")
self.assertEqual(result["agent_session"]["runtime"]["action"], "create")
self.assertEqual(result["agent_session"]["runtime"]["session_id"], result["agent_session"]["session_id"])
self.assertEqual(result["agent_session"]["runtime"]["agent_id"], "")
registry = load_agent_sessions(run_root)
self.assertEqual(registry["roles"]["worker"]["session_id"], result["agent_session"]["session_id"])
```

- [ ] **Step 3: Update worker reuse test to record runtime id before second dispatch**

In `test_orchestrate_reuses_worker_agent_session_on_replayed_role`, after `first = orchestrate(run_root, state)`, add:

```python
record_runtime_agent_id(run_root, "worker", first["agent_session"]["session_id"], "actual-runtime-worker-123")
```

Replace reuse assertions with:

```python
self.assertEqual(second["agent_session"]["action"], "reuse")
self.assertEqual(second["agent_session"]["session_id"], first["agent_session"]["session_id"])
self.assertEqual(second["agent_session"]["runtime_agent_id"], "actual-runtime-worker-123")
self.assertEqual(second["agent_session"]["runtime"]["action"], "resume_by_agent_id")
self.assertEqual(second["agent_session"]["runtime"]["agent_id"], "actual-runtime-worker-123")
self.assertEqual(second["agent_session"]["runtime"]["session_id"], first["agent_session"]["session_id"])
self.assertTrue(second["agent_session"]["runtime"]["must_resume_exact_agent_id"])
```

- [ ] **Step 4: Add worker reuse fail-closed test**

Add this test after worker reuse test:

```python
def test_orchestrate_reuse_fails_without_runtime_agent_id(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / ".yolo"
        state = {
            "state_version": 1,
            "task_id": "task-001",
            "task_title": "Persist agent sessions",
            "task_goal": "Keep worker context.",
            "task_scope": [],
            "task_inputs": {},
            "task_handoff_notes": [],
            "gate_id": "gate-task-001",
            "gate_attempt": 0,
            "gate_max_attempts": 5,
            "requested_role": "worker",
            "dispatch_status": "pending",
            "dispatch_intent": {"role": "worker", "action": "worker_update"},
            "dispatch_claim": {},
            "dispatch_generation": 0,
            "last_dispatch": {},
            "worker_request": "",
            "worker_question": "",
            "human_handoff": {},
            "blocked_for_human": False,
            "status": "active",
            "owner": "worker",
            "supervision": {"last_token_io_at": "2026-05-11T00:00:00+00:00", "last_progress_at": "", "stall_timeout_seconds": 600, "retry_limit": 3, "retry_count": 0},
        }
        write_state(run_root, state)
        orchestrate(run_root, state)
        next_state = load_state(run_root)
        next_state["state_version"] += 1
        next_state["dispatch_status"] = "pending"
        next_state["dispatch_intent"] = {"role": "worker", "action": "worker_update"}
        next_state["dispatch_claim"] = {}
        next_state["last_dispatch"] = {}
        write_state(run_root, next_state)

        with self.assertRaises(ValueError) as raised:
            orchestrate(run_root, next_state)

        self.assertIn("runtime_agent_id is missing", str(raised.exception))
```

- [ ] **Step 5: Update legacy replay normalization**

Replace `ensure_dispatch_agent_session()` branch that reads legacy `agent_id` with:

```python
if isinstance(agent_session, dict) and agent_session:
    if "runtime" in agent_session:
        return dispatch
    action = str(agent_session.get("action", ""))
    session_id = str(agent_session.get("session_id") or agent_session.get("agent_id") or "")
    runtime_agent_id = str(agent_session.get("runtime_agent_id", ""))
    if action and session_id:
        enriched = dict(dispatch)
        normalized_session = dict(agent_session)
        normalized_session.pop("agent_id", None)
        normalized_session["session_id"] = session_id
        normalized_session["runtime_agent_id"] = runtime_agent_id
        normalized_session["runtime"] = dispatch_runtime_contract(action, session_id, runtime_agent_id)
        enriched["agent_session"] = normalized_session
        return enriched
    return dispatch
```

- [ ] **Step 6: Update legacy replay test expectations**

In `test_orchestrate_enriches_legacy_replayed_dispatch_with_agent_session`, replace persisted assertion with:

```python
self.assertEqual(result["agent_session"]["action"], "create")
self.assertEqual(result["agent_session"]["runtime"]["action"], "create")
self.assertEqual(persisted["last_dispatch"]["agent_session"]["session_id"], result["agent_session"]["session_id"])
```

- [ ] **Step 7: Run orchestrator tests**

Run:

```bash
cd /datf/hanxi/software/claude-yolo-until-done/repo && python3 -m unittest tests.test_orchestrator -v
```

Expected: `tests.test_orchestrator` passes.

---

### Task 5: Update docs and doc tests

**Files:**
- Modify: `tests/test_docs_and_templates.py:118-132`
- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `policy/run-state-contract.md`
- Test: `tests/test_docs_and_templates.py`

- [ ] **Step 1: Update doc test expectations**

In `test_docs_describe_persistent_role_agent_sessions`, extend assertions inside the loop:

```python
self.assertIn("session_id", body)
self.assertIn("runtime_agent_id", body)
self.assertIn("actual Agent tool", body)
self.assertIn("no fresh-agent fallback", body)
```

Keep existing assertions for `agent_sessions.json`, `role lab notebook`, `per `.yolo/` run`, `resume/send to exactly`, `fresh role agent`, and `Replacement is explicit only`.

- [ ] **Step 2: Update `README.md` role session section**

Find existing role-agent session text in `README.md`. Replace or extend it with this paragraph:

```markdown
Role-agent sessions are per `.yolo/` run. `agent_sessions.json` is routing metadata, not workflow authority; `state.json` remains authoritative. Each role entry separates `session_id` (workflow-generated role/generation audit id) from `runtime_agent_id` (actual Agent tool id returned after first create). `session_action=create` creates the role agent once for that generation and the operator must record the actual Agent tool `agentId` as `runtime_agent_id` before any reuse. `session_action=reuse` means resume/send to exactly `runtime_agent_id`; there is no fresh-agent fallback. Replacement is explicit only and creates a new generation with a new `session_id` and empty `runtime_agent_id` until creation is recorded.
```

- [ ] **Step 3: Update `SKILL.md` runtime model section**

Replace the current role session paragraph with:

```markdown
Role agent sessions are per `.yolo/` run. Reuse the same role agent for later dispatches to that role when possible.

Each role dispatch carries routing metadata. `create` means create the role agent once for the recorded generation. The generated `session_id` is audit identity only; after Agent creation, record the actual Agent tool `agentId` as `runtime_agent_id`. `reuse` means resume/send to exactly `runtime_agent_id`; do not create a fresh role agent with new context. If `runtime_agent_id` is missing on reuse, fail closed instead of falling back. Replacement is explicit only and creates a new generation through replacement flow.

`agent_sessions.json` stores role-agent routing metadata. It is not workflow authority. `state.json` remains authoritative.
```

- [ ] **Step 4: Update `policy/run-state-contract.md`**

Find role-agent session section and replace or extend it with:

```markdown
## Role-agent routing metadata

`agent_sessions.json` is per-run routing metadata. It is not workflow authority; `state.json` remains authoritative for task status, owner, gates, dispatch status, and completion.

Each role session has:
- `session_id`: workflow-generated role/generation audit id.
- `runtime_agent_id`: actual Agent tool id returned by first create dispatch.
- `generation`: explicit replacement lineage.
- role log and summary paths under `.yolo/agents/`.

`session_action=create` may create the role agent for the recorded generation. After creation, the operator records the actual Agent tool `agentId` as `runtime_agent_id`. `session_action=reuse` must resume/send to exactly `runtime_agent_id`. Missing `runtime_agent_id` on reuse is a hard blocker with no fresh-agent fallback. Replacement is explicit only.
```

- [ ] **Step 5: Run docs tests**

Run:

```bash
cd /datf/hanxi/software/claude-yolo-until-done/repo && python3 -m unittest tests.test_docs_and_templates -v
```

Expected: `tests.test_docs_and_templates` passes.

---

### Task 6: Run combined verification and inspect impact

**Files:**
- No edits expected.
- Test: targeted unit suites plus GitNexus change detection.

- [ ] **Step 1: Run targeted implementation tests**

Run:

```bash
cd /datf/hanxi/software/claude-yolo-until-done/repo && python3 -m unittest tests.test_agent_sessions tests.test_grill_storm_loop tests.test_orchestrator tests.test_docs_and_templates -v
```

Expected: all tests pass.

- [ ] **Step 2: Run focused runtime regression tests**

Run:

```bash
cd /datf/hanxi/software/claude-yolo-until-done/repo && python3 -m unittest tests.test_grill_storm_runtime tests.test_grill_storm_loop tests.test_agent_sessions tests.test_docs_and_templates -v
```

Expected: all tests pass.

- [ ] **Step 3: Run GitNexus change detection**

Run MCP tool:

```text
mcp__gitnexus__detect_changes(scope="unstaged", repo="claude-yolo-until-done")
```

Expected: changed symbols are limited to agent session routing, planning dispatch routing, orchestrator dispatch normalization, docs/tests.

- [ ] **Step 4: Report remaining bench blocker status**

Report whether implementation is ready to rerun real test4. Do not claim real bench pass until rerun produces evidence under `/datg/hanxi/tmp/claude-yolo/real_test/test4` or new bench directory.

---

## Self-review

Spec coverage:
- Runtime id capture: Task 2.
- Reuse exact actual Agent tool id: Tasks 2, 3, 4.
- Fail closed on missing runtime id: Tasks 1, 2, 3, 4.
- Replacement reset: Tasks 1, 2.
- All five roles: shared `ROLE_NAMES` schema plus orchestrator/planning coverage.
- Docs: Task 5.
- Verification: Task 6.

Placeholder scan clean. No commit steps included because user explicitly said not to commit.

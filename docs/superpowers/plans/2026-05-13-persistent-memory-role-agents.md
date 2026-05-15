# Persistent Memory Role Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace unsupported exact live Agent reuse with Claude Code project-memory continuity for all role agents.

**Architecture:** Every role dispatch creates a fresh subagent and restores continuity from `.claude/agent-memory/<role>/MEMORY.md`, `.yolo/agents/<role>-log.md`, and workflow docs/state. `.yolo/agent_sessions.json` remains routing/audit metadata only, now recording role invocation and memory paths instead of required runtime resume handles.

**Tech Stack:** Python standard library workflow scripts, unittest tests, Claude Code subagent markdown definitions with `memory: project`.

---

## File Structure

- Modify `.claude/agents/muse.md`, `.claude/agents/logos.md`, `.claude/agents/worker.md`, `.claude/agents/watcher.md`, `.claude/agents/helper.md` to add `memory: project` and role memory rules.
- Create `.claude/agent-memory/{muse,logos,worker,watcher,helper}/MEMORY.md` default memory files.
- Modify `workflow/agent_sessions.py` to introduce project-memory registry schema and dispatch metadata.
- Modify `workflow/grill_storm_loop.py` to emit memory-based dispatch payloads and prompts.
- Modify `workflow/orchestrator.py` to emit memory-based dispatch payloads for worker/watcher/helper.
- Modify `README.md`, `SKILL.md`, `.claude/skills/grill-storm/SKILL.md`, `policy/run-state-contract.md` to document project-memory continuity.
- Modify tests: `tests/test_agent_sessions.py`, `tests/test_grill_storm_loop.py`, `tests/test_orchestrator.py`, `tests/test_docs_and_templates.py`, and `tests/test_bootstrap_lightweight_bundle.py`.

---

### Task 1: Add role project memory files and docs tests

**Files:**
- Modify: `.claude/agents/muse.md`
- Modify: `.claude/agents/logos.md`
- Modify: `.claude/agents/worker.md`
- Modify: `.claude/agents/watcher.md`
- Modify: `.claude/agents/helper.md`
- Create: `.claude/agent-memory/muse/MEMORY.md`
- Create: `.claude/agent-memory/logos/MEMORY.md`
- Create: `.claude/agent-memory/worker/MEMORY.md`
- Create: `.claude/agent-memory/watcher/MEMORY.md`
- Create: `.claude/agent-memory/helper/MEMORY.md`
- Test: `tests/test_docs_and_templates.py`

- [ ] **Step 1: Write failing docs test**

Add assertions to `tests/test_docs_and_templates.py::test_agent_role_files_define_minimal_constraints` so each role file must contain `memory: project`, `project memory`, `MEMORY.md`, and role log language.

For each role case, add required strings:

```python
"memory: project",
"project memory",
"MEMORY.md",
"role log",
```

Add a new test:

```python
def test_role_agent_project_memory_files_exist(self) -> None:
    for role in ("muse", "logos", "worker", "watcher", "helper"):
        memory = SKILL_ROOT / ".claude" / "agent-memory" / role / "MEMORY.md"
        body = memory.read_text(encoding="utf-8")
        self.assertIn(f"# {role} memory", body)
        self.assertIn("## Role Conventions", body)
        self.assertIn("## Project Conventions", body)
        self.assertIn("## Reliable Verification", body)
```

- [ ] **Step 2: Run docs test to verify failure**

Run:

```bash
python3 -m unittest tests.test_docs_and_templates.DocsAndTemplatesTest.test_agent_role_files_define_minimal_constraints tests.test_docs_and_templates.DocsAndTemplatesTest.test_role_agent_project_memory_files_exist -v
```

Expected: FAIL because role frontmatter and memory files are missing.

- [ ] **Step 3: Update role definitions**

For each `.claude/agents/<role>.md`, add frontmatter line:

```yaml
memory: project
```

Add body rules adapted per role:

```markdown
## Persistent project memory
Before role work, consult your project memory `MEMORY.md` when relevant, then read your run role log and dispatch-required docs. After role work, update your run role log with concise operational context. Update project memory only with durable role/project learnings: stable conventions, recurring issues, reliable verification, or risky modules. Do not store task chatter, secrets, full diffs, or unverified guesses.
```

For Muse/Logos add:

```markdown
Do not edit shipped source code. Write only allowed planning docs, your role log, and your project memory.
```

For Watcher add:

```markdown
Do not fix source code during review. Write review results, your role log, and durable project memory only.
```

For Worker/Helper add:

```markdown
Modify source files only when the supplied task packet authorizes it.
```

- [ ] **Step 4: Create default memory files**

Create each `.claude/agent-memory/<role>/MEMORY.md` with:

```markdown
# <role> memory

## Role Conventions

## Project Conventions

## Risky Areas

## Reliable Verification

## Recurring Issues
```

Use lowercase role name in title.

- [ ] **Step 5: Run docs test to verify pass**

Run same command from Step 2.

Expected: PASS.

---

### Task 2: Convert role registry to project-memory continuity

**Files:**
- Modify: `workflow/agent_sessions.py`
- Test: `tests/test_agent_sessions.py`

- [ ] **Step 1: Write failing registry tests**

Update `tests/test_agent_sessions.py` imports only if names change. Add/adjust tests to assert default role entry has these fields:

```python
self.assertEqual(session["role_invocation_id"], "")
self.assertEqual(session["last_runtime_agent_id"], "")
self.assertEqual(session["continuity_model"], "project_memory")
self.assertEqual(session["memory_scope"], "project")
self.assertEqual(session["memory_path"], f".claude/agent-memory/{role}/MEMORY.md")
self.assertEqual(session["role_log_path"], f".yolo/agents/{role}-log.md")
self.assertEqual(session["summary_path"], f".yolo/agents/{role}-summary.md")
```

Replace runtime-id reuse tests with audit-only tests:

```python
def test_record_runtime_agent_id_is_audit_only(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / ".yolo"
        first = resolve_role_session(run_root, "worker", "worker:gate-task-001:1", now="2026-05-11T00:00:00+00:00")
        updated = record_runtime_agent_id(run_root, "worker", first["role_invocation_id"], "actual-runtime-worker-123", now="2026-05-11T00:00:30+00:00")
        second = resolve_role_session(run_root, "worker", "worker:gate-task-001:2", now="2026-05-11T00:01:00+00:00")

        self.assertEqual(updated["last_runtime_agent_id"], "actual-runtime-worker-123")
        self.assertEqual(second["action"], "create")
        self.assertNotEqual(second["role_invocation_id"], first["role_invocation_id"])
        self.assertEqual(second["continuity_model"], "project_memory")
        self.assertEqual(second["dispatch"]["dispatch_action"], "create")
        self.assertNotIn("resume_by_agent_id", json.dumps(second))
```

Add legacy migration test:

```python
def test_load_agent_sessions_migrates_exact_reuse_schema_to_memory_schema(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / ".yolo"
        run_root.mkdir()
        agent_sessions_path(run_root).write_text(json.dumps({
            "version": 1,
            "roles": {
                role: {
                    "role_session_id": "worker-1-legacy" if role == "worker" else "",
                    "runtime_agent_id": "actual-runtime-worker-123" if role == "worker" else "",
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
        }) + "\n", encoding="utf-8")

        registry = load_agent_sessions(run_root)
        worker = registry["roles"]["worker"]
        self.assertEqual(registry["version"], 2)
        self.assertEqual(worker["role_invocation_id"], "worker-1-legacy")
        self.assertEqual(worker["last_runtime_agent_id"], "actual-runtime-worker-123")
        self.assertEqual(worker["continuity_model"], "project_memory")
        self.assertNotIn("role_session_id", worker)
        self.assertNotIn("runtime_agent_id", worker)
```

- [ ] **Step 2: Run agent session tests to verify failure**

Run:

```bash
python3 -m unittest tests.test_agent_sessions -v
```

Expected: FAIL because schema still uses exact runtime reuse fields.

- [ ] **Step 3: Implement schema helpers**

In `workflow/agent_sessions.py` add constants:

```python
CONTINUITY_MODEL_PROJECT_MEMORY = "project_memory"
DISPATCH_ACTION_CREATE = "create"
MEMORY_SCOPE_PROJECT = "project"
```

Add helpers:

```python
def role_memory_path(role: str) -> str:
    require_role(role)
    return f".claude/agent-memory/{role}/MEMORY.md"


def role_log_registry_path(role: str) -> str:
    require_role(role)
    return f".yolo/agents/{role}-log.md"
```

Update `default_role_session(role)` to return version 2 fields:

```python
return {
    "role_invocation_id": "",
    "last_runtime_agent_id": "",
    "generation": 0,
    "status": "",
    "continuity_model": CONTINUITY_MODEL_PROJECT_MEMORY,
    "memory_scope": MEMORY_SCOPE_PROJECT,
    "memory_path": role_memory_path(role),
    "role_log_path": role_log_registry_path(role),
    "summary_path": f".yolo/agents/{role}-summary.md",
    "created_at": "",
    "last_seen_at": "",
    "last_dispatch_owner": "",
    "replacement_reason": "",
}
```

Update `normalize_role_session(role, session)` to migrate old names:

```python
legacy_role_invocation_id = session.get("role_invocation_id") or session.get("role_session_id") or session.get("agent_id", "")
legacy_last_runtime_agent_id = session.get("last_runtime_agent_id") or session.get("runtime_agent_id", "")
merged = default_role_session(role)
for key, value in session.items():
    if key not in {"agent_id", "role_session_id", "runtime_agent_id", "agent_runtime", "runtime"} and key in merged:
        merged[key] = value
if isinstance(legacy_role_invocation_id, str):
    merged["role_invocation_id"] = legacy_role_invocation_id
if isinstance(legacy_last_runtime_agent_id, str):
    merged["last_runtime_agent_id"] = legacy_last_runtime_agent_id
merged["continuity_model"] = CONTINUITY_MODEL_PROJECT_MEMORY
merged["memory_scope"] = MEMORY_SCOPE_PROJECT
merged["memory_path"] = role_memory_path(role)
merged["role_log_path"] = role_log_registry_path(role)
merged["summary_path"] = f".yolo/agents/{role}-summary.md"
return merged
```

Update `default_agent_sessions()` version to `2`.

- [ ] **Step 4: Implement memory dispatch contract**

Replace exact runtime contract with:

```python
def dispatch_memory_contract(role: str, role_invocation_id: str, last_runtime_agent_id: str = "") -> dict:
    require_role(role)
    return {
        "dispatch_action": DISPATCH_ACTION_CREATE,
        "continuity_model": CONTINUITY_MODEL_PROJECT_MEMORY,
        "role_invocation_id": role_invocation_id,
        "last_runtime_agent_id": last_runtime_agent_id,
        "memory": {
            "scope": MEMORY_SCOPE_PROJECT,
            "path": role_memory_path(role),
            "required": True,
        },
        "role_log": role_log_registry_path(role),
        "summary_path": f".yolo/agents/{role}-summary.md",
    }
```

Keep a compatibility wrapper only if imports need it:

```python
def dispatch_runtime_contract(action: str, role_session_id: str, runtime_agent_id: str = "") -> dict:
    raise ValueError("Exact runtime Agent reuse is unsupported; use dispatch_memory_contract")
```

If tests/imports are updated to no longer import `dispatch_runtime_contract`, delete it instead.

- [ ] **Step 5: Update resolver and recorder**

Change `resolve_role_session()` so every dispatch increments generation and creates a new role invocation id:

```python
session["generation"] = int(session.get("generation", 0)) + 1
session["role_invocation_id"] = new_agent_id(role, session["generation"])
session["status"] = "active"
session["created_at"] = observed_at
session["last_seen_at"] = observed_at
session["last_dispatch_owner"] = dispatch_owner
session["continuity_model"] = CONTINUITY_MODEL_PROJECT_MEMORY
session["memory_scope"] = MEMORY_SCOPE_PROJECT
session["memory_path"] = role_memory_path(role)
session["role_log_path"] = role_log_registry_path(role)
session["summary_path"] = f".yolo/agents/{role}-summary.md"
dispatch = dispatch_memory_contract(role, session["role_invocation_id"], session.get("last_runtime_agent_id", ""))
```

Return:

```python
return {"role": role, "action": DISPATCH_ACTION_CREATE, **session, "dispatch": dispatch}
```

Change `record_runtime_agent_id()` signature behavior to accept `role_invocation_id` and write `last_runtime_agent_id`; returned dispatch remains create/memory-based.

- [ ] **Step 6: Run agent session tests to verify pass**

Run:

```bash
python3 -m unittest tests.test_agent_sessions -v
```

Expected: PASS.

---

### Task 3: Update grill-storm dispatch payload and prompt

**Files:**
- Modify: `workflow/grill_storm_loop.py`
- Test: `tests/test_grill_storm_loop.py`

- [ ] **Step 1: Write failing grill-storm dispatch tests**

Update tests to expect:

```python
self.assertEqual(dispatch["dispatch_action"], "create")
self.assertEqual(dispatch["continuity_model"], "project_memory")
self.assertIn("role_invocation_id", dispatch)
self.assertIn("memory", dispatch)
self.assertEqual(dispatch["memory"]["scope"], "project")
self.assertEqual(dispatch["memory"]["path"], ".claude/agent-memory/muse/MEMORY.md")
self.assertTrue(dispatch["memory"]["required"])
self.assertIn("role_log", dispatch)
self.assertNotIn("agent_runtime", dispatch)
self.assertNotIn("runtime_agent_id", dispatch)
self.assertNotIn("session_action", dispatch)
```

Update prompt assertions to require:

```python
self.assertIn("continuity_model: project_memory", prompt)
self.assertIn("project memory", prompt)
self.assertIn("MEMORY.md", prompt)
self.assertIn("role log", prompt)
self.assertIn("fresh Agent", prompt)
self.assertNotIn("resume_by_agent_id", prompt)
self.assertNotIn("Do not create a fresh", prompt)
```

Remove old tests that expect missing runtime id reuse failure. Replace with a test that repeated dispatches create new role invocation ids while preserving memory path:

```python
def test_persistent_memory_dispatch_creates_fresh_invocation_each_round(self) -> None:
    ...
    self.assertEqual(dispatch1["dispatch_action"], "create")
    self.assertEqual(dispatch2["dispatch_action"], "create")
    self.assertNotEqual(dispatch1["role_invocation_id"], dispatch2["role_invocation_id"])
    self.assertEqual(dispatch1["memory"]["path"], dispatch2["memory"]["path"])
```

- [ ] **Step 2: Run grill-storm tests to verify failure**

Run:

```bash
python3 -m unittest tests.test_grill_storm_loop -v
```

Expected: FAIL because payload still uses exact runtime reuse fields.

- [ ] **Step 3: Update `build_agent_prompt()`**

Replace Agent session routing section with Project memory continuity section:

```python
lines.extend([
    "## Role continuity",
    f"- dispatch_action: {dispatch.get('dispatch_action', '')}",
    f"- continuity_model: {dispatch.get('continuity_model', '')}",
    f"- role_invocation_id: {dispatch.get('role_invocation_id', '')}",
    f"- last_runtime_agent_id: {dispatch.get('last_runtime_agent_id', '')}",
    f"- project memory: {dispatch.get('memory', {}).get('path', '')}",
    f"- role log: {dispatch.get('role_log', '')}",
    "- Runtime creates a fresh Agent for this role turn. Use project memory, role log, and docs mailbox for continuity.",
])
```

Keep existing read/write docs sections.

- [ ] **Step 4: Update `build_dispatch_request()`**

Map session result fields:

```python
request["dispatch_action"] = session["action"]
request["continuity_model"] = session["continuity_model"]
request["role_invocation_id"] = session["role_invocation_id"]
request["last_runtime_agent_id"] = session.get("last_runtime_agent_id", "")
request["agent_generation"] = session["generation"]
request["memory"] = session["dispatch"]["memory"]
request["role_log"] = session["dispatch"]["role_log"]
request["summary_path"] = session["dispatch"]["summary_path"]
request["docs_mailbox"] = sorted(set(request["read"] + request["write_any_of"]))
```

Remove `session_action`, `runtime_agent_id`, and `agent_runtime` from new payload.

- [ ] **Step 5: Run grill-storm tests to verify pass**

Run:

```bash
python3 -m unittest tests.test_grill_storm_loop -v
```

Expected: PASS.

---

### Task 4: Update orchestrator dispatch payloads

**Files:**
- Modify: `workflow/orchestrator.py`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing orchestrator tests**

Update worker/watcher/helper agent session tests to expect `agent_session` fields:

```python
self.assertEqual(result["agent_session"]["action"], "create")
self.assertEqual(result["agent_session"]["continuity_model"], "project_memory")
self.assertIn("role_invocation_id", result["agent_session"])
self.assertIn("dispatch", result["agent_session"])
self.assertEqual(result["agent_session"]["dispatch"]["dispatch_action"], "create")
self.assertEqual(result["agent_session"]["dispatch"]["memory"]["path"], ".claude/agent-memory/worker/MEMORY.md")
self.assertNotIn("runtime", result["agent_session"])
self.assertNotIn("runtime_agent_id", result["agent_session"])
```

Replace reuse-failure tests with audit-only tests:

```python
def test_orchestrate_records_last_runtime_agent_id_without_reuse_requirement(self) -> None:
    ...
    record_runtime_agent_id(run_root, "worker", first["agent_session"]["role_invocation_id"], "actual-runtime-worker-123")
    second = orchestrate(run_root, state, consumer_id="worker-consumer")
    self.assertEqual(second["agent_session"]["last_runtime_agent_id"], "actual-runtime-worker-123")
    self.assertEqual(second["agent_session"]["dispatch"]["dispatch_action"], "create")
    self.assertNotEqual(second["agent_session"]["role_invocation_id"], first["agent_session"]["role_invocation_id"])
```

- [ ] **Step 2: Run orchestrator tests to verify failure**

Run:

```bash
python3 -m unittest tests.test_orchestrator -v
```

Expected: FAIL because orchestrator still normalizes runtime exact-reuse payloads.

- [ ] **Step 3: Update `ensure_dispatch_agent_session()`**

Remove legacy runtime normalization for `agent_runtime`. Normalize old dispatch only into memory schema when needed:

```python
if isinstance(agent_session, dict) and agent_session:
    if "dispatch" in agent_session and agent_session.get("continuity_model") == "project_memory":
        return dispatch
    return dispatch
```

For missing session, call `resolve_role_session()` and set returned session.

- [ ] **Step 4: Update rebuilt live claim behavior**

Where replayed dispatches are enriched, require project-memory `dispatch` field rather than `runtime`. If a replayed old exact-runtime dispatch appears, enrich by resolving a new project-memory invocation instead of trying to resume old runtime id.

- [ ] **Step 5: Run orchestrator tests to verify pass**

Run:

```bash
python3 -m unittest tests.test_orchestrator -v
```

Expected: PASS.

---

### Task 5: Update docs and policy contract

**Files:**
- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `.claude/skills/grill-storm/SKILL.md`
- Modify: `policy/run-state-contract.md`
- Test: `tests/test_docs_and_templates.py`

- [ ] **Step 1: Write failing docs tests**

Update `test_docs_describe_persistent_role_agent_sessions` to require in README, SKILL, and contract:

```python
"project memory"
"memory: project"
"role_invocation_id"
"last_runtime_agent_id"
"continuity_model"
"project_memory"
"fresh Agent"
"audit evidence only"
```

And reject:

```python
self.assertNotIn("resume_by_agent_id", body)
self.assertNotIn("must_resume_exact_agent_id", body)
self.assertNotIn("no fresh-agent fallback", body)
```

Keep `agent_sessions.json` requirement but describe it as role invocation metadata.

- [ ] **Step 2: Run docs tests to verify failure**

Run:

```bash
python3 -m unittest tests.test_docs_and_templates -v
```

Expected: FAIL because docs still promise exact runtime reuse.

- [ ] **Step 3: Update docs**

Replace Persistent Role Agents sections with:

```markdown
Role continuity uses Claude Code subagent project memory. Each dispatch creates a fresh Agent for the role. The fresh Agent restores continuity from `.claude/agent-memory/<role>/MEMORY.md`, `.yolo/agents/<role>-log.md`, and the dispatch-required docs/state.

`agent_sessions.json` stores role invocation routing/audit metadata only. `state.json` remains workflow authority. `role_invocation_id` is workflow-generated audit identity. `last_runtime_agent_id` is the last Agent tool id observed for audit evidence only; it is not a resume handle.
```

Update examples to show `dispatch_action=create` and `continuity_model=project_memory`.

- [ ] **Step 4: Run docs tests to verify pass**

Run:

```bash
python3 -m unittest tests.test_docs_and_templates -v
```

Expected: PASS.

---

### Task 6: Update bootstrap memory initialization

**Files:**
- Modify: `workflow/agent_sessions.py`
- Modify: `workflow/bootstrap.py` if needed
- Test: `tests/test_bootstrap_lightweight_bundle.py`

- [ ] **Step 1: Write failing bootstrap test**

In `tests/test_bootstrap_lightweight_bundle.py`, extend agent session registry/bootstrap test to assert project memory files exist under project root:

```python
for role in ("muse", "logos", "worker", "watcher", "helper"):
    memory = project_dir / ".claude" / "agent-memory" / role / "MEMORY.md"
    self.assertTrue(memory.exists())
    body = memory.read_text(encoding="utf-8")
    self.assertIn(f"# {role} memory", body)
    self.assertIn("## Role Conventions", body)
```

- [ ] **Step 2: Run bootstrap test to verify failure**

Run:

```bash
python3 -m unittest tests.test_bootstrap_lightweight_bundle -v
```

Expected: FAIL because bootstrap does not create role memory files yet.

- [ ] **Step 3: Implement memory initialization**

In `workflow/agent_sessions.py`, add:

```python
def role_memory_file(project_dir: Path, role: str) -> Path:
    require_role(role)
    return project_dir / ".claude" / "agent-memory" / role / "MEMORY.md"


def ensure_role_memory_files(project_dir: Path) -> None:
    for role in ROLE_NAMES:
        path = role_memory_file(project_dir, role)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(
                f"# {role} memory\n\n"
                "## Role Conventions\n\n"
                "## Project Conventions\n\n"
                "## Risky Areas\n\n"
                "## Reliable Verification\n\n"
                "## Recurring Issues\n",
                encoding="utf-8",
            )
```

Call this from bootstrap/preflight initialization path using the project directory. If bootstrap already calls `ensure_agent_session_files(run_root)`, add a `project_dir` argument where needed or call separately from bootstrap.

- [ ] **Step 4: Run bootstrap test to verify pass**

Run:

```bash
python3 -m unittest tests.test_bootstrap_lightweight_bundle -v
```

Expected: PASS.

---

### Task 7: Final verification and impact check

**Files:**
- No new files beyond prior tasks.

- [ ] **Step 1: Run targeted suite**

Run:

```bash
python3 -m unittest tests.test_agent_sessions tests.test_grill_storm_loop tests.test_orchestrator tests.test_docs_and_templates tests.test_bootstrap_lightweight_bundle -v
```

Expected: PASS.

- [ ] **Step 2: Run runtime regression suite**

Run:

```bash
python3 -m unittest tests.test_grill_storm_runtime tests.test_grill_storm_loop tests.test_agent_sessions tests.test_docs_and_templates -v
```

Expected: PASS.

- [ ] **Step 3: Run GitNexus change detection**

Run MCP:

```text
mcp__gitnexus__detect_changes(scope="unstaged", repo="claude-yolo-until-done")
```

Expected: changed symbols include role registry, grill-storm dispatch, orchestrator dispatch, docs/tests. Risk may be HIGH/CRITICAL because workflow core changed; verify affected processes match expected dispatch/session flows.

- [ ] **Step 4: Real bench readiness note**

Record that real6 should verify:

- no `resume_by_agent_id` blocker,
- memory files exist,
- fresh Muse/Logos rounds use project memory and role logs,
- human approval remains visible and not fabricated.

Do not claim real6 passed until it is run.

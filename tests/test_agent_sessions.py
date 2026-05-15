from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from agent_sessions import (
    ROLE_NAMES,
    agent_log_path,
    agent_sessions_path,
    append_planning_round,
    append_role_log_entry,
    build_replacement_prompt_context,
    ensure_agent_session_files,
    ensure_project_role_memory_files,
    load_agent_sessions,
    load_planning_rounds,
    project_role_memory_path,
    replace_role_session,
    resolve_role_session,
)


class AgentSessionsTest(unittest.TestCase):
    def test_ensure_agent_session_files_writes_registry_and_role_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"

            ensure_agent_session_files(run_root)

            registry_path = agent_sessions_path(run_root)
            self.assertTrue(registry_path.exists())
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(registry["version"], 2)
            self.assertEqual(set(registry["roles"]), set(ROLE_NAMES))
            for role in ROLE_NAMES:
                session = registry["roles"][role]
                self.assertEqual(session["role_invocation_id"], "")
                self.assertEqual(session["last_runtime_agent_id"], "")
                self.assertEqual(session["generation"], 0)
                self.assertEqual(session["status"], "")
                self.assertEqual(session["continuity_model"], "project_memory")
                self.assertEqual(session["memory_scope"], "project")
                self.assertEqual(session["memory_path"], f".claude/agent-memory/{role}/MEMORY.md")
                self.assertEqual(session["role_log_path"], f"agents/{role}-log.md")
                self.assertEqual(session["summary_path"], f"agents/{role}-summary.md")
                self.assertTrue(agent_log_path(run_root, role).exists())

    def test_ensure_project_role_memory_files_writes_role_memory_stubs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)

            ensure_project_role_memory_files(project_root)

            for role in ROLE_NAMES:
                body = project_role_memory_path(project_root, role).read_text(encoding="utf-8")
                self.assertIn(f"# {role} memory", body)
                self.assertIn("## Role Conventions", body)
                self.assertIn("## Project Conventions", body)
                self.assertIn("## Reliable Verification", body)

    def test_load_agent_sessions_migrates_legacy_agent_id_to_role_invocation_id(self) -> None:
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

            self.assertEqual(registry["version"], 2)
            self.assertEqual(registry["roles"]["worker"]["role_invocation_id"], "worker-1-legacy")
            self.assertEqual(registry["roles"]["worker"]["last_runtime_agent_id"], "")
            self.assertEqual(registry["roles"]["worker"]["continuity_model"], "project_memory")
            self.assertNotIn("agent_id", registry["roles"]["worker"])

    def test_load_agent_sessions_fails_closed_on_malformed_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            run_root.mkdir()
            agent_sessions_path(run_root).write_text("not json", encoding="utf-8")

            with self.assertRaises(ValueError) as raised:
                load_agent_sessions(run_root)

            self.assertIn("agent_sessions.json is malformed", str(raised.exception))

    def test_resolve_role_session_reuses_project_memory_continuity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"

            first = resolve_role_session(run_root, "worker", "worker:gate-task-001:1", now="2026-05-11T00:00:00+00:00")
            second = resolve_role_session(run_root, "worker", "worker:gate-task-001:2", now="2026-05-11T00:01:00+00:00")

            self.assertEqual(first["action"], "create")
            self.assertTrue(first["role_invocation_id"].startswith("worker-1-"))
            self.assertEqual(first["last_runtime_agent_id"], "")
            self.assertEqual(first["continuity_model"], "project_memory")
            self.assertEqual(first["memory_scope"], "project")
            self.assertEqual(first["memory_path"], ".claude/agent-memory/worker/MEMORY.md")
            self.assertEqual(first["role_log_path"], "agents/worker-log.md")
            self.assertEqual(second["action"], "create")
            self.assertEqual(second["role_invocation_id"], first["role_invocation_id"])
            self.assertEqual(second["last_runtime_agent_id"], "")
            registry = load_agent_sessions(run_root)
            self.assertEqual(registry["roles"]["worker"]["last_dispatch_owner"], "worker:gate-task-001:2")

    def test_resolve_role_session_keeps_roles_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"

            worker = resolve_role_session(run_root, "worker", "worker:gate-task-001:1", now="2026-05-11T00:00:00+00:00")
            watcher = resolve_role_session(run_root, "watcher", "watcher:gate-task-001:2", now="2026-05-11T00:01:00+00:00")

            self.assertNotEqual(worker["role_invocation_id"], watcher["role_invocation_id"])
            self.assertEqual(worker["role"], "worker")
            self.assertEqual(watcher["role"], "watcher")

    def test_replace_role_session_marks_generation_and_notebook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            original = resolve_role_session(run_root, "worker", "worker:gate-task-001:1", now="2026-05-11T00:00:00+00:00")

            replacement = replace_role_session(
                run_root,
                "worker",
                "worker:gate-task-001:1",
                "stored agent unavailable",
                now="2026-05-11T00:02:00+00:00",
            )

            self.assertEqual(replacement["action"], "replace")
            self.assertEqual(replacement["generation"], 2)
            self.assertNotEqual(replacement["role_invocation_id"], original["role_invocation_id"])
            self.assertEqual(replacement["last_runtime_agent_id"], "")
            self.assertEqual(replacement["continuity_model"], "project_memory")

            next_dispatch = resolve_role_session(run_root, "worker", "worker:gate-task-001:2", now="2026-05-11T00:03:00+00:00")

            self.assertEqual(next_dispatch["action"], "create")
            self.assertEqual(next_dispatch["role_invocation_id"], replacement["role_invocation_id"])
            self.assertEqual(next_dispatch["last_runtime_agent_id"], "")
            log_text = agent_log_path(run_root, "worker").read_text(encoding="utf-8")
            self.assertIn("replacement generation 2", log_text)
            self.assertIn("stored agent unavailable", log_text)

    def test_append_role_log_entry_uses_caveman_lab_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            ensure_agent_session_files(run_root)

            append_role_log_entry(
                run_root,
                "worker",
                "dispatch worker:gate-task-001:1",
                hypothesis=["Loop reset likely stale."],
                actions=["Read `workflow/controller.py`."],
                observations=["Reset clears review."],
                result=["PASS targeted test."],
                next_steps=["Watcher verify."],
                now="2026-05-11T00:03:00+00:00",
            )

            log_text = agent_log_path(run_root, "worker").read_text(encoding="utf-8")
            self.assertIn("## 2026-05-11T00:03:00+00:00 dispatch worker:gate-task-001:1", log_text)
            self.assertIn("Hypothesis:\n- Loop reset likely stale.", log_text)
            self.assertIn("Actions:\n- Read `workflow/controller.py`.", log_text)
            self.assertIn("Observations:\n- Reset clears review.", log_text)
            self.assertIn("Result:\n- PASS targeted test.", log_text)
            self.assertIn("Next:\n- Watcher verify.", log_text)

    def test_build_replacement_prompt_context_includes_durable_paths_and_notebook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            run_root.mkdir()
            (run_root / "state.json").write_text('{"status":"active","state_version":7,"last_dispatch":{"role":"worker"}}\n', encoding="utf-8")
            (run_root / "trace.md").write_text("# Trace\n- worker submit\n", encoding="utf-8")
            ensure_agent_session_files(run_root)
            append_role_log_entry(
                run_root,
                "worker",
                "dispatch worker:gate-task-001:7",
                actions=["Read controller."],
                result=["Need replacement."],
                now="2026-05-11T00:04:00+00:00",
            )

            context = build_replacement_prompt_context(run_root, "worker", "stored agent unavailable")

            self.assertEqual(context["role"], "worker")
            self.assertEqual(context["replacement_reason"], "stored agent unavailable")
            self.assertIn('"state_version":7', context["state_json"])
            self.assertIn("worker submit", context["trace_tail"])
            self.assertIn("Read controller.", context["role_log_tail"])
            self.assertIn("last_dispatch", context["state_json"])

    def test_append_planning_round_persists_role_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            ensure_agent_session_files(run_root)

            record = append_planning_round(
                run_root,
                {
                    "role": "muse",
                    "round": 1,
                    "status": "completed",
                    "docs_touched": ["docs/intent.md", "docs/decisions.md"],
                    "summary": "Confirmed execution gate ownership.",
                    "decisions_recorded": ["Preflight owns execution readiness."],
                    "questions_added": [],
                    "next_recommendation": "Logos should compare validator placement options.",
                },
                now="2026-05-11T01:00:00+00:00",
            )

            self.assertEqual(record["role"], "muse")
            self.assertEqual(record["round"], 1)
            rounds = load_planning_rounds(run_root)
            self.assertEqual(rounds[0]["summary"], "Confirmed execution gate ownership.")
            self.assertEqual(rounds[0]["recorded_at"], "2026-05-11T01:00:00+00:00")
            log_text = agent_log_path(run_root, "muse").read_text(encoding="utf-8")
            self.assertIn("planning round 1", log_text)
            self.assertIn("Confirmed execution gate ownership.", log_text)

    def test_append_planning_round_rejects_non_planning_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"

            with self.assertRaises(ValueError) as raised:
                append_planning_round(
                    run_root,
                    {
                        "role": "worker",
                        "round": 1,
                        "status": "completed",
                        "docs_touched": [],
                        "summary": "bad",
                        "decisions_recorded": [],
                        "questions_added": [],
                        "next_recommendation": "bad",
                    },
                    now="2026-05-11T01:00:00+00:00",
                )

            self.assertIn("Unsupported planning role agent", str(raised.exception))

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"
GRILL_STORM_LOOP_PATH = WORKFLOW_DIR / "grill_storm_loop.py"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from agent_sessions import load_agent_sessions
from grill_storm_loop import build_dispatch_request, run_planning_step
from human_approvals import record_human_approval


class GrillStormLoopTest(unittest.TestCase):
    def write_human_approvals(self, project_dir: Path, *sources: str) -> None:
        for source in sources:
            record_human_approval(project_dir, source, f"prompt {source}", f"approved {source}")

    def write_docs(self, project_dir: Path, *, docs_dir: str = "docs", decisions: str = "# Decisions\n\n## Decision Log\n") -> None:
        docs = project_dir / docs_dir
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "intent.md").write_text("# Intent\n\n## Primary Goal\n- Build safe planning flow.\n", encoding="utf-8")
        (docs / "open-questions.md").write_text("# Open Questions\n\n## High Priority\n- [ ] None.\n", encoding="utf-8")
        (docs / "decisions.md").write_text(decisions, encoding="utf-8")
        (docs / "spec.md").write_text("# Spec\n\nStatus: draft\n\n## Acceptance Criteria\n- [ ] Docs converge.\n", encoding="utf-8")
        (docs / "plan.md").write_text("# Plan\n\nStatus: draft\n\n## Steps\n1. Step: converge docs.\n   Verify: validator passes.\n", encoding="utf-8")

    def test_planning_step_requests_muse_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(project_dir)

            payload = run_planning_step(project_dir, run_root=project_dir / ".yolo", max_rounds=6)

            self.assertEqual(payload["status"], "dispatch_required")
            dispatch = payload["dispatch_request"]
            self.assertEqual(dispatch["role"], "muse")
            self.assertEqual(dispatch["round"], 1)
            self.assertEqual(dispatch["project_dir"], str(project_dir.resolve()))
            self.assertEqual(dispatch["run_root"], str((project_dir / ".yolo").resolve()))
            self.assertIn("docs/intent.md", dispatch["read"])
            self.assertIn("docs/decisions.md", dispatch["write_any_of"])
            self.assertIn("required_output_schema", dispatch)
            self.assertIn("agent_prompt", dispatch)
            self.assertIn("Muse", dispatch["agent_prompt"])
            self.assertEqual(dispatch["session_action"], "create")
            self.assertEqual(dispatch["dispatch_action"], "create")
            self.assertEqual(dispatch["continuity_model"], "project_memory")
            self.assertTrue(dispatch["role_invocation_id"].startswith("muse-1-"))
            self.assertEqual(dispatch["last_runtime_agent_id"], "")
            self.assertEqual(dispatch["agent_generation"], 1)
            self.assertEqual(dispatch["memory"]["scope"], "project")
            self.assertEqual(dispatch["memory"]["path"], ".claude/agent-memory/muse/MEMORY.md")
            self.assertEqual(dispatch["role_log"], "agents/muse-log.md")
            memory_path = project_dir / ".claude" / "agent-memory" / "muse" / "MEMORY.md"
            self.assertTrue(memory_path.exists())
            self.assertIn("# muse memory", memory_path.read_text(encoding="utf-8"))

    def test_persistent_session_reused_across_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(project_dir)
            run_root = project_dir / ".yolo"

            dispatch1 = run_planning_step(project_dir, run_root=run_root)["dispatch_request"]
            self.assertEqual(dispatch1["session_action"], "create")
            role_invocation_id_1 = dispatch1["role_invocation_id"]

            from grill_storm_loop import record_round_result
            record_round_result(
                dispatch1,
                {
                    "role": "muse",
                    "round": 1,
                    "status": "completed",
                    "docs_touched": ["docs/decisions.md"],
                    "summary": "Muse explored intent.",
                    "decisions_recorded": ["User wants safe planning."],
                    "questions_added": [],
                    "next_recommendation": "Logos evaluate feasibility.",
                },
            )

            decisions = (project_dir / "docs" / "decisions.md").read_text(encoding="utf-8")
            self.assertIn("- Actor: muse", decisions)
            self.assertIn("- Decision: User wants safe planning.", decisions)

            dispatch2 = run_planning_step(project_dir, run_root=run_root)["dispatch_request"]
            self.assertEqual(dispatch2["role"], "logos")
            self.assertEqual(dispatch2["session_action"], "create")
            self.assertEqual(dispatch2["dispatch_action"], "create")
            self.assertEqual(dispatch2["continuity_model"], "project_memory")
            self.assertIn("Logos", dispatch2["agent_prompt"])

            sessions = load_agent_sessions(run_root)
            self.assertEqual(sessions["roles"]["muse"]["role_invocation_id"], role_invocation_id_1)
            self.assertEqual(sessions["roles"]["muse"]["generation"], 1)
            self.assertEqual(sessions["roles"]["muse"]["status"], "active")
            self.assertEqual(sessions["roles"]["logos"]["generation"], 1)
            self.assertEqual(sessions["roles"]["logos"]["status"], "active")

    def test_planning_dispatch_reuses_project_memory_continuity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(project_dir)
            run_root = project_dir / ".yolo"
            first = run_planning_step(project_dir, run_root=run_root)["dispatch_request"]
            role_invocation_id = first["role_invocation_id"]

            dispatch = build_dispatch_request(
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

            self.assertEqual(dispatch["session_action"], "create")
            self.assertEqual(dispatch["dispatch_action"], "create")
            self.assertEqual(dispatch["continuity_model"], "project_memory")
            self.assertEqual(dispatch["role_invocation_id"], role_invocation_id)
            self.assertEqual(dispatch["last_runtime_agent_id"], "")
            self.assertEqual(dispatch["memory"]["path"], ".claude/agent-memory/muse/MEMORY.md")
            self.assertEqual(dispatch["role_log"], "agents/muse-log.md")
            self.assertIn(role_invocation_id, dispatch["agent_prompt"])
            self.assertIn("project memory", dispatch["agent_prompt"])
            self.assertIn("role log", dispatch["agent_prompt"])

    def test_build_dispatch_request_rejects_unknown_actor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            status = {"status": "needs_internal_round", "next_actor": "architect", "read": [], "write_any_of": [], "reason": "bad"}

            with self.assertRaises(ValueError) as raised:
                build_dispatch_request(project_dir, status, run_root=None, round_number=1)

            self.assertIn("Unsupported grill-storm actor", str(raised.exception))

    def test_planning_step_uses_custom_docs_dir_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(project_dir, docs_dir="planning")

            payload = run_planning_step(project_dir, run_root=project_dir / ".yolo", docs_dir_arg="planning")

            dispatch = payload["dispatch_request"]
            self.assertIn("planning/intent.md", dispatch["read"])
            self.assertIn("planning/decisions.md", dispatch["write_any_of"])

    def test_record_round_result_rejects_disallowed_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(project_dir)
            dispatch = run_planning_step(project_dir, run_root=project_dir / ".yolo")["dispatch_request"]

            from grill_storm_loop import record_round_result

            with self.assertRaises(ValueError) as raised:
                record_round_result(
                    dispatch,
                    {
                        "role": "muse",
                        "round": 1,
                        "status": "completed",
                        "docs_touched": ["docs/plan.md"],
                        "summary": "Tried to edit plan.",
                        "decisions_recorded": [],
                        "questions_added": [],
                        "next_recommendation": "Logos should continue.",
                    },
                )

            self.assertIn("outside allowed write set", str(raised.exception))

    def test_record_round_result_requires_progress_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(project_dir)
            dispatch = run_planning_step(project_dir, run_root=project_dir / ".yolo")["dispatch_request"]

            from grill_storm_loop import record_round_result

            with self.assertRaises(ValueError) as raised:
                record_round_result(
                    dispatch,
                    {
                        "role": "muse",
                        "round": 1,
                        "status": "completed",
                        "docs_touched": [],
                        "summary": "No progress.",
                        "decisions_recorded": [],
                        "questions_added": [],
                        "next_recommendation": "Retry.",
                    },
                )

            self.assertIn("no docs, decisions, or questions", str(raised.exception))

    def test_record_round_result_persists_valid_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(project_dir)
            dispatch = run_planning_step(project_dir, run_root=project_dir / ".yolo")["dispatch_request"]

            from agent_sessions import load_planning_rounds
            from grill_storm_loop import record_round_result

            persisted = record_round_result(
                dispatch,
                {
                    "role": "muse",
                    "round": 1,
                    "status": "completed",
                    "docs_touched": ["docs/decisions.md"],
                    "summary": "Recorded preflight ownership decision.",
                    "decisions_recorded": ["Preflight owns execution readiness."],
                    "questions_added": [],
                    "next_recommendation": "Logos should compare options.",
                },
                now="2026-05-11T02:00:00+00:00",
            )

            self.assertEqual(persisted["role"], "muse")
            rounds = load_planning_rounds(project_dir / ".yolo")
            self.assertEqual(rounds[0]["summary"], "Recorded preflight ownership decision.")

    def test_blocked_round_does_not_count_as_internal_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(project_dir)
            run_root = project_dir / ".yolo"
            dispatch1 = run_planning_step(project_dir, run_root=run_root)["dispatch_request"]

            from grill_storm_loop import record_round_result
            record_round_result(
                dispatch1,
                {
                    "role": "muse",
                    "round": 1,
                    "status": "blocked",
                    "docs_touched": ["docs/open-questions.md"],
                    "summary": "Muse could not decide.",
                    "decisions_recorded": ["Potential direction is not ready."],
                    "questions_added": ["Need operator input."],
                    "next_recommendation": "Retry Muse after input.",
                },
            )

            decisions = (project_dir / "docs" / "decisions.md").read_text(encoding="utf-8")
            self.assertNotIn("Potential direction is not ready.", decisions)
            dispatch2 = run_planning_step(project_dir, run_root=run_root)["dispatch_request"]
            self.assertEqual(dispatch2["role"], "muse")
            self.assertEqual(dispatch2["round"], 2)

    def test_recorded_spec_self_review_round_unblocks_human_spec_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            decisions = "# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Muse\n- Status: accepted\n- Actor: muse\n- Decision: Muse explored intent.\n\n### 2026-05-12 - Logos\n- Status: accepted\n- Actor: logos\n- Decision: Logos converged approach.\n\n### 2026-05-12 - Human consensus approval\n- Status: accepted\n- Actor: human\n- Source: consensus\n- Decision: Build human-gated planning.\n"
            self.write_docs(project_dir, decisions=decisions)
            self.write_human_approvals(project_dir, "consensus")
            spec_text = "# Spec\n\nStatus: draft\n\n## Problem\nNeed durable planning docs.\n\n## Acceptance Criteria\n- Docs converge.\n"
            (project_dir / "docs" / "spec.md").write_text(spec_text, encoding="utf-8")
            run_root = project_dir / ".yolo"
            dispatch = run_planning_step(project_dir, run_root=run_root)["dispatch_request"]
            self.assertEqual(dispatch["planning_mode"], "logos-spec-reviewer")

            from grill_storm_loop import record_round_result
            record_round_result(
                dispatch,
                {
                    "role": "logos",
                    "round": dispatch["round"],
                    "status": "completed",
                    "docs_touched": ["docs/decisions.md"],
                    "summary": "Spec self-review passed.",
                    "decisions_recorded": ["Spec has clear problem and acceptance criteria."],
                    "questions_added": [],
                    "next_recommendation": "Ask human to approve spec.",
                },
                now="2026-05-12T00:00:00+00:00",
            )

            body = (project_dir / "docs" / "decisions.md").read_text(encoding="utf-8")
            self.assertIn("- Source: spec-self-review", body)
            self.assertNotIn("- Source: spec-review", body)
            (project_dir / "docs" / "spec.md").write_text(spec_text.replace("Status: draft", "Status: self-reviewed"), encoding="utf-8")
            payload = run_planning_step(project_dir, run_root=run_root)
            self.assertEqual(payload["status"], "human_spec_review")

    def test_cli_next_outputs_dispatch_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(project_dir)

            result = subprocess.run(
                [sys.executable, str(GRILL_STORM_LOOP_PATH), "next", "--project-dir", str(project_dir), "--run-root", str(project_dir / ".yolo")],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "dispatch_required")
            self.assertEqual(payload["dispatch_request"]["role"], "muse")

    def test_cli_record_accepts_round_result_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(project_dir)
            next_result = subprocess.run(
                [sys.executable, str(GRILL_STORM_LOOP_PATH), "next", "--project-dir", str(project_dir), "--run-root", str(project_dir / ".yolo")],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            dispatch = json.loads(next_result.stdout)["dispatch_request"]
            result_payload = {
                "dispatch_request": dispatch,
                "round_result": {
                    "role": "muse",
                    "round": 1,
                    "status": "completed",
                    "docs_touched": ["docs/decisions.md"],
                    "summary": "Recorded decision.",
                    "decisions_recorded": ["Preflight owns readiness."],
                    "questions_added": [],
                    "next_recommendation": "Logos continue.",
                },
            }

            record_result = subprocess.run(
                [
                    sys.executable,
                    str(GRILL_STORM_LOOP_PATH),
                    "record",
                    "--project-dir",
                    str(project_dir),
                    "--run-root",
                    str(project_dir / ".yolo"),
                    "--result-json",
                    json.dumps(result_payload),
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(record_result.returncode, 0, record_result.stderr)
            payload = json.loads(record_result.stdout)
            self.assertEqual(payload["status"], "recorded")
            self.assertEqual(payload["record"]["summary"], "Recorded decision.")

    def test_max_rounds_blocks_non_converging_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(project_dir)
            run_root = project_dir / ".yolo"
            dispatch = run_planning_step(project_dir, run_root=run_root, max_rounds=1)["dispatch_request"]
            from grill_storm_loop import record_round_result
            record_round_result(
                dispatch,
                {
                    "role": "muse",
                    "round": 1,
                    "status": "completed",
                    "docs_touched": ["docs/decisions.md"],
                    "summary": "Recorded insufficient decision.",
                    "decisions_recorded": ["Need more analysis."],
                    "questions_added": [],
                    "next_recommendation": "Continue.",
                },
            )

            payload = run_planning_step(project_dir, run_root=run_root, max_rounds=1)

            self.assertEqual(payload["status"], "max_rounds_exceeded")
            self.assertFalse(payload["human_allowed"])

    def test_step_passes_through_ask_user_after_two_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            decisions = "# Decisions\n\n## Decision Log\n\n### 2026-05-11 - Muse\n- Status: accepted\n- Actor: muse\n- Decision: Ask late.\n\n### 2026-05-11 - Logos\n- Status: accepted\n- Actor: logos\n- Decision: Keep preflight gate.\n\n### 2026-05-12 - Human consensus approval\n- Status: accepted\n- Actor: human\n- Source: consensus\n- Decision: Build approved planning docs.\n\n### 2026-05-12 - Logos spec self-review\n- Status: accepted\n- Actor: logos\n- Source: spec-self-review\n- Decision: Spec passes self-review.\n\n### 2026-05-12 - Human spec review\n- Status: accepted\n- Actor: human\n- Source: spec-review\n- Decision: Spec approved.\n\n### 2026-05-12 - Human plan review\n- Status: accepted\n- Actor: human\n- Source: plan-review\n- Decision: Plan approved.\n"
            self.write_docs(project_dir, decisions=decisions)
            (project_dir / "docs" / "open-questions.md").write_text("# Open Questions\n\n## High Priority\n- [ ] Blocking: yes | Question: Which owner approves execution? | Recommended: preflight\n", encoding="utf-8")

            payload = run_planning_step(project_dir, run_root=project_dir / ".yolo")

            self.assertEqual(payload["status"], "ask_user")
            self.assertEqual(payload["question"], "Which owner approves execution?")

    def test_step_passes_through_ready_for_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            decisions = "# Decisions\n\n## Decision Log\n\n### 2026-05-11 - Muse\n- Status: accepted\n- Actor: muse\n- Decision: Ask late.\n\n### 2026-05-11 - Logos\n- Status: accepted\n- Actor: logos\n- Decision: Keep preflight gate.\n\n### 2026-05-12 - Human consensus approval\n- Status: accepted\n- Actor: human\n- Source: consensus\n- Decision: Build approved planning docs.\n\n### 2026-05-12 - Logos spec self-review\n- Status: accepted\n- Actor: logos\n- Source: spec-self-review\n- Decision: Spec passes self-review.\n\n### 2026-05-12 - Human spec review\n- Status: accepted\n- Actor: human\n- Source: spec-review\n- Decision: Spec approved.\n\n### 2026-05-12 - Human plan review\n- Status: accepted\n- Actor: human\n- Source: plan-review\n- Decision: Plan approved.\n"
            self.write_docs(project_dir, decisions=decisions)
            self.write_human_approvals(project_dir, "consensus", "spec-review", "plan-review")
            (project_dir / "docs" / "spec.md").write_text("# Spec\n\nStatus: approved\n\n## Acceptance Criteria\n- [x] Docs converge.\n", encoding="utf-8")
            (project_dir / "docs" / "plan.md").write_text("# Plan\n\nStatus: approved\n\n## Steps\n1. Step: run execution.\n   Files: workflow/grill_storm.py\n   Run: python -m unittest tests.test_grill_storm_loop -v\n   Expected: PASS\n   Verify: tests pass.\n\n## Rollback / Safety\n- Revert loop dispatch.\n", encoding="utf-8")

            payload = run_planning_step(project_dir, run_root=project_dir / ".yolo")

            self.assertEqual(payload["status"], "ready_for_execution")
            self.assertIn("spec", payload)
            self.assertIn("plan", payload)

    def test_loop_dispatches_logos_spec_authoring_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            decisions = "# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Muse\n- Status: accepted\n- Actor: muse\n- Decision: Muse explored intent.\n\n### 2026-05-12 - Logos\n- Status: accepted\n- Actor: logos\n- Decision: Logos converged approach.\n\n### 2026-05-12 - Human consensus approval\n- Status: accepted\n- Actor: human\n- Source: consensus\n- Decision: Build human-gated planning.\n"
            self.write_docs(project_dir, decisions=decisions)
            self.write_human_approvals(project_dir, "consensus")
            (project_dir / "docs" / "open-questions.md").write_text("# Open Questions\n\n## High Priority\n- [ ] None.\n", encoding="utf-8")

            payload = run_planning_step(project_dir, run_root=project_dir / ".yolo")

            self.assertEqual(payload["status"], "dispatch_required")
            dispatch = payload["dispatch_request"]
            self.assertEqual(dispatch["role"], "logos")
            self.assertEqual(dispatch["planning_mode"], "logos-spec-writer")
            self.assertIn("logos-spec-writer", dispatch["agent_prompt"])
            self.assertIn("docs/spec.md", dispatch["write_any_of"])

    def test_loop_passes_through_human_dialogue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            decisions = "# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Muse\n- Status: accepted\n- Actor: muse\n- Decision: Muse explored options.\n\n### 2026-05-12 - Logos consensus\n- Status: accepted\n- Actor: logos\n- Source: consensus-candidate\n- Decision: Surface one approach.\n- Consensus: Controller gates | Summary: add state gates | Tradeoffs: clear ownership | Recommended: true\n"
            self.write_docs(project_dir, decisions=decisions)
            (project_dir / "docs" / "open-questions.md").write_text("# Open Questions\n\n## High Priority\n- [ ] None.\n", encoding="utf-8")

            payload = run_planning_step(project_dir, run_root=project_dir / ".yolo")

            self.assertEqual(payload["status"], "human_dialogue")
            self.assertEqual(payload["dialogue_type"], "consensus")

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


class GrillStormLoopTest(unittest.TestCase):
    def write_docs(self, project_dir: Path, *, docs_dir: str = "docs", decisions: str = "# Decisions\n\n## Decision Log\n") -> None:
        docs = project_dir / docs_dir
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "intent.md").write_text("# Intent\n\n## Primary Goal\n- Build safe planning flow.\n", encoding="utf-8")
        (docs / "open-questions.md").write_text("# Open Questions\n\n## High Priority\n- [ ] None.\n", encoding="utf-8")
        (docs / "decisions.md").write_text(decisions, encoding="utf-8")
        (docs / "spec.md").write_text("# Spec\n\nStatus: draft\n\n## Acceptance Criteria\n- [ ] Docs converge.\n", encoding="utf-8")
        (docs / "plan.md").write_text("# Plan\n\nStatus: draft\n\n## Steps\n1. Step: converge docs.\n   Verify: validator passes.\n", encoding="utf-8")

    def test_planning_step_requests_interviewer_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(project_dir)

            payload = run_planning_step(project_dir, run_root=project_dir / ".yolo", max_rounds=6)

            self.assertEqual(payload["status"], "dispatch_required")
            dispatch = payload["dispatch_request"]
            self.assertEqual(dispatch["role"], "interviewer")
            self.assertEqual(dispatch["round"], 1)
            self.assertEqual(dispatch["project_dir"], str(project_dir.resolve()))
            self.assertEqual(dispatch["run_root"], str((project_dir / ".yolo").resolve()))
            self.assertIn("docs/intent.md", dispatch["read"])
            self.assertIn("docs/decisions.md", dispatch["write_any_of"])
            self.assertIn("required_output_schema", dispatch)
            self.assertIn("agent_prompt", dispatch)
            self.assertIn("Muse", dispatch["agent_prompt"])
            self.assertEqual(dispatch["session_action"], "create")
            self.assertTrue(dispatch["agent_id"].startswith("interviewer-1-"))
            self.assertEqual(dispatch["agent_generation"], 1)

    def test_persistent_session_reused_across_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            self.write_docs(project_dir)
            run_root = project_dir / ".yolo"

            dispatch1 = run_planning_step(project_dir, run_root=run_root)["dispatch_request"]
            self.assertEqual(dispatch1["session_action"], "create")
            agent_id_1 = dispatch1["agent_id"]

            from grill_storm_loop import record_round_result
            record_round_result(
                dispatch1,
                {
                    "role": "interviewer",
                    "round": 1,
                    "status": "completed",
                    "docs_touched": ["docs/decisions.md"],
                    "summary": "Muse explored intent.",
                    "decisions_recorded": ["User wants safe planning."],
                    "questions_added": [],
                    "next_recommendation": "Logos evaluate feasibility.",
                },
            )

            decisions = "# Decisions\n\n## Decision Log\n\n### 2026-05-11 - Interviewer\n- Status: accepted\n- Actor: interviewer\n- Decision: User wants safe planning.\n"
            self.write_docs(project_dir, decisions=decisions)

            dispatch2 = run_planning_step(project_dir, run_root=run_root)["dispatch_request"]
            self.assertEqual(dispatch2["role"], "planner")
            self.assertEqual(dispatch2["session_action"], "create")
            self.assertIn("Logos", dispatch2["agent_prompt"])

            sessions = load_agent_sessions(run_root)
            self.assertEqual(sessions["roles"]["interviewer"]["agent_id"], agent_id_1)
            self.assertEqual(sessions["roles"]["interviewer"]["generation"], 1)
            self.assertEqual(sessions["roles"]["interviewer"]["status"], "active")
            self.assertEqual(sessions["roles"]["planner"]["generation"], 1)
            self.assertEqual(sessions["roles"]["planner"]["status"], "active")

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
                        "role": "interviewer",
                        "round": 1,
                        "status": "completed",
                        "docs_touched": ["docs/plan.md"],
                        "summary": "Tried to edit plan.",
                        "decisions_recorded": [],
                        "questions_added": [],
                        "next_recommendation": "Planner should continue.",
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
                        "role": "interviewer",
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
                    "role": "interviewer",
                    "round": 1,
                    "status": "completed",
                    "docs_touched": ["docs/decisions.md"],
                    "summary": "Recorded preflight ownership decision.",
                    "decisions_recorded": ["Preflight owns execution readiness."],
                    "questions_added": [],
                    "next_recommendation": "Planner should compare options.",
                },
                now="2026-05-11T02:00:00+00:00",
            )

            self.assertEqual(persisted["role"], "interviewer")
            rounds = load_planning_rounds(project_dir / ".yolo")
            self.assertEqual(rounds[0]["summary"], "Recorded preflight ownership decision.")

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
            self.assertEqual(payload["dispatch_request"]["role"], "interviewer")

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
                    "role": "interviewer",
                    "round": 1,
                    "status": "completed",
                    "docs_touched": ["docs/decisions.md"],
                    "summary": "Recorded decision.",
                    "decisions_recorded": ["Preflight owns readiness."],
                    "questions_added": [],
                    "next_recommendation": "Planner continue.",
                },
            }

            record_result = subprocess.run(
                [sys.executable, str(GRILL_STORM_LOOP_PATH), "record", "--result-json", json.dumps(result_payload)],
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
                    "role": "interviewer",
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
            decisions = "# Decisions\n\n## Decision Log\n\n### 2026-05-11 - Interviewer\n- Status: accepted\n- Actor: interviewer\n- Decision: Ask late.\n\n### 2026-05-11 - Planner\n- Status: accepted\n- Actor: planner\n- Decision: Keep preflight gate.\n\n### 2026-05-12 - Human consensus approval\n- Status: accepted\n- Actor: human\n- Source: consensus\n- Decision: Build approved planning docs.\n\n### 2026-05-12 - Logos spec self-review\n- Status: accepted\n- Actor: planner\n- Source: spec-self-review\n- Decision: Spec passes self-review.\n\n### 2026-05-12 - Human spec review\n- Status: accepted\n- Actor: human\n- Source: spec-review\n- Decision: Spec approved.\n\n### 2026-05-12 - Human plan review\n- Status: accepted\n- Actor: human\n- Source: plan-review\n- Decision: Plan approved.\n"
            self.write_docs(project_dir, decisions=decisions)
            (project_dir / "docs" / "open-questions.md").write_text("# Open Questions\n\n## High Priority\n- [ ] Blocking: yes | Question: Which owner approves execution? | Recommended: preflight\n", encoding="utf-8")

            payload = run_planning_step(project_dir, run_root=project_dir / ".yolo")

            self.assertEqual(payload["status"], "ask_user")
            self.assertEqual(payload["question"], "Which owner approves execution?")

    def test_step_passes_through_ready_for_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            decisions = "# Decisions\n\n## Decision Log\n\n### 2026-05-11 - Interviewer\n- Status: accepted\n- Actor: interviewer\n- Decision: Ask late.\n\n### 2026-05-11 - Planner\n- Status: accepted\n- Actor: planner\n- Decision: Keep preflight gate.\n\n### 2026-05-12 - Human consensus approval\n- Status: accepted\n- Actor: human\n- Source: consensus\n- Decision: Build approved planning docs.\n\n### 2026-05-12 - Logos spec self-review\n- Status: accepted\n- Actor: planner\n- Source: spec-self-review\n- Decision: Spec passes self-review.\n\n### 2026-05-12 - Human spec review\n- Status: accepted\n- Actor: human\n- Source: spec-review\n- Decision: Spec approved.\n\n### 2026-05-12 - Human plan review\n- Status: accepted\n- Actor: human\n- Source: plan-review\n- Decision: Plan approved.\n"
            self.write_docs(project_dir, decisions=decisions)
            (project_dir / "docs" / "spec.md").write_text("# Spec\n\nStatus: approved\n\n## Acceptance Criteria\n- [x] Docs converge.\n", encoding="utf-8")
            (project_dir / "docs" / "plan.md").write_text("# Plan\n\nStatus: approved\n\n## Steps\n1. Step: run execution.\n   Files: workflow/grill_storm.py\n   Run: python -m unittest tests.test_grill_storm_loop -v\n   Expected: PASS\n   Verify: tests pass.\n\n## Rollback / Safety\n- Revert loop dispatch.\n", encoding="utf-8")

            payload = run_planning_step(project_dir, run_root=project_dir / ".yolo")

            self.assertEqual(payload["status"], "ready_for_execution")
            self.assertIn("spec", payload)
            self.assertIn("plan", payload)

    def test_loop_dispatches_planner_spec_authoring_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            decisions = "# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Interviewer\n- Status: accepted\n- Actor: interviewer\n- Decision: Muse explored intent.\n\n### 2026-05-12 - Planner\n- Status: accepted\n- Actor: planner\n- Decision: Logos converged approach.\n\n### 2026-05-12 - Human consensus approval\n- Status: accepted\n- Actor: human\n- Source: consensus\n- Decision: Build human-gated planning.\n"
            self.write_docs(project_dir, decisions=decisions)
            (project_dir / "docs" / "open-questions.md").write_text("# Open Questions\n\n## High Priority\n- [ ] None.\n", encoding="utf-8")

            payload = run_planning_step(project_dir, run_root=project_dir / ".yolo")

            self.assertEqual(payload["status"], "dispatch_required")
            dispatch = payload["dispatch_request"]
            self.assertEqual(dispatch["role"], "planner")
            self.assertEqual(dispatch["planning_mode"], "logos-spec-writer")
            self.assertIn("logos-spec-writer", dispatch["agent_prompt"])
            self.assertIn("docs/spec.md", dispatch["write_any_of"])

    def test_loop_passes_through_human_dialogue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            decisions = "# Decisions\n\n## Decision Log\n\n### 2026-05-12 - Interviewer\n- Status: accepted\n- Actor: interviewer\n- Decision: Muse explored options.\n\n### 2026-05-12 - Planner consensus\n- Status: accepted\n- Actor: planner\n- Source: consensus-candidate\n- Decision: Surface one approach.\n- Consensus: Controller gates | Summary: add state gates | Tradeoffs: clear ownership | Recommended: true\n"
            self.write_docs(project_dir, decisions=decisions)
            (project_dir / "docs" / "open-questions.md").write_text("# Open Questions\n\n## High Priority\n- [ ] None.\n", encoding="utf-8")

            payload = run_planning_step(project_dir, run_root=project_dir / ".yolo")

            self.assertEqual(payload["status"], "human_dialogue")
            self.assertEqual(payload["dialogue_type"], "consensus")

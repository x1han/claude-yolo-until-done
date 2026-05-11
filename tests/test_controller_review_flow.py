from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from controller import update_for_helper_request

BOOTSTRAP_PATH = SKILL_ROOT / "workflow" / "bootstrap.py"
CONTROLLER_PATH = SKILL_ROOT / "workflow" / "controller.py"
CLEANUP_PATH = SKILL_ROOT / "workflow" / "cleanup_claude_yolo.py"
INSTALL_HOOKS_PATH = SKILL_ROOT / "workflow" / "install_claude_hooks.py"
RUN_GATE_PATH = SKILL_ROOT / "hooks" / "run_gate.py"


class ControllerReviewFlowTest(unittest.TestCase):
    def run_loop_iteration(self, project_dir: Path, run_root: Path, expected_versions: tuple[int, int, int], *, converged: bool = False) -> dict:
        submit_version, review_version, complete_version = expected_versions
        submit_command = [
            sys.executable,
            str(CONTROLLER_PATH),
            "--run-root",
            str(run_root),
            "--actor",
            "worker",
            "--action",
            "submit",
            "--expected-version",
            str(submit_version),
            "--worker-claim",
            "Implemented loop iteration.",
            "--files-changed",
            "workflow/controller.py",
            "--verification-command",
            "python -m unittest tests.test_controller_review_flow",
            "--verification-result",
            "pass",
        ]
        if converged:
            submit_command.append("--loop-converged")
        submit = subprocess.run(
            submit_command,
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(submit.returncode, 0, submit.stderr)

        approve = subprocess.run(
            [
                sys.executable,
                str(CONTROLLER_PATH),
                "--run-root",
                str(run_root),
                "--actor",
                "watcher",
                "--action",
                "review",
                "--expected-version",
                str(review_version),
                "--verdict",
                "approve",
                "--scope-checked",
                "workflow/controller.py",
                "--acceptance-basis",
                "Loop iteration satisfies the approved plan.",
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(approve.returncode, 0, approve.stderr)

        complete = subprocess.run(
            [
                sys.executable,
                str(CONTROLLER_PATH),
                "--run-root",
                str(run_root),
                "--actor",
                "watcher",
                "--action",
                "complete",
                "--expected-version",
                str(complete_version),
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(complete.returncode, 0, complete.stderr)
        return json.loads((run_root / "state.json").read_text(encoding="utf-8"))

    def bootstrap_loop_run(self, project_dir: Path, run_root: Path, *, max_iterations: int | None = None, stop_on_convergence: bool = False) -> None:
        spec_path = project_dir / "spec.md"
        plan_path = project_dir / "plan.md"
        spec_path.write_text("# Spec\nLoop mode repeats the approved plan until stop policy fires.\n", encoding="utf-8")
        plan_path.write_text("# Plan\n## Tasks\n1. Complete one acyclic iteration.\n", encoding="utf-8")
        command = [
            sys.executable,
            str(BOOTSTRAP_PATH),
            "--spec",
            str(spec_path),
            "--plan",
            str(plan_path),
            "--run-root",
            str(run_root),
            "--goal",
            "Repeat approved work until loop policy stops.",
            "--success-criterion",
            "each approved iteration either schedules the next worker or stops for cleanup.",
            "--mode",
            "loop",
        ]
        if max_iterations is not None:
            command.extend(["--loop-max-iterations", str(max_iterations)])
        if stop_on_convergence:
            command.append("--loop-stop-on-convergence")
        bootstrap = subprocess.run(command, cwd=project_dir, capture_output=True, text=True, check=False)
        self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

    def test_loop_complete_schedules_next_worker_iteration_before_max_iterations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.bootstrap_loop_run(project_dir, run_root, max_iterations=2)

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            state["gate_attempt"] = 4
            (run_root / "state.json").write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

            state = self.run_loop_iteration(project_dir, run_root, (1, 2, 3))

            self.assertEqual(state["status"], "active")
            self.assertEqual(state["owner"], "worker")
            self.assertEqual(state["next_action"], "worker_update")
            self.assertFalse(state["cleanup_required"])
            self.assertEqual(state["loop"]["iteration"], 2)
            self.assertEqual(state["loop"]["stop_reason"], "")
            self.assertEqual(state["requested_role"], "worker")
            self.assertEqual(state["dispatch_status"], "running")
            self.assertEqual(state["dispatch_claim"]["owner"], "worker:gate-task-001:3")
            self.assertEqual(state["last_dispatch"]["role"], "worker")
            self.assertEqual(state["gate_attempt"], 0)
            self.assertEqual(state["review"], {})
            self.assertEqual(state["worker_claim"], "")
            self.assertEqual(state["verification_command"], "")
            self.assertEqual(state["verification_result"], "")

    def test_loop_complete_stops_at_max_iterations_and_records_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.bootstrap_loop_run(project_dir, run_root, max_iterations=1)

            state = self.run_loop_iteration(project_dir, run_root, (1, 2, 3))

            self.assertEqual(state["status"], "ready_for_cleanup")
            self.assertEqual(state["owner"], "watcher")
            self.assertEqual(state["next_action"], "complete")
            self.assertTrue(state["cleanup_required"])
            self.assertEqual(state["dispatch_status"], "idle")
            self.assertEqual(state["last_dispatch"], {})
            self.assertEqual(state["loop"]["iteration"], 1)
            self.assertEqual(state["loop"]["stop_reason"], "max_iterations")

    def test_loop_complete_stops_on_convergence_and_records_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            run_root = project_dir / ".yolo"
            self.bootstrap_loop_run(project_dir, run_root, stop_on_convergence=True)

            state = self.run_loop_iteration(project_dir, run_root, (1, 2, 3), converged=True)

            self.assertEqual(state["status"], "ready_for_cleanup")
            self.assertTrue(state["cleanup_required"])
            self.assertEqual(state["loop"]["iteration"], 1)
            self.assertEqual(state["loop"]["stop_reason"], "converged")

    def test_no_human_run_rejects_need_human(self) -> None:
        state = {
            "allow_need_human": False,
            "owner": "worker",
            "next_action": "worker_update",
            "requested_role": "worker",
            "dispatch_status": "idle",
            "last_dispatch": {},
            "blocked_for_human": False,
            "worker_request": "",
            "worker_question": "",
            "human_handoff": {"summary": "stale"},
        }

        with self.assertRaisesRegex(SystemExit, "forbids need_human"):
            update_for_helper_request(state, "need_human", "Need product guidance.")

        self.assertFalse(state["blocked_for_human"])
        self.assertEqual(state["worker_request"], "")
        self.assertEqual(state["worker_question"], "")

    def test_no_human_run_still_allows_need_helper_and_clears_stale_human_state(self) -> None:
        state = {
            "allow_need_human": False,
            "owner": "human",
            "next_action": "human_handoff",
            "requested_role": "human",
            "dispatch_status": "dispatched",
            "last_dispatch": {"role": "human"},
            "blocked_for_human": True,
            "worker_request": "need_human",
            "worker_question": "Need product guidance.",
            "human_handoff": {"summary": "stale"},
            "resume_target": {"role": "worker", "action": "worker_rework"},
            "gate_reason": "stale_handoff",
        }

        update_for_helper_request(state, "need_helper", "Check validator scope.")

        self.assertFalse(state["blocked_for_human"])
        self.assertEqual(state["human_handoff"], {})
        self.assertEqual(state["resume_target"], {})
        self.assertEqual(state["owner"], "worker")
        self.assertEqual(state["next_action"], "worker_update")
        self.assertEqual(state["worker_request"], "need_helper")
        self.assertEqual(state["worker_question"], "Check validator scope.")
        self.assertEqual(state["requested_role"], "helper")
        self.assertEqual(state["dispatch_status"], "pending")
        self.assertEqual(state["last_dispatch"], {})
        self.assertEqual(state["gate_reason"], "")

    def test_need_human_persists_resume_target_before_handoff(self) -> None:
        state = {
            "allow_need_human": True,
            "owner": "worker",
            "next_action": "worker_rework",
            "requested_role": "worker",
            "dispatch_status": "completed",
            "last_dispatch": {"role": "worker"},
            "blocked_for_human": False,
            "worker_request": "",
            "worker_question": "",
            "human_handoff": {},
            "resume_target": {},
            "gate_reason": "worker_return_stop_block",
        }

        update_for_helper_request(state, "need_human", "Need product guidance.")

        self.assertTrue(state["blocked_for_human"])
        self.assertEqual(state["owner"], "human")
        self.assertEqual(state["next_action"], "human_handoff")
        self.assertEqual(state["requested_role"], "human")
        self.assertEqual(state["resume_target"], {"role": "worker", "action": "worker_rework"})
        self.assertEqual(state["worker_request"], "need_human")
        self.assertEqual(state["worker_question"], "Need product guidance.")

    def test_worker_submit_then_watcher_reject_approve_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"

            spec_path.write_text("# Spec\nReview flow stays within the same task gate.\n", encoding="utf-8")
            plan_path.write_text(
                "# Plan\n## Tasks\n1. Preserve gate identity during rework.\n",
                encoding="utf-8",
            )

            bootstrap = subprocess.run(
                [
                    sys.executable,
                    str(BOOTSTRAP_PATH),
                    "--spec",
                    str(spec_path),
                    "--plan",
                    str(plan_path),
                    "--run-root",
                    str(run_root),
                    "--goal",
                    "Ship reviewed workflow state transitions.",
                    "--success-criterion",
                    "worker submissions move the run into watcher review.",
                    "--success-criterion",
                    "watchers can reject, approve, and complete the run.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["gate_id"], "gate-task-001")
            self.assertEqual(state["gate_attempt"], 0)
            self.assertFalse(state["cleanup_required"])
            self.assertTrue((run_root / "watcher_checklist.json").exists())

            submit = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER_PATH),
                    "--run-root",
                    str(run_root),
                    "--actor",
                    "worker",
                    "--action",
                    "submit",
                    "--expected-version",
                    "1",
                    "--worker-claim",
                    "Implemented review flow.",
                    "--files-changed",
                    "workflow/controller.py",
                    "workflow/state.py",
                    "--verification-command",
                    "python -m unittest tests.test_controller_review_flow",
                    "--verification-result",
                    "pass",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(submit.returncode, 0, submit.stderr)

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "needs_review")
            self.assertEqual(state["owner"], "watcher")
            self.assertEqual(state["next_action"], "watcher_review")
            self.assertEqual(state["worker_claim"], "Implemented review flow.")
            self.assertEqual(state["files_changed"], ["workflow/controller.py", "workflow/state.py"])
            self.assertEqual(state["verification_command"], "python -m unittest tests.test_controller_review_flow")
            self.assertEqual(state["verification_result"], "pass")
            self.assertTrue(state["submitted_at"])
            self.assertEqual(state["review"], {})
            self.assertEqual(state["state_version"], 2)
            self.assertEqual(state["last_transition_actor"], "worker")
            self.assertEqual(state["last_transition_id"], "worker:submit:2")
            self.assertEqual(state["requested_role"], "watcher")
            self.assertEqual(state["dispatch_status"], "running")
            self.assertEqual(state["dispatch_claim"]["owner"], "watcher:gate-task-001:1")
            self.assertEqual(state["last_dispatch"]["role"], "watcher")

            worker_complete = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER_PATH),
                    "--run-root",
                    str(run_root),
                    "--actor",
                    "worker",
                    "--action",
                    "complete",
                    "--expected-version",
                    "2",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(worker_complete.returncode, 0)

            reject = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER_PATH),
                    "--run-root",
                    str(run_root),
                    "--actor",
                    "watcher",
                    "--action",
                    "review",
                    "--expected-version",
                    "2",
                    "--verdict",
                    "rework_required",
                    "--scope-checked",
                    "workflow/controller.py",
                    "--problem",
                    "Completion is not gated on an approved review.",
                    "--required-rework",
                    "Require watcher approval before completion.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(reject.returncode, 0, reject.stderr)

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "rework_required")
            self.assertEqual(state["owner"], "worker")
            self.assertEqual(state["next_action"], "worker_rework")
            self.assertEqual(state["gate_id"], "gate-task-001")
            self.assertEqual(state["gate_attempt"], 0)
            self.assertEqual(state["review"]["verdict"], "rework_required")
            self.assertEqual(state["review"]["scope_checked"], ["workflow/controller.py"])
            self.assertEqual(state["review"]["problems"], ["Completion is not gated on an approved review."])
            self.assertEqual(state["review"]["required_rework"], ["Require watcher approval before completion."])
            self.assertEqual(state["review"]["acceptance_basis"], [])
            self.assertTrue(state["reviewed_at"])
            self.assertEqual(state["requested_role"], "worker")
            self.assertEqual(state["dispatch_status"], "running")
            self.assertEqual(state["dispatch_claim"]["owner"], "worker:gate-task-001:2")
            self.assertEqual(state["last_dispatch"]["role"], "worker")

            resubmit = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER_PATH),
                    "--run-root",
                    str(run_root),
                    "--actor",
                    "worker",
                    "--action",
                    "submit",
                    "--expected-version",
                    "3",
                    "--worker-claim",
                    "Addressed watcher rework.",
                    "--files-changed",
                    "workflow/controller.py",
                    "workflow/state.py",
                    "--verification-command",
                    "python -m unittest tests.test_controller_review_flow",
                    "--verification-result",
                    "pass after rework",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(resubmit.returncode, 0, resubmit.stderr)

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "needs_review")
            self.assertEqual(state["gate_id"], "gate-task-001")
            self.assertEqual(state["gate_attempt"], 0)
            self.assertEqual(state["requested_role"], "watcher")
            self.assertEqual(state["dispatch_status"], "running")
            self.assertEqual(state["dispatch_claim"]["owner"], "watcher:gate-task-001:3")
            self.assertEqual(state["last_dispatch"]["role"], "watcher")

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            state["worker_request"] = "need_helper"
            state["worker_question"] = "Should helper inspect validators?"
            state["blocked_for_human"] = True
            state["human_handoff"] = {"reason": "stale"}
            (run_root / "state.json").write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

            approve = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER_PATH),
                    "--run-root",
                    str(run_root),
                    "--actor",
                    "watcher",
                    "--action",
                    "review",
                    "--expected-version",
                    "4",
                    "--verdict",
                    "approve",
                    "--scope-checked",
                    "workflow/controller.py",
                    "workflow/state.py",
                    "--acceptance-basis",
                    "Completion is now gated on approved review.",
                    "--acceptance-basis",
                    "Submission and rework transitions match the workflow contract.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(approve.returncode, 0, approve.stderr)

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "approved")
            self.assertEqual(state["owner"], "watcher")
            self.assertEqual(state["next_action"], "watcher_complete")
            self.assertEqual(state["review"]["verdict"], "approve")
            self.assertEqual(state["review"]["scope_checked"], ["workflow/controller.py", "workflow/state.py"])
            self.assertEqual(state["review"]["problems"], [])
            self.assertEqual(state["review"]["required_rework"], [])
            self.assertEqual(
                state["review"]["acceptance_basis"],
                [
                    "Completion is now gated on approved review.",
                    "Submission and rework transitions match the workflow contract.",
                ],
            )
            self.assertEqual(state["requested_role"], "watcher")
            self.assertEqual(state["dispatch_status"], "running")
            self.assertEqual(state["dispatch_claim"]["owner"], "watcher:gate-task-001:4")
            self.assertEqual(state["last_dispatch"]["role"], "watcher")
            self.assertFalse(state["blocked_for_human"])
            self.assertEqual(state["human_handoff"], {})
            self.assertEqual(state["worker_request"], "")
            self.assertEqual(state["worker_question"], "")

            complete = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER_PATH),
                    "--run-root",
                    str(run_root),
                    "--actor",
                    "watcher",
                    "--action",
                    "complete",
                    "--expected-version",
                    "5",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(complete.returncode, 0, complete.stderr)

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "ready_for_cleanup")
            self.assertNotEqual(state["status"], "complete")
            self.assertEqual(state["next_action"], "complete")
            self.assertEqual(state["owner"], "watcher")
            self.assertTrue(state["cleanup_required"])
            self.assertEqual(state["dispatch_status"], "idle")
            self.assertEqual(state["last_dispatch"], {})
            self.assertFalse(state["blocked_for_human"])
            self.assertEqual(state["human_handoff"], {})
            self.assertEqual(state["worker_request"], "")
            self.assertEqual(state["worker_question"], "")

            completion = subprocess.run(
                [
                    sys.executable,
                    str(RUN_GATE_PATH),
                    "--validator",
                    "completion",
                    "--run-root",
                    str(run_root),
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completion.returncode, 0, completion.stderr)

            trace = (run_root / "trace.md").read_text(encoding="utf-8")
            self.assertIn("worker submit", trace)
            self.assertIn("claim=Implemented review flow.", trace)
            self.assertIn("verification=pass", trace)
            self.assertIn("watcher review: rework_required", trace)
            self.assertIn("problems=Completion is not gated on an approved review.", trace)
            self.assertIn("required_rework=Require watcher approval before completion.", trace)
            self.assertIn("watcher review: approve", trace)
            self.assertIn("acceptance_basis=Completion is now gated on approved review.; Submission and rework transitions match the workflow contract.", trace)
            self.assertIn("watcher complete", trace)

            cleanup = subprocess.run(
                [
                    sys.executable,
                    str(CLEANUP_PATH),
                    "--project-dir",
                    str(project_dir),
                    "--run-root",
                    ".yolo",
                    "--mode",
                    "complete",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
            self.assertFalse((run_root / "state.json").exists())
            self.assertFalse((run_root / "trace.md").exists())
            self.assertFalse((run_root / "watcher_checklist.json").exists())

            settings = json.loads((project_dir / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
            self.assertNotIn("claudeYoloUntilDone", settings)
            self.assertNotIn("SessionStart", settings.get("hooks", {}))
            self.assertNotIn("Stop", settings.get("hooks", {}))
            self.assertNotIn("UserPromptSubmit", settings.get("hooks", {}))

    def test_watcher_review_rejects_non_live_dispatch_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"

            spec_path.write_text("# Spec\nReview flow stays within the same task gate.\n", encoding="utf-8")
            plan_path.write_text("# Plan\n## Tasks\n1. Preserve gate identity during rework.\n", encoding="utf-8")

            bootstrap = subprocess.run(
                [
                    sys.executable,
                    str(BOOTSTRAP_PATH),
                    "--spec",
                    str(spec_path),
                    "--plan",
                    str(plan_path),
                    "--run-root",
                    str(run_root),
                    "--goal",
                    "Ship reviewed workflow state transitions.",
                    "--success-criterion",
                    "worker submissions move the run into watcher review.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            submit = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER_PATH),
                    "--run-root",
                    str(run_root),
                    "--actor",
                    "worker",
                    "--action",
                    "submit",
                    "--expected-version",
                    "1",
                    "--worker-claim",
                    "Implemented review flow.",
                    "--files-changed",
                    "workflow/controller.py",
                    "--verification-command",
                    "python -m unittest tests.test_controller_review_flow",
                    "--verification-result",
                    "pass",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(submit.returncode, 0, submit.stderr)

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            state["dispatch_status"] = "completed"
            state["dispatch_claim"] = {}
            (run_root / "state.json").write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

            review = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER_PATH),
                    "--run-root",
                    str(run_root),
                    "--actor",
                    "watcher",
                    "--action",
                    "review",
                    "--expected-version",
                    "2",
                    "--verdict",
                    "approve",
                    "--scope-checked",
                    "workflow/controller.py",
                    "--acceptance-basis",
                    "Completion is now gated on approved review.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(review.returncode, 0)
            self.assertIn("dispatch authority", review.stderr or review.stdout)

    def test_worker_submit_rejects_stale_expected_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"

            spec_path.write_text("# Spec\nReview flow stays within the same task gate.\n", encoding="utf-8")
            plan_path.write_text("# Plan\n## Tasks\n1. Preserve gate identity during rework.\n", encoding="utf-8")

            bootstrap = subprocess.run(
                [
                    sys.executable,
                    str(BOOTSTRAP_PATH),
                    "--spec",
                    str(spec_path),
                    "--plan",
                    str(plan_path),
                    "--run-root",
                    str(run_root),
                    "--goal",
                    "Ship reviewed workflow state transitions.",
                    "--success-criterion",
                    "worker submissions move the run into watcher review.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            submit = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER_PATH),
                    "--run-root",
                    str(run_root),
                    "--actor",
                    "worker",
                    "--action",
                    "submit",
                    "--expected-version",
                    "0",
                    "--worker-claim",
                    "Implemented review flow.",
                    "--files-changed",
                    "workflow/controller.py",
                    "--verification-command",
                    "python -m unittest tests.test_controller_review_flow",
                    "--verification-result",
                    "pass",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(submit.returncode, 0)
            self.assertIn("Stale state version", submit.stderr or submit.stdout)

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "active")
            self.assertEqual(state["state_version"], 1)
            self.assertEqual(state["dispatch_status"], "pending")
            self.assertEqual(state["last_dispatch"], {})
            self.assertEqual(state["last_transition_actor"], "")
            self.assertEqual(state["last_transition_id"], "")

    def test_worker_submit_updates_state_version_and_dispatch_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"

            spec_path.write_text("# Spec\nReview flow stays within the same task gate.\n", encoding="utf-8")
            plan_path.write_text("# Plan\n## Tasks\n1. Preserve gate identity during rework.\n", encoding="utf-8")

            bootstrap = subprocess.run(
                [
                    sys.executable,
                    str(BOOTSTRAP_PATH),
                    "--spec",
                    str(spec_path),
                    "--plan",
                    str(plan_path),
                    "--run-root",
                    str(run_root),
                    "--goal",
                    "Ship reviewed workflow state transitions.",
                    "--success-criterion",
                    "worker submissions move the run into watcher review.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            submit = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER_PATH),
                    "--run-root",
                    str(run_root),
                    "--actor",
                    "worker",
                    "--action",
                    "submit",
                    "--expected-version",
                    "1",
                    "--worker-claim",
                    "Implemented review flow.",
                    "--files-changed",
                    "workflow/controller.py",
                    "workflow/state.py",
                    "--verification-command",
                    "python -m unittest tests.test_controller_review_flow",
                    "--verification-result",
                    "pass",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(submit.returncode, 0, submit.stderr)

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["state_version"], 2)
            self.assertEqual(state["last_transition_id"], "worker:submit:2")
            self.assertEqual(state["requested_role"], "watcher")
            self.assertEqual(state["dispatch_status"], "running")
            self.assertEqual(state["dispatch_claim"]["owner"], "watcher:gate-task-001:1")
            self.assertEqual(state["last_dispatch"]["role"], "watcher")

    def test_worker_submit_clears_stale_helper_and_human_routing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            spec_path = project_dir / "spec.md"
            plan_path = project_dir / "plan.md"
            run_root = project_dir / ".yolo"

            spec_path.write_text("# Spec\nReview flow stays within the same task gate.\n", encoding="utf-8")
            plan_path.write_text("# Plan\n## Tasks\n1. Preserve gate identity during rework.\n", encoding="utf-8")

            bootstrap = subprocess.run(
                [
                    sys.executable,
                    str(BOOTSTRAP_PATH),
                    "--spec",
                    str(spec_path),
                    "--plan",
                    str(plan_path),
                    "--run-root",
                    str(run_root),
                    "--goal",
                    "Ship reviewed workflow state transitions.",
                    "--success-criterion",
                    "worker submissions move the run into watcher review.",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            state["worker_request"] = "need_helper"
            state["worker_question"] = "Should helper inspect validators?"
            state["blocked_for_human"] = True
            state["human_handoff"] = {"reason": "stale"}
            (run_root / "state.json").write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

            submit = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER_PATH),
                    "--run-root",
                    str(run_root),
                    "--actor",
                    "worker",
                    "--action",
                    "submit",
                    "--expected-version",
                    "1",
                    "--worker-claim",
                    "Implemented review flow.",
                    "--files-changed",
                    "workflow/controller.py",
                    "--verification-command",
                    "python -m unittest tests.test_controller_review_flow",
                    "--verification-result",
                    "pass",
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(submit.returncode, 0, submit.stderr)

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "needs_review")
            self.assertEqual(state["requested_role"], "watcher")
            self.assertEqual(state["dispatch_status"], "running")
            self.assertEqual(state["dispatch_claim"]["owner"], "watcher:gate-task-001:1")
            self.assertEqual(state["last_dispatch"]["role"], "watcher")
            self.assertFalse(state["blocked_for_human"])
            self.assertEqual(state["human_handoff"], {})
            self.assertEqual(state["worker_request"], "")
            self.assertEqual(state["worker_question"], "")


if __name__ == "__main__":
    unittest.main()

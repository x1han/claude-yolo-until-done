from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = SKILL_ROOT / "workflow" / "bootstrap.py"
CONTROLLER_PATH = SKILL_ROOT / "workflow" / "controller.py"
CLEANUP_PATH = SKILL_ROOT / "workflow" / "cleanup_claude_yolo.py"
INSTALL_HOOKS_PATH = SKILL_ROOT / "workflow" / "install_claude_hooks.py"
RUN_GATE_PATH = SKILL_ROOT / "hooks" / "run_gate.py"


class ControllerReviewFlowTest(unittest.TestCase):
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
            self.assertEqual(state["requested_role"], "watcher")
            self.assertEqual(state["dispatch_status"], "dispatched")
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
            self.assertEqual(state["dispatch_status"], "dispatched")
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
            self.assertEqual(state["dispatch_status"], "dispatched")
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
            self.assertEqual(state["dispatch_status"], "dispatched")
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
                ],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(complete.returncode, 0, complete.stderr)

            state = json.loads((run_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "complete")
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
            self.assertEqual(state["dispatch_status"], "dispatched")
            self.assertEqual(state["last_dispatch"]["role"], "watcher")
            self.assertFalse(state["blocked_for_human"])
            self.assertEqual(state["human_handoff"], {})
            self.assertEqual(state["worker_request"], "")
            self.assertEqual(state["worker_question"], "")


if __name__ == "__main__":
    unittest.main()

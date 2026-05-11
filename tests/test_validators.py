from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = SKILL_ROOT / "hooks"
WORKFLOW_DIR = SKILL_ROOT / "workflow"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from lifecycle import build_completion_certification, compute_certification_hash
from validate_completion import run as validate_completion
from validate_submission import run as validate_submission


class ValidatorsTest(unittest.TestCase):
    def completion_certification(self, state: dict) -> dict:
        payload = build_completion_certification(state, "2026-05-01T00:01:30Z")
        return {
            "certification": {"completion": payload},
            "certification_hash": compute_certification_hash(payload),
        }

    def test_submission_validator_rejects_missing_worker_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "needs_review",
                        "task_id": "task-001",
                        "task_title": "Fix parser handling",
                        "task_inputs": {"task_id": "task-001", "task_title": "Fix parser handling"},
                        "worker_claim": "",
                        "files_changed": ["src/app.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed: 1 passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {},
                        "reviewed_at": "",
                        "owner": "watcher",
                        "next_action": "watcher_review",
                        "plan_path": "docs/plan.md",
                        "spec_path": "docs/spec.md",
                        "updated_at": "2026-05-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            (run_root / "trace.md").write_text("- 2026-05-01T00:00:00Z worker submit: claim=Updated src/app.py\n", encoding="utf-8")
            report = validate_submission(run_root)
            self.assertFalse(report["passed"])

    def test_submission_validator_rejects_stale_dispatched_state_for_worker_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "needs_review",
                        "task_id": "task-001",
                        "task_title": "Fix parser handling",
                        "task_inputs": {"task_id": "task-001", "task_title": "Fix parser handling"},
                        "worker_claim": "Updated file",
                        "files_changed": ["workflow/controller.py"],
                        "verification_command": "python -m unittest -v",
                        "verification_result": "passed",
                        "submitted_at": "2026-05-07T00:00:00Z",
                        "review": {},
                        "reviewed_at": "",
                        "owner": "watcher",
                        "next_action": "watcher_review",
                        "cleanup_required": False,
                        "plan_path": "docs/plan.md",
                        "spec_path": "docs/spec.md",
                        "requested_role": "watcher",
                        "dispatch_status": "dispatched",
                        "last_dispatch": {"role": "worker", "task_id": "task-001"},
                        "updated_at": "2026-05-07T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            (run_root / "trace.md").write_text("- 2026-05-07T00:00:00Z worker submit: claim=Updated file\n", encoding="utf-8")
            report = validate_submission(run_root)
            self.assertFalse(report["passed"])
            self.assertIn("dispatch_matches_review_target", {item["name"] for item in report["failures"]})

    def test_submission_validator_reports_from_authoritative_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "needs_review",
                        "task_id": "task-001",
                        "task_title": "Fix parser handling",
                        "task_inputs": {"task_id": "task-001", "task_title": "Fix parser handling"},
                        "worker_claim": "Updated parser handling.",
                        "files_changed": ["src/app.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed: 1 passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {},
                        "reviewed_at": "",
                        "owner": "watcher",
                        "next_action": "watcher_review",
                        "cleanup_required": False,
                        "requested_role": "watcher",
                        "dispatch_status": "completed",
                        "last_dispatch": {"role": "watcher", "task_id": "task-001"},
                        "certification": {
                            "submission": {
                                "status": "stale",
                                "state_version": 1,
                                "actor": "worker",
                                "action": "submit",
                            }
                        },
                        "plan_path": "docs/plan.md",
                        "spec_path": "docs/spec.md",
                        "updated_at": "2026-05-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            report = validate_submission(run_root)
            self.assertTrue(report["passed"])
            self.assertTrue(all(item["source"] == "state.json" for item in report["checks"]))
            self.assertEqual(report["warnings"][0]["name"], "submission_certification_not_authoritative")

    def test_submission_validator_rejects_missing_authoritative_task_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "needs_review",
                        "worker_claim": "Updated parser handling.",
                        "files_changed": ["src/app.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed: 1 passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {},
                        "reviewed_at": "",
                        "owner": "watcher",
                        "next_action": "watcher_review",
                        "cleanup_required": False,
                        "plan_path": "docs/plan.md",
                        "spec_path": "docs/spec.md",
                        "updated_at": "2026-05-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            report = validate_submission(run_root)
            self.assertFalse(report["passed"])
            self.assertTrue(
                {"state_field_task_id_present", "state_field_task_title_present", "state_field_task_inputs_present"}.issubset(
                    {item["name"] for item in report["failures"]}
                )
            )

    def test_completion_validator_rejects_complete_without_approved_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "ready_for_cleanup",
                        "task_id": "task-001",
                        "task_title": "Fix parser handling",
                        "task_inputs": {"task_id": "task-001", "task_title": "Fix parser handling"},
                        "worker_claim": "Updated parser handling.",
                        "files_changed": ["src/app.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed: 1 passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {"verdict": "rework_required", "scope_checked": [], "problems": ["x"], "required_rework": ["y"], "acceptance_basis": []},
                        "reviewed_at": "2026-05-01T00:01:00Z",
                        "owner": "watcher",
                        "next_action": "complete",
                        "plan_path": "docs/plan.md",
                        "spec_path": "docs/spec.md",
                        "updated_at": "2026-05-01T00:01:00Z",
                    }
                ),
                encoding="utf-8",
            )
            (run_root / "trace.md").write_text("- 2026-05-01T00:01:00Z watcher review: rework_required\n", encoding="utf-8")
            report = validate_completion(run_root)
            self.assertFalse(report["passed"])

    def test_completion_validator_rejects_ready_for_cleanup_without_cleanup_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "ready_for_cleanup",
                        "task_id": "task-001",
                        "task_title": "Fix parser handling",
                        "task_inputs": {"task_id": "task-001", "task_title": "Fix parser handling"},
                        "worker_claim": "Updated parser handling.",
                        "files_changed": ["src/app.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed: 1 passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {
                            "verdict": "approve",
                            "scope_checked": ["src/app.py"],
                            "problems": [],
                            "required_rework": [],
                            "acceptance_basis": ["verification passed freshly"],
                        },
                        "reviewed_at": "2026-05-01T00:01:00Z",
                        "owner": "watcher",
                        "next_action": "complete",
                        "cleanup_required": False,
                        "plan_path": "docs/plan.md",
                        "spec_path": "docs/spec.md",
                        "updated_at": "2026-05-01T00:01:00Z",
                    }
                ),
                encoding="utf-8",
            )
            (run_root / "trace.md").write_text(
                "- 2026-05-01T00:00:00Z worker submit: claim=Updated parser handling.\n"
                "- 2026-05-01T00:01:00Z watcher review: approve; scope_checked=src/app.py\n"
                "- 2026-05-01T00:02:00Z watcher complete\n",
                encoding="utf-8",
            )
            report = validate_completion(run_root)
            self.assertFalse(report["passed"])
            self.assertIn("cleanup_required_true", {item["name"] for item in report["failures"]})

    def test_completion_validator_rejects_review_scope_that_misses_changed_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "ready_for_cleanup",
                        "task_id": "task-001",
                        "task_title": "Fix parser handling",
                        "task_inputs": {"task_id": "task-001", "task_title": "Fix parser handling"},
                        "worker_claim": "Updated parser handling.",
                        "files_changed": ["src/app.py", "src/util.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed: 1 passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {
                            "verdict": "approve",
                            "scope_checked": ["src/app.py"],
                            "problems": [],
                            "required_rework": [],
                            "acceptance_basis": ["verification passed freshly"],
                        },
                        "reviewed_at": "2026-05-01T00:01:00Z",
                        "owner": "watcher",
                        "next_action": "complete",
                        "cleanup_required": True,
                        "plan_path": "docs/plan.md",
                        "spec_path": "docs/spec.md",
                        "updated_at": "2026-05-01T00:01:00Z",
                    }
                ),
                encoding="utf-8",
            )
            (run_root / "trace.md").write_text(
                "- 2026-05-01T00:00:00Z worker submit: claim=Updated parser handling.\n"
                "- 2026-05-01T00:01:00Z watcher review: approve; scope_checked=src/app.py\n"
                "- 2026-05-01T00:02:00Z watcher complete\n",
                encoding="utf-8",
            )
            report = validate_completion(run_root)
            self.assertFalse(report["passed"])
            self.assertIn("scope_checked_covers_files_changed", {item["name"] for item in report["failures"]})

    def test_completion_validator_rejects_wrong_cleanup_state_in_certification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "ready_for_cleanup",
                        "task_id": "task-001",
                        "task_title": "Fix parser handling",
                        "task_inputs": {"task_id": "task-001", "task_title": "Fix parser handling"},
                        "worker_claim": "Updated parser handling.",
                        "files_changed": ["src/app.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed: 1 passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {
                            "verdict": "approve",
                            "scope_checked": ["src/app.py"],
                            "problems": [],
                            "required_rework": [],
                            "acceptance_basis": ["verification passed freshly"],
                        },
                        "reviewed_at": "2026-05-01T00:01:00Z",
                        "owner": "watcher",
                        "next_action": "complete",
                        "cleanup_required": True,
                        "certification_hash": "abc123",
                        "certification": {
                            "completion": {
                                "status": "ok",
                                "cleanup_state": "complete",
                                "certified_at": "2026-05-01T00:01:30Z",
                                "task_id": "task-001",
                                "review_verdict": "approve",
                                "files_changed": ["src/app.py"],
                            }
                        },
                        "plan_path": "docs/plan.md",
                        "spec_path": "docs/spec.md",
                        "updated_at": "2026-05-01T00:01:00Z",
                    }
                ),
                encoding="utf-8",
            )
            (run_root / "trace.md").write_text(
                "- 2026-05-01T00:00:00Z worker submit: claim=Updated parser handling.\n"
                "- 2026-05-01T00:01:00Z watcher review: approve; scope_checked=src/app.py\n"
                "- 2026-05-01T00:02:00Z watcher complete\n",
                encoding="utf-8",
            )
            report = validate_completion(run_root)
            self.assertFalse(report["passed"])
            self.assertIn(
                "completion_certification_cleanup_state_ready_for_cleanup",
                {item["name"] for item in report["failures"]},
            )

    def test_completion_validator_rejects_missing_cleanup_ready_state_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "ready_for_cleanup",
                        "task_id": "task-001",
                        "task_title": "Fix parser handling",
                        "task_inputs": {"task_id": "task-001", "task_title": "Fix parser handling"},
                        "worker_claim": "Updated parser handling.",
                        "files_changed": ["src/app.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed: 1 passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {
                            "verdict": "approve",
                            "scope_checked": ["src/app.py"],
                            "problems": [],
                            "required_rework": [],
                            "acceptance_basis": ["verification passed freshly"],
                        },
                        "reviewed_at": "2026-05-01T00:01:00Z",
                        "owner": "watcher",
                        "next_action": "complete",
                        "cleanup_required": True,
                        "certification_hash": "wrong-hash",
                        "certification": {
                            "completion": {
                                "status": "ok",
                                "cleanup_state": "ready_for_cleanup",
                                "certified_at": "2026-05-01T00:01:30Z",
                                "task_id": "task-001",
                                "review_verdict": "approve",
                                "files_changed": ["src/app.py"],
                            }
                        },
                        "plan_path": "docs/plan.md",
                        "spec_path": "docs/spec.md",
                        "updated_at": "2026-05-01T00:01:00Z",
                    }
                ),
                encoding="utf-8",
            )
            (run_root / "trace.md").write_text(
                "- 2026-05-01T00:00:00Z worker submit: claim=Updated parser handling.\n"
                "- 2026-05-01T00:01:00Z watcher review: approve; scope_checked=src/app.py\n"
                "- 2026-05-01T00:02:00Z watcher complete\n",
                encoding="utf-8",
            )
            report = validate_completion(run_root)
            self.assertFalse(report["passed"])
            self.assertIn("completion_certification_cleanup_ready_state_hash_present", {item["name"] for item in report["failures"]})

    def test_completion_validator_rejects_mismatched_certification_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "state.json").write_text(
                json.dumps(
                    {
                        "goal": "Fix it.",
                        "success_criteria": ["It works."],
                        "status": "ready_for_cleanup",
                        "task_id": "task-001",
                        "task_title": "Fix parser handling",
                        "task_inputs": {"task_id": "task-001", "task_title": "Fix parser handling"},
                        "worker_claim": "Updated parser handling.",
                        "files_changed": ["src/app.py"],
                        "verification_command": "pytest -q",
                        "verification_result": "passed: 1 passed",
                        "submitted_at": "2026-05-01T00:00:00Z",
                        "review": {
                            "verdict": "approve",
                            "scope_checked": ["src/app.py"],
                            "problems": [],
                            "required_rework": [],
                            "acceptance_basis": ["verification passed freshly"],
                        },
                        "reviewed_at": "2026-05-01T00:01:00Z",
                        "owner": "watcher",
                        "next_action": "complete",
                        "cleanup_required": True,
                        "certification_hash": "wrong-hash",
                        "certification": {
                            "completion": {
                                "status": "ok",
                                "cleanup_state": "ready_for_cleanup",
                                "certified_at": "2026-05-01T00:01:30Z",
                                "task_id": "task-001",
                                "review_verdict": "approve",
                                "files_changed": ["src/app.py"],
                            }
                        },
                        "plan_path": "docs/plan.md",
                        "spec_path": "docs/spec.md",
                        "updated_at": "2026-05-01T00:01:00Z",
                    }
                ),
                encoding="utf-8",
            )
            (run_root / "trace.md").write_text(
                "- 2026-05-01T00:00:00Z worker submit: claim=Updated parser handling.\n"
                "- 2026-05-01T00:01:00Z watcher review: approve; scope_checked=src/app.py\n"
                "- 2026-05-01T00:02:00Z watcher complete\n",
                encoding="utf-8",
            )
            report = validate_completion(run_root)
            self.assertFalse(report["passed"])
            self.assertIn("completion_certification_hash_matches", {item["name"] for item in report["failures"]})

    def legacy_completion_certification(self, state: dict) -> dict:
        review = state.get("review") if isinstance(state.get("review"), dict) else {}
        snapshot = {
            "status": state.get("status", ""),
            "task_id": state.get("task_id", ""),
            "task_title": state.get("task_title", ""),
            "owner": state.get("owner", ""),
            "next_action": state.get("next_action", ""),
            "cleanup_required": state.get("cleanup_required"),
            "worker_claim": state.get("worker_claim", ""),
            "files_changed": list(state.get("files_changed", [])),
            "verification_command": state.get("verification_command", ""),
            "verification_result": state.get("verification_result", ""),
            "submitted_at": state.get("submitted_at", ""),
            "reviewed_at": state.get("reviewed_at", ""),
            "review_verdict": review.get("verdict", ""),
            "review_scope_checked": list(review.get("scope_checked", [])),
            "review_problems": list(review.get("problems", [])),
            "review_required_rework": list(review.get("required_rework", [])),
            "review_acceptance_basis": list(review.get("acceptance_basis", [])),
        }
        payload = {
            "status": "ok",
            "certified_at": "2026-05-01T00:01:30Z",
            "cleanup_state": "ready_for_cleanup",
            "cleanup_ready_state_hash": compute_certification_hash(snapshot),
            "task_id": state.get("task_id", ""),
            "review_verdict": review.get("verdict", ""),
            "files_changed": list(state.get("files_changed", [])),
        }
        return {
            "certification": {"completion": payload},
            "certification_hash": compute_certification_hash(payload),
        }

    def test_completion_validator_accepts_legacy_cleanup_certification_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            state = {
                "goal": "Fix it.",
                "success_criteria": ["It works."],
                "status": "ready_for_cleanup",
                "task_id": "task-001",
                "task_title": "Fix parser handling",
                "task_inputs": {"task_id": "task-001", "task_title": "Fix parser handling"},
                "worker_claim": "Updated parser handling.",
                "files_changed": ["src/app.py"],
                "verification_command": "pytest -q",
                "verification_result": "passed: 1 passed",
                "submitted_at": "2026-05-01T00:00:00Z",
                "review": {
                    "verdict": "approve",
                    "scope_checked": ["src/app.py"],
                    "problems": [],
                    "required_rework": [],
                    "acceptance_basis": ["verification passed freshly"],
                },
                "reviewed_at": "2026-05-01T00:01:00Z",
                "owner": "watcher",
                "next_action": "complete",
                "cleanup_required": True,
                "plan_path": "docs/plan.md",
                "spec_path": "docs/spec.md",
                "updated_at": "2026-05-01T00:01:00Z",
            }
            state.update(self.legacy_completion_certification(state))
            (run_root / "state.json").write_text(json.dumps(state), encoding="utf-8")
            (run_root / "trace.md").write_text(
                "- 2026-05-01T00:00:00Z worker submit: claim=Updated parser handling.\n"
                "- 2026-05-01T00:01:00Z watcher review: approve; scope_checked=src/app.py\n"
                "- 2026-05-01T00:02:00Z watcher complete\n",
                encoding="utf-8",
            )

            report = validate_completion(run_root)

            self.assertTrue(report["passed"])

    def test_completion_validator_rejects_loop_stop_reason_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            state = {
                "goal": "Fix it.",
                "success_criteria": ["It works."],
                "status": "ready_for_cleanup",
                "task_id": "task-001",
                "task_title": "Fix parser handling",
                "task_inputs": {"task_id": "task-001", "task_title": "Fix parser handling"},
                "worker_claim": "Updated parser handling.",
                "files_changed": ["src/app.py"],
                "verification_command": "pytest -q",
                "verification_result": "passed: 1 passed",
                "submitted_at": "2026-05-01T00:00:00Z",
                "review": {
                    "verdict": "approve",
                    "scope_checked": ["src/app.py"],
                    "problems": [],
                    "required_rework": [],
                    "acceptance_basis": ["verification passed freshly"],
                },
                "reviewed_at": "2026-05-01T00:01:00Z",
                "owner": "watcher",
                "next_action": "complete",
                "cleanup_required": True,
                "mode": "loop",
                "loop": {
                    "enabled": True,
                    "iteration": 3,
                    "max_iterations": 3,
                    "stop_on_convergence": False,
                    "converged": False,
                    "stop_reason": "max_iterations",
                },
                "plan_path": "docs/plan.md",
                "spec_path": "docs/spec.md",
                "updated_at": "2026-05-01T00:01:00Z",
            }
            state.update(self.completion_certification(state))
            state["loop"]["stop_reason"] = "converged"
            (run_root / "state.json").write_text(json.dumps(state), encoding="utf-8")
            (run_root / "trace.md").write_text(
                "- 2026-05-01T00:00:00Z worker submit: claim=Updated parser handling.\n"
                "- 2026-05-01T00:01:00Z watcher review: approve; scope_checked=src/app.py\n"
                "- 2026-05-01T00:02:00Z watcher complete\n",
                encoding="utf-8",
            )

            report = validate_completion(run_root)

            self.assertFalse(report["passed"])
            self.assertIn("completion_certification_cleanup_ready_state_hash_matches", {item["name"] for item in report["failures"]})

    def test_completion_validator_accepts_ready_for_cleanup_from_authoritative_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            state = {
                "goal": "Fix it.",
                "success_criteria": ["It works."],
                "status": "ready_for_cleanup",
                "task_id": "task-001",
                "task_title": "Fix parser handling",
                "task_inputs": {"task_id": "task-001", "task_title": "Fix parser handling"},
                "worker_claim": "Updated parser handling.",
                "files_changed": ["src/app.py"],
                "verification_command": "pytest -q",
                "verification_result": "passed: 1 passed",
                "submitted_at": "2026-05-01T00:00:00Z",
                "review": {
                    "verdict": "approve",
                    "scope_checked": ["src/app.py"],
                    "problems": [],
                    "required_rework": [],
                    "acceptance_basis": ["verification passed freshly"],
                },
                "reviewed_at": "2026-05-01T00:01:00Z",
                "owner": "watcher",
                "next_action": "complete",
                "cleanup_required": True,
                "plan_path": "docs/plan.md",
                "spec_path": "docs/spec.md",
                "updated_at": "2026-05-01T00:01:00Z",
            }
            state.update(self.completion_certification(state))
            (run_root / "state.json").write_text(
                json.dumps(state),
                encoding="utf-8",
            )
            (run_root / "trace.md").write_text(
                "- 2026-05-01T00:00:00Z worker submit: claim=Updated parser handling.\n"
                "- 2026-05-01T00:01:00Z watcher review: approve; scope_checked=src/app.py\n"
                "- 2026-05-01T00:02:00Z watcher complete\n",
                encoding="utf-8",
            )
            report = validate_completion(run_root)
            self.assertTrue(report["passed"])
            self.assertEqual(report["warnings"], [])


if __name__ == "__main__":
    unittest.main()

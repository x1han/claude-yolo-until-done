from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPORT_WORKER_IO_PATH = SKILL_ROOT / "workflow" / "report_worker_io.py"


class ReportWorkerIoCliTest(unittest.TestCase):
    def write_run_state(self, run_root: Path, **overrides: object) -> None:
        state = {
            "status": "active",
            "owner": "worker",
            "next_action": "worker_update",
            "requested_role": "worker",
            "task_id": "task-001",
            "gate_id": "gate-task-001",
            "state_version": 2,
            "dispatch_status": "running",
            "dispatch_generation": 3,
            "dispatch_intent": {"role": "worker", "action": "worker_update"},
            "dispatch_claim": {
                "owner": "worker:gate-task-001:3",
                "claimed_at": "2026-05-10T00:00:00+00:00",
                "lease_expires_at": "2026-05-10T00:02:00+00:00",
            },
            "last_dispatch": {
                "role": "worker",
                "task_id": "task-001",
                "gate_id": "gate-task-001",
                "next_action": "worker_update",
                "dispatched_at": "2026-05-10T00:00:00+00:00",
                "task_packet": {"task_id": "task-001"},
            },
            "supervision": {
                "last_token_io_at": "",
                "last_progress_at": "",
                "stall_timeout_seconds": 600,
                "retry_limit": 3,
                "retry_count": 0,
                "last_recovery_at": "",
                "last_recovery_reason": "",
            },
        }
        state.update(overrides)
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "state.json").write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    def load_state(self, run_root: Path) -> dict:
        return json.loads((run_root / "state.json").read_text(encoding="utf-8"))

    def test_report_token_io_updates_supervision_for_current_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(run_root)
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_WORKER_IO_PATH),
                    "--run-root",
                    str(run_root),
                    "--event",
                    "token_io",
                    "--dispatch-owner",
                    "worker:gate-task-001:3",
                    "--expected-version",
                    "2",
                ],
                cwd=SKILL_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            state = self.load_state(run_root)
            self.assertTrue(state["supervision"]["last_token_io_at"])
            self.assertEqual(state["state_version"], 3)

    def test_report_token_io_rejects_stale_dispatch_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / ".yolo"
            self.write_run_state(run_root)
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_WORKER_IO_PATH),
                    "--run-root",
                    str(run_root),
                    "--event",
                    "token_io",
                    "--dispatch-owner",
                    "worker:gate-task-001:2",
                    "--expected-version",
                    "2",
                ],
                cwd=SKILL_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("current dispatch owner", result.stderr)


if __name__ == "__main__":
    unittest.main()

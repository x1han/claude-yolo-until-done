from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = SKILL_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from gate_03 import run as run_gate_03


class Gate03StructuredEvidenceTest(unittest.TestCase):
    def test_stage_03_accepts_failed_status_with_detail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / "acceptance").mkdir()
            (run_root / "runtime_context.json").write_text("{}", encoding="utf-8")
            (run_root / "gates.json").write_text(json.dumps({"gates": []}), encoding="utf-8")
            (run_root / "checkoffs.json").write_text(json.dumps({"checkoffs": []}), encoding="utf-8")
            (run_root / "resume.md").write_text("# Resume\n", encoding="utf-8")
            (run_root / "report.md").write_text(
                "## Verification\n- Before status: failed\n- After status: passed\n- Passed: true\nfixed it\nfixture\n",
                encoding="utf-8",
            )
            (run_root / "acceptance" / "task-01.step-01.json").write_text(
                json.dumps({"watcher_decision": "approved", "approved_at": "2026-05-01T00:00:00+00:00"}),
                encoding="utf-8",
            )
            (run_root / "run_state.json").write_text(
                json.dumps(
                    {
                        "current_stage": "stage-03",
                        "current_target": "fixture",
                        "current_task_id": "task-01",
                        "current_step_id": "step-01",
                        "pending_acceptance_path": str(run_root / "acceptance" / "task-01.step-01.json"),
                        "verification_target": "python -m unittest tests.test_gate_03_structured_evidence -v",
                        "repair_summary": "fixed it",
                        "verification_commands": ["python -m unittest tests.test_gate_03_structured_evidence -v"],
                        "verification_before_status": "failed: AssertionError",
                        "verification_after_status": "passed",
                        "verification_passed": True,
                        "verification_evidence_updated_at": "2026-05-01T00:00:00+00:00",
                        "latest_watcher_decision": "approved",
                        "step_status": "approved",
                    }
                ),
                encoding="utf-8",
            )

            report = run_gate_03(run_root)

            checks = {item["name"]: item for item in report["checks"]}
            self.assertTrue(checks["verification_before_status_recorded"]["passed"])
            self.assertTrue(checks["report_mentions_verification_before_status"]["passed"])


if __name__ == "__main__":
    unittest.main()

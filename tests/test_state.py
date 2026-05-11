from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

import state as workflow_state


class StatePersistenceTest(unittest.TestCase):
    def test_write_json_keeps_original_file_when_atomic_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "state.json"
            target.write_text(json.dumps({"status": "old"}) + "\n", encoding="utf-8")
            original_write_text = Path.write_text

            def flaky_write_text(self: Path, data: str, *args: object, **kwargs: object) -> int:
                if self.parent == target.parent and self.name.startswith(target.name):
                    original_write_text(self, '{"status":"partial"', *args, **kwargs)
                    raise OSError("simulated write failure")
                return original_write_text(self, data, *args, **kwargs)

            with patch.object(Path, "write_text", new=flaky_write_text):
                with self.assertRaisesRegex(OSError, "simulated write failure"):
                    workflow_state.write_json(target, {"status": "new"})

            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"status": "old"})

    def test_transition_state_allows_only_one_same_version_transition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            workflow_state.write_state(
                run_root,
                {
                    "state_version": 1,
                    "worker_claim": "",
                    "updated_at": "",
                    "last_transition_actor": "",
                    "last_transition_id": "",
                },
            )
            barrier = threading.Barrier(2)
            original_load_state = workflow_state.load_state
            results: list[str] = []
            errors: list[Exception] = []

            def synchronized_load_state(path: Path) -> dict:
                payload = original_load_state(path)
                try:
                    barrier.wait(timeout=0.2)
                except threading.BrokenBarrierError:
                    pass
                return payload

            def runner(label: str) -> None:
                try:
                    state = workflow_state.transition_state(
                        run_root,
                        actor="worker",
                        action="submit",
                        expected_version=1,
                        apply_transition=lambda current, _timestamp: current.__setitem__("worker_claim", label),
                    )
                    results.append(state["worker_claim"])
                except Exception as error:  # pragma: no cover - exercised by assertions below
                    errors.append(error)

            with patch.object(workflow_state, "load_state", side_effect=synchronized_load_state):
                first = threading.Thread(target=runner, args=("first",))
                second = threading.Thread(target=runner, args=("second",))
                first.start()
                second.start()
                first.join()
                second.join()

            self.assertEqual(len(results), 1)
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], workflow_state.StaleStateVersionError)
            persisted = workflow_state.load_state(run_root)
            self.assertIn(persisted["worker_claim"], {"first", "second"})
            self.assertEqual(persisted["state_version"], 2)

    def test_append_trace_event_appends_without_rewriting_existing_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            trace = workflow_state.trace_path(run_root)
            trace.write_text("# trace\n", encoding="utf-8")
            original_write_text = Path.write_text

            def fail_on_full_rewrite(self: Path, data: str, *args: object, **kwargs: object) -> int:
                if self == trace and data.startswith("# trace\n"):
                    raise AssertionError("append_trace_event rewrote existing trace")
                return original_write_text(self, data, *args, **kwargs)

            with patch.object(Path, "write_text", new=fail_on_full_rewrite):
                workflow_state.append_trace_event(run_root, "worker update")

            rendered = trace.read_text(encoding="utf-8")
            self.assertIn("worker update", rendered)
            self.assertEqual(rendered.count("# trace\n"), 1)

    def test_append_trace_event_preserves_concurrent_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            trace = workflow_state.trace_path(run_root)
            trace.write_text("# trace\n", encoding="utf-8")
            barrier = threading.Barrier(2)
            original_read_text = Path.read_text
            errors: list[Exception] = []

            def synchronized_read_text(self: Path, *args: object, **kwargs: object) -> str:
                text = original_read_text(self, *args, **kwargs)
                if self == trace:
                    try:
                        barrier.wait(timeout=0.2)
                    except threading.BrokenBarrierError:
                        pass
                return text

            def runner(label: str) -> None:
                try:
                    workflow_state.append_trace_event(run_root, label)
                except Exception as error:  # pragma: no cover - exercised by assertions below
                    errors.append(error)

            with patch.object(Path, "read_text", new=synchronized_read_text):
                first = threading.Thread(target=runner, args=("first",))
                second = threading.Thread(target=runner, args=("second",))
                first.start()
                second.start()
                first.join()
                second.join()

            self.assertEqual(errors, [])
            rendered = trace.read_text(encoding="utf-8")
            self.assertIn("first", rendered)
            self.assertIn("second", rendered)
            self.assertEqual(rendered.count("first"), 1)
            self.assertEqual(rendered.count("second"), 1)


if __name__ == "__main__":
    unittest.main()

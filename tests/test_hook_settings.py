from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = SKILL_ROOT / "workflow"

import sys

if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

import hook_settings


class HookSettingsTest(unittest.TestCase):
    def test_install_hook_set_reports_changed_then_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / ".claude" / "settings.local.json"
            python_exe = Path("/usr/bin/python3")
            bridge_path = Path("/tmp/claude_hook_bridge.py")

            first = hook_settings.install_hook_set(settings_path, python_exe, bridge_path, ".yolo")
            second = hook_settings.install_hook_set(settings_path, python_exe, bridge_path, ".yolo")

            self.assertTrue(first["_hook_result"]["changed"])
            self.assertFalse(second["_hook_result"]["changed"])
            self.assertEqual(first["_hook_result"]["run_root"], ".yolo")
            self.assertEqual(second["_hook_result"]["run_root"], ".yolo")

    def test_concurrent_install_preserves_both_run_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / ".claude" / "settings.local.json"
            python_exe = Path("/usr/bin/python3")
            bridge_path = Path("/tmp/claude_hook_bridge.py")
            first_loaded = threading.Event()
            release_first = threading.Event()
            errors: list[BaseException] = []
            original_load_json = hook_settings.load_json

            def delayed_load_json(path: Path) -> dict:
                payload = original_load_json(path)
                if threading.current_thread().name == "install-a":
                    first_loaded.set()
                    release_first.wait(timeout=2)
                return payload

            def install(run_root: str) -> None:
                try:
                    hook_settings.install_hook_set(settings_path, python_exe, bridge_path, run_root)
                except BaseException as error:  # pragma: no cover - surfaced through assertion below
                    errors.append(error)

            with patch("hook_settings.load_json", side_effect=delayed_load_json):
                first = threading.Thread(target=install, name="install-a", args=(".yolo-a",))
                second = threading.Thread(target=install, name="install-b", args=(".yolo-b",))
                first.start()
                self.assertTrue(first_loaded.wait(timeout=1), "first install did not reach delayed read")
                second.start()
                time.sleep(0.2)
                release_first.set()
                first.join(timeout=2)
                second.join(timeout=2)

            self.assertEqual(errors, [])
            settings = hook_settings.load_json(settings_path)
            runs = settings["claudeYoloUntilDone"]["runs"]
            self.assertEqual(set(runs), {".yolo-a", ".yolo-b"})
            self.assertEqual(len(hook_settings.installed_hook_groups(settings, ".yolo-a")), 3)
            self.assertEqual(len(hook_settings.installed_hook_groups(settings, ".yolo-b")), 3)


if __name__ == "__main__":
    unittest.main()

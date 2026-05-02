from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]


class DocsAndTemplatesTest(unittest.TestCase):
    def test_docs_describe_lightweight_runtime_only(self) -> None:
        legacy_terms = [
            "run_state.json",
            "runtime_context.json",
            "gates.json",
            "checkoffs.json",
            "resume.md",
            "report.md",
            "--stage",
        ]
        for relative in ("README.md", "QUICKSTART.md", "SKILL.md"):
            body = (SKILL_ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("state.json", body)
            self.assertIn("trace.md", body)
            for term in legacy_terms:
                self.assertNotIn(term, body)
            self.assertNotRegex(body, r"[A-Z]:\\")
            self.assertNotIn("powershell", body.lower())
            self.assertNotIn("codex", body.lower())

    def test_hook_template_contains_only_lifecycle_groups(self) -> None:
        payload = json.loads((SKILL_ROOT / "templates" / "claude-settings-local.example.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(payload["hooks"].keys()), ["SessionEnd", "SessionStart", "Stop"])
        self.assertEqual(payload["hooks"]["SessionStart"][0]["metadata"]["workflow"], "claude-yolo-until-done")
        self.assertIn("<python>", payload["hooks"]["SessionStart"][0]["hooks"][0]["command"])
        self.assertNotRegex(json.dumps(payload), re.compile(r"[A-Z]:\\"))

    def test_legacy_heavy_runtime_files_are_removed(self) -> None:
        legacy_paths = [
            SKILL_ROOT / "hooks" / "gate_01.py",
            SKILL_ROOT / "hooks" / "gate_02.py",
            SKILL_ROOT / "hooks" / "gate_03.py",
            SKILL_ROOT / "hooks" / "gate_04.py",
            SKILL_ROOT / "hooks" / "gate_05.py",
            SKILL_ROOT / "templates" / "runtime-context-template.json",
            SKILL_ROOT / "templates" / "run-state-template.json",
            SKILL_ROOT / "templates" / "gates-template.json",
            SKILL_ROOT / "templates" / "checkoffs-template.json",
            SKILL_ROOT / "templates" / "report-template.md",
            SKILL_ROOT / "templates" / "resume-template.md",
            SKILL_ROOT / "templates" / "workflow-manifest-template.json",
            SKILL_ROOT / "tests" / "test_gate_03_structured_evidence.py",
        ]
        for path in legacy_paths:
            self.assertFalse(path.exists(), str(path))


if __name__ == "__main__":
    unittest.main()

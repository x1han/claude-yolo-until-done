from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]


class DocsAndTemplatesTest(unittest.TestCase):
    def test_agent_role_files_define_minimal_constraints(self) -> None:
        cases = {
            ".claude/agents/worker.md": [
                "supplied task packet",
                "Do not give final approval.",
            ],
            ".claude/agents/helper.md": [
                "supplied task packet",
                "Do not give final approval.",
            ],
            ".claude/agents/watcher.md": [
                "independent review",
                "checklist",
                "verification evidence",
            ],
        }
        for relative, required_strings in cases.items():
            body = (SKILL_ROOT / relative).read_text(encoding="utf-8")
            for required in required_strings:
                self.assertIn(required, body, f"{relative}: missing {required!r}")

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

    def test_docs_describe_preflight_and_prompt_gate(self) -> None:
        readme = (SKILL_ROOT / "README.md").read_text(encoding="utf-8")
        quickstart = (SKILL_ROOT / "QUICKSTART.md").read_text(encoding="utf-8")
        contract = (SKILL_ROOT / "policy" / "hook-contract.md").read_text(encoding="utf-8")
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        runtime = (SKILL_ROOT / "policy" / "required-runtime.md").read_text(encoding="utf-8")
        self.assertIn("preflight", skill)
        self.assertIn("preflight", quickstart)
        self.assertNotIn("0号", skill)
        self.assertNotIn("0号", quickstart)
        self.assertIn("UserPromptSubmit", readme)
        self.assertIn("complete", readme)
        self.assertNotIn("SessionEnd", quickstart)
        self.assertIn("SessionEnd is disabled", contract)
        self.assertIn("claude -p", readme)
        self.assertIn("claude -p", quickstart)
        self.assertIn("claude -p", skill)
        self.assertIn("claude -p", runtime)

    def test_docs_describe_simple_superpowers_then_yolo_usage(self) -> None:
        readme = (SKILL_ROOT / "README.md").read_text(encoding="utf-8")
        quickstart = (SKILL_ROOT / "QUICKSTART.md").read_text(encoding="utf-8")
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        required_inputs = (SKILL_ROOT / "policy" / "required-inputs.md").read_text(encoding="utf-8")
        self.assertIn("superpowers", readme)
        self.assertIn("tell Claude Code to use `claude-yolo-until-done` to execute the approved plan", readme)
        self.assertIn("output folder", readme)
        self.assertIn("defaults to the current working directory", readme)
        self.assertIn("`.yolo/` lives inside that output folder and is the default run-root model", readme)
        self.assertIn("If the approved plan and spec exist but the run root does not yet exist", skill)
        self.assertIn("bootstrap.py", skill)
        self.assertIn("Only a continue-run path should fail closed for missing durable state", skill)
        self.assertIn("same-run claude-yolo hook groups", skill)
        self.assertIn("classify the run as new-run or continue-run", quickstart)
        self.assertIn("install the current local claude-yolo hook set", quickstart)
        self.assertIn("## New run", required_inputs)
        self.assertIn("## Continue run", required_inputs)
        self.assertNotIn("Before the workflow starts, all of the following must exist and be current", required_inputs)
        self.assertNotIn("executing-plans", skill)
        self.assertNotIn("subagent-driven-development", skill)
        self.assertNotIn("executing-plans", quickstart)
        self.assertNotIn("subagent-driven-development", quickstart)

    def test_hook_template_contains_only_lifecycle_groups(self) -> None:
        payload = json.loads((SKILL_ROOT / "templates" / "claude-settings-local.example.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(payload["hooks"].keys()), ["SessionStart", "Stop", "UserPromptSubmit"])
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

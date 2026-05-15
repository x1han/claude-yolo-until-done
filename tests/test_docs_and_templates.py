from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]


class DocsAndTemplatesTest(unittest.TestCase):
    def test_agent_role_files_define_minimal_constraints(self) -> None:
        cases = {
            "agents/worker.md": [
                "supplied task packet",
                "Do not give final approval.",
                "execute the complete approved spec/plan",
                "do not pre-plan future loop iterations",
            ],
            "agents/helper.md": [
                "supplied task packet",
                "Do not give final approval.",
            ],
            "agents/watcher.md": [
                "independent review",
                "checklist",
                "verification evidence",
                "same complete approved spec/plan",
                "preplanned loop slice",
            ],
            "agents/muse.md": [
                "Muse",
                "right-brain",
                "1-3 adjacent but divergent possibilities",
                "shared planning docs",
                "one key question",
                "recommended answer",
                "consensus candidates",
                "joint uncertainty",
                "Do not write final spec or plan.",
            ],
            "agents/logos.md": [
                "Logos",
                "left-brain",
                "logical spec/plan architect",
                "shared planning docs",
                "spec",
                "plan",
                "Do not write unconfirmed assumptions as final conclusions.",
                "logos-converger",
                "logos-spec-writer",
                "logos-spec-reviewer",
                "logos-plan-writer",
                "Do not mark spec or plan approved without human approval.",
            ],
        }
        for required_strings in cases.values():
            required_strings.extend([
                "memory: project",
                "project memory",
                "MEMORY.md",
                "role log",
            ])
        for relative, required_strings in cases.items():
            body = (SKILL_ROOT / relative).read_text(encoding="utf-8")
            for required in required_strings:
                self.assertIn(required, body, f"{relative}: missing {required!r}")

    def test_role_agent_project_memory_is_local_runtime_state(self) -> None:
        self.assertFalse((SKILL_ROOT / ".claude" / "agent-memory").exists())

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

    def test_docs_describe_loop_mode_usage_and_stop_policy(self) -> None:
        readme = (SKILL_ROOT / "README.md").read_text(encoding="utf-8")
        quickstart = (SKILL_ROOT / "QUICKSTART.md").read_text(encoding="utf-8")
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        required_inputs = (SKILL_ROOT / "policy" / "required-inputs.md").read_text(encoding="utf-8")
        run_state = (SKILL_ROOT / "policy" / "run-state-contract.md").read_text(encoding="utf-8")
        for body in (readme, quickstart):
            self.assertIn("--mode loop", body)
            self.assertIn("--loop-max-iterations", body)
            self.assertIn("--loop-stop-on-convergence", body)
            self.assertIn("A+B", body)
            self.assertIn("either stop condition", body)
            self.assertIn("continue-run", body)
            self.assertIn("mode/config", body)
        for body in (skill, required_inputs):
            self.assertIn("--mode loop", body)
            self.assertIn("--loop-max-iterations", body)
            self.assertIn("--loop-stop-on-convergence", body)
            self.assertIn("A+B", body)
            self.assertIn("either stop condition", body)
            self.assertIn("mode/config", body)
        for body in (readme, quickstart, skill, run_state):
            self.assertIn("repeat the same complete approved spec/plan", body)
            self.assertIn("fixed loop N means N complete acyclic executions", body)
            self.assertIn("default max 10", body)
            self.assertIn("do not pre-plan future loop iterations", body)

    def test_docs_describe_persistent_role_agent_sessions(self) -> None:
        readme = (SKILL_ROOT / "README.md").read_text(encoding="utf-8")
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        contract = (SKILL_ROOT / "policy" / "run-state-contract.md").read_text(encoding="utf-8")

        for body in (readme, skill, contract):
            self.assertIn("agent_sessions.json", body)
            self.assertIn("role lab notebook", body)
            self.assertIn("per `.yolo/` run", body)
            self.assertIn("project memory", body)
            self.assertIn("role_invocation_id", body)
            self.assertIn("last_runtime_agent_id", body)
            self.assertIn("fresh Agent subagent", body)
            self.assertIn("Continuity comes from project memory", body)
            self.assertIn("state.json", body)
            self.assertIn("remains authoritative", body)
            self.assertIn("Replacement is explicit only", body)
        self.assertNotIn("resume_by_agent_id", readme)

    def test_docs_describe_grill_first_then_yolo_usage(self) -> None:
        readme = (SKILL_ROOT / "README.md").read_text(encoding="utf-8")
        quickstart = (SKILL_ROOT / "QUICKSTART.md").read_text(encoding="utf-8")
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        required_inputs = (SKILL_ROOT / "policy" / "required-inputs.md").read_text(encoding="utf-8")
        self.assertIn("first-party `skills/grill-storm`", readme)
        self.assertIn("tell Claude Code to use `claude-yolo-until-done` to execute approved plan", readme)
        self.assertIn("output folder", readme)
        self.assertIn("defaults to current working directory", readme)
        self.assertIn("`.yolo/` lives inside output folder and is default run-root model", readme)
        self.assertIn("Muse", skill)
        self.assertIn("Logos", skill)
        self.assertIn("run root does not yet exist", skill)
        self.assertIn("bootstrap.py", skill)
        self.assertIn("Only continue-run path should fail closed for missing durable state", skill)
        self.assertIn("same-run claude-yolo hook groups", skill)
        self.assertIn("init_grill_docs.py", quickstart)
        self.assertIn("workflow/preflight.py", quickstart)
        self.assertNotIn("workflow/bootstrap.py", quickstart)
        self.assertIn("classify run as new-run or continue-run", quickstart)
        self.assertIn("install current local claude-yolo hook set", quickstart)
        self.assertIn("## New run", required_inputs)
        self.assertIn("## Continue run", required_inputs)
        self.assertIn("docs/spec.md", required_inputs)
        self.assertIn("docs/plan.md", required_inputs)
        self.assertNotIn("docs/claude-yolo/spec.md", required_inputs)
        self.assertNotIn("docs/claude-yolo/plan.md", required_inputs)
        self.assertNotIn("docs/superpowers/specs/", required_inputs)
        self.assertNotIn("docs/superpowers/plans/", required_inputs)
        self.assertNotIn("`superpowers` is mandatory", skill)
        self.assertNotIn("executing-plans", skill)
        self.assertNotIn("subagent-driven-development", skill)
        self.assertNotIn("executing-plans", quickstart)
        self.assertNotIn("subagent-driven-development", quickstart)

    def test_repo_keeps_mutable_planning_docs_out_of_shipped_tree(self) -> None:
        mutable_paths = [
            "docs/intent.md",
            "docs/open-questions.md",
            "docs/decisions.md",
            "docs/spec.md",
            "docs/plan.md",
            "docs/superpowers/specs",
            "docs/superpowers/plans",
        ]
        for relative in mutable_paths:
            self.assertFalse((SKILL_ROOT / relative).exists(), relative)

    def test_grill_storm_skill_is_project_owned(self) -> None:
        grill_skill = (SKILL_ROOT / "skills" / "grill-storm" / "SKILL.md").read_text(encoding="utf-8")
        root_skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        required_authoring = (SKILL_ROOT / "policy" / "required-authoring.md").read_text(encoding="utf-8")

        self.assertIn("name: grill-storm", grill_skill)
        self.assertIn("workflow/grill_storm_loop.py", grill_skill)
        self.assertIn("workflow/validate_grill_docs.py", grill_skill)
        self.assertIn("Muse", grill_skill)
        self.assertIn("Logos", grill_skill)
        self.assertIn("human-approved spec", grill_skill)
        self.assertIn("human-approved plan", grill_skill)
        self.assertIn("workflow/grill_storm_loop.py", root_skill)
        self.assertIn("human_dialogue", root_skill)
        self.assertIn("docs mailbox", required_authoring)

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

from __future__ import annotations

import json
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class JiraActionSkillTests(unittest.TestCase):
    def test_manifest_registers_new_write_capable_skills_for_both_agents(self) -> None:
        manifest = json.loads((PACKAGE_ROOT / "Skills~" / "manifest.json").read_text(encoding="utf-8"))
        by_name = {skill["name"]: skill for skill in manifest["skills"]}

        for name in ("jira-plan", "jira-auto-start"):
            self.assertEqual("write-capable", by_name[name]["access"])
            self.assertEqual({"codex", "claude"}, set(by_name[name]["agents"]))
            self.assertTrue(by_name[name]["includeShared"])

    def test_auto_start_classifies_all_todo_and_handles_planning_lock(self) -> None:
        for agent, helper in (("Codex", ".agents"), ("Claude", ".claude")):
            contents = self._read_skill(agent, "jira-auto-start")

            self.assertIn(
                f"python3 {helper}/skills/jira-auto-start/scripts/ai_jira_cli.py list --state todo --format json",
                contents,
            )
            self.assertIn(
                f"python3 {helper}/skills/jira-auto-start/scripts/ai_jira_cli.py list --state progress --format json",
                contents,
            )
            self.assertNotIn("list --state all", contents)
            self.assertIn("exactly one", contents)
            self.assertIn("first startable", contents.lower())
            self.assertIn("needs-plan", contents)
            self.assertIn("blocked", contents)
            self.assertIn("approval-required", contents)
            self.assertIn("descriptionContract", contents)
            self.assertIn("planning lock", contents.lower())
            self.assertIn("replace-plan", contents)
            self.assertIn("expected-updated", contents)
            self.assertIn("configuredStatuses.done", contents)
            self.assertIn("every todo", contents)
            self.assertIn("prerequisite", contents.lower())
            self.assertIn("transition", contents.lower())
            self.assertIn("pull request", contents.lower())

    def test_plan_requires_full_draft_approval_and_stops_before_implementation(self) -> None:
        for agent in ("Codex", "Claude"):
            contents = self._read_skill(agent, "jira-plan")

            self.assertIn("## QA 확인 필요 사항", contents)
            self.assertIn("## Auto Start", contents)
            self.assertIn("## Goal", contents)
            self.assertIn("## Completion Criteria", contents)
            self.assertIn("## Validation Plan", contents)
            self.assertIn("Korean", contents)
            self.assertIn("English", contents)
            self.assertIn("explicit", contents.lower())
            self.assertIn("Tools/AI/jira/create_issue.py", contents)
            self.assertIn("--description-file", contents)
            self.assertIn("replace-plan", contents)
            self.assertIn("planning lock", contents.lower())
            self.assertIn("Leave the issue in todo", contents)
            self.assertIn("do not implement", contents.lower())

    def test_run_skills_require_verified_qa_and_pr_for_done(self) -> None:
        for agent in ("Codex", "Claude"):
            contents = self._read_skill(agent, "jira-run")

            self.assertIn("descriptionContract", contents)
            self.assertIn("replace-plan", contents)
            self.assertIn("planning lock", contents.lower())
            self.assertIn("QA", contents)
            self.assertIn("PR URL", contents)

    def test_codex_write_skills_disable_implicit_invocation(self) -> None:
        for name in ("jira-plan", "jira-auto-start", "jira-run"):
            path = PACKAGE_ROOT / "Skills~" / "Codex" / name / "agents" / "openai.yaml"
            metadata = path.read_text(encoding="utf-8")

            self.assertIn("allow_implicit_invocation: false", metadata)

    def test_claude_write_skills_disable_model_invocation(self) -> None:
        for name in ("jira-plan", "jira-auto-start", "jira-run"):
            contents = self._read_skill("Claude", name)
            self.assertIn("disable-model-invocation: true", contents)

    @staticmethod
    def _read_skill(agent: str, name: str) -> str:
        path = PACKAGE_ROOT / "Skills~" / agent / name / "SKILL.md"
        return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

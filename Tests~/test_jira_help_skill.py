from __future__ import annotations

import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class JiraHelpSkillTests(unittest.TestCase):
    def test_codex_help_documents_package_skills_and_command_safety(self) -> None:
        contents = self._read_skill("Codex")

        self.assertIn("`com.actionfit.ai-jira`", contents)
        self.assertIn("`jira-help`", contents)
        self.assertIn("`jira-todo`", contents)
        self.assertIn("`jira-run`", contents)
        self.assertIn("$jira-help", contents)
        self.assertIn("$jira-todo", contents)
        self.assertIn("$jira-run MCC-1234", contents)
        self.assertIn(".agents/skills/jira-help/scripts/ai_jira_cli.py", contents)
        self.assertIn("list --state todo", contents)
        self.assertIn("list --state progress", contents)
        self.assertIn("list --state all", contents)
        self.assertIn("detail MCC-1234", contents)
        self.assertIn("create_issue.py", contents)
        self.assertIn("update_description.py", contents)
        self.assertIn("transition_issue.py", contents)
        self.assertIn("Do not query Jira", contents)
        self.assertNotIn("TODO", contents)

    def test_claude_help_uses_claude_local_helper_and_same_command_families(self) -> None:
        contents = self._read_skill("Claude")

        self.assertIn("`com.actionfit.ai-jira`", contents)
        self.assertIn("$jira-help", contents)
        self.assertIn("$jira-todo", contents)
        self.assertIn("$jira-run MCC-1234", contents)
        self.assertIn(".claude/skills/jira-help/scripts/ai_jira_cli.py", contents)
        self.assertIn("list --state todo", contents)
        self.assertIn("list --state progress", contents)
        self.assertIn("detail MCC-1234", contents)
        self.assertIn("create_issue.py", contents)
        self.assertIn("update_description.py", contents)
        self.assertIn("transition_issue.py", contents)
        self.assertIn("Do not query Jira", contents)
        self.assertNotIn("TODO", contents)

    @staticmethod
    def _read_skill(agent: str) -> str:
        path = PACKAGE_ROOT / "Skills~" / agent / "jira-help" / "SKILL.md"
        return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

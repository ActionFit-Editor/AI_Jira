from __future__ import annotations

import json
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class JiraHelpSkillTests(unittest.TestCase):
    def test_codex_help_reads_generated_inventory_and_documents_command_safety(self) -> None:
        contents = self._read_skill("Codex")

        self.assertIn("`PACKAGE_SKILLS.md`", contents)
        self.assertIn("complete related-skill list", contents)
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

        self.assertIn("`PACKAGE_SKILLS.md`", contents)
        self.assertIn("complete related-skill list", contents)
        self.assertIn(".claude/skills/jira-help/scripts/ai_jira_cli.py", contents)
        self.assertIn("list --state todo", contents)
        self.assertIn("list --state progress", contents)
        self.assertIn("detail MCC-1234", contents)
        self.assertIn("create_issue.py", contents)
        self.assertIn("update_description.py", contents)
        self.assertIn("transition_issue.py", contents)
        self.assertIn("Do not query Jira", contents)
        self.assertNotIn("TODO", contents)

    def test_schema_v2_manifest_declares_help_prefix_and_access(self) -> None:
        manifest = json.loads((PACKAGE_ROOT / "Skills~" / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(2, manifest["schemaVersion"])
        self.assertEqual("jira", manifest["skillPrefix"])
        self.assertEqual("jira-help", manifest["helpSkill"])
        by_name = {skill["name"]: skill for skill in manifest["skills"]}
        self.assertEqual("read-only", by_name["jira-help"]["access"])
        self.assertEqual("read-only", by_name["jira-todo"]["access"])
        self.assertEqual("write-capable", by_name["jira-run"]["access"])
        self.assertEqual({"codex", "claude"}, set(by_name["jira-help"]["agents"]))

    @staticmethod
    def _read_skill(agent: str) -> str:
        path = PACKAGE_ROOT / "Skills~" / agent / "jira-help" / "SKILL.md"
        return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

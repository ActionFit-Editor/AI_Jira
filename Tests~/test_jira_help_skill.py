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
        self.assertIn("overlap --format json", contents)
        self.assertIn("every assignee", contents)
        self.assertIn("todo, progress, and done", contents)
        self.assertIn("never feeds task recommendation", contents)
        self.assertIn("detail MCC-1234", contents)
        self.assertIn("ai_jira_write_cli.py", contents)
        self.assertIn("create", contents)
        self.assertIn("--title-only-needs-plan", contents)
        self.assertIn("explicit exact-title", contents)
        self.assertIn("update-description", contents)
        self.assertIn("replace-plan", contents)
        self.assertIn("expected-updated", contents)
        self.assertIn("transition", contents)
        self.assertIn("finalize", contents)
        self.assertIn("start", contents)
        self.assertIn("--coverage-file", contents)
        self.assertIn("--review-file", contents)
        self.assertIn("completion-baseline-gate.md", contents)
        self.assertIn("--outcome incomplete", contents)
        self.assertIn("allow_description_append", contents)
        self.assertIn("--to todo", contents)
        self.assertIn("--pr-url", contents)
        self.assertIn("complete planning approval views in Korean", contents)
        self.assertIn("exact mixed-language storage draft", contents)
        self.assertIn("never a back-translation", contents)
        self.assertIn("lost canonical state", contents)
        self.assertIn("one-to-three-question rounds", contents)
        self.assertIn("current planning invocation", contents)
        self.assertIn("difference, advantages, and disadvantages", contents)
        self.assertIn("Do not query Jira", contents)
        self.assertNotIn("TODO", contents)

    def test_claude_help_uses_claude_local_helper_and_same_command_families(self) -> None:
        contents = self._read_skill("Claude")

        self.assertIn("`PACKAGE_SKILLS.md`", contents)
        self.assertIn("complete related-skill list", contents)
        self.assertIn(".claude/skills/jira-help/scripts/ai_jira_cli.py", contents)
        self.assertIn("list --state todo", contents)
        self.assertIn("list --state progress", contents)
        self.assertIn("overlap --format json", contents)
        self.assertIn("every assignee", contents)
        self.assertIn("todo, progress, and done", contents)
        self.assertIn("never feeds task recommendation", contents)
        self.assertIn("detail MCC-1234", contents)
        self.assertIn("ai_jira_write_cli.py", contents)
        self.assertIn("create", contents)
        self.assertIn("--title-only-needs-plan", contents)
        self.assertIn("explicit exact-title", contents)
        self.assertIn("update-description", contents)
        self.assertIn("replace-plan", contents)
        self.assertIn("expected-updated", contents)
        self.assertIn("transition", contents)
        self.assertIn("finalize", contents)
        self.assertIn("start", contents)
        self.assertIn("--coverage-file", contents)
        self.assertIn("--review-file", contents)
        self.assertIn("completion-baseline-gate.md", contents)
        self.assertIn("--outcome incomplete", contents)
        self.assertIn("allow_description_append", contents)
        self.assertIn("--to todo", contents)
        self.assertIn("--pr-url", contents)
        self.assertIn("complete approval views in Korean", contents)
        self.assertIn("exact pre-preview mixed-language storage draft", contents)
        self.assertIn("never a back-translation", contents)
        self.assertIn("lost canonical state", contents)
        self.assertIn("one-to-three-question rounds", contents)
        self.assertIn("current planning invocation", contents)
        self.assertIn("difference, advantages, and disadvantages", contents)
        self.assertIn("Do not query Jira", contents)
        self.assertNotIn("TODO", contents)

    def test_schema_v2_manifest_declares_help_prefix_and_access(self) -> None:
        manifest = json.loads((PACKAGE_ROOT / "Skills~" / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(2, manifest["schemaVersion"])
        self.assertEqual("jira", manifest["skillPrefix"])
        self.assertEqual("jira-help", manifest["helpSkill"])
        by_name = {skill["name"]: skill for skill in manifest["skills"]}
        self.assertEqual("read-only", by_name["jira-help"]["access"])
        self.assertEqual("write-capable", by_name["jira-setup"]["access"])
        self.assertEqual("read-only", by_name["jira-todo"]["access"])
        self.assertEqual("write-capable", by_name["jira-run"]["access"])
        self.assertEqual({"codex", "claude"}, set(by_name["jira-help"]["agents"]))
        self.assertEqual({"codex", "claude"}, set(by_name["jira-setup"]["agents"]))

    def test_setup_skill_is_secret_free_explicit_and_read_only_against_jira(self) -> None:
        for agent in ("Codex", "Claude"):
            path = PACKAGE_ROOT / "Skills~" / agent / "jira-setup" / "SKILL.md"
            contents = path.read_text(encoding="utf-8")

            self.assertIn("JIRA_EMAIL", contents)
            self.assertIn("JIRA_API_TOKEN", contents)
            self.assertIn("automation.dry_run: true", contents)
            self.assertIn("keep every `allow_*` write gate false", contents)
            self.assertIn("Never request a token in chat", contents)
            self.assertIn("list --state todo --format json", contents)
            self.assertNotIn("TODO", contents)

        codex_metadata = (
            PACKAGE_ROOT / "Skills~" / "Codex" / "jira-setup" / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("allow_implicit_invocation: true", codex_metadata)

    @staticmethod
    def _read_skill(agent: str) -> str:
        path = PACKAGE_ROOT / "Skills~" / agent / "jira-help" / "SKILL.md"
        return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

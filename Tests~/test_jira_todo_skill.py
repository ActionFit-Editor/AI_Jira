from __future__ import annotations

import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class JiraTodoSkillTests(unittest.TestCase):
    def test_codex_queries_todo_candidates_and_progress_exclusions_separately(self) -> None:
        contents = self._read_skill("Codex")

        self.assertIn(
            "python3 .agents/skills/jira-todo/scripts/ai_jira_cli.py list --state todo --format json",
            contents,
        )
        self.assertIn(
            "python3 .agents/skills/jira-todo/scripts/ai_jira_cli.py list --state progress --format json",
            contents,
        )
        self.assertIn("Only issues returned by the `todo` query may appear as actionable", contents)
        self.assertIn("it is not a reason to recommend continuing that issue", contents)
        self.assertIn("`active`", contents)
        self.assertIn("`reserved`", contents)
        self.assertIn("`stranded-review`", contents)
        self.assertIn("PID liveness", contents)
        self.assertIn("Never expire, release, steal", contents)
        self.assertNotIn("list --state all", contents)

    def test_claude_queries_todo_candidates_and_progress_exclusions_separately(self) -> None:
        contents = self._read_skill("Claude")

        self.assertIn(
            "python3 .claude/skills/jira-todo/scripts/ai_jira_cli.py list --state todo --format json",
            contents,
        )
        self.assertIn(
            "python3 .claude/skills/jira-todo/scripts/ai_jira_cli.py list --state progress --format json",
            contents,
        )
        self.assertIn("Only todo-query issues may be recommended as new work", contents)
        self.assertIn("never reasons to recommend continuing", contents)
        self.assertIn("`active`", contents)
        self.assertIn("`reserved`", contents)
        self.assertIn("`stranded-review`", contents)
        self.assertIn("PID liveness", contents)
        self.assertIn("expire, release, steal", contents)
        self.assertNotIn("list --state all", contents)

    @staticmethod
    def _read_skill(agent: str) -> str:
        path = PACKAGE_ROOT / "Skills~" / agent / "jira-todo" / "SKILL.md"
        return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

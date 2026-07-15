from __future__ import annotations

import sys
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parents[1]
PROJECT_JIRA_DIR = REPOSITORY_ROOT / "Tools" / "AI" / "jira"
sys.path.insert(0, str(PROJECT_JIRA_DIR))

from create_issue import validate_new_description
from jira_client import automation
from transition_issue import validate_done_handoff
from update_description import append_requirements, require_mode_gate


class ProjectJiraWriteToolTests(unittest.TestCase):
    def test_new_issue_requires_complete_managed_description(self) -> None:
        with self.assertRaises(SystemExit):
            validate_new_description("## Goal\nIncomplete")

        from test_jira_description import managed_description

        validate_new_description(managed_description())

    def test_plan_refinement_gate_defaults_to_false(self) -> None:
        self.assertFalse(automation({})["allow_description_plan_refinement"])

    def test_additional_requirements_use_english_managed_heading(self) -> None:
        updated = append_requirements("## Goal\nExisting goal", "- Keep the current behavior.")

        self.assertIn("## Additional Requirements", updated)
        self.assertNotIn("## 추가 요구사항", updated)

    def test_each_description_mode_requires_its_specific_gate(self) -> None:
        with self.assertRaises(SystemExit):
            require_mode_gate({"allow_description_append": True}, "replace-plan")

        require_mode_gate(
            {"allow_description_plan_refinement": True},
            "replace-plan",
        )

    def test_done_handoff_requires_pr_and_issue_qa_record(self) -> None:
        issue = {
            "fields": {
                "status": {"name": "개발 진행 중"},
                "description": """## QA 확인 필요 사항

### 2026-07-15 / MCC-1490
- 변경 요약: 완료

---

### 계획
- 확인 항목:

---

## Goal
Done
""",
            }
        }

        validate_done_handoff(
            "MCC-1490",
            issue,
            "개발 진행 중",
            "https://github.com/ActionFit/Cat_Merge_Cafe/pull/1234",
        )

        with self.assertRaises(SystemExit):
            validate_done_handoff("MCC-1490", issue, "개발 진행 중", None)
        with self.assertRaises(SystemExit):
            validate_done_handoff(
                "MCC-1491",
                issue,
                "개발 진행 중",
                "https://github.com/ActionFit/Cat_Merge_Cafe/pull/1234",
            )


if __name__ == "__main__":
    unittest.main()

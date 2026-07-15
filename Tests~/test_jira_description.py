from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "Tools~"
sys.path.insert(0, str(TOOLS_DIR))

from jira_description import (
    has_qa_completion_record,
    parse_description_contract,
    prepend_qa_record,
    replace_managed_plan,
)


def managed_description(
    *,
    allowed: str = "yes",
    prerequisites: str = "none",
    decisions: str = "none",
    qa_plan: str = "- 확인 항목:",
) -> str:
    return f"""## QA 확인 필요 사항

### 계획
{qa_plan}

---

## Auto Start
- Allowed: {allowed}
- Prerequisites: {prerequisites}
- Decisions Required: {decisions}

## Goal
Create a deterministic Jira workflow.

## Scope
- Parse the managed contract.

## Out of Scope
- Package publishing.

## Completion Criteria
- Structured details expose readiness.

## Validation Plan
- Run Python unit tests.

## Dependencies and Risks
- Existing legacy descriptions remain unchanged.
"""


class JiraDescriptionTests(unittest.TestCase):
    def test_complete_mixed_language_contract_is_ready(self) -> None:
        result = parse_description_contract(managed_description(prerequisites="MCC-1400, MCC-1401"))

        self.assertEqual("ready", result["state"])
        self.assertTrue(result["structurallyComplete"])
        self.assertTrue(result["qaAtTop"])
        self.assertEqual(["MCC-1400", "MCC-1401"], result["autoStart"]["prerequisiteKeys"])
        self.assertFalse(result["autoStart"]["hasUnresolvedDecisions"])

    def test_missing_contract_sections_need_plan(self) -> None:
        result = parse_description_contract("## QA 확인 필요 사항\n\n### 계획\n- 확인 항목:\n")

        self.assertEqual("needs-plan", result["state"])
        self.assertIn("Auto Start", result["missingSections"])
        self.assertIn("Goal", result["missingSections"])

    def test_qa_plan_subsection_is_required_once(self) -> None:
        missing = parse_description_contract(managed_description().replace("### 계획", "### 참고"))
        duplicate = parse_description_contract(
            managed_description().replace("### 계획", "### 계획\n\n### 계획")
        )

        self.assertEqual(0, missing["qaPlanCount"])
        self.assertEqual("needs-plan", missing["state"])
        self.assertEqual(2, duplicate["qaPlanCount"])
        self.assertEqual("needs-plan", duplicate["state"])

    def test_headings_inside_code_fences_do_not_satisfy_contract(self) -> None:
        description = """## QA 확인 필요 사항

### 계획
- 확인 항목:

---

## 배경
Example only:

```md
## QA 확인 필요 사항
## Auto Start
- Allowed: yes
- Prerequisites: none
- Decisions Required: none
## Goal
## Scope
## Out of Scope
## Completion Criteria
## Validation Plan
## Dependencies and Risks
```
"""

        result = parse_description_contract(description)

        self.assertEqual(1, result["qaHeadingCount"])
        self.assertEqual("needs-plan", result["state"])
        self.assertIn("Auto Start", result["missingSections"])

    def test_explicit_disallow_is_blocked(self) -> None:
        result = parse_description_contract(managed_description(allowed="no"))

        self.assertEqual("blocked", result["state"])
        self.assertFalse(result["autoStart"]["allowed"])

    def test_auto_start_fields_inside_code_fence_are_ignored(self) -> None:
        description = managed_description().replace(
            "- Allowed: yes\n- Prerequisites: none\n- Decisions Required: none",
            """```md
- Allowed: yes
- Prerequisites: none
- Decisions Required: none
```""",
        )

        result = parse_description_contract(description)

        self.assertEqual("needs-plan", result["state"])
        self.assertEqual(
            ["Allowed", "Prerequisites", "Decisions Required"],
            result["autoStart"]["missingFields"],
        )

    def test_duplicate_managed_sections_and_fields_need_plan(self) -> None:
        duplicate_section = managed_description() + "\n## Goal\nDuplicate goal.\n"
        duplicate_field = managed_description().replace(
            "- Allowed: yes",
            "- Allowed: yes\n- Allowed: no",
        )

        section_result = parse_description_contract(duplicate_section)
        field_result = parse_description_contract(duplicate_field)

        self.assertEqual(["Goal"], section_result["duplicateSections"])
        self.assertEqual("needs-plan", section_result["state"])
        self.assertEqual(["Allowed"], field_result["autoStart"]["duplicateFields"])
        self.assertEqual("needs-plan", field_result["state"])

    def test_unresolved_decision_needs_plan(self) -> None:
        result = parse_description_contract(
            managed_description(decisions="Choose whether legacy issues should be migrated.")
        )

        self.assertEqual("needs-plan", result["state"])
        self.assertTrue(result["structurallyComplete"])
        self.assertTrue(result["autoStart"]["hasUnresolvedDecisions"])

    def test_ambiguous_prerequisite_needs_plan(self) -> None:
        result = parse_description_contract(managed_description(prerequisites="the package task"))

        self.assertEqual("needs-plan", result["state"])
        self.assertTrue(result["autoStart"]["ambiguousPrerequisites"])
        self.assertIn("Prerequisites", result["autoStart"]["invalidFields"])

    def test_plan_replacement_preserves_qa_history_and_unmanaged_sections(self) -> None:
        current = """## QA 확인 필요 사항

### 2026-07-14 / MCC-1490
- 변경 요약: 기존 기록

---

### 계획
- 확인 항목: 기존 계획

---

## 목표
기존 계획

## 추가 요구사항

### 2026-07-15
- 기존 추가 요구사항
"""
        approved = managed_description(qa_plan="- 확인 항목: 신규 계획")

        updated = replace_managed_plan(current, approved)

        self.assertTrue(updated.startswith("## QA 확인 필요 사항"))
        self.assertEqual(1, updated.count("## QA 확인 필요 사항"))
        self.assertIn("### 2026-07-14 / MCC-1490", updated)
        self.assertIn("- 확인 항목: 신규 계획", updated)
        self.assertIn("## Auto Start", updated)
        self.assertIn("## 추가 요구사항", updated)
        self.assertIn("기존 추가 요구사항", updated)
        self.assertNotIn("- 확인 항목: 기존 계획", updated)

    def test_plan_replacement_preserves_legacy_freeform_text(self) -> None:
        updated = replace_managed_plan(
            "Legacy operator note without a managed heading.",
            managed_description(),
        )

        self.assertIn("Legacy operator note without a managed heading.", updated)
        self.assertTrue(updated.startswith("## QA 확인 필요 사항"))

    def test_qa_prepend_is_idempotent_for_same_date_and_issue(self) -> None:
        description = managed_description(qa_plan="- 확인 항목: 회귀 테스트")

        first = prepend_qa_record(description, "MCC-1490", "2026-07-15", "- 변경 요약: 첫 기록")
        second = prepend_qa_record(first, "MCC-1490", "2026-07-15", "- 변경 요약: 갱신 기록")

        self.assertEqual(1, second.count("### 2026-07-15 / MCC-1490"))
        self.assertNotIn("첫 기록", second)
        self.assertIn("갱신 기록", second)
        self.assertIn("### 계획", second)
        self.assertTrue(has_qa_completion_record(second, "MCC-1490"))


if __name__ == "__main__":
    unittest.main()

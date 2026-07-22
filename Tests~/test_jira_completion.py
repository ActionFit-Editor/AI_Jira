from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PACKAGE_ROOT / "Tools~"
sys.path.insert(0, str(TOOLS_DIR))

from jira_completion import (
    COMPLETION_PROPERTY_KEY,
    build_active_property,
    build_planning_property,
    extract_snapshot,
    validate_completion_gate,
    validate_plan_coverage,
    with_state,
)
from jira_description import prepend_qa_record
from finalize_session import finalize_incomplete
from start_session import start_session
from transition_issue import begin_planning, complete_issue, finish_planning


def managed_description(goal: str = "Protect Jira completion.", scope: str = "Seal every requirement.") -> str:
    return f"""## QA 확인 필요 사항

### 계획
- 확인 항목: 완료 게이트

---

## Auto Start
- Allowed: yes
- Prerequisites: none
- Decisions Required: none

## Goal
{goal}

## Scope
- {scope}
- Validate exact completion evidence.

## Out of Scope
- Package publishing.

## Completion Criteria
- Missing baselines fail closed.
- Partial reviews fail closed.

## Validation Plan
- Run Python tests.

## Dependencies and Risks
- Jira issue property permissions are required.
"""


def completed_description() -> str:
    return prepend_qa_record(
        managed_description(),
        "MCC-1603",
        "2026-07-23",
        """- 변경 요약: 완료 봉인 게이트 구현
- 검증 결과: Python 테스트 통과
- 미검증 항목: 없음
- QA 확인 항목: 완료 전환 차단 확인
- 위험 영역: Jira 상태와 property 보상""",
    )


class SessionClient:
    def __init__(self, description: str, status: str = "해야 할 일") -> None:
        self.description = description
        self.status = status
        self.updated = "2026-07-23T10:00:00.000+0900"
        self.property = None
        self.property_writes = []

    def get_issue(self, issue_key: str, fields=None) -> dict:
        return {
            "key": issue_key,
            "fields": {
                "status": {"name": self.status},
                "summary": "Jira completion gate",
                "description": self.description,
                "updated": self.updated,
            },
        }

    def get_issue_property(self, issue_key: str, property_key: str):
        self.assert_property_key(property_key)
        return self.property

    def set_issue_property(self, issue_key: str, property_key: str, value: dict) -> None:
        self.assert_property_key(property_key)
        self.property = value
        self.property_writes.append(value)

    def delete_issue_property(self, issue_key: str, property_key: str) -> None:
        self.assert_property_key(property_key)
        self.property = None

    def list_transitions(self, issue_key: str) -> list[dict]:
        return [
            {"id": "10", "to": {"name": "해야 할 일"}},
            {"id": "20", "to": {"name": "개발 진행 중"}},
            {"id": "30", "to": {"name": "개발 완료"}},
        ]

    def transition_issue(self, issue_key: str, transition_id: str) -> dict:
        self.status = {"10": "해야 할 일", "20": "개발 진행 중", "30": "개발 완료"}[transition_id]
        self.updated = "2026-07-23T10:01:00.000+0900"
        return {}

    def update_description(self, issue_key: str, description: str) -> dict:
        self.description = description
        return {}

    @staticmethod
    def assert_property_key(property_key: str) -> None:
        if property_key != COMPLETION_PROPERTY_KEY:
            raise AssertionError(property_key)


class FailingOncePropertyClient(SessionClient):
    def __init__(self, description: str, status: str = "해야 할 일") -> None:
        super().__init__(description, status)
        self.failed = False

    def set_issue_property(self, issue_key: str, property_key: str, value: dict) -> None:
        super().set_issue_property(issue_key, property_key, value)
        if not self.failed:
            self.failed = True
            raise SystemExit("property read-after-write verification failed")


class JiraCompletionTests(unittest.TestCase):
    def test_snapshot_ids_and_digest_ignore_qa_history(self) -> None:
        original = managed_description()
        with_qa = prepend_qa_record(
            original,
            "MCC-1603",
            "2026-07-23",
            "- 변경 요약: QA history does not change requirements",
        )

        first = extract_snapshot(original)
        second = extract_snapshot(with_qa)

        self.assertEqual(first, second)
        self.assertTrue(all(item["id"].startswith("REQ-") for item in first["requirements"]))

    def test_start_seals_baseline_before_entering_progress(self) -> None:
        client = SessionClient(managed_description())

        result = start_session(
            client,
            "MCC-1603",
            {"todo": "해야 할 일", "progress": "개발 진행 중", "done": "개발 완료"},
            "MCC-1603-jira-completion-baseline-gate",
            session_id="session-1603",
        )

        self.assertEqual("개발 진행 중", client.status)
        self.assertEqual("active", result["state"])
        self.assertEqual("session-1603", result["sessionId"])
        self.assertGreater(len(result["baseline"]["requirements"]), 0)
        self.assertEqual(["prepared", "active"], [item["state"] for item in client.property_writes])

    def test_start_restores_property_when_preparation_verification_fails(self) -> None:
        client = FailingOncePropertyClient(managed_description())

        with self.assertRaisesRegex(SystemExit, "baseline preparation failed"):
            start_session(
                client,
                "MCC-1603",
                {"todo": "해야 할 일", "progress": "개발 진행 중", "done": "개발 완료"},
                "MCC-1603-jira-completion-baseline-gate",
                session_id="session-1603",
            )

        self.assertEqual("해야 할 일", client.status)
        self.assertIsNone(client.property)

    def test_planning_lock_captures_post_transition_updated_value(self) -> None:
        client = SessionClient("Original free-form requirement")

        planning = begin_planning(
            client,
            "MCC-1603",
            {"todo": "해야 할 일", "progress": "개발 진행 중", "done": "개발 완료"},
        )

        self.assertEqual("개발 진행 중", client.status)
        self.assertEqual("2026-07-23T10:00:00.000+0900", planning["sourceUpdated"])
        self.assertEqual("2026-07-23T10:01:00.000+0900", planning["capturedUpdated"])
        self.assertEqual(["planning", "planning"], [item["state"] for item in client.property_writes])

    def test_planning_release_restores_active_lock_when_property_close_fails(self) -> None:
        client = FailingOncePropertyClient("Original free-form requirement", status="개발 진행 중")
        planning = build_planning_property(
            "MCC-1603",
            client.description,
            client.updated,
            planning_id="planning-1603",
        )
        client.property = planning

        with self.assertRaisesRegex(SystemExit, "Planning property close failed"):
            finish_planning(
                client,
                "MCC-1603",
                {"todo": "해야 할 일", "progress": "개발 진행 중", "done": "개발 완료"},
            )

        self.assertEqual("개발 진행 중", client.status)
        self.assertEqual("planning", client.property["state"])

    def test_legacy_progress_cannot_be_sealed_in_place(self) -> None:
        client = SessionClient(managed_description(), status="개발 진행 중")

        with self.assertRaisesRegex(SystemExit, "Legacy progress issues"):
            start_session(
                client,
                "MCC-1603",
                {"todo": "해야 할 일", "progress": "개발 진행 중", "done": "개발 완료"},
                "MCC-1603-jira-completion-baseline-gate",
                session_id="session-1603",
            )

    def test_start_rejects_a_branch_with_only_a_longer_key_prefix(self) -> None:
        client = SessionClient(managed_description())

        with self.assertRaisesRegex(SystemExit, "exact Jira issue key"):
            start_session(
                client,
                "MCC-1603",
                {"todo": "해야 할 일", "progress": "개발 진행 중", "done": "개발 완료"},
                "MCC-16030-wrong-task",
                session_id="session-1603",
            )

    def test_planning_lock_cannot_start_an_uncovered_description(self) -> None:
        client = SessionClient(managed_description(), status="개발 진행 중")
        planning = build_planning_property(
            "MCC-1603",
            "Original requirement",
            client.updated,
            planning_id="planning-1603",
        )
        planning["approvedPlan"] = {
            "baselineCandidate": extract_snapshot(
                managed_description(scope="A different approved scope.")
            )
        }
        client.property = planning

        with self.assertRaisesRegex(SystemExit, "do not match the plan covered"):
            start_session(
                client,
                "MCC-1603",
                {"todo": "해야 할 일", "progress": "개발 진행 중", "done": "개발 완료"},
                "MCC-1603-jira-completion-baseline-gate",
                session_id="session-1603",
            )

    def test_completion_requires_exact_baseline_and_review_coverage(self) -> None:
        description = completed_description()
        prepared = build_active_property(
            "MCC-1603",
            description,
            "2026-07-23T10:00:00.000+0900",
            session_id="session-1603",
            branch="MCC-1603-jira-completion-baseline-gate",
        )
        active = with_state(prepared, "active")
        pr_url = "https://github.com/ActionFitGames/Cat_Merge_Cafe/pull/1603"
        review = {
            "version": 1,
            "issueKey": "MCC-1603",
            "sessionId": "session-1603",
            "baselineDigest": active["baseline"]["descriptionDigest"],
            "prUrl": pr_url,
            "requirements": [
                {"id": item["id"], "status": "complete", "evidence": ["test:pass"]}
                for item in active["baseline"]["requirements"]
            ],
        }
        issue = {"fields": {"status": {"name": "개발 진행 중"}, "description": description}}

        validate_completion_gate("MCC-1603", issue, "개발 진행 중", active, review, pr_url)

        with self.assertRaisesRegex(SystemExit, "every sealed requirement"):
            validate_completion_gate(
                "MCC-1603",
                issue,
                "개발 진행 중",
                active,
                {**review, "requirements": review["requirements"][:-1]},
                pr_url,
            )
        changed_issue = {
            "fields": {
                "status": {"name": "개발 진행 중"},
                "description": description.replace(
                    "- Validate exact completion evidence.",
                    "- Validate exact completion evidence.\n- Newly added scope.",
                ),
            }
        }
        with self.assertRaisesRegex(SystemExit, "changed after implementation start"):
            validate_completion_gate(
                "MCC-1603", changed_issue, "개발 진행 중", active, review, pr_url
            )

    def test_oversized_completion_review_is_not_truncated_or_transitioned(self) -> None:
        description = completed_description()
        client = SessionClient(description, status="개발 진행 중")
        prepared = build_active_property(
            "MCC-1603",
            description,
            client.updated,
            session_id="session-1603",
            branch="MCC-1603-jira-completion-baseline-gate",
        )
        client.property = with_state(prepared, "active")
        pr_url = "https://github.com/ActionFitGames/Cat_Merge_Cafe/pull/1603"
        review = {
            "version": 1,
            "issueKey": "MCC-1603",
            "sessionId": "session-1603",
            "baselineDigest": client.property["baseline"]["descriptionDigest"],
            "prUrl": pr_url,
            "requirements": [
                {
                    "id": item["id"],
                    "status": "complete",
                    "evidence": ["x" * 40000],
                }
                for item in client.property["baseline"]["requirements"]
            ],
        }

        with self.assertRaisesRegex(SystemExit, "at most 32768 bytes"):
            complete_issue(
                client,
                "MCC-1603",
                {"todo": "해야 할 일", "progress": "개발 진행 중", "done": "개발 완료"},
                pr_url,
                review,
            )

        self.assertEqual("개발 진행 중", client.status)
        self.assertEqual("active", client.property["state"])

    def test_completion_restores_active_property_when_preparation_verification_fails(self) -> None:
        description = completed_description()
        client = FailingOncePropertyClient(description, status="개발 진행 중")
        prepared = build_active_property(
            "MCC-1603",
            description,
            client.updated,
            session_id="session-1603",
            branch="MCC-1603-jira-completion-baseline-gate",
        )
        client.property = with_state(prepared, "active")
        pr_url = "https://github.com/ActionFitGames/Cat_Merge_Cafe/pull/1603"
        review = {
            "version": 1,
            "issueKey": "MCC-1603",
            "sessionId": "session-1603",
            "baselineDigest": client.property["baseline"]["descriptionDigest"],
            "prUrl": pr_url,
            "requirements": [
                {"id": item["id"], "status": "complete", "evidence": ["test:pass"]}
                for item in client.property["baseline"]["requirements"]
            ],
        }

        with self.assertRaisesRegex(SystemExit, "Completion property preparation failed"):
            complete_issue(
                client,
                "MCC-1603",
                {"todo": "해야 할 일", "progress": "개발 진행 중", "done": "개발 완료"},
                pr_url,
                review,
            )

        self.assertEqual("개발 진행 중", client.status)
        self.assertEqual("active", client.property["state"])

    def test_incomplete_finalize_restores_active_property_when_close_verification_fails(self) -> None:
        client = FailingOncePropertyClient(managed_description(), status="개발 진행 중")
        prepared = build_active_property(
            "MCC-1603",
            client.description,
            client.updated,
            session_id="session-1603",
            branch="MCC-1603-jira-completion-baseline-gate",
        )
        client.property = with_state(prepared, "active")

        with self.assertRaisesRegex(SystemExit, "completion property close failed"):
            finalize_incomplete(
                client,
                "MCC-1603",
                {"todo": "해야 할 일", "progress": "개발 진행 중", "done": "개발 완료"},
                "2026-07-23",
                completed_work="Implementation",
                remaining_work="Review",
                branch_or_pr="MCC-1603 branch",
                validation="Python tests",
                blocker_or_approval="Property verification",
                resume_condition="Retry after recovery",
            )

        self.assertEqual("개발 진행 중", client.status)
        self.assertEqual("active", client.property["state"])

    def test_mcc_1597_scope_narrowing_requires_explicit_replanning_approval(self) -> None:
        fixture = json.loads(
            (PACKAGE_ROOT / "Tests~" / "Fixtures~" / "mcc_1597_scope_regression.json").read_text(
                encoding="utf-8"
            )
        )
        planning = build_planning_property(
            fixture["issueKey"],
            fixture["originalDescription"],
            "2026-07-22T09:00:00.000+0900",
            planning_id="planning-1597",
        )
        narrowed = managed_description(
            goal=fixture["narrowedGoal"],
            scope="Add one all-table CSV export command.",
        )
        source_id = planning["preRefinement"]["requirements"][0]["id"]
        coverage = {
            "version": 1,
            "scopeChangeApproved": False,
            "approvalSummary": "",
            "requirements": [
                {
                    "sourceId": source_id,
                    "disposition": fixture["expectedBlockedDisposition"],
                    "targetIds": [],
                    "rationale": "Only CSV export moved into the first PR.",
                }
            ],
        }

        with self.assertRaisesRegex(SystemExit, "scopeChangeApproved=true"):
            validate_plan_coverage(planning, narrowed, coverage)

        coverage["scopeChangeApproved"] = True
        coverage["approvalSummary"] = "User separately approved deferring every non-export requirement."
        target = validate_plan_coverage(planning, narrowed, coverage)
        self.assertGreater(len(target["requirements"]), 0)


if __name__ == "__main__":
    unittest.main()

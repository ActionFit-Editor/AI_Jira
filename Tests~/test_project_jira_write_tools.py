from __future__ import annotations

import sys
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parents[1]
PROJECT_JIRA_DIR = REPOSITORY_ROOT / "Tools" / "AI" / "jira"
REQUIRED_PROJECT_TOOLS = (
    "create_issue.py",
    "finalize_session.py",
    "jira_client.py",
    "transition_issue.py",
    "update_description.py",
)
if not all((PROJECT_JIRA_DIR / name).is_file() for name in REQUIRED_PROJECT_TOOLS):
    raise unittest.SkipTest("Consuming project does not provide optional Jira write compatibility tools.")
sys.path.insert(0, str(PROJECT_JIRA_DIR))

from create_issue import validate_new_description
from finalize_session import (
    finalize_done,
    finalize_incomplete,
    require_finalization_gates,
    validate_handoff_date,
)
from jira_client import JiraClient, automation
from transition_issue import find_transition, validate_done_handoff
from update_description import append_requirements, require_mode_gate

from jira_description import has_handoff_record, has_qa_completion_record


ACTIVE_SPRINT_PATH = "/rest/agile/1.0/board/3/sprint?maxResults=50&state=active"
ISSUE_STATUS_PATH = "/rest/api/3/issue/MCC-1?fields=status"
ISSUE_VERIFY_PATH = "/rest/api/3/issue/MCC-1?fields=status%2Cassignee"


def jira_config(
    *,
    issue_create_overrides: dict | None = None,
    automation_overrides: dict | None = None,
) -> dict:
    automation_config = {
        "dry_run": False,
        "allow_issue_create": True,
        "allow_sprint_add": True,
    }
    automation_config.update(automation_overrides or {})
    issue_create = {
        "issue_type": "이슈",
        "assign_to_current_user": True,
        "create_status": "todo",
        "board_id": 3,
    }
    issue_create.update(issue_create_overrides or {})
    return {
        "jira_base_url": "https://example.atlassian.net",
        "project_key": "MCC",
        "statuses": {
            "todo": "해야 할 일",
            "progress": "개발 진행 중",
            "done": "개발 완료",
        },
        "automation": automation_config,
        "issue_create": issue_create,
    }


class RecordingJiraClient(JiraClient):
    def __init__(self, config: dict, responses: dict) -> None:
        super().__init__(config)
        self.responses = responses
        self.calls: list[tuple[str, str, dict | None]] = []

    def request(self, method: str, path: str, body: dict | None = None) -> dict:
        key = (method.upper(), path)
        self.calls.append((key[0], path, body))
        if key not in self.responses:
            raise AssertionError(f"Unexpected Jira request: {key}")
        response = self.responses[key]
        if isinstance(response, BaseException):
            raise response
        return response


class FinalizationClient:
    def __init__(self, description: str, *, fail_transition: bool = False) -> None:
        self.description = description
        self.status = "개발 진행 중"
        self.fail_transition = fail_transition
        self.description_updates = 0
        self.transition_calls = 0

    def get_issue(self, issue_key: str, fields: list[str] | None = None) -> dict:
        return {
            "key": issue_key,
            "fields": {
                "status": {"name": self.status},
                "description": self.description,
            },
        }

    def update_description(self, issue_key: str, description: str) -> dict:
        self.description_updates += 1
        self.description = description
        return {}

    def list_transitions(self, issue_key: str) -> list[dict]:
        return [
            {"id": "10", "name": "해야 할 일", "to": {"name": "해야 할 일"}},
            {"id": "30", "name": "개발 완료", "to": {"name": "개발 완료"}},
        ]

    def transition_issue(self, issue_key: str, transition_id: str) -> dict:
        self.transition_calls += 1
        if self.fail_transition:
            raise SystemExit("transition request failed")
        self.status = "개발 완료" if transition_id == "30" else "해야 할 일"
        return {}


def successful_create_responses(*, sprint_issues: list[dict] | None = None) -> dict:
    sprint = {"id": 42, "name": "Sprint A", "state": "active"}
    return {
        ("GET", ACTIVE_SPRINT_PATH): {"values": [sprint]},
        ("GET", "/rest/api/3/myself"): {"accountId": "account-1"},
        ("POST", "/rest/api/3/issue"): {"id": "10001", "key": "MCC-1"},
        ("GET", ISSUE_STATUS_PATH): {"fields": {"status": {"name": "해야 할 일"}}},
        ("POST", "/rest/agile/1.0/sprint/42/issue"): {},
        ("GET", ISSUE_VERIFY_PATH): {
            "fields": {
                "status": {"name": "해야 할 일"},
                "assignee": {"accountId": "account-1"},
            }
        },
        ("POST", "/rest/api/3/search/jql"): {
            "issues": sprint_issues if sprint_issues is not None else [{"key": "MCC-1"}]
        },
    }


class ProjectJiraWriteToolTests(unittest.TestCase):
    def test_transition_selection_prefers_destination_over_action_name(self) -> None:
        transitions = [
            {"id": "11", "name": "해야 할 일", "to": {"name": "개발 진행 중"}},
            {"id": "21", "name": "진행 중", "to": {"name": "해야 할 일"}},
        ]

        selected = find_transition(transitions, "해야 할 일")

        self.assertIsNotNone(selected)
        self.assertEqual("21", selected["id"])

    def test_new_issue_requires_complete_managed_description(self) -> None:
        with self.assertRaises(SystemExit):
            validate_new_description("## Goal\nIncomplete")

        from test_jira_description import managed_description

        validate_new_description(managed_description())

    def test_plan_refinement_gate_defaults_to_false(self) -> None:
        self.assertFalse(automation({})["allow_description_plan_refinement"])

    def test_missing_sprint_setting_defaults_to_required_active_sprint(self) -> None:
        client = RecordingJiraClient(jira_config(), successful_create_responses())

        result = client.create_issue("요약", "설명")

        self.assertEqual("MCC-1", result["key"])
        self.assertEqual(("GET", ACTIVE_SPRINT_PATH), client.calls[0][:2])
        search_body = client.calls[-1][2]
        self.assertEqual([10001], search_body["reconcileIssues"])
        self.assertEqual('key = "MCC-1" AND sprint = 42', search_body["jql"])

    def test_explicit_false_sprint_setting_blocks_before_any_request(self) -> None:
        client = RecordingJiraClient(
            jira_config(issue_create_overrides={"add_to_active_sprint_after_create": False}),
            {},
        )

        with self.assertRaisesRegex(SystemExit, "requires active-sprint placement"):
            client.create_issue("요약", "설명")

        self.assertEqual([], client.calls)

    def test_disabled_sprint_gate_blocks_before_any_request(self) -> None:
        client = RecordingJiraClient(
            jira_config(automation_overrides={"allow_sprint_add": False}),
            {},
        )

        with self.assertRaisesRegex(SystemExit, "allow_sprint_add=true"):
            client.create_issue("요약", "설명")

        self.assertEqual([], client.calls)

    def test_missing_active_sprint_blocks_before_issue_create_request(self) -> None:
        client = RecordingJiraClient(
            jira_config(),
            {("GET", ACTIVE_SPRINT_PATH): {"values": []}},
        )

        with self.assertRaisesRegex(SystemExit, "No active Jira sprint"):
            client.create_issue("요약", "설명")

        self.assertNotIn("/rest/api/3/issue", [call[1] for call in client.calls])

    def test_ambiguous_active_sprint_blocks_before_issue_create_request(self) -> None:
        client = RecordingJiraClient(
            jira_config(),
            {
                ("GET", ACTIVE_SPRINT_PATH): {
                    "values": [
                        {"id": 42, "name": "Sprint A", "state": "active"},
                        {"id": 43, "name": "Sprint B", "state": "active"},
                    ]
                }
            },
        )

        with self.assertRaisesRegex(SystemExit, "Multiple active Jira sprints"):
            client.create_issue("요약", "설명")

        self.assertNotIn("/rest/api/3/issue", [call[1] for call in client.calls])

    def test_inactive_fixed_sprint_blocks_before_issue_create_request(self) -> None:
        client = RecordingJiraClient(
            jira_config(issue_create_overrides={"active_sprint_id": 42}),
            {
                ("GET", "/rest/agile/1.0/sprint/42"): {
                    "id": 42,
                    "name": "Closed Sprint",
                    "state": "closed",
                }
            },
        )

        with self.assertRaisesRegex(SystemExit, "Configured sprint is not active"):
            client.create_issue("요약", "설명")

        self.assertNotIn("/rest/api/3/issue", [call[1] for call in client.calls])

    def test_sprint_assignment_failure_reports_created_issue_recovery(self) -> None:
        responses = successful_create_responses()
        responses[("POST", "/rest/agile/1.0/sprint/42/issue")] = SystemExit("permission denied")
        client = RecordingJiraClient(jira_config(), responses)

        with self.assertRaises(SystemExit) as raised:
            client.create_issue("요약", "설명")

        message = str(raised.exception)
        self.assertIn("Created Jira issue MCC-1", message)
        self.assertIn("Sprint A (42)", message)
        self.assertIn("Manually move MCC-1", message)
        self.assertIn("permission denied", message)

    def test_unexpected_post_create_failure_reports_created_issue_recovery(self) -> None:
        responses = successful_create_responses()
        responses[("POST", "/rest/agile/1.0/sprint/42/issue")] = RuntimeError("connection dropped")
        client = RecordingJiraClient(jira_config(), responses)

        with self.assertRaises(SystemExit) as raised:
            client.create_issue("요약", "설명")

        message = str(raised.exception)
        self.assertIn("Created Jira issue MCC-1", message)
        self.assertIn("Sprint A (42)", message)
        self.assertIn("connection dropped", message)

    def test_sprint_assignment_helper_resolves_target_when_not_provided(self) -> None:
        responses = successful_create_responses()
        client = RecordingJiraClient(jira_config(), responses)

        client.add_created_issue_to_active_sprint("MCC-1")

        self.assertEqual(("GET", ACTIVE_SPRINT_PATH), client.calls[0][:2])
        self.assertEqual(
            ("POST", "/rest/agile/1.0/sprint/42/issue", {"issues": ["MCC-1"]}),
            client.calls[1],
        )

    def test_post_create_status_mismatch_reports_created_issue_recovery(self) -> None:
        responses = successful_create_responses()
        responses[("GET", ISSUE_VERIFY_PATH)] = {
            "fields": {
                "status": {"name": "개발 진행 중"},
                "assignee": {"accountId": "account-1"},
            }
        }
        client = RecordingJiraClient(jira_config(), responses)

        with self.assertRaisesRegex(SystemExit, "Post-create status verification failed"):
            client.create_issue("요약", "설명")

    def test_post_create_assignee_mismatch_reports_created_issue_recovery(self) -> None:
        responses = successful_create_responses()
        responses[("GET", ISSUE_VERIFY_PATH)] = {
            "fields": {
                "status": {"name": "해야 할 일"},
                "assignee": {"accountId": "different-account"},
            }
        }
        client = RecordingJiraClient(jira_config(), responses)

        with self.assertRaisesRegex(SystemExit, "Post-create assignee verification failed"):
            client.create_issue("요약", "설명")

    def test_post_create_sprint_mismatch_reports_created_issue_recovery(self) -> None:
        client = RecordingJiraClient(
            jira_config(),
            successful_create_responses(sprint_issues=[]),
        )

        with self.assertRaisesRegex(SystemExit, "MCC-1 is not in sprint 42"):
            client.create_issue("요약", "설명")

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

    def test_finalization_gates_require_real_transition_and_incomplete_description_write(self) -> None:
        with self.assertRaisesRegex(SystemExit, "dry_run=false"):
            require_finalization_gates({"dry_run": True}, "done")
        with self.assertRaisesRegex(SystemExit, "allow_transition=true"):
            require_finalization_gates({"dry_run": False}, "done")
        with self.assertRaisesRegex(SystemExit, "allow_description_append=true"):
            require_finalization_gates(
                {"dry_run": False, "allow_transition": True},
                "incomplete",
            )

    def test_handoff_date_requires_exact_iso_calendar_date(self) -> None:
        self.assertEqual("2026-07-15", validate_handoff_date("2026-07-15"))
        for invalid in ("2026-7-15", "2026-02-30", "15-07-2026"):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                SystemExit, "exact YYYY-MM-DD"
            ):
                validate_handoff_date(invalid)

    def test_incomplete_finalization_verifies_handoff_and_returns_to_todo(self) -> None:
        from test_jira_description import managed_description

        client = FinalizationClient(managed_description())
        finalize_incomplete(
            client,
            "MCC-1490",
            jira_config()["statuses"],
            "2026-07-15",
            completed_work="구조 분석",
            remaining_work="PR 생성",
            branch_or_pr="MCC-1490-work / PR 없음",
            validation="단위 테스트 통과",
            blocker_or_approval="없음",
            resume_condition="PR 생성부터 재개",
        )

        self.assertEqual("해야 할 일", client.status)
        self.assertEqual(1, client.description_updates)
        self.assertEqual(1, client.transition_calls)
        self.assertTrue(has_handoff_record(client.description, "MCC-1490"))
        self.assertFalse(has_qa_completion_record(client.description, "MCC-1490"))

    def test_incomplete_transition_failure_reports_verified_partial_success(self) -> None:
        from test_jira_description import managed_description

        client = FinalizationClient(managed_description(), fail_transition=True)
        with self.assertRaisesRegex(SystemExit, "handoff is verified, but todo finalization failed"):
            finalize_incomplete(
                client,
                "MCC-1490",
                jira_config()["statuses"],
                "2026-07-15",
                completed_work="분석",
                remaining_work="구현",
                branch_or_pr="MCC-1490-work",
                validation="미실행",
                blocker_or_approval="없음",
                resume_condition="구현부터 재개",
            )

        self.assertEqual("개발 진행 중", client.status)
        self.assertTrue(has_handoff_record(client.description, "MCC-1490"))

    def test_done_finalization_requires_verified_qa_and_reaches_done(self) -> None:
        client = FinalizationClient(
            """## QA 확인 필요 사항

### 2026-07-15 / MCC-1490
- 변경 요약: 완료

---

### 계획
- 확인 항목:

---

## Goal
Done
"""
        )

        finalize_done(
            client,
            "MCC-1490",
            jira_config()["statuses"],
            "https://github.com/ActionFitGames/Cat_Merge_Cafe/pull/1234",
        )

        self.assertEqual("개발 완료", client.status)
        self.assertEqual(1, client.transition_calls)


if __name__ == "__main__":
    unittest.main()

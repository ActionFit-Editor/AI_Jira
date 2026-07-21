from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "Tools~"
sys.path.insert(0, str(TOOLS_DIR))

from jira_work_items import (
    build_jql,
    build_overlap_jql,
    load_config,
    normalize_issue_links,
    query_overlap_work_items,
    query_work_item,
    query_work_items,
    write_json,
    write_text,
)


class FakeJiraReadApi:
    def __init__(self) -> None:
        self.jql = ""
        self.max_results = 0

    def search_issues(self, jql: str, max_results: int) -> dict:
        self.jql = jql
        self.max_results = max_results
        return {
            "issues": [
                {
                    "key": "MCC-1439",
                    "fields": {
                        "summary": "한글 작업 목록",
                        "status": {"name": "개발 진행 중"},
                        "updated": "2026-07-13T17:30:00.000+0900",
                    },
                }
            ],
            "isLast": True,
        }

    def get_issue(self, issue_key: str, fields: list[str]) -> dict:
        self.issue_key = issue_key
        self.fields = fields
        return {
            "key": issue_key,
            "fields": {
                "summary": "스킬 자동 설치",
                "status": {"name": "개발 진행 중"},
                "updated": "2026-07-13T18:00:00.000+0900",
                "description": {
                    "type": "doc",
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "한글 설명"}]},
                        {"type": "bulletList", "content": [
                            {"type": "listItem", "content": [
                                {"type": "paragraph", "content": [{"type": "text", "text": "안전 설치"}]}
                            ]}
                        ]},
                    ],
                },
                "priority": {"name": "Medium"},
                "labels": ["ai-jira"],
                "assignee": {"displayName": "개발자"},
                "issuetype": {"name": "추가"},
                "resolution": None,
                "project": {"key": "MCC"},
                "issuelinks": [
                    {
                        "type": {
                            "name": "Blocks",
                            "inward": "is blocked by",
                            "outward": "blocks",
                        },
                        "inwardIssue": {
                            "key": "MCC-1400",
                            "fields": {
                                "summary": "선행 패키지 작업",
                                "status": {"name": "개발 완료"},
                                "resolution": {"name": "Done"},
                            },
                        },
                    },
                    {
                        "type": {
                            "name": "Blocks",
                            "inward": "is blocked by",
                            "outward": "blocks",
                        },
                        "outwardIssue": {
                            "key": "MCC-1500",
                            "fields": {
                                "summary": "후속 작업",
                                "status": {"name": "해야 할 일"},
                                "resolution": None,
                            },
                        },
                    },
                ],
            },
        }


class FakePagedJiraReadApi:
    def __init__(self, responses: dict[str | None, dict]) -> None:
        self.responses = responses
        self.calls = []

    def search_issues(
        self,
        jql: str,
        max_results: int,
        next_page_token: str | None = None,
        fields: list[str] | None = None,
    ) -> dict:
        self.calls.append((jql, max_results, next_page_token, fields))
        return self.responses[next_page_token]


class JiraWorkItemsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "jira_base_url": "https://actionfit.atlassian.net",
            "project_key": "MCC",
            "statuses": {
                "todo": "해야 할 일",
                "progress": "개발 진행 중",
                "done": "개발 완료",
            },
        }

    def test_build_jql_for_all_unresolved_work_states(self) -> None:
        jql, statuses = build_jql(self.config, "all")

        self.assertEqual(["해야 할 일", "개발 진행 중"], statuses)
        self.assertIn('project = "MCC"', jql)
        self.assertIn("assignee = currentUser()", jql)
        self.assertIn("resolution = Unresolved", jql)
        self.assertIn('status IN ("해야 할 일", "개발 진행 중")', jql)
        self.assertTrue(jql.endswith("ORDER BY updated DESC"))

    def test_build_overlap_jql_uses_project_and_all_configured_lifecycle_states(self) -> None:
        jql, statuses = build_overlap_jql(self.config)

        self.assertEqual(["해야 할 일", "개발 진행 중", "개발 완료"], statuses)
        self.assertIn('project = "MCC"', jql)
        self.assertIn('status IN ("해야 할 일", "개발 진행 중", "개발 완료")', jql)
        self.assertNotIn("assignee", jql)
        self.assertNotIn("resolution", jql)
        self.assertTrue(jql.endswith("ORDER BY updated DESC"))

    def test_build_overlap_jql_requires_project_and_every_lifecycle_mapping(self) -> None:
        missing_project = {**self.config, "project_key": ""}
        with self.assertRaisesRegex(SystemExit, "Missing Jira project_key"):
            build_overlap_jql(missing_project)

        missing_done = {**self.config, "statuses": {**self.config["statuses"], "done": ""}}
        with self.assertRaisesRegex(SystemExit, "Missing Jira status mapping.*done"):
            build_overlap_jql(missing_done)

    def test_overlap_query_reads_every_page_and_reports_completion(self) -> None:
        api = FakePagedJiraReadApi(
            {
                None: {
                    "issues": [self._overlap_issue("MCC-1", "해야 할 일", "개발자 A")],
                    "isLast": False,
                    "nextPageToken": "page-2",
                },
                "page-2": {
                    "issues": [self._overlap_issue("MCC-2", "개발 완료", "개발자 B")],
                    "isLast": True,
                },
            }
        )

        result = query_overlap_work_items(self.config, page_size=25, api=api)

        self.assertTrue(result["complete"])
        self.assertEqual("project", result["scope"])
        self.assertEqual(["todo", "progress", "done"], result["states"])
        self.assertEqual(["해야 할 일", "개발 진행 중", "개발 완료"], result["statuses"])
        self.assertEqual(2, result["pageCount"])
        self.assertEqual(2, result["returnedCount"])
        self.assertEqual([None, "page-2"], [call[2] for call in api.calls])
        self.assertEqual(["summary", "status", "updated", "assignee"], api.calls[0][3])
        self.assertEqual("개발자 B", result["items"][1]["assignee"])

    def test_overlap_query_rejects_repeated_page_token(self) -> None:
        api = FakePagedJiraReadApi(
            {
                None: {"issues": [], "isLast": False, "nextPageToken": "repeat"},
                "repeat": {"issues": [], "isLast": False, "nextPageToken": "repeat"},
            }
        )

        with self.assertRaisesRegex(SystemExit, "repeated a nextPageToken"):
            query_overlap_work_items(self.config, api=api)

    def test_overlap_query_rejects_missing_terminal_evidence(self) -> None:
        api = FakePagedJiraReadApi({None: {"issues": []}})

        with self.assertRaisesRegex(SystemExit, "without explicit terminal evidence"):
            query_overlap_work_items(self.config, api=api)

    def test_overlap_query_rejects_terminal_page_with_token(self) -> None:
        api = FakePagedJiraReadApi(
            {None: {"issues": [], "isLast": True, "nextPageToken": "unexpected"}}
        )

        with self.assertRaisesRegex(SystemExit, "terminal page with a nextPageToken"):
            query_overlap_work_items(self.config, api=api)

    def test_overlap_query_rejects_issue_outside_configured_states(self) -> None:
        api = FakePagedJiraReadApi(
            {
                None: {
                    "issues": [self._overlap_issue("MCC-3", "QA 진행 중", "개발자 C")],
                    "isLast": True,
                }
            }
        )

        with self.assertRaisesRegex(SystemExit, "outside configured lifecycle statuses"):
            query_overlap_work_items(self.config, api=api)

    def test_query_returns_structured_items(self) -> None:
        api = FakeJiraReadApi()

        result = query_work_items(self.config, state="progress", max_results=25, api=api)

        self.assertEqual(1, result["returnedCount"])
        self.assertEqual(25, api.max_results)
        self.assertIn('status = "개발 진행 중"', api.jql)
        self.assertEqual("한글 작업 목록", result["items"][0]["summary"])
        self.assertEqual(
            "https://actionfit.atlassian.net/browse/MCC-1439",
            result["items"][0]["url"],
        )

    def test_json_output_preserves_korean(self) -> None:
        result = query_work_items(self.config, api=FakeJiraReadApi())
        output = io.StringIO()

        write_json(result, output)

        rendered = output.getvalue()
        self.assertIn("한글 작업 목록", rendered)
        self.assertNotIn("\\u", rendered)
        self.assertEqual("개발 진행 중", json.loads(rendered)["items"][0]["status"])

    def test_text_output_contains_requested_fields(self) -> None:
        result = query_work_items(self.config, api=FakeJiraReadApi())
        output = io.StringIO()

        write_text(result, output)

        self.assertEqual(
            "MCC-1439 [개발 진행 중] 한글 작업 목록 "
            "(updated: 2026-07-13T17:30:00.000+0900)\n",
            output.getvalue(),
        )

    def test_config_loader_accepts_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(self.config, ensure_ascii=False), encoding="utf-8-sig")

            loaded = load_config(str(path))

        self.assertEqual("개발 진행 중", loaded["statuses"]["progress"])

    def test_query_one_issue_returns_implementation_context(self) -> None:
        api = FakeJiraReadApi()

        result = query_work_item(self.config, "MCC-1441", api=api)

        self.assertEqual("MCC-1441", api.issue_key)
        self.assertIn("description", api.fields)
        self.assertIn("issuelinks", api.fields)
        self.assertEqual("스킬 자동 설치", result["summary"])
        self.assertEqual("한글 설명\n안전 설치", result["description"])
        self.assertEqual("개발자", result["assignee"])
        self.assertEqual("MCC", result["project"])
        self.assertEqual("", result["resolution"])
        self.assertEqual("needs-plan", result["descriptionContract"]["state"])
        self.assertFalse(result["descriptionContract"]["structurallyComplete"])
        self.assertEqual("개발 완료", result["configuredStatuses"]["done"])
        self.assertEqual(
            {
                "key": "MCC-1400",
                "direction": "inward",
                "relation": "is blocked by",
                "type": "Blocks",
                "summary": "선행 패키지 작업",
                "status": "개발 완료",
                "resolution": "Done",
            },
            result["issueLinks"][0],
        )
        self.assertEqual("blocks", result["issueLinks"][1]["relation"])

    def test_issue_link_normalization_excludes_the_current_issue_from_full_link(self) -> None:
        links = [
            {
                "type": {"name": "Dependency", "inward": "depends on", "outward": "is required by"},
                "inwardIssue": {"key": "MCC-1399", "fields": {"summary": "선행 작업"}},
                "outwardIssue": {"key": "MCC-1441", "fields": {"summary": "현재 작업"}},
            }
        ]

        result = normalize_issue_links(links, "MCC-1441")

        self.assertEqual(1, len(result))
        self.assertEqual("MCC-1399", result[0]["key"])
        self.assertEqual("depends on", result[0]["relation"])

    def test_one_issue_json_preserves_korean(self) -> None:
        result = query_work_item(self.config, "MCC-1441", api=FakeJiraReadApi())
        output = io.StringIO()

        write_json(result, output)

        self.assertIn("한글 설명", output.getvalue())
        self.assertNotIn("\\u", output.getvalue())

    @staticmethod
    def _overlap_issue(key: str, status: str, assignee: str) -> dict:
        return {
            "key": key,
            "fields": {
                "summary": f"{key} 요약",
                "status": {"name": status},
                "assignee": {"displayName": assignee},
                "updated": "2026-07-21T00:00:00.000+0000",
            },
        }


if __name__ == "__main__":
    unittest.main()

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
    load_config,
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
            },
        }


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

    def test_build_jql_for_all_actionable_states(self) -> None:
        jql, statuses = build_jql(self.config, "all")

        self.assertEqual(["해야 할 일", "개발 진행 중"], statuses)
        self.assertIn('project = "MCC"', jql)
        self.assertIn("assignee = currentUser()", jql)
        self.assertIn("resolution = Unresolved", jql)
        self.assertIn('status IN ("해야 할 일", "개발 진행 중")', jql)
        self.assertTrue(jql.endswith("ORDER BY updated DESC"))

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
        self.assertEqual("스킬 자동 설치", result["summary"])
        self.assertEqual("한글 설명\n안전 설치", result["description"])
        self.assertEqual("개발자", result["assignee"])
        self.assertEqual("MCC", result["project"])
        self.assertEqual("", result["resolution"])

    def test_one_issue_json_preserves_korean(self) -> None:
        result = query_work_item(self.config, "MCC-1441", api=FakeJiraReadApi())
        output = io.StringIO()

        write_json(result, output)

        self.assertIn("한글 설명", output.getvalue())
        self.assertNotIn("\\u", output.getvalue())


if __name__ == "__main__":
    unittest.main()

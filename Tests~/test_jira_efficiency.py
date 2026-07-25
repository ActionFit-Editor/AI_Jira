from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1] / "Tools~"
sys.path.insert(0, str(TOOLS))

from jira_classification import classify_work_items
from jira_snapshot import build_snapshot


def ready_description(prerequisites: str = "none", suffix: str = "") -> str:
    return f"""## QA 확인 필요 사항

### 계획
- 확인 항목: 자동 검증

---

## Auto Start
- Allowed: yes
- Prerequisites: {prerequisites}
- Decisions Required: none

## Goal
- Keep bounded evidence.

## Scope
- Add one compact command. {suffix}

## Out of Scope
- Production changes.

## Completion Criteria
- The bounded command passes tests.

## Validation Plan
- Run the focused test suite.

## Dependencies and Risks
- None beyond declared prerequisites.
"""


def issue(key: str, description: str, status: str = "해야 할 일", resolution: str = "") -> dict:
    return {
        "key": key,
        "fields": {
            "summary": f"{key} 한글 요약",
            "status": {"name": status},
            "updated": "2026-07-25T00:00:00.000+0000",
            "description": description,
            "project": {"key": "MCC"},
            "resolution": {"name": resolution} if resolution else None,
            "priority": {"name": "Medium"},
            "labels": [],
            "assignee": {"displayName": "개발자"},
            "issuetype": {"name": "Task"},
            "issuelinks": [],
        },
    }


class FakeApi:
    def __init__(self, candidate: dict, prerequisites: list[dict] | None = None) -> None:
        self.candidate = candidate
        self.prerequisites = prerequisites or []
        self.search_calls: list[tuple[str, list[str] | None]] = []
        self.get_calls: list[str] = []

    def search_issues(
        self,
        jql: str,
        max_results: int,
        fields: list[str] | None = None,
        next_page_token: str | None = None,
    ) -> dict:
        self.search_calls.append((jql, fields))
        values = self.prerequisites if jql.startswith("key IN") else [self.candidate]
        return {"issues": values, "isLast": True}

    def get_issue(self, issue_key: str, fields: list[str]) -> dict:
        self.get_calls.append(issue_key)
        if issue_key == self.candidate["key"]:
            return self.candidate
        for value in self.prerequisites:
            if value["key"] == issue_key:
                return value
        raise SystemExit("not found")

    def get_issue_property(self, issue_key: str, property_key: str) -> dict:
        return {
            "version": 1,
            "state": "active",
            "sessionId": "session-1",
            "branch": f"{issue_key}-branch",
            "baseline": {
                "descriptionDigest": "sha256:test",
                "requirements": [{"id": "REQ-1", "text": "must not leak"}],
                "sections": [{"body": "FULL BASELINE MUST NOT LEAK"}],
            },
        }


class JiraEfficiencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "jira_base_url": "https://example.test",
            "project_key": "MCC",
            "statuses": {
                "todo": "해야 할 일",
                "progress": "개발 진행 중",
                "done": "개발 완료",
                "done_auto": "개발 완료 - 자동 검증 필요",
                "done_manual": "개발 완료 - 수동 검증 필요",
                "done_verified": "개발 완료 - 검증 완료",
            },
        }

    def test_compact_classification_batches_prerequisites_and_omits_full_description(self) -> None:
        marker = "VERY-LONG-PLAN-" * 500
        candidate = issue("MCC-1", ready_description("MCC-2", marker))
        prerequisite = issue(
            "MCC-2",
            ready_description(),
            status="개발 완료 - 수동 검증 필요",
            resolution="Done",
        )
        api = FakeApi(candidate, [prerequisite])

        result = classify_work_items(self.config, api=api)
        encoded = json.dumps(result, ensure_ascii=False)

        self.assertEqual("startable", result["items"][0]["classification"])
        self.assertEqual(["MCC-2"], [item["key"] for item in result["items"][0]["prerequisites"]])
        self.assertNotIn(marker, encoded)
        self.assertEqual(2, len(api.search_calls))
        self.assertIn("description", api.search_calls[0][1])
        self.assertNotIn("description", api.search_calls[1][1])

    def test_snapshot_reads_only_selected_issue_and_explicit_prerequisite(self) -> None:
        candidate = issue("MCC-1", ready_description("MCC-2", "SECRET DESCRIPTION"))
        prerequisite = issue("MCC-2", ready_description(), status="개발 완료", resolution="Done")
        api = FakeApi(candidate, [prerequisite])

        def runner(command: list[str], cwd: Path) -> tuple[int, str, str]:
            if command[:2] == ["git", "for-each-ref"]:
                return 0, "MCC-1-branch\nunrelated\n", ""
            if command[:3] == ["gh", "pr", "list"]:
                return 0, '[{"number": 1, "url": "https://example.test/pr/1"}]', ""
            return 0, json.dumps(
                {
                    "slots": [
                        {
                            "slot": "slot-1",
                            "path": "/tmp/slot-1",
                            "branch": "MCC-1-branch",
                            "head": "abc",
                            "lease": {"state": "active", "task": "MCC-1", "lease_id": "lease"},
                        }
                    ]
                }
            ), ""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tool = root / "Packages/com.actionfit.ai-worktrees/Tools/manage_worktree_slots.py"
            tool.parent.mkdir(parents=True)
            tool.write_text("# test", encoding="utf-8")
            with patch("jira_snapshot.shutil.which", return_value="/usr/bin/gh"):
                result = build_snapshot(
                    self.config,
                    "MCC-1",
                    api=api,
                    project_root=root,
                    runner=runner,
                )

        encoded = json.dumps(result, ensure_ascii=False)
        self.assertEqual(["MCC-1", "MCC-2"], api.get_calls)
        self.assertTrue(result["bounds"]["selectedIssueOnly"])
        self.assertFalse(result["bounds"]["fullDescriptionsIncluded"])
        self.assertEqual(1, result["session"]["requirementCount"])
        self.assertNotIn("SECRET DESCRIPTION", encoded)
        self.assertNotIn("FULL BASELINE MUST NOT LEAK", encoded)

    def test_compact_classification_preserves_inward_blocking_link_semantics(self) -> None:
        candidate = issue("MCC-1", ready_description())
        candidate["fields"]["issuelinks"] = [
            {
                "type": {"name": "Blocks", "inward": "is blocked by", "outward": "blocks"},
                "inwardIssue": {
                    "key": "MCC-2",
                    "fields": {
                        "summary": "선행 작업",
                        "status": {"name": "개발 완료"},
                        "resolution": {"name": "Done"},
                    },
                },
            }
        ]
        prerequisite = issue("MCC-2", ready_description(), status="개발 완료", resolution="Done")

        result = classify_work_items(self.config, api=FakeApi(candidate, [prerequisite]))

        observed = result["items"][0]["prerequisites"]
        self.assertEqual(["MCC-2"], [item["key"] for item in observed])
        self.assertEqual("inward-link", observed[0]["source"])
        self.assertEqual("startable", result["items"][0]["classification"])


if __name__ == "__main__":
    unittest.main()

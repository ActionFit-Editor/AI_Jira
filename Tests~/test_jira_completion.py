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
    DEVELOPMENT_COMPLETE_PROPERTY_STATES,
    MAX_PROPERTY_BYTES,
    build_active_property,
    build_planning_property,
    extract_snapshot,
    property_size,
    require_property_size,
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


class SealedSnapshotPayloadTests(unittest.TestCase):
    # Digest produced by the implementation that still stored section prose. Pinning it proves the
    # seal is unchanged for existing issues, so in-flight baselines keep matching their description.
    MANAGED_DESCRIPTION_DIGEST = (
        "sha256:055e534a49d0f6acf94a3fff9969c492e429ae79eafb51eafc22cb0d1baa49b6"
    )

    def legacy_snapshot(self, description: str) -> dict:
        """Reproduce the stored shape written before section prose was dropped."""
        snapshot = extract_snapshot(description)
        sections = [{"heading": "Goal", "body": "Prose an earlier version persisted."}]
        return {**snapshot, "sections": sections}

    def test_snapshot_keeps_digest_and_requirements_without_storing_prose(self) -> None:
        description = managed_description(scope="Seal a uniquely traceable scope sentence.")

        snapshot = extract_snapshot(description)

        self.assertEqual({"descriptionDigest", "requirements"}, set(snapshot))
        self.assertGreater(len(snapshot["requirements"]), 0)
        serialized = json.dumps(snapshot, ensure_ascii=False)
        self.assertNotIn("Out of Scope", serialized)
        self.assertNotIn("Dependencies and Risks", serialized)

    def test_digest_matches_the_implementation_that_stored_prose(self) -> None:
        self.assertEqual(
            self.MANAGED_DESCRIPTION_DIGEST,
            extract_snapshot(managed_description())["descriptionDigest"],
        )

    def test_digest_still_detects_prose_changed_outside_requirement_items(self) -> None:
        baseline = extract_snapshot(managed_description())
        reworded = managed_description(goal="Protect Jira completion with a reworded goal.")

        self.assertNotEqual(
            baseline["descriptionDigest"], extract_snapshot(reworded)["descriptionDigest"]
        )

    def test_carry_forward_drops_legacy_prose_and_preserves_the_seal(self) -> None:
        description = managed_description()
        stored = {
            "version": 1,
            "issueKey": "MCC-1672",
            "state": "closed-incomplete",
            "preRefinement": self.legacy_snapshot(description),
        }

        prepared = build_active_property(
            "MCC-1672",
            description,
            "2026-07-26T10:00:00.000+0900",
            session_id="session-1672",
            branch="MCC-1672-drop-sealed-snapshot-sections",
            previous=stored,
        )

        carried = prepared["preRefinement"]
        self.assertNotIn("sections", carried)
        self.assertEqual(stored["preRefinement"]["descriptionDigest"], carried["descriptionDigest"])
        self.assertEqual(stored["preRefinement"]["requirements"], carried["requirements"])
        self.assertIn("sections", stored["preRefinement"])

    def test_carry_forward_also_drops_prose_from_an_approved_plan(self) -> None:
        description = managed_description()
        stored = {
            "version": 1,
            "issueKey": "MCC-1672",
            "state": "planned",
            "approvedPlan": {"preRefinement": self.legacy_snapshot(description)},
        }

        prepared = build_active_property(
            "MCC-1672",
            description,
            "2026-07-26T10:00:00.000+0900",
            session_id="session-1672",
            branch="MCC-1672-drop-sealed-snapshot-sections",
            previous=stored,
        )

        self.assertNotIn("sections", prepared["preRefinement"])

    def test_legacy_prose_snapshot_still_validates_plan_coverage(self) -> None:
        planning = build_planning_property(
            "MCC-1672",
            managed_description(),
            "2026-07-26T09:00:00.000+0900",
            planning_id="planning-1672",
        )
        planning["preRefinement"] = self.legacy_snapshot(managed_description())
        clarified = managed_description(scope="Seal every requirement with explicit evidence.")
        coverage = {
            "version": 1,
            "requirements": [
                {
                    "sourceId": item["id"],
                    "disposition": "clarified" if "Seal every requirement" in item["text"] else "retained",
                    "targetIds": [],
                }
                for item in planning["preRefinement"]["requirements"]
            ],
        }
        target_ids = {item["id"] for item in extract_snapshot(clarified)["requirements"]}
        for entry in coverage["requirements"]:
            if entry["disposition"] == "retained":
                entry["targetIds"] = [entry["sourceId"]]
            else:
                entry["targetIds"] = sorted(
                    target_ids - {item["id"] for item in planning["preRefinement"]["requirements"]}
                )

        approved = validate_plan_coverage(planning, clarified, coverage)

        self.assertNotIn("sections", approved)
        self.assertGreater(len(approved["requirements"]), 0)

    def test_long_description_start_stays_within_the_property_limit(self) -> None:
        long_scope = " ".join(
            f"Deliver bounded capability number {index} with explicit verifiable evidence."
            for index in range(120)
        )
        description = managed_description(scope=long_scope)
        stored = {
            "version": 1,
            "issueKey": "MCC-1672",
            "state": "closed-incomplete",
            "preRefinement": self.legacy_snapshot(description),
        }

        prepared = build_active_property(
            "MCC-1672",
            description,
            "2026-07-26T10:00:00.000+0900",
            session_id="session-1672",
            branch="MCC-1672-drop-sealed-snapshot-sections",
            previous=stored,
        )

        self.assertLessEqual(property_size(prepared), MAX_PROPERTY_BYTES)
        self.assertNotIn("sections", prepared["baseline"])
        self.assertNotIn("sections", prepared["preRefinement"])

    def test_property_limit_still_rejects_an_oversized_payload(self) -> None:
        oversized = {
            "version": 1,
            "issueKey": "MCC-1672",
            "state": "active",
            "baseline": {
                "descriptionDigest": "sha256:test",
                "requirements": [
                    {"id": f"REQ-{index:012X}", "section": "Scope", "text": "x" * 200}
                    for index in range(400)
                ],
            },
        }

        self.assertGreater(property_size(oversized), MAX_PROPERTY_BYTES)
        with self.assertRaisesRegex(SystemExit, "Shorten the managed Jira description"):
            require_property_size(oversized)


class DevelopmentCompletePayloadTests(unittest.TestCase):
    """The completion property must not keep artifacts that no reader consumes."""

    def active_property(self, description: str) -> dict:
        prepared = build_active_property(
            "MCC-1674",
            description,
            "2026-07-26T10:00:00.000+0900",
            session_id="session-1674",
            branch="MCC-1674-drop-prerefinement-at-completion",
            previous={
                "version": 1,
                "issueKey": "MCC-1674",
                "state": "closed-incomplete",
                "preRefinement": extract_snapshot(managed_description(goal="Original goal.")),
            },
        )
        self.assertIn("preRefinement", prepared, "the active property still needs the snapshot")
        return prepared

    def test_every_development_complete_state_drops_the_pre_refinement_snapshot(self) -> None:
        active = with_state(self.active_property(completed_description()), "active")

        for state in sorted(DEVELOPMENT_COMPLETE_PROPERTY_STATES):
            with self.subTest(state=state):
                self.assertNotIn("preRefinement", with_state(active, state))

    def test_pre_completion_states_keep_the_snapshot(self) -> None:
        active = self.active_property(completed_description())

        for state in ("active", "planning", "closed-incomplete"):
            with self.subTest(state=state):
                self.assertIn(
                    "preRefinement",
                    with_state(active, state),
                    "a pre-completion state still has readers for the snapshot",
                )

    def test_plan_coverage_still_reads_the_snapshot(self) -> None:
        planning = build_planning_property(
            "MCC-1674",
            managed_description(),
            "2026-07-26T09:00:00.000+0900",
            planning_id="planning-1674",
        )
        clarified = managed_description(scope="Seal every requirement with explicit evidence.")
        source_ids = [item["id"] for item in planning["preRefinement"]["requirements"]]
        target_ids = {item["id"] for item in extract_snapshot(clarified)["requirements"]}
        coverage = {
            "version": 1,
            "requirements": [
                {"sourceId": i, "disposition": "retained", "targetIds": [i]}
                if i in target_ids
                else {"sourceId": i, "disposition": "clarified",
                      "targetIds": sorted(target_ids - set(source_ids))}
                for i in source_ids
            ],
        }

        approved = validate_plan_coverage(planning, clarified, coverage)

        self.assertGreater(len(approved["requirements"]), 0)

    def test_a_large_issue_now_fits_the_property_limit_at_completion(self) -> None:
        # managed_description renders the scope as bullets, so join with a bullet prefix to
        # produce a genuinely large requirement set rather than one long sentence.
        long_scope = "\n- ".join(
            f"Deliver bounded capability number {index} with explicit verifiable evidence."
            for index in range(60)
        )
        description = prepend_qa_record(
            managed_description(scope=long_scope),
            "MCC-1674",
            "2026-07-26",
            """- 변경 요약: 큰 이슈 픽스처
- 검증 결과: Python 테스트 통과
- 미검증 항목: 없음
- QA 확인 항목: 없음
- 위험 영역: 없음""",
        )
        active = with_state(self.active_property(description), "active")
        requirements = active["baseline"]["requirements"]
        review = {
            "version": 1,
            "issueKey": "MCC-1674",
            "sessionId": "session-1674",
            "baselineDigest": active["baseline"]["descriptionDigest"],
            "prUrl": "https://github.com/ActionFitGames/Cat_Merge_Cafe/pull/1",
            "requirements": [
                {"id": item["id"], "status": "complete", "evidence": ["test:pass"]}
                for item in requirements
            ],
        }

        completed = with_state(
            active,
            "completed",
            review=review,
            verification={"version": 1, "issueKey": "MCC-1674", "checks": []},
        )

        self.assertGreaterEqual(len(requirements), 60, "the fixture must exercise a large issue")
        self.assertNotIn("preRefinement", completed)
        self.assertLessEqual(property_size(completed), MAX_PROPERTY_BYTES)

    def test_the_limit_still_rejects_a_payload_that_is_genuinely_too_large(self) -> None:
        oversized = {
            "version": 1,
            "issueKey": "MCC-1674",
            "state": "active",
            "baseline": {
                "descriptionDigest": "sha256:test",
                "requirements": [
                    {"id": f"REQ-{index:012X}", "section": "Scope", "text": "x" * 200}
                    for index in range(400)
                ],
            },
        }

        with self.assertRaisesRegex(SystemExit, "Shorten the managed Jira description"):
            with_state(oversized, "completed")


if __name__ == "__main__":
    unittest.main()

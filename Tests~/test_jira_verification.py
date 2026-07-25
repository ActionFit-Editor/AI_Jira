from __future__ import annotations

import sys
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PACKAGE_ROOT / "Tools~"
sys.path.insert(0, str(TOOLS_DIR))

from jira_completion import COMPLETION_PROPERTY_KEY, build_active_property, with_state
from jira_description import parse_description_contract, prepend_qa_record
from jira_statuses import (
    lifecycle_state,
    ordinary_done_statuses,
    require_statuses,
    verification_state,
)
from jira_verification import (
    apply_automatic_result,
    development_complete_target,
    validate_verification_plan,
)
from jira_work_items import build_jql, query_work_item
from start_session import require_prerequisites_done
from transition_issue import complete_issue, require_transition_targets
from verify_session import finalize_verification, required_targets_for_status


LEGACY_STATUSES = {
    "todo": "해야 할 일",
    "progress": "개발 진행 중",
    "done": "개발 완료",
}
EXTENDED_STATUSES = {
    **LEGACY_STATUSES,
    "done_auto": "개발 완료 - 자동 검증 필요",
    "done_manual": "개발 완료 - 수동 검증 필요",
    "done_verified": "개발 완료 - 검증 완료",
}
COMMIT = "a" * 40
OTHER_COMMIT = "b" * 40
PR_URL = "https://github.com/ActionFitGames/Cat_Merge_Cafe/pull/1655"


def managed_description(*, unverified: str = "자동 Editor 확인, 수동 UX 확인") -> str:
    base = """## QA 확인 필요 사항

### 계획
- 확인 항목: 자동 및 수동 검증 상태

---

## Auto Start
- Allowed: yes
- Prerequisites: none
- Decisions Required: none

## Goal
- Separate development completion from deferred validation.

## Scope
- Add an automatic verification queue.

## Out of Scope
- Package publishing.

## Completion Criteria
- Preserve evidence for every result.

## Validation Plan
- Required validation may use editor-simulated evidence.
- Conditional device-verified evidence requires separate approval.
- Player builds are intentionally excluded.

## Dependencies and Risks
- Jira transitions must exist.
"""
    return prepend_qa_record(
        base,
        "MCC-1655",
        "2026-07-25",
        f"""- 변경 요약: 검증 상태와 자동 QA 구현
- 검증 결과: Python 테스트 통과
- 미검증 항목: {unverified}
- QA 확인 항목: 상태 전이와 후보 고정
- 위험 영역: Jira property와 상태 보상""",
    )


def active_session(description: str) -> dict:
    prepared = build_active_property(
        "MCC-1655",
        description,
        "2026-07-25T10:00:00.000+0900",
        session_id="session-1655",
        branch="MCC-1655-verification-lifecycle",
    )
    return with_state(prepared, "active")


def completion_review(session: dict) -> dict:
    return {
        "version": 1,
        "issueKey": "MCC-1655",
        "sessionId": session["sessionId"],
        "baselineDigest": session["baseline"]["descriptionDigest"],
        "prUrl": PR_URL,
        "requirements": [
            {"id": item["id"], "status": "complete", "evidence": ["test:pass"]}
            for item in session["baseline"]["requirements"]
        ],
    }


def verification_plan(*modes: str) -> dict:
    checks = []
    for index, mode in enumerate(modes, 1):
        checks.append(
            {
                "id": f"{mode.upper()}-{index:03d}",
                "mode": mode,
                "description": f"{mode} check {index}",
                "evidenceLevel": "automated" if mode == "automatic" else "manual",
                "status": "pending",
            }
        )
    return {
        "version": 1,
        "issueKey": "MCC-1655",
        "candidate": {
            "prUrl": PR_URL,
            "branch": "MCC-1655-verification-lifecycle",
            "commit": COMMIT,
        },
        "checks": checks,
    }


class ExtendedClient:
    def __init__(self, description: str, status: str = EXTENDED_STATUSES["progress"]) -> None:
        self.description = description
        self.status = status
        self.property = None
        self.fail_transition = False
        self.property_writes = []

    def get_issue(self, issue_key: str, fields=None) -> dict:
        return {
            "key": issue_key,
            "fields": {
                "status": {"name": self.status},
                "description": self.description,
                "updated": "2026-07-25T10:00:00.000+0900",
                "resolution": None,
            },
        }

    def get_issue_property(self, issue_key: str, property_key: str):
        if property_key != COMPLETION_PROPERTY_KEY:
            raise AssertionError(property_key)
        return self.property

    def set_issue_property(self, issue_key: str, property_key: str, value: dict) -> None:
        if property_key != COMPLETION_PROPERTY_KEY:
            raise AssertionError(property_key)
        self.property = value
        self.property_writes.append(value)

    def delete_issue_property(self, issue_key: str, property_key: str) -> None:
        self.property = None

    def list_transitions(self, issue_key: str) -> list[dict]:
        destinations = {
            EXTENDED_STATUSES["todo"],
            EXTENDED_STATUSES["progress"],
            EXTENDED_STATUSES["done"],
            EXTENDED_STATUSES["done_auto"],
            EXTENDED_STATUSES["done_manual"],
            EXTENDED_STATUSES["done_verified"],
        }
        return [
            {"id": status, "name": status, "to": {"name": status}}
            for status in destinations
        ]

    def transition_issue(self, issue_key: str, transition_id: str) -> dict:
        if self.fail_transition:
            raise SystemExit("transition failed")
        self.status = transition_id
        return {}


class DetailApi:
    def __init__(self, status: str) -> None:
        self.status = status

    def get_issue(self, issue_key: str, fields: list[str]) -> dict:
        return {
            "key": issue_key,
            "fields": {
                "summary": "검증 상태",
                "status": {"name": self.status},
                "updated": "2026-07-25T10:00:00.000+0900",
                "description": "",
                "project": {"key": "MCC"},
            },
        }


class PrerequisiteClient:
    def __init__(self, statuses: dict[str, str]) -> None:
        self.statuses = statuses

    def get_issue(self, issue_key: str, fields=None) -> dict:
        return {
            "fields": {
                "status": {"name": self.statuses[issue_key]},
                "resolution": None,
            }
        }


class JiraVerificationTests(unittest.TestCase):
    def test_status_contract_preserves_legacy_and_rejects_partial_or_duplicate_extended(self) -> None:
        self.assertEqual(
            LEGACY_STATUSES,
            require_statuses({"statuses": LEGACY_STATUSES}),
        )
        with self.assertRaisesRegex(SystemExit, "partial"):
            require_statuses(
                {
                    "statuses": {
                        **LEGACY_STATUSES,
                        "done_auto": EXTENDED_STATUSES["done_auto"],
                    }
                }
            )
        with self.assertRaisesRegex(SystemExit, "distinct"):
            require_statuses(
                {
                    "statuses": {
                        **EXTENDED_STATUSES,
                        "done_auto": EXTENDED_STATUSES["done"],
                    }
                }
            )
        self.assertEqual(
            EXTENDED_STATUSES,
            require_statuses({"statuses": EXTENDED_STATUSES}),
        )

    def test_extended_filters_do_not_reuse_todo_all_or_resolution_filter(self) -> None:
        config = {"project_key": "MCC", "statuses": EXTENDED_STATUSES}

        automatic_jql, automatic = build_jql(config, "automatic-validation")
        all_jql, all_statuses = build_jql(config, "all")

        self.assertEqual([EXTENDED_STATUSES["done_auto"]], automatic)
        self.assertNotIn("resolution = Unresolved", automatic_jql)
        self.assertEqual(
            [EXTENDED_STATUSES["todo"], EXTENDED_STATUSES["progress"]],
            all_statuses,
        )
        self.assertIn("resolution = Unresolved", all_jql)
        self.assertNotIn(EXTENDED_STATUSES["done_auto"], all_jql)

    def test_detail_reports_manual_and_verified_states(self) -> None:
        config = {
            "jira_base_url": "https://actionfit.atlassian.net",
            "project_key": "MCC",
            "statuses": EXTENDED_STATUSES,
        }

        manual = query_work_item(
            config,
            "MCC-1655",
            api=DetailApi(EXTENDED_STATUSES["done_manual"]),
        )
        verified = query_work_item(
            config,
            "MCC-1655",
            api=DetailApi(EXTENDED_STATUSES["done_verified"]),
        )

        self.assertEqual("manual-validation", manual["lifecycleState"])
        self.assertTrue(manual["verificationState"]["developmentComplete"])
        self.assertEqual("verified", verified["verificationState"]["state"])
        self.assertEqual(
            EXTENDED_STATUSES["done_verified"],
            verified["configuredStatuses"]["done_verified"],
        )

    def test_all_development_complete_statuses_satisfy_ordinary_prerequisites(self) -> None:
        self.assertEqual(
            {
                EXTENDED_STATUSES["done"],
                EXTENDED_STATUSES["done_auto"],
                EXTENDED_STATUSES["done_manual"],
                EXTENDED_STATUSES["done_verified"],
            },
            ordinary_done_statuses(EXTENDED_STATUSES),
        )
        client = PrerequisiteClient(
            {
                "MCC-1": EXTENDED_STATUSES["done_auto"],
                "MCC-2": EXTENDED_STATUSES["done_verified"],
            }
        )
        ordinary = managed_description().replace(
            "- Prerequisites: none",
            "- Prerequisites: MCC-1",
        )
        require_prerequisites_done(client, "MCC-1655", ordinary, EXTENDED_STATUSES)

        verified_only = ordinary.replace("MCC-1", "MCC-1 [verified]")
        with self.assertRaisesRegex(SystemExit, "is not verified"):
            require_prerequisites_done(
                client,
                "MCC-1655",
                verified_only,
                EXTENDED_STATUSES,
            )
        verified_only = verified_only.replace("MCC-1", "MCC-2")
        require_prerequisites_done(
            client,
            "MCC-1655",
            verified_only,
            EXTENDED_STATUSES,
        )
        contract = parse_description_contract(verified_only)
        self.assertTrue(
            contract["autoStart"]["prerequisiteRequirements"][0]["requiresVerified"]
        )

    def test_verification_plan_rejects_arbitrary_commands_and_unapproved_device_work(self) -> None:
        description = managed_description()
        session = active_session(description)
        plan = verification_plan("automatic")
        plan["checks"][0]["command"] = "rm -rf something"
        with self.assertRaisesRegex(SystemExit, "executable Jira text"):
            validate_verification_plan(
                plan,
                issue_key="MCC-1655",
                session=session,
                pr_url=PR_URL,
                description=description,
            )

        plan = verification_plan("automatic")
        plan["candidate"]["Commands"] = ["python unsafe.py"]
        with self.assertRaisesRegex(SystemExit, r"\$\.candidate\.Commands"):
            validate_verification_plan(
                plan,
                issue_key="MCC-1655",
                session=session,
                pr_url=PR_URL,
                description=description,
            )

        plan = verification_plan("automatic")
        plan["checks"][0]["evidenceLevel"] = "player-build"
        with self.assertRaisesRegex(SystemExit, "does not explicitly authorize"):
            validate_verification_plan(
                plan,
                issue_key="MCC-1655",
                session=session,
                pr_url=PR_URL,
                description=description,
            )

    def test_completion_routes_automatic_before_manual_and_preserves_candidate(self) -> None:
        description = managed_description()
        client = ExtendedClient(description)
        client.property = active_session(description)

        completed = complete_issue(
            client,
            "MCC-1655",
            EXTENDED_STATUSES,
            PR_URL,
            completion_review(client.property),
            verification_plan("automatic", "manual"),
        )

        self.assertEqual(EXTENDED_STATUSES["done_auto"], client.status)
        self.assertEqual("awaiting-automatic-validation", completed["state"])
        self.assertEqual(COMMIT, completed["verification"]["candidate"]["commit"])
        self.assertEqual(
            EXTENDED_STATUSES["done_auto"],
            completed["developmentCompleteStatus"],
        )

    def test_completion_routes_manual_or_verified_from_remaining_checks(self) -> None:
        description = managed_description()
        session = active_session(description)
        manual = validate_verification_plan(
            verification_plan("manual"),
            issue_key="MCC-1655",
            session=session,
            pr_url=PR_URL,
            description=description,
        )
        self.assertEqual(
            (EXTENDED_STATUSES["done_manual"], "awaiting-manual-validation"),
            development_complete_target(EXTENDED_STATUSES, manual),
        )

        verified_description = managed_description(unverified="없음")
        verified_session = active_session(verified_description)
        client = ExtendedClient(verified_description)
        client.property = verified_session
        completed = complete_issue(
            client,
            "MCC-1655",
            EXTENDED_STATUSES,
            PR_URL,
            completion_review(verified_session),
            verification_plan(),
        )
        self.assertEqual(EXTENDED_STATUSES["done_verified"], client.status)
        self.assertEqual("completed", completed["state"])

    def test_deferred_completion_requires_named_unverified_work(self) -> None:
        description = managed_description(unverified="없음")
        client = ExtendedClient(description)
        client.property = active_session(description)

        with self.assertRaisesRegex(SystemExit, "must name pending validation"):
            complete_issue(
                client,
                "MCC-1655",
                EXTENDED_STATUSES,
                PR_URL,
                completion_review(client.property),
                verification_plan("automatic"),
            )

        self.assertEqual(EXTENDED_STATUSES["progress"], client.status)
        self.assertEqual("active", client.property["state"])

    def test_automatic_pass_advances_to_manual_then_verified(self) -> None:
        description = managed_description()
        session = active_session(description)
        plan = validate_verification_plan(
            verification_plan("automatic", "manual"),
            issue_key="MCC-1655",
            session=session,
            pr_url=PR_URL,
            description=description,
        )
        session = with_state(
            session,
            "awaiting-automatic-validation",
            verification=plan,
        )
        result = {
            "version": 1,
            "issueKey": "MCC-1655",
            "outcome": "passed",
            "reason": "all-checks-passed",
            "resumeCondition": "",
            "evidence": ["candidate checked"],
            "checks": [
                {
                    "id": "AUTOMATIC-001",
                    "status": "passed",
                    "evidence": ["test:pass"],
                }
            ],
        }

        updated, target = apply_automatic_result(
            "MCC-1655", session, result, COMMIT
        )

        self.assertEqual("done_manual", target)
        self.assertEqual("awaiting-manual-validation", updated["state"])

        only_auto_plan = validate_verification_plan(
            verification_plan("automatic"),
            issue_key="MCC-1655",
            session=active_session(managed_description(unverified="없음")),
            pr_url=PR_URL,
            description=managed_description(unverified="없음"),
        )
        only_auto_session = with_state(
            active_session(managed_description(unverified="없음")),
            "awaiting-automatic-validation",
            verification=only_auto_plan,
        )
        _, target = apply_automatic_result(
            "MCC-1655", only_auto_session, result, COMMIT
        )
        self.assertEqual("done_verified", target)

    def test_defect_returns_todo_and_environment_blocker_preserves_pending_queue(self) -> None:
        description = managed_description()
        session = active_session(description)
        plan = validate_verification_plan(
            verification_plan("automatic"),
            issue_key="MCC-1655",
            session=session,
            pr_url=PR_URL,
            description=description,
        )
        session = with_state(
            session,
            "awaiting-automatic-validation",
            verification=plan,
        )
        defect = {
            "version": 1,
            "issueKey": "MCC-1655",
            "outcome": "defect",
            "reason": "related-defect",
            "resumeCondition": "Fix the related regression and create a new candidate.",
            "evidence": ["assertion failed"],
            "checks": [
                {
                    "id": "AUTOMATIC-001",
                    "status": "failed",
                    "evidence": ["failure log"],
                }
            ],
        }
        updated, target = apply_automatic_result(
            "MCC-1655", session, defect, COMMIT
        )
        self.assertEqual("todo", target)
        self.assertEqual("closed-defect", updated["state"])

        blocked = {
            "version": 1,
            "issueKey": "MCC-1655",
            "outcome": "blocked",
            "reason": "environment",
            "resumeCondition": "Connect the required device.",
            "evidence": ["device unavailable"],
            "checks": [
                {
                    "id": "AUTOMATIC-001",
                    "status": "blocked",
                    "evidence": ["no device"],
                }
            ],
        }
        updated, target = apply_automatic_result(
            "MCC-1655", session, blocked, COMMIT
        )
        self.assertEqual("done_auto", target)
        self.assertEqual("pending", updated["verification"]["checks"][0]["status"])
        self.assertEqual(
            "blocked",
            updated["verification"]["checks"][0]["lastAttempt"]["status"],
        )

    def test_stale_candidate_is_recorded_without_running_checks(self) -> None:
        description = managed_description()
        session = active_session(description)
        plan = validate_verification_plan(
            verification_plan("automatic"),
            issue_key="MCC-1655",
            session=session,
            pr_url=PR_URL,
            description=description,
        )
        session = with_state(
            session,
            "awaiting-automatic-validation",
            verification=plan,
        )
        stale = {
            "version": 1,
            "issueKey": "MCC-1655",
            "outcome": "blocked",
            "reason": "stale-candidate",
            "resumeCondition": "Record and approve the new candidate revision.",
            "evidence": ["expected a..., observed b..."],
            "checks": [],
        }

        updated, target = apply_automatic_result(
            "MCC-1655", session, stale, OTHER_COMMIT
        )

        self.assertEqual("done_auto", target)
        self.assertEqual(
            OTHER_COMMIT,
            updated["verification"]["attempts"][-1]["observedCommit"],
        )
        self.assertEqual("pending", updated["verification"]["checks"][0]["status"])

        with self.assertRaisesRegex(SystemExit, "requires the observed commit to differ"):
            apply_automatic_result("MCC-1655", session, stale, COMMIT)

        stale_with_checks = {
            **stale,
            "checks": [
                {
                    "id": "AUTOMATIC-001",
                    "status": "blocked",
                    "evidence": ["check should not have run"],
                }
            ],
        }
        with self.assertRaisesRegex(SystemExit, "must not report executed checks"):
            apply_automatic_result(
                "MCC-1655",
                session,
                stale_with_checks,
                OTHER_COMMIT,
            )

    def test_transition_preflight_fails_before_property_write(self) -> None:
        class MissingTransitionClient(ExtendedClient):
            def list_transitions(self, issue_key: str) -> list[dict]:
                return [
                    {
                        "id": EXTENDED_STATUSES["done_auto"],
                        "to": {"name": EXTENDED_STATUSES["done_auto"]},
                    }
                ]

        client = MissingTransitionClient(managed_description())
        with self.assertRaisesRegex(SystemExit, "missing configured destination"):
            require_transition_targets(
                client,
                "MCC-1655",
                [
                    EXTENDED_STATUSES["done_auto"],
                    EXTENDED_STATUSES["done_manual"],
                ],
            )
        self.assertEqual([], client.property_writes)
        self.assertEqual(
            [
                EXTENDED_STATUSES["todo"],
                EXTENDED_STATUSES["done_manual"],
                EXTENDED_STATUSES["done_verified"],
            ],
            required_targets_for_status(
                EXTENDED_STATUSES["done_auto"], EXTENDED_STATUSES
            ),
        )

    def test_automatic_transition_failure_restores_previous_property(self) -> None:
        description = managed_description()
        session = active_session(description)
        plan = validate_verification_plan(
            verification_plan("automatic"),
            issue_key="MCC-1655",
            session=session,
            pr_url=PR_URL,
            description=description,
        )
        previous = with_state(
            session,
            "awaiting-automatic-validation",
            verification=plan,
        )
        client = ExtendedClient(
            description,
            status=EXTENDED_STATUSES["done_auto"],
        )
        client.property = previous
        client.fail_transition = True
        result = {
            "version": 1,
            "issueKey": "MCC-1655",
            "outcome": "passed",
            "reason": "all-checks-passed",
            "resumeCondition": "",
            "evidence": ["candidate checked"],
            "checks": [
                {
                    "id": "AUTOMATIC-001",
                    "status": "passed",
                    "evidence": ["test:pass"],
                }
            ],
        }

        with self.assertRaisesRegex(SystemExit, "transition failed"):
            finalize_verification(
                client,
                "MCC-1655",
                EXTENDED_STATUSES,
                COMMIT,
                result,
            )

        self.assertEqual(previous, client.property)
        self.assertEqual(EXTENDED_STATUSES["done_auto"], client.status)

    def test_state_helpers_keep_manual_user_transition_authoritative(self) -> None:
        self.assertEqual(
            "verified",
            lifecycle_state(EXTENDED_STATUSES["done_verified"], EXTENDED_STATUSES),
        )
        state = verification_state(
            EXTENDED_STATUSES["done_verified"], EXTENDED_STATUSES
        )
        self.assertTrue(state["developmentComplete"])
        self.assertEqual("verified", state["state"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from copy import deepcopy
from datetime import date
import sys
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_TOOLS = PACKAGE_ROOT / "Tools~"
sys.path.insert(0, str(PACKAGE_TOOLS))

from jira_completion import COMPLETION_PROPERTY_KEY, extract_snapshot
from jira_legacy_reclassification import (
    LEGACY_RECLASSIFICATION_PROPERTY_KEY,
    apply_reclassification,
    prepare_reclassification,
    rollback_reclassification,
)
from test_jira_description import managed_description


ISSUE_KEY = "MCC-1661"
SOURCE_UPDATED = "2026-07-25T00:00:00.000+0000"
MIGRATION_ID = "11111111-2222-4333-8444-555555555555"
PR_URL = "https://github.com/ActionFitGames/Cat_Merge_Cafe/pull/1661"
BRANCH = "MCC-1661-legacy-work"
COMMIT = "0123456789abcdef0123456789abcdef01234567"


def statuses() -> dict[str, str]:
    return {
        "todo": "해야 할 일",
        "progress": "개발 진행 중",
        "done": "개발 완료",
        "done_auto": "개발 완료 - 자동 검증 필요",
        "done_manual": "개발 완료 - 수동 검증 필요",
        "done_verified": "개발 완료 - 검증 완료",
    }


def config(**automation_overrides) -> dict:
    gates = {
        "dry_run": False,
        "allow_transition": True,
        "allow_description_prepend_qa": True,
    }
    gates.update(automation_overrides)
    return {
        "project_key": "MCC",
        "statuses": statuses(),
        "automation": gates,
    }


def verification_plan(*, mode: str = "manual", status: str = "pending") -> dict:
    evidence_level = "manual" if mode == "manual" else "automated"
    check = {
        "id": "LEGACY-CHECK-001",
        "mode": mode,
        "description": "Verify the remaining legacy functional behavior.",
        "evidenceLevel": evidence_level,
        "status": status,
    }
    if status == "passed":
        check["evidence"] = ["Existing repository-owned validation passed."]
        check["completedAt"] = "2026-07-25T00:00:00Z"
    return {
        "version": 1,
        "issueKey": ISSUE_KEY,
        "candidate": {
            "prUrl": PR_URL,
            "branch": BRANCH,
            "commit": COMMIT,
        },
        "checks": [check],
    }


def review(description: str, *, candidate: dict | None = None) -> dict:
    baseline = extract_snapshot(description)
    candidate_value = candidate or verification_plan()["candidate"]
    return {
        "version": 1,
        "issueKey": ISSUE_KEY,
        "migrationId": MIGRATION_ID,
        "expectedUpdated": SOURCE_UPDATED,
        "approvalSummary": "Approved legacy todo reclassification after exact implementation review.",
        "reviewedAt": "2026-07-25T00:00:00Z",
        "candidate": deepcopy(candidate_value),
        "implementationEvidence": ["Merged PR implements every managed requirement."],
        "validationEvidence": ["Focused repository tests passed."],
        "requirements": [
            {
                "id": item["id"],
                "status": "complete",
                "evidence": [f'{item["id"]} is covered by the merged implementation and tests.'],
            }
            for item in baseline["requirements"]
        ],
    }


def qa_artifact() -> dict:
    return {
        "version": 1,
        "issueKey": ISSUE_KEY,
        "date": date.today().isoformat(),
        "record": {
            "변경 요약": "기존 todo 구현 증거를 검토해 수동 검증 대기로 재분류",
            "검증 결과": "요구사항 전체와 후보 PR 및 저장소 검증 증거 확인",
            "미검증 항목": "승인된 환경의 남은 수동 기능 확인",
            "QA 확인 항목": "기록된 candidate와 수동 확인 항목 점검",
            "위험 영역": "Jira lifecycle, description, issue property",
        },
    }


class FakeClient:
    def __init__(self, *, description: str | None = None) -> None:
        self.issue = {
            "key": ISSUE_KEY,
            "fields": {
                "status": {"name": statuses()["todo"]},
                "description": description or managed_description(),
                "updated": SOURCE_UPDATED,
                "resolution": None,
                "project": {"key": "MCC"},
                "assignee": {"accountId": "account-1"},
            },
        }
        self.current_user = {"accountId": "account-1"}
        self.properties: dict[str, dict] = {
            COMPLETION_PROPERTY_KEY: {
                "version": 1,
                "state": "closed-incomplete",
                "issueKey": ISSUE_KEY,
            }
        }
        self.calls: list[tuple] = []
        self.writes: list[tuple] = []
        self.fail_once: str | None = None
        self.drop_once: str | None = None
        self.fail_missing_migration_read_once = False
        self._update_sequence = 0

    def _fail(self, name: str) -> None:
        if self.fail_once == name:
            self.fail_once = None
            raise SystemExit(f"injected {name} failure")

    def _touch(self) -> None:
        self._update_sequence += 1
        self.issue["fields"]["updated"] = f"2026-07-25T00:00:0{self._update_sequence}.000+0000"

    def _drop(self, name: str) -> bool:
        if self.drop_once == name:
            self.drop_once = None
            return True
        return False

    def get_issue(self, issue_key: str, fields: list[str] | None = None) -> dict:
        self.calls.append(("get_issue", tuple(fields or [])))
        return deepcopy(self.issue)

    def get_current_user(self) -> dict:
        self.calls.append(("get_current_user",))
        return deepcopy(self.current_user)

    def get_issue_property(self, issue_key: str, property_key: str):
        self.calls.append(("get_property", property_key))
        if (
            self.fail_missing_migration_read_once
            and property_key == LEGACY_RECLASSIFICATION_PROPERTY_KEY
            and property_key not in self.properties
        ):
            self.fail_missing_migration_read_once = False
            raise SystemExit("injected post-delete migration read failure")
        return deepcopy(self.properties.get(property_key))

    def set_issue_property(self, issue_key: str, property_key: str, value: dict) -> None:
        name = (
            "set:migration"
            if property_key == LEGACY_RECLASSIFICATION_PROPERTY_KEY
            else "set:completion"
        )
        self.writes.append(("set_property", property_key))
        self._fail(name)
        if self._drop(name):
            return
        self.properties[property_key] = deepcopy(value)
        self._touch()

    def delete_issue_property(self, issue_key: str, property_key: str) -> None:
        self.writes.append(("delete_property", property_key))
        self._fail(f"delete:{property_key}")
        self.properties.pop(property_key, None)
        self._touch()

    def update_description(self, issue_key: str, description: str) -> dict:
        self.writes.append(("update_description",))
        self._fail("update:description")
        if self._drop("update:description"):
            return {}
        self.issue["fields"]["description"] = description
        self._touch()
        return {}

    def list_transitions(self, issue_key: str) -> list[dict]:
        self.calls.append(("list_transitions",))
        return [
            {"id": "10", "name": "progress", "to": {"name": statuses()["progress"]}},
            {"id": "20", "name": "todo", "to": {"name": statuses()["todo"]}},
            {"id": "30", "name": "auto", "to": {"name": statuses()["done_auto"]}},
            {"id": "40", "name": "manual", "to": {"name": statuses()["done_manual"]}},
            {"id": "50", "name": "verified", "to": {"name": statuses()["done_verified"]}},
        ]

    def transition_issue(self, issue_key: str, transition_id: str) -> dict:
        target_by_id = {
            "20": statuses()["todo"],
            "30": statuses()["done_auto"],
            "40": statuses()["done_manual"],
            "50": statuses()["done_verified"],
        }
        target = target_by_id[transition_id]
        self.writes.append(("transition", target))
        self._fail(f"transition:{target}")
        if self._drop(f"transition:{target}"):
            return {}
        self.issue["fields"]["status"] = {"name": target}
        self._touch()
        return {}


def artifacts(description: str, *, mode: str = "manual") -> tuple[dict, dict, dict]:
    plan = verification_plan(mode=mode)
    return review(description, candidate=plan["candidate"]), plan, qa_artifact()


class JiraLegacyReclassificationTests(unittest.TestCase):
    def test_inspect_is_read_only_and_manual_plan_derives_manual_target(self) -> None:
        client = FakeClient()
        review_value, plan, qa = artifacts(client.issue["fields"]["description"])

        result, context = prepare_reclassification(
            client,
            config(),
            statuses(),
            ISSUE_KEY,
            operation="inspect",
            expected_updated=SOURCE_UPDATED,
            review_value=review_value,
            verification_value=plan,
            qa_value=qa,
            enforce_write_gates=False,
        )

        self.assertEqual([], client.writes)
        self.assertTrue(result["eligible"])
        self.assertEqual(statuses()["done_manual"], result["targetStatus"])
        self.assertEqual("awaiting-manual-validation", context["propertyState"])

    def test_automatic_pending_check_takes_precedence(self) -> None:
        client = FakeClient()
        review_value, plan, qa = artifacts(
            client.issue["fields"]["description"],
            mode="automatic",
        )

        result, context = prepare_reclassification(
            client,
            config(),
            statuses(),
            ISSUE_KEY,
            operation="preflight",
            expected_updated=SOURCE_UPDATED,
            review_value=review_value,
            verification_value=plan,
            qa_value=qa,
            enforce_write_gates=True,
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(statuses()["done_auto"], result["targetStatus"])
        self.assertEqual("awaiting-automatic-validation", context["propertyState"])

    def test_plan_without_pending_checks_is_rejected(self) -> None:
        client = FakeClient()
        plan = verification_plan(status="passed")
        review_value = review(
            client.issue["fields"]["description"],
            candidate=plan["candidate"],
        )

        result, _ = prepare_reclassification(
            client,
            config(),
            statuses(),
            ISSUE_KEY,
            operation="preflight",
            expected_updated=SOURCE_UPDATED,
            review_value=review_value,
            verification_value=plan,
            qa_value=qa_artifact(),
            enforce_write_gates=True,
        )

        self.assertFalse(result["eligible"])
        self.assertIn(
            "direct verified migration is forbidden",
            " ".join(item["message"] for item in result["blockers"]),
        )

    def test_preflight_rejects_identity_snapshot_property_and_gate_failures(self) -> None:
        cases = {
            "project": lambda client, cfg: client.issue["fields"].update(
                {"project": {"key": "OTHER"}}
            ),
            "assignee": lambda client, cfg: client.issue["fields"].update(
                {"assignee": {"accountId": "other"}}
            ),
            "resolution": lambda client, cfg: client.issue["fields"].update(
                {"resolution": {"name": "Done"}}
            ),
            "status": lambda client, cfg: client.issue["fields"].update(
                {"status": {"name": statuses()["progress"]}}
            ),
            "active-property": lambda client, cfg: client.properties.update(
                {
                    COMPLETION_PROPERTY_KEY: {
                        "version": 1,
                        "state": "active",
                        "issueKey": ISSUE_KEY,
                    }
                }
            ),
            "backup": lambda client, cfg: client.properties.update(
                {
                    LEGACY_RECLASSIFICATION_PROPERTY_KEY: {
                        "version": 1,
                        "state": "applied",
                        "issueKey": ISSUE_KEY,
                        "migrationId": "other",
                    }
                }
            ),
            "dry-run": lambda client, cfg: cfg["automation"].update(
                {"dry_run": True}
            ),
            "transition-gate": lambda client, cfg: cfg["automation"].update(
                {"allow_transition": False}
            ),
            "qa-gate": lambda client, cfg: cfg["automation"].update(
                {"allow_description_prepend_qa": False}
            ),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                client = FakeClient()
                configured = config()
                mutate(client, configured)
                review_value, plan, qa = artifacts(
                    client.issue["fields"]["description"]
                )
                result, _ = prepare_reclassification(
                    client,
                    configured,
                    statuses(),
                    ISSUE_KEY,
                    operation="preflight",
                    expected_updated=SOURCE_UPDATED,
                    review_value=review_value,
                    verification_value=plan,
                    qa_value=qa,
                    enforce_write_gates=True,
                )
                self.assertFalse(result["eligible"])
                self.assertEqual([], client.writes)

    def test_preflight_rejects_stale_updated_and_incomplete_coverage(self) -> None:
        client = FakeClient()
        review_value, plan, qa = artifacts(client.issue["fields"]["description"])
        review_value["requirements"].pop()

        result, _ = prepare_reclassification(
            client,
            config(),
            statuses(),
            ISSUE_KEY,
            operation="preflight",
            expected_updated="stale",
            review_value=review_value,
            verification_value=plan,
            qa_value=qa,
            enforce_write_gates=True,
        )

        codes = {item["code"] for item in result["blockers"]}
        self.assertIn("stale-updated", codes)
        self.assertIn("legacy-review", codes)
        self.assertEqual([], client.writes)

    def test_preflight_rejects_forbidden_action_fields_and_missing_transition(self) -> None:
        client = FakeClient()
        review_value, plan, qa = artifacts(client.issue["fields"]["description"])
        review_value["command"] = "never run Jira text"
        client.list_transitions = lambda issue_key: [
            {"id": "20", "name": "todo", "to": {"name": statuses()["todo"]}}
        ]

        result, _ = prepare_reclassification(
            client,
            config(),
            statuses(),
            ISSUE_KEY,
            operation="preflight",
            expected_updated=SOURCE_UPDATED,
            review_value=review_value,
            verification_value=plan,
            qa_value=qa,
            enforce_write_gates=True,
        )

        codes = {item["code"] for item in result["blockers"]}
        self.assertIn("legacy-review", codes)
        self.assertIn("transitions", codes)

    def test_compressed_backup_keeps_large_legacy_description_bounded(self) -> None:
        description = managed_description() + "\n## Legacy Notes\n" + ("A" * 60000)
        client = FakeClient(description=description)
        review_value, plan, qa = artifacts(description)

        result, context = prepare_reclassification(
            client,
            config(),
            statuses(),
            ISSUE_KEY,
            operation="preflight",
            expected_updated=SOURCE_UPDATED,
            review_value=review_value,
            verification_value=plan,
            qa_value=qa,
            enforce_write_gates=True,
        )

        self.assertTrue(result["eligible"])
        encoded = context["migrationProperty"]["source"]["descriptionBackup"]
        self.assertEqual("gzip+base64", encoded["encoding"])
        self.assertLess(len(encoded["data"]), 1000)

    def test_apply_writes_in_order_and_is_idempotent_for_exact_migration(self) -> None:
        client = FakeClient()
        review_value, plan, qa = artifacts(client.issue["fields"]["description"])

        result = apply_reclassification(
            client,
            config(),
            statuses(),
            ISSUE_KEY,
            expected_updated=SOURCE_UPDATED,
            review_value=review_value,
            verification_value=plan,
            qa_value=qa,
        )

        self.assertTrue(result["applied"])
        self.assertFalse(result["idempotent"])
        self.assertEqual(
            [
                ("set_property", LEGACY_RECLASSIFICATION_PROPERTY_KEY),
                ("update_description",),
                ("set_property", COMPLETION_PROPERTY_KEY),
                ("transition", statuses()["done_manual"]),
            ],
            client.writes,
        )
        self.assertEqual(statuses()["done_manual"], client.issue["fields"]["status"]["name"])
        self.assertEqual(
            "awaiting-manual-validation",
            client.properties[COMPLETION_PROPERTY_KEY]["state"],
        )
        self.assertTrue(
            client.properties[LEGACY_RECLASSIFICATION_PROPERTY_KEY]["source"][
                "completionPropertyPresent"
            ]
        )
        self.assertEqual(
            "gzip+base64",
            client.properties[LEGACY_RECLASSIFICATION_PROPERTY_KEY]["source"][
                "completionPropertyBackup"
            ]["encoding"],
        )

        client.writes.clear()
        client.issue["fields"]["resolution"] = {"name": "Done"}
        retried = apply_reclassification(
            client,
            config(),
            statuses(),
            ISSUE_KEY,
            expected_updated=SOURCE_UPDATED,
            review_value=review_value,
            verification_value=plan,
            qa_value=qa,
        )
        self.assertTrue(retried["idempotent"])
        self.assertEqual([], client.writes)

    def test_every_apply_failure_boundary_compensates_to_exact_source(self) -> None:
        for failure in (
            "set:migration",
            "update:description",
            "set:completion",
            f"transition:{statuses()['done_manual']}",
        ):
            with self.subTest(failure=failure):
                client = FakeClient()
                source_issue = deepcopy(client.issue)
                source_property = deepcopy(client.properties[COMPLETION_PROPERTY_KEY])
                review_value, plan, qa = artifacts(
                    client.issue["fields"]["description"]
                )
                client.fail_once = failure

                with self.assertRaisesRegex(SystemExit, "apply failed"):
                    apply_reclassification(
                        client,
                        config(),
                        statuses(),
                        ISSUE_KEY,
                        expected_updated=SOURCE_UPDATED,
                        review_value=review_value,
                        verification_value=plan,
                        qa_value=qa,
                    )

                self.assertEqual(
                    source_issue["fields"]["status"],
                    client.issue["fields"]["status"],
                )
                self.assertEqual(
                    source_issue["fields"]["description"].strip(),
                    client.issue["fields"]["description"].strip(),
                )
                self.assertEqual(
                    source_property,
                    client.properties.get(COMPLETION_PROPERTY_KEY),
                )
                self.assertNotIn(
                    LEGACY_RECLASSIFICATION_PROPERTY_KEY,
                    client.properties,
                )

    def test_every_apply_readback_mismatch_compensates_to_exact_source(self) -> None:
        for dropped in (
            "set:migration",
            "update:description",
            "set:completion",
            f"transition:{statuses()['done_manual']}",
        ):
            with self.subTest(dropped=dropped):
                client = FakeClient()
                source_issue = deepcopy(client.issue)
                source_property = deepcopy(client.properties[COMPLETION_PROPERTY_KEY])
                review_value, plan, qa = artifacts(
                    client.issue["fields"]["description"]
                )
                client.drop_once = dropped

                with self.assertRaisesRegex(SystemExit, "apply failed"):
                    apply_reclassification(
                        client,
                        config(),
                        statuses(),
                        ISSUE_KEY,
                        expected_updated=SOURCE_UPDATED,
                        review_value=review_value,
                        verification_value=plan,
                        qa_value=qa,
                    )

                self.assertEqual(
                    source_issue["fields"]["status"],
                    client.issue["fields"]["status"],
                )
                self.assertEqual(
                    source_issue["fields"]["description"].strip(),
                    client.issue["fields"]["description"].strip(),
                )
                self.assertEqual(
                    source_property,
                    client.properties.get(COMPLETION_PROPERTY_KEY),
                )
                self.assertNotIn(
                    LEGACY_RECLASSIFICATION_PROPERTY_KEY,
                    client.properties,
                )

    def test_rollback_requires_unchanged_snapshot_and_restores_source(self) -> None:
        client = FakeClient()
        source_description = client.issue["fields"]["description"]
        source_property = deepcopy(client.properties[COMPLETION_PROPERTY_KEY])
        review_value, plan, qa = artifacts(source_description)
        applied = apply_reclassification(
            client,
            config(),
            statuses(),
            ISSUE_KEY,
            expected_updated=SOURCE_UPDATED,
            review_value=review_value,
            verification_value=plan,
            qa_value=qa,
        )
        current_updated = applied["current"]["updated"]

        result = rollback_reclassification(
            client,
            config(),
            statuses(),
            ISSUE_KEY,
            migration_id=MIGRATION_ID,
            expected_updated=current_updated,
        )

        self.assertTrue(result["rolledBack"])
        self.assertEqual(statuses()["todo"], client.issue["fields"]["status"]["name"])
        self.assertEqual(source_description.strip(), client.issue["fields"]["description"].strip())
        self.assertEqual(source_property, client.properties.get(COMPLETION_PROPERTY_KEY))
        self.assertNotIn(LEGACY_RECLASSIFICATION_PROPERTY_KEY, client.properties)

    def test_rollback_refuses_later_description_edit(self) -> None:
        client = FakeClient()
        review_value, plan, qa = artifacts(client.issue["fields"]["description"])
        applied = apply_reclassification(
            client,
            config(),
            statuses(),
            ISSUE_KEY,
            expected_updated=SOURCE_UPDATED,
            review_value=review_value,
            verification_value=plan,
            qa_value=qa,
        )
        client.issue["fields"]["description"] += "\nLater user edit."

        with self.assertRaisesRegex(SystemExit, "changed Jira description"):
            rollback_reclassification(
                client,
                config(),
                statuses(),
                ISSUE_KEY,
                migration_id=MIGRATION_ID,
                expected_updated=applied["current"]["updated"],
            )

    def test_rollback_rejects_tampered_source_and_target_statuses(self) -> None:
        for section, value, expected_message in (
            ("source", statuses()["progress"], "invalid source status"),
            ("target", statuses()["done_verified"], "invalid target status"),
        ):
            with self.subTest(section=section):
                client = FakeClient()
                review_value, plan, qa = artifacts(
                    client.issue["fields"]["description"]
                )
                applied = apply_reclassification(
                    client,
                    config(),
                    statuses(),
                    ISSUE_KEY,
                    expected_updated=SOURCE_UPDATED,
                    review_value=review_value,
                    verification_value=plan,
                    qa_value=qa,
                )
                client.properties[LEGACY_RECLASSIFICATION_PROPERTY_KEY][
                    section
                ]["status"] = value

                with self.assertRaisesRegex(SystemExit, expected_message):
                    rollback_reclassification(
                        client,
                        config(),
                        statuses(),
                        ISSUE_KEY,
                        migration_id=MIGRATION_ID,
                        expected_updated=applied["current"]["updated"],
                    )

    def test_every_rollback_failure_boundary_restores_migrated_state(self) -> None:
        for failure in (
            f"transition:{statuses()['todo']}",
            "set:completion",
            "update:description",
            f"delete:{LEGACY_RECLASSIFICATION_PROPERTY_KEY}",
        ):
            with self.subTest(failure=failure):
                client = FakeClient()
                review_value, plan, qa = artifacts(
                    client.issue["fields"]["description"]
                )
                applied = apply_reclassification(
                    client,
                    config(),
                    statuses(),
                    ISSUE_KEY,
                    expected_updated=SOURCE_UPDATED,
                    review_value=review_value,
                    verification_value=plan,
                    qa_value=qa,
                )
                migrated_description = client.issue["fields"]["description"]
                migrated_property = deepcopy(
                    client.properties[COMPLETION_PROPERTY_KEY]
                )
                client.fail_once = failure

                with self.assertRaisesRegex(SystemExit, "rollback failed"):
                    rollback_reclassification(
                        client,
                        config(),
                        statuses(),
                        ISSUE_KEY,
                        migration_id=MIGRATION_ID,
                        expected_updated=applied["current"]["updated"],
                    )

                self.assertEqual(
                    statuses()["done_manual"],
                    client.issue["fields"]["status"]["name"],
                )
                self.assertEqual(
                    migrated_description.strip(),
                    client.issue["fields"]["description"].strip(),
                )
                self.assertEqual(
                    migrated_property,
                    client.properties[COMPLETION_PROPERTY_KEY],
                )
                self.assertIn(
                    LEGACY_RECLASSIFICATION_PROPERTY_KEY,
                    client.properties,
                )

    def test_rollback_restores_migration_property_after_post_delete_read_failure(
        self,
    ) -> None:
        client = FakeClient()
        review_value, plan, qa = artifacts(client.issue["fields"]["description"])
        applied = apply_reclassification(
            client,
            config(),
            statuses(),
            ISSUE_KEY,
            expected_updated=SOURCE_UPDATED,
            review_value=review_value,
            verification_value=plan,
            qa_value=qa,
        )
        migrated_description = client.issue["fields"]["description"]
        migrated_property = deepcopy(client.properties[COMPLETION_PROPERTY_KEY])
        migration_property = deepcopy(
            client.properties[LEGACY_RECLASSIFICATION_PROPERTY_KEY]
        )
        client.fail_missing_migration_read_once = True

        with self.assertRaisesRegex(SystemExit, "rollback failed"):
            rollback_reclassification(
                client,
                config(),
                statuses(),
                ISSUE_KEY,
                migration_id=MIGRATION_ID,
                expected_updated=applied["current"]["updated"],
            )

        self.assertEqual(
            statuses()["done_manual"],
            client.issue["fields"]["status"]["name"],
        )
        self.assertEqual(
            migrated_description.strip(),
            client.issue["fields"]["description"].strip(),
        )
        self.assertEqual(
            migrated_property,
            client.properties[COMPLETION_PROPERTY_KEY],
        )
        self.assertEqual(
            migration_property,
            client.properties[LEGACY_RECLASSIFICATION_PROPERTY_KEY],
        )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Fail-closed contracts and orchestration for one legacy todo reclassification."""

from __future__ import annotations

import base64
from copy import deepcopy
from datetime import date
import gzip
import hashlib
import json
import re
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from jira_client import adf_to_text, automation
from jira_completion import (
    COMPLETION_PROPERTY_KEY,
    MAX_PROPERTY_BYTES,
    TERMINAL_PROPERTY_STATES,
    extract_snapshot,
    normalize_text,
    require_property_identity,
    require_property_size,
    utc_timestamp,
)
from jira_description import (
    parse_description_contract,
    prepend_qa_record,
    validate_qa_completion_record,
)
from jira_statuses import has_extended_lifecycle
from jira_verification import (
    development_complete_target,
    validate_verification_plan,
)
from transition_issue import find_transition


LEGACY_RECLASSIFICATION_PROPERTY_KEY = "actionfit.ai-jira.legacy-reclassification"
LEGACY_RECLASSIFICATION_VERSION = 1
FORBIDDEN_ACTION_FIELDS = {"command", "commands", "shell", "script"}
QA_FIELDS = (
    "변경 요약",
    "검증 결과",
    "미검증 항목",
    "QA 확인 항목",
    "위험 영역",
)
ISSUE_KEY_BOUNDARY = r"(?<![A-Z0-9]){issue_key}(?![A-Z0-9])"


def json_digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def text_digest(value: str) -> str:
    canonical = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def require_bounded_property(value: dict[str, Any], label: str) -> None:
    size = len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    if size > MAX_PROPERTY_BYTES:
        raise SystemExit(
            f"{label} is {size} bytes; Jira issue properties allow at most "
            f"{MAX_PROPERTY_BYTES} bytes."
        )


def encode_backup(value: Any, *, json_value: bool) -> dict[str, Any]:
    if json_value:
        raw = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        media_type = "application/json"
    else:
        raw = str(value).encode("utf-8")
        media_type = "text/plain; charset=utf-8"
    compressed = gzip.compress(raw, mtime=0)
    return {
        "encoding": "gzip+base64",
        "mediaType": media_type,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "data": base64.b64encode(compressed).decode("ascii"),
    }


def decode_backup(value: Any, *, json_value: bool) -> Any:
    if (
        not isinstance(value, dict)
        or value.get("encoding") != "gzip+base64"
        or not isinstance(value.get("data"), str)
        or not isinstance(value.get("sha256"), str)
    ):
        raise SystemExit("Legacy reclassification backup payload is invalid.")
    try:
        raw = gzip.decompress(base64.b64decode(value["data"], validate=True))
    except (ValueError, OSError) as error:
        raise SystemExit("Legacy reclassification backup payload cannot be decoded.") from error
    if hashlib.sha256(raw).hexdigest() != value["sha256"]:
        raise SystemExit("Legacy reclassification backup payload digest does not match.")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SystemExit("Legacy reclassification backup payload is not UTF-8.") from error
    if not json_value:
        return decoded
    try:
        return json.loads(decoded)
    except json.JSONDecodeError as error:
        raise SystemExit("Legacy reclassification JSON backup payload is invalid.") from error


def require_string(value: Any, label: str) -> str:
    result = normalize_text(str(value or ""))
    if not result:
        raise SystemExit(f"{label} must be a non-empty string.")
    return result


def require_evidence(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not normalize_text(item) for item in value)
    ):
        raise SystemExit(f"{label} requires at least one non-empty evidence string.")
    return [normalize_text(item) for item in value]


def forbidden_action_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).casefold() in FORBIDDEN_ACTION_FIELDS:
                found.append(child_path)
            found.extend(forbidden_action_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(forbidden_action_paths(child, f"{path}[{index}]"))
    return found


def require_migration_id(value: Any) -> str:
    migration_id = require_string(value, "Legacy review migrationId")
    try:
        parsed = UUID(migration_id)
    except ValueError as error:
        raise SystemExit("Legacy review migrationId must be an exact UUID.") from error
    if str(parsed) != migration_id.lower():
        raise SystemExit("Legacy review migrationId must use canonical lowercase UUID form.")
    return migration_id.lower()


def require_issue_branch(issue_key: str, branch: Any) -> str:
    branch_value = require_string(branch, "Legacy candidate branch")
    pattern = re.compile(
        ISSUE_KEY_BOUNDARY.format(issue_key=re.escape(issue_key.upper()))
    )
    if not pattern.search(branch_value.upper()):
        raise SystemExit("Legacy candidate branch must contain the exact Jira issue key.")
    return branch_value


def validate_legacy_review(
    value: dict[str, Any],
    *,
    issue_key: str,
    expected_updated: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("version") != LEGACY_RECLASSIFICATION_VERSION:
        raise SystemExit("Legacy review uses an unsupported contract version.")
    forbidden = forbidden_action_paths(value)
    if forbidden:
        raise SystemExit(
            "Legacy reviews cannot contain executable Jira text fields: "
            + ", ".join(forbidden)
        )
    if str(value.get("issueKey", "")).upper() != issue_key.upper():
        raise SystemExit("Legacy review belongs to a different Jira issue.")
    if str(value.get("expectedUpdated", "")) != expected_updated:
        raise SystemExit("Legacy review expectedUpdated does not match the approved Jira snapshot.")

    migration_id = require_migration_id(value.get("migrationId"))
    approval_summary = require_string(
        value.get("approvalSummary"), "Legacy review approvalSummary"
    )
    reviewed_at = require_string(value.get("reviewedAt"), "Legacy review reviewedAt")
    implementation_evidence = require_evidence(
        value.get("implementationEvidence"), "Legacy review implementationEvidence"
    )
    validation_evidence = require_evidence(
        value.get("validationEvidence"), "Legacy review validationEvidence"
    )

    review_candidate = value.get("candidate")
    if not isinstance(review_candidate, dict) or review_candidate != candidate:
        raise SystemExit(
            "Legacy review candidate must exactly match the verification-plan candidate."
        )

    expected_ids = {
        str(item["id"]) for item in baseline.get("requirements", [])
    }
    if not expected_ids:
        raise SystemExit("Legacy review requires a non-empty managed requirement baseline.")
    entries = value.get("requirements")
    if not isinstance(entries, list):
        raise SystemExit("Legacy review requires a requirements array.")

    normalized_requirements: list[dict[str, Any]] = []
    observed_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit("Each legacy review requirement must be an object.")
        requirement_id = str(entry.get("id", ""))
        if not requirement_id:
            raise SystemExit("Legacy review contains an empty requirement ID.")
        if requirement_id in observed_ids:
            raise SystemExit(
                f"Legacy review contains duplicate requirement ID: {requirement_id}."
            )
        if requirement_id not in expected_ids:
            raise SystemExit(
                f"Legacy review references unknown requirement ID: {requirement_id}."
            )
        if entry.get("status") != "complete":
            raise SystemExit(
                f"Legacy review requirement {requirement_id} must be complete."
            )
        normalized_requirements.append(
            {
                "id": requirement_id,
                "status": "complete",
                "evidence": require_evidence(
                    entry.get("evidence"),
                    f"Legacy review requirement {requirement_id}",
                ),
            }
        )
        observed_ids.add(requirement_id)

    if observed_ids != expected_ids:
        missing = sorted(expected_ids - observed_ids)
        raise SystemExit(
            "Legacy review must cover every managed requirement exactly once: "
            + "missing="
            + ",".join(missing)
        )

    return {
        "version": LEGACY_RECLASSIFICATION_VERSION,
        "issueKey": issue_key.upper(),
        "migrationId": migration_id,
        "expectedUpdated": expected_updated,
        "approvalSummary": approval_summary,
        "reviewedAt": reviewed_at,
        "candidate": deepcopy(candidate),
        "implementationEvidence": implementation_evidence,
        "validationEvidence": validation_evidence,
        "requirements": normalized_requirements,
    }


def validate_qa_artifact(
    value: dict[str, Any],
    *,
    issue_key: str,
    description: str,
) -> tuple[dict[str, Any], str, str]:
    if not isinstance(value, dict) or value.get("version") != LEGACY_RECLASSIFICATION_VERSION:
        raise SystemExit("Legacy QA artifact uses an unsupported contract version.")
    forbidden = forbidden_action_paths(value)
    if forbidden:
        raise SystemExit(
            "Legacy QA artifacts cannot contain executable Jira text fields: "
            + ", ".join(forbidden)
        )
    if str(value.get("issueKey", "")).upper() != issue_key.upper():
        raise SystemExit("Legacy QA artifact belongs to a different Jira issue.")

    record_date = str(value.get("date", ""))
    try:
        parsed_date = date.fromisoformat(record_date)
    except ValueError as error:
        raise SystemExit("Legacy QA date must use exact YYYY-MM-DD format.") from error
    if parsed_date.isoformat() != record_date:
        raise SystemExit("Legacy QA date must use exact YYYY-MM-DD format.")

    record = value.get("record")
    if not isinstance(record, dict):
        raise SystemExit("Legacy QA artifact requires a record object.")
    unknown_fields = sorted(set(record) - set(QA_FIELDS))
    if unknown_fields:
        raise SystemExit(
            "Legacy QA artifact contains unsupported fields: " + ", ".join(unknown_fields)
        )
    normalized_record = {
        field: require_string(record.get(field), f"Legacy QA {field}")
        for field in QA_FIELDS
    }
    qa_text = "\n".join(f"- {field}: {normalized_record[field]}" for field in QA_FIELDS)
    updated_description = prepend_qa_record(
        description,
        issue_key,
        record_date,
        qa_text,
    )
    qa_errors = validate_qa_completion_record(
        updated_description,
        issue_key,
        require_no_unverified=False,
        require_pending_unverified=True,
    )
    if qa_errors:
        raise SystemExit("Legacy QA completion record is invalid: " + "; ".join(qa_errors))

    normalized = {
        "version": LEGACY_RECLASSIFICATION_VERSION,
        "issueKey": issue_key.upper(),
        "date": record_date,
        "record": normalized_record,
    }
    return normalized, qa_text, updated_description


def validate_candidate_plan(
    value: dict[str, Any],
    *,
    issue_key: str,
    description: str,
    statuses: dict[str, str],
) -> tuple[dict[str, Any], str, str]:
    candidate = value.get("candidate") if isinstance(value, dict) else None
    if not isinstance(candidate, dict):
        raise SystemExit("Legacy verification plan requires a candidate object.")
    pr_url = require_string(candidate.get("prUrl"), "Legacy candidate prUrl")
    parsed = urlparse(pr_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("Legacy candidate prUrl must be an HTTP(S) pull request URL.")
    branch = require_issue_branch(issue_key, candidate.get("branch"))
    normalized = validate_verification_plan(
        value,
        issue_key=issue_key,
        session={"branch": branch},
        pr_url=pr_url,
        description=description,
    )
    target_status, property_state = development_complete_target(statuses, normalized)
    if property_state == "completed":
        raise SystemExit(
            "Legacy reclassification requires at least one pending automatic or manual check; "
            "direct verified migration is forbidden."
        )
    return normalized, target_status, property_state


def build_completion_property(
    *,
    issue_key: str,
    expected_updated: str,
    baseline: dict[str, Any],
    review: dict[str, Any],
    verification: dict[str, Any],
    qa_artifact: dict[str, Any],
    target_status: str,
    property_state: str,
) -> dict[str, Any]:
    now = utc_timestamp()
    review_digest = json_digest(review)
    value = {
        "version": 1,
        "state": property_state,
        "issueKey": issue_key.upper(),
        "sessionId": review["migrationId"],
        "branch": verification["candidate"]["branch"],
        "baseline": deepcopy(baseline),
        "capturedUpdated": expected_updated,
        "createdAt": now,
        "updatedAt": now,
        "developmentCompletedAt": now,
        "prUrl": verification["candidate"]["prUrl"],
        "reviewDigest": review_digest,
        "review": deepcopy(review),
        "developmentCompleteStatus": target_status,
        "verification": deepcopy(verification),
        "legacyReclassification": {
            "version": LEGACY_RECLASSIFICATION_VERSION,
            "migrationId": review["migrationId"],
            "approvalSummary": review["approvalSummary"],
            "sourceUpdated": expected_updated,
            "qaRecordIdentity": json_digest(qa_artifact),
            "backupPropertyKey": LEGACY_RECLASSIFICATION_PROPERTY_KEY,
            "migratedAt": now,
        },
    }
    require_property_size(value)
    return value


def build_migration_property(
    *,
    issue_key: str,
    migration_id: str,
    source_status: str,
    source_updated: str,
    source_description: str,
    source_completion_property: dict[str, Any] | None,
    target_status: str,
    target_description: str,
    target_completion_property: dict[str, Any],
    qa_artifact: dict[str, Any],
) -> dict[str, Any]:
    value = {
        "version": LEGACY_RECLASSIFICATION_VERSION,
        "state": "applied",
        "issueKey": issue_key.upper(),
        "migrationId": migration_id,
        "source": {
            "status": source_status,
            "updated": source_updated,
            "descriptionBackup": encode_backup(
                source_description,
                json_value=False,
            ),
            "descriptionDigest": text_digest(source_description),
            "completionPropertyPresent": source_completion_property is not None,
            "completionPropertyBackup": encode_backup(
                source_completion_property,
                json_value=True,
            ),
        },
        "target": {
            "status": target_status,
            "descriptionDigest": text_digest(target_description),
            "completionPropertyDigest": json_digest(target_completion_property),
            "candidate": deepcopy(
                target_completion_property["verification"]["candidate"]
            ),
            "qaArtifact": deepcopy(qa_artifact),
        },
        "createdAt": utc_timestamp(),
    }
    require_bounded_property(value, "Legacy reclassification migration property")
    return value


def _field(issue: dict[str, Any], name: str) -> Any:
    return (issue.get("fields") or {}).get(name)


def _status(issue: dict[str, Any]) -> str:
    return str((_field(issue, "status") or {}).get("name", ""))


def _description(issue: dict[str, Any]) -> str:
    return adf_to_text(_field(issue, "description")).strip()


def _account_id(value: Any) -> str:
    return str((value or {}).get("accountId", ""))


def _project_key(value: Any) -> str:
    return str((value or {}).get("key", ""))


def _capture_error(blockers: list[dict[str, str]], code: str, action) -> Any:
    try:
        return action()
    except (SystemExit, ValueError) as error:
        blockers.append({"code": code, "message": str(error)})
        return None


def _base_result(
    issue_key: str,
    issue: dict[str, Any],
    *,
    operation: str,
    blockers: list[dict[str, str]],
    target_status: str = "",
    migration_id: str = "",
) -> dict[str, Any]:
    return {
        "version": LEGACY_RECLASSIFICATION_VERSION,
        "operation": operation,
        "readOnly": operation in {"inspect", "preflight"},
        "issueKey": issue_key.upper(),
        "current": {
            "status": _status(issue),
            "updated": str(_field(issue, "updated") or ""),
        },
        "targetStatus": target_status,
        "migrationId": migration_id,
        "eligible": not blockers,
        "blockers": blockers,
    }


def prepare_reclassification(
    client,
    config: dict[str, Any],
    statuses: dict[str, str],
    issue_key: str,
    *,
    operation: str,
    expected_updated: str,
    review_value: dict[str, Any],
    verification_value: dict[str, Any],
    qa_value: dict[str, Any],
    enforce_write_gates: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    blockers: list[dict[str, str]] = []
    issue = _capture_error(
        blockers,
        "issue-read",
        lambda: client.get_issue(
            issue_key,
            fields=[
                "status",
                "description",
                "updated",
                "resolution",
                "project",
                "assignee",
            ],
        ),
    )
    if not isinstance(issue, dict):
        return _base_result(issue_key, {}, operation=operation, blockers=blockers), None
    current_user = _capture_error(
        blockers,
        "current-user-read",
        lambda: client.get_current_user(),
    )
    previous_completion = _capture_error(
        blockers,
        "completion-property-read",
        lambda: client.get_issue_property(issue_key, COMPLETION_PROPERTY_KEY),
    )
    existing_migration = _capture_error(
        blockers,
        "migration-property-read",
        lambda: client.get_issue_property(
            issue_key, LEGACY_RECLASSIFICATION_PROPERTY_KEY
        ),
    )
    transitions = _capture_error(
        blockers,
        "transition-read",
        lambda: client.list_transitions(issue_key),
    )
    transitions = transitions if isinstance(transitions, list) else []

    observed_key = str(issue.get("key", issue_key)).upper()
    if observed_key != issue_key.upper():
        blockers.append(
            {
                "code": "issue-identity",
                "message": f"Expected issue {issue_key.upper()}, observed {observed_key}.",
            }
        )
    project_key = str(config.get("project_key", ""))
    if not project_key or _project_key(_field(issue, "project")) != project_key:
        blockers.append(
            {
                "code": "project",
                "message": "Legacy reclassification requires the configured Jira project.",
            }
        )
    if not _account_id(current_user) or _account_id(_field(issue, "assignee")) != _account_id(
        current_user
    ):
        blockers.append(
            {
                "code": "assignee",
                "message": "Legacy reclassification requires assignment to the authenticated Jira user.",
            }
        )
    if _field(issue, "resolution"):
        blockers.append(
            {
                "code": "resolution",
                "message": "Legacy reclassification requires an unresolved issue.",
            }
        )
    if _status(issue) != statuses.get("todo"):
        blockers.append(
            {
                "code": "status",
                "message": (
                    f"Legacy reclassification requires status={statuses.get('todo')}; "
                    f"observed={_status(issue) or '(missing)'}."
                ),
            }
        )
    observed_updated = str(_field(issue, "updated") or "")
    if not expected_updated or observed_updated != expected_updated:
        blockers.append(
            {
                "code": "stale-updated",
                "message": (
                    f"Legacy reclassification expected updated={expected_updated or '(missing)'}; "
                    f"observed={observed_updated or '(missing)'}."
                ),
            }
        )

    description = _description(issue)
    contract = parse_description_contract(description)
    if contract.get("state") != "ready":
        blockers.append(
            {
                "code": "description",
                "message": "Legacy reclassification requires descriptionContract.state=ready.",
            }
        )
    baseline = _capture_error(
        blockers,
        "baseline",
        lambda: extract_snapshot(description),
    )
    if not isinstance(baseline, dict) or not baseline.get("requirements"):
        blockers.append(
            {
                "code": "requirements",
                "message": "Legacy reclassification requires a non-empty managed requirement baseline.",
            }
        )

    if previous_completion is not None:
        validated_previous = _capture_error(
            blockers,
            "completion-property",
            lambda: require_property_identity(previous_completion, issue_key),
        )
        if (
            isinstance(validated_previous, dict)
            and validated_previous.get("state") not in TERMINAL_PROPERTY_STATES
        ):
            blockers.append(
                {
                    "code": "completion-property",
                    "message": (
                        "Legacy reclassification requires an absent or terminal completion property; "
                        f"observed={validated_previous.get('state')}."
                    ),
                }
            )

    if not has_extended_lifecycle(statuses):
        blockers.append(
            {
                "code": "statuses",
                "message": "Legacy reclassification requires the complete extended lifecycle mappings.",
            }
        )

    normalized_verification = None
    target_status = ""
    property_state = ""
    if has_extended_lifecycle(statuses):
        candidate_result = _capture_error(
            blockers,
            "verification-plan",
            lambda: validate_candidate_plan(
                verification_value,
                issue_key=issue_key,
                description=description,
                statuses=statuses,
            ),
        )
        if candidate_result is not None:
            normalized_verification, target_status, property_state = candidate_result

    normalized_review = None
    if (
        isinstance(baseline, dict)
        and isinstance(normalized_verification, dict)
    ):
        normalized_review = _capture_error(
            blockers,
            "legacy-review",
            lambda: validate_legacy_review(
                review_value,
                issue_key=issue_key,
                expected_updated=expected_updated,
                baseline=baseline,
                candidate=normalized_verification["candidate"],
            ),
        )

    qa_result = _capture_error(
        blockers,
        "qa-record",
        lambda: validate_qa_artifact(
            qa_value,
            issue_key=issue_key,
            description=description,
        ),
    )
    normalized_qa = qa_text = target_description = None
    if qa_result is not None:
        normalized_qa, qa_text, target_description = qa_result

    migration_id = (
        normalized_review.get("migrationId", "")
        if isinstance(normalized_review, dict)
        else ""
    )
    completion_property = None
    migration_property = None
    if (
        isinstance(baseline, dict)
        and isinstance(normalized_review, dict)
        and isinstance(normalized_verification, dict)
        and isinstance(normalized_qa, dict)
        and isinstance(target_description, str)
        and target_status
        and property_state
    ):
        completion_property = _capture_error(
            blockers,
            "completion-property-size",
            lambda: build_completion_property(
                issue_key=issue_key,
                expected_updated=expected_updated,
                baseline=baseline,
                review=normalized_review,
                verification=normalized_verification,
                qa_artifact=normalized_qa,
                target_status=target_status,
                property_state=property_state,
            ),
        )
        if isinstance(completion_property, dict):
            migration_property = _capture_error(
                blockers,
                "migration-property-size",
                lambda: build_migration_property(
                    issue_key=issue_key,
                    migration_id=migration_id,
                    source_status=statuses["todo"],
                    source_updated=expected_updated,
                    source_description=description,
                    source_completion_property=previous_completion,
                    target_status=target_status,
                    target_description=target_description,
                    target_completion_property=completion_property,
                    qa_artifact=normalized_qa,
                ),
            )

    already_applied = False
    if existing_migration is not None:
        same_migration = (
            isinstance(existing_migration, dict)
            and existing_migration.get("version") == LEGACY_RECLASSIFICATION_VERSION
            and str(existing_migration.get("issueKey", "")).upper() == issue_key.upper()
            and existing_migration.get("migrationId") == migration_id
        )
        target = existing_migration.get("target") if same_migration else {}
        exact_applied = bool(
            same_migration
            and _status(issue) == target.get("status")
            and text_digest(description) == target.get("descriptionDigest")
            and json_digest(previous_completion)
            == target.get("completionPropertyDigest")
        )
        if exact_applied:
            already_applied = True
            blockers = [
                blocker
                for blocker in blockers
                if blocker["code"]
                not in {
                    "status",
                    "stale-updated",
                    "resolution",
                    "completion-property",
                }
            ]
        else:
            blockers.append(
                {
                    "code": "migration-property",
                    "message": "A conflicting or incomplete legacy reclassification property already exists.",
                }
            )

    required_destinations = [
        target_status,
        statuses.get("todo", ""),
    ]
    missing_destinations = [
        target
        for target in required_destinations
        if target and find_transition(transitions, target) is None
    ]
    if missing_destinations:
        blockers.append(
            {
                "code": "transitions",
                "message": (
                    "Jira transition preflight is missing configured destination(s): "
                    + ", ".join(missing_destinations)
                ),
            }
        )

    options = automation(config)
    gates = {
        "dryRunDisabled": not bool(options.get("dry_run", True)),
        "transitionEnabled": bool(options.get("allow_transition")),
        "qaDescriptionEnabled": bool(
            options.get("allow_description_prepend_qa")
        ),
    }
    if enforce_write_gates:
        if not gates["dryRunDisabled"]:
            blockers.append(
                {
                    "code": "write-gate",
                    "message": "Legacy reclassification requires automation.dry_run=false.",
                }
            )
        if not gates["transitionEnabled"]:
            blockers.append(
                {
                    "code": "write-gate",
                    "message": "Legacy reclassification requires automation.allow_transition=true.",
                }
            )
        if not gates["qaDescriptionEnabled"]:
            blockers.append(
                {
                    "code": "write-gate",
                    "message": (
                        "Legacy reclassification requires "
                        "automation.allow_description_prepend_qa=true."
                    ),
                }
            )

    result = _base_result(
        issue_key,
        issue,
        operation=operation,
        blockers=blockers,
        target_status=target_status,
        migration_id=migration_id,
    )
    result["gates"] = gates
    result["alreadyApplied"] = already_applied
    result["requirementCount"] = len((baseline or {}).get("requirements", []))
    result["candidate"] = (
        deepcopy(normalized_verification["candidate"])
        if isinstance(normalized_verification, dict)
        else {}
    )
    context = None
    if not blockers or already_applied:
        context = {
            "issue": issue,
            "description": description,
            "previousCompletion": previous_completion,
            "existingMigration": existing_migration,
            "transitions": transitions,
            "baseline": baseline,
            "review": normalized_review,
            "verification": normalized_verification,
            "qa": normalized_qa,
            "qaText": qa_text,
            "targetDescription": target_description,
            "targetStatus": target_status,
            "propertyState": property_state,
            "completionProperty": completion_property,
            "migrationProperty": migration_property,
            "alreadyApplied": already_applied,
        }
    return result, context


def _verify_description(client, issue_key: str, expected: str) -> None:
    observed = client.get_issue(issue_key, fields=["description"])
    if _description(observed) != expected.strip():
        raise SystemExit("Jira description failed read-after-write verification.")


def _verify_property(client, issue_key: str, property_key: str, expected: Any) -> None:
    observed = client.get_issue_property(issue_key, property_key)
    if observed != expected:
        raise SystemExit(f"Jira property {property_key} failed read-after-write verification.")


def _transition_and_verify(client, issue_key: str, target_status: str) -> None:
    transition = find_transition(client.list_transitions(issue_key), target_status)
    if not transition:
        raise SystemExit(f'No transition found for configured status "{target_status}".')
    client.transition_issue(issue_key, str(transition["id"]))
    observed = client.get_issue(issue_key, fields=["status"])
    if _status(observed) != target_status:
        raise SystemExit(
            f'{issue_key} transition verification failed: expected "{target_status}", '
            f'observed "{_status(observed) or "(missing)"}".'
        )


def _restore_completion_property(
    client,
    issue_key: str,
    previous: dict[str, Any] | None,
) -> None:
    if previous is None:
        client.delete_issue_property(issue_key, COMPLETION_PROPERTY_KEY)
    else:
        client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, previous)
    _verify_property(client, issue_key, COMPLETION_PROPERTY_KEY, previous)


def compensate_apply(
    client,
    issue_key: str,
    *,
    source_status: str,
    source_description: str,
    source_completion_property: dict[str, Any] | None,
) -> list[str]:
    recovery: list[str] = []
    safe = True
    try:
        observed = client.get_issue(issue_key, fields=["status"])
        if _status(observed) != source_status:
            _transition_and_verify(client, issue_key, source_status)
        recovery.append("status restored")
    except SystemExit as error:
        safe = False
        recovery.append(f"status restore failed: {error}")

    try:
        observed_property = client.get_issue_property(
            issue_key, COMPLETION_PROPERTY_KEY
        )
        if observed_property != source_completion_property:
            _restore_completion_property(
                client, issue_key, source_completion_property
            )
        recovery.append("completion property restored")
    except SystemExit as error:
        safe = False
        recovery.append(f"completion property restore failed: {error}")

    try:
        observed_issue = client.get_issue(issue_key, fields=["description"])
        if _description(observed_issue) != source_description.strip():
            client.update_description(issue_key, source_description)
            _verify_description(client, issue_key, source_description)
        recovery.append("description restored")
    except SystemExit as error:
        safe = False
        recovery.append(f"description restore failed: {error}")

    if safe:
        try:
            client.delete_issue_property(
                issue_key, LEGACY_RECLASSIFICATION_PROPERTY_KEY
            )
            _verify_property(
                client,
                issue_key,
                LEGACY_RECLASSIFICATION_PROPERTY_KEY,
                None,
            )
            recovery.append("migration property removed")
        except SystemExit as error:
            recovery.append(f"migration property removal failed: {error}")
    else:
        recovery.append("migration property preserved for recovery")
    return recovery


def apply_reclassification(
    client,
    config: dict[str, Any],
    statuses: dict[str, str],
    issue_key: str,
    *,
    expected_updated: str,
    review_value: dict[str, Any],
    verification_value: dict[str, Any],
    qa_value: dict[str, Any],
) -> dict[str, Any]:
    result, context = prepare_reclassification(
        client,
        config,
        statuses,
        issue_key,
        operation="apply",
        expected_updated=expected_updated,
        review_value=review_value,
        verification_value=verification_value,
        qa_value=qa_value,
        enforce_write_gates=True,
    )
    if context is None:
        raise SystemExit(
            "Legacy reclassification apply preflight failed: "
            + "; ".join(item["message"] for item in result["blockers"])
        )
    if context["alreadyApplied"]:
        result["applied"] = True
        result["idempotent"] = True
        return result

    source_description = context["description"]
    source_completion = context["previousCompletion"]
    try:
        client.set_issue_property(
            issue_key,
            LEGACY_RECLASSIFICATION_PROPERTY_KEY,
            context["migrationProperty"],
        )
        _verify_property(
            client,
            issue_key,
            LEGACY_RECLASSIFICATION_PROPERTY_KEY,
            context["migrationProperty"],
        )

        client.update_description(issue_key, context["targetDescription"])
        _verify_description(client, issue_key, context["targetDescription"])

        client.set_issue_property(
            issue_key,
            COMPLETION_PROPERTY_KEY,
            context["completionProperty"],
        )
        _verify_property(
            client,
            issue_key,
            COMPLETION_PROPERTY_KEY,
            context["completionProperty"],
        )

        _transition_and_verify(client, issue_key, context["targetStatus"])
    except SystemExit as error:
        recovery = compensate_apply(
            client,
            issue_key,
            source_status=statuses["todo"],
            source_description=source_description,
            source_completion_property=source_completion,
        )
        raise SystemExit(
            "Legacy reclassification apply failed; "
            + "; ".join(recovery)
            + f". Cause: {error}"
        ) from error

    observed = client.get_issue(issue_key, fields=["status", "description", "updated"])
    _verify_property(
        client,
        issue_key,
        COMPLETION_PROPERTY_KEY,
        context["completionProperty"],
    )
    _verify_property(
        client,
        issue_key,
        LEGACY_RECLASSIFICATION_PROPERTY_KEY,
        context["migrationProperty"],
    )
    result.update(
        {
            "applied": True,
            "idempotent": False,
            "eligible": True,
            "current": {
                "status": _status(observed),
                "updated": str(_field(observed, "updated") or ""),
            },
        }
    )
    return result


def validate_migration_property(
    value: Any,
    *,
    issue_key: str,
    migration_id: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("version") != LEGACY_RECLASSIFICATION_VERSION:
        raise SystemExit("Legacy reclassification migration property is missing or invalid.")
    if str(value.get("issueKey", "")).upper() != issue_key.upper():
        raise SystemExit("Legacy reclassification migration property belongs to another issue.")
    if value.get("migrationId") != migration_id:
        raise SystemExit("Legacy reclassification migrationId does not match.")
    if value.get("state") != "applied":
        raise SystemExit("Legacy reclassification migration property is not applied.")
    if not isinstance(value.get("source"), dict) or not isinstance(value.get("target"), dict):
        raise SystemExit("Legacy reclassification migration property is incomplete.")
    return value


def rollback_reclassification(
    client,
    config: dict[str, Any],
    statuses: dict[str, str],
    issue_key: str,
    *,
    migration_id: str,
    expected_updated: str,
) -> dict[str, Any]:
    migration_id = require_migration_id(migration_id)
    options = automation(config)
    if options.get("dry_run", True):
        raise SystemExit("Legacy reclassification rollback requires automation.dry_run=false.")
    if not options.get("allow_transition"):
        raise SystemExit(
            "Legacy reclassification rollback requires automation.allow_transition=true."
        )
    if not options.get("allow_description_prepend_qa"):
        raise SystemExit(
            "Legacy reclassification rollback requires "
            "automation.allow_description_prepend_qa=true."
        )
    if not has_extended_lifecycle(statuses):
        raise SystemExit(
            "Legacy reclassification rollback requires the complete extended lifecycle mappings."
        )

    issue = client.get_issue(
        issue_key,
        fields=[
            "status",
            "description",
            "updated",
            "resolution",
            "project",
            "assignee",
        ],
    )
    current_user = client.get_current_user()
    if _project_key(_field(issue, "project")) != str(config.get("project_key", "")):
        raise SystemExit("Legacy rollback requires the configured Jira project.")
    if _account_id(_field(issue, "assignee")) != _account_id(current_user):
        raise SystemExit("Legacy rollback requires the authenticated Jira assignee.")
    if str(_field(issue, "updated") or "") != expected_updated:
        raise SystemExit("Legacy rollback expectedUpdated does not match the current Jira snapshot.")

    migration = validate_migration_property(
        client.get_issue_property(
            issue_key, LEGACY_RECLASSIFICATION_PROPERTY_KEY
        ),
        issue_key=issue_key,
        migration_id=migration_id,
    )
    source = migration["source"]
    target = migration["target"]
    if source.get("status") != statuses["todo"]:
        raise SystemExit(
            "Legacy rollback migration property has an invalid source status."
        )
    if target.get("status") not in {
        statuses["done_auto"],
        statuses["done_manual"],
    }:
        raise SystemExit(
            "Legacy rollback migration property has an invalid target status."
        )
    source_description = decode_backup(
        source.get("descriptionBackup"),
        json_value=False,
    )
    if text_digest(source_description) != source.get("descriptionDigest"):
        raise SystemExit(
            "Legacy rollback source description digest does not match its backup."
        )
    source_completion_property = decode_backup(
        source.get("completionPropertyBackup"),
        json_value=True,
    )
    if not source.get("completionPropertyPresent"):
        if source_completion_property is not None:
            raise SystemExit(
                "Legacy rollback source completion-property presence does not match its backup."
            )
        source_completion_property = None
    elif not isinstance(source_completion_property, dict):
        raise SystemExit(
            "Legacy rollback source completion-property backup must be an object."
        )
    current_completion = client.get_issue_property(
        issue_key, COMPLETION_PROPERTY_KEY
    )
    current_description = _description(issue)
    if _status(issue) != target.get("status"):
        raise SystemExit("Legacy rollback refuses a changed Jira status.")
    if text_digest(current_description) != target.get("descriptionDigest"):
        raise SystemExit("Legacy rollback refuses a changed Jira description.")
    if json_digest(current_completion) != target.get("completionPropertyDigest"):
        raise SystemExit("Legacy rollback refuses a changed completion property.")
    if (
        ((current_completion or {}).get("verification") or {}).get("candidate")
        != target.get("candidate")
    ):
        raise SystemExit("Legacy rollback refuses a changed migration candidate.")
    if find_transition(client.list_transitions(issue_key), str(source.get("status", ""))) is None:
        raise SystemExit("Legacy rollback cannot reach the captured source status.")

    try:
        _transition_and_verify(client, issue_key, str(source["status"]))
        _restore_completion_property(
            client,
            issue_key,
            source_completion_property,
        )
        client.update_description(issue_key, source_description)
        _verify_description(client, issue_key, source_description)
        client.delete_issue_property(
            issue_key, LEGACY_RECLASSIFICATION_PROPERTY_KEY
        )
        _verify_property(
            client,
            issue_key,
            LEGACY_RECLASSIFICATION_PROPERTY_KEY,
            None,
        )
    except SystemExit as error:
        recovery: list[str] = []
        try:
            if client.get_issue_property(
                issue_key, LEGACY_RECLASSIFICATION_PROPERTY_KEY
            ) != migration:
                client.set_issue_property(
                    issue_key,
                    LEGACY_RECLASSIFICATION_PROPERTY_KEY,
                    migration,
                )
                _verify_property(
                    client,
                    issue_key,
                    LEGACY_RECLASSIFICATION_PROPERTY_KEY,
                    migration,
                )
            recovery.append("migration property restored")
        except SystemExit as recovery_error:
            recovery.append(
                f"migration property restore failed: {recovery_error}"
            )
        try:
            observed_description = client.get_issue(
                issue_key, fields=["description"]
            )
            if _description(observed_description) != current_description:
                client.update_description(issue_key, current_description)
                _verify_description(client, issue_key, current_description)
            recovery.append("migrated description restored")
        except SystemExit as recovery_error:
            recovery.append(f"migrated description restore failed: {recovery_error}")
        try:
            if client.get_issue_property(
                issue_key, COMPLETION_PROPERTY_KEY
            ) != current_completion:
                client.set_issue_property(
                    issue_key, COMPLETION_PROPERTY_KEY, current_completion
                )
                _verify_property(
                    client,
                    issue_key,
                    COMPLETION_PROPERTY_KEY,
                    current_completion,
                )
            recovery.append("migrated completion property restored")
        except SystemExit as recovery_error:
            recovery.append(
                f"migrated completion property restore failed: {recovery_error}"
            )
        try:
            observed_status = client.get_issue(issue_key, fields=["status"])
            if _status(observed_status) != str(target.get("status", "")):
                _transition_and_verify(
                    client, issue_key, str(target.get("status", ""))
                )
            recovery.append("migrated status restored")
        except SystemExit as recovery_error:
            recovery.append(f"migrated status restore failed: {recovery_error}")
        raise SystemExit(
            "Legacy reclassification rollback failed; "
            + "; ".join(recovery)
            + f". Cause: {error}"
        ) from error

    observed = client.get_issue(issue_key, fields=["status", "updated"])
    return {
        "version": LEGACY_RECLASSIFICATION_VERSION,
        "operation": "rollback",
        "issueKey": issue_key.upper(),
        "migrationId": migration_id,
        "rolledBack": True,
        "current": {
            "status": _status(observed),
            "updated": str(_field(observed, "updated") or ""),
        },
    }

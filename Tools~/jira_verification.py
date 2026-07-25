#!/usr/bin/env python3
"""Versioned deferred-validation plans and automatic verification results."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from jira_completion import normalize_text, require_property_identity, utc_timestamp
from jira_description import top_level_sections


VERIFICATION_CONTRACT_VERSION = 1
AUTOMATIC_EVIDENCE_LEVELS = {
    "automated",
    "editor-simulated",
    "remote-assisted",
    "player-build",
    "device-verified",
}
BLOCK_REASONS = {"environment", "approval", "stale-candidate"}
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
FORBIDDEN_ACTION_FIELDS = {"command", "commands", "shell", "script"}


def _require_string(value: Any, label: str) -> str:
    normalized = normalize_text(str(value or ""))
    if not normalized:
        raise SystemExit(f"{label} must be a non-empty string.")
    return normalized


def _require_commit(value: Any, label: str) -> str:
    commit = str(value or "").strip().lower()
    if not COMMIT_PATTERN.fullmatch(commit):
        raise SystemExit(f"{label} must be an exact 40-character Git commit SHA.")
    return commit


def _require_evidence(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not normalize_text(item) for item in value)
    ):
        raise SystemExit(f"{label} requires at least one non-empty evidence string.")
    return [normalize_text(item) for item in value]


def _forbidden_action_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).casefold() in FORBIDDEN_ACTION_FIELDS:
                found.append(child_path)
            found.extend(_forbidden_action_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_action_paths(child, f"{path}[{index}]"))
    return found


def _validation_plan_body(description: str) -> str:
    for section in top_level_sections(description):
        if section["heading"] == "Validation Plan":
            return section["body"]
    return ""


def validate_verification_plan(
    value: dict[str, Any],
    *,
    issue_key: str,
    session: dict[str, Any],
    pr_url: str,
    description: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("version") != VERIFICATION_CONTRACT_VERSION:
        raise SystemExit("Verification plan uses an unsupported contract version.")
    forbidden_paths = _forbidden_action_paths(value)
    if forbidden_paths:
        raise SystemExit(
            "Verification plans cannot contain executable Jira text fields: "
            + ", ".join(forbidden_paths)
        )
    if str(value.get("issueKey", "")).upper() != issue_key.upper():
        raise SystemExit("Verification plan belongs to a different Jira issue.")

    candidate = value.get("candidate")
    if not isinstance(candidate, dict):
        raise SystemExit("Verification plan requires a candidate object.")
    if candidate.get("prUrl") != pr_url:
        raise SystemExit("Verification candidate prUrl must exactly match --pr-url.")
    if candidate.get("branch") != session.get("branch"):
        raise SystemExit("Verification candidate branch must match the sealed implementation branch.")
    _require_commit(candidate.get("commit"), "Verification candidate commit")

    checks = value.get("checks")
    if not isinstance(checks, list):
        raise SystemExit("Verification plan requires a checks array.")
    validation_body = _validation_plan_body(description)
    observed_ids: set[str] = set()
    normalized_checks: list[dict[str, Any]] = []
    for item in checks:
        if not isinstance(item, dict):
            raise SystemExit("Each verification check must be an object.")
        check_id = _require_string(item.get("id"), "Verification check id")
        if check_id in observed_ids:
            raise SystemExit(f"Verification plan contains duplicate check id: {check_id}.")
        observed_ids.add(check_id)
        mode = str(item.get("mode", "")).strip()
        if mode not in {"automatic", "manual"}:
            raise SystemExit(f"Verification check {check_id} has an invalid mode.")
        description_value = _require_string(
            item.get("description"), f"Verification check {check_id} description"
        )
        evidence_level = str(item.get("evidenceLevel", "")).strip()
        if mode == "automatic" and evidence_level not in AUTOMATIC_EVIDENCE_LEVELS:
            raise SystemExit(
                f"Automatic verification check {check_id} has an invalid evidenceLevel."
            )
        if mode == "manual" and evidence_level != "manual":
            raise SystemExit(
                f"Manual verification check {check_id} must use evidenceLevel=manual."
            )
        if evidence_level in {"player-build", "device-verified"} and evidence_level not in validation_body:
            raise SystemExit(
                f"Verification check {check_id} requires {evidence_level}, but the approved "
                "Validation Plan does not explicitly authorize that evidence level."
            )
        status = str(item.get("status", "pending")).strip()
        if status not in {"pending", "passed"}:
            raise SystemExit(
                f"Initial verification check {check_id} status must be pending or passed."
            )
        normalized = {
            "id": check_id,
            "mode": mode,
            "description": description_value,
            "evidenceLevel": evidence_level,
            "status": status,
            "evidence": [],
        }
        if status == "passed":
            normalized["evidence"] = _require_evidence(
                item.get("evidence"), f"Passed verification check {check_id}"
            )
            normalized["completedAt"] = _require_string(
                item.get("completedAt"), f"Passed verification check {check_id} completedAt"
            )
        normalized_checks.append(normalized)

    normalized = {
        "version": VERIFICATION_CONTRACT_VERSION,
        "issueKey": issue_key.upper(),
        "candidate": {
            "prUrl": pr_url,
            "branch": session["branch"],
            "commit": str(candidate["commit"]).lower(),
        },
        "checks": normalized_checks,
        "attempts": [],
    }
    digest_source = json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    normalized["planDigest"] = (
        "sha256:" + hashlib.sha256(digest_source.encode("utf-8")).hexdigest()
    )
    return normalized


def pending_modes(plan: dict[str, Any]) -> set[str]:
    return {
        str(check.get("mode"))
        for check in plan.get("checks", [])
        if check.get("status") == "pending"
    }


def development_complete_target(
    statuses: dict[str, str],
    plan: dict[str, Any],
) -> tuple[str, str]:
    modes = pending_modes(plan)
    if "automatic" in modes:
        return statuses["done_auto"], "awaiting-automatic-validation"
    if "manual" in modes:
        return statuses["done_manual"], "awaiting-manual-validation"
    return statuses["done_verified"], "completed"


def require_automatic_candidate(
    issue_key: str,
    status_name: str,
    statuses: dict[str, str],
    property_value: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if status_name != statuses["done_auto"]:
        raise SystemExit(
            "Automatic verification requires the configured done_auto status. "
            f"Observed status={status_name or '(missing)'}."
        )
    session = require_property_identity(property_value, issue_key)
    if session.get("state") != "awaiting-automatic-validation":
        raise SystemExit(
            "Automatic verification requires state=awaiting-automatic-validation."
        )
    plan = session.get("verification")
    if not isinstance(plan, dict) or plan.get("version") != VERIFICATION_CONTRACT_VERSION:
        raise SystemExit("Automatic verification requires a versioned verification plan.")
    if str(plan.get("issueKey", "")).upper() != issue_key.upper():
        raise SystemExit("Verification plan belongs to a different Jira issue.")
    _require_commit((plan.get("candidate") or {}).get("commit"), "Recorded candidate commit")
    if not any(
        check.get("mode") == "automatic" and check.get("status") == "pending"
        for check in plan.get("checks", [])
    ):
        raise SystemExit("Automatic verification plan has no pending automatic checks.")
    return session, plan


def apply_automatic_result(
    issue_key: str,
    session: dict[str, Any],
    result: dict[str, Any],
    observed_commit: str,
) -> tuple[dict[str, Any], str]:
    if not isinstance(result, dict) or result.get("version") != VERIFICATION_CONTRACT_VERSION:
        raise SystemExit("Automatic verification result uses an unsupported contract version.")
    if str(result.get("issueKey", "")).upper() != issue_key.upper():
        raise SystemExit("Automatic verification result belongs to a different Jira issue.")

    plan = deepcopy(session["verification"])
    expected_commit = _require_commit(
        plan["candidate"].get("commit"), "Recorded candidate commit"
    )
    observed_commit = _require_commit(observed_commit, "Observed candidate commit")
    outcome = str(result.get("outcome", "")).strip()
    if outcome not in {"passed", "defect", "blocked"}:
        raise SystemExit("Automatic verification outcome must be passed, defect, or blocked.")
    reason = str(result.get("reason", "")).strip()
    if observed_commit != expected_commit and not (
        outcome == "blocked" and reason == "stale-candidate"
    ):
        raise SystemExit(
            "Automatic verification candidate is stale. Record a stale-candidate blocked "
            "result instead of validating a different revision."
        )
    if outcome == "blocked" and reason not in BLOCK_REASONS:
        raise SystemExit(
            "Blocked automatic verification reason must be environment, approval, or stale-candidate."
        )
    if outcome == "blocked" and reason == "stale-candidate" and observed_commit == expected_commit:
        raise SystemExit(
            "A stale-candidate result requires the observed commit to differ from the recorded candidate."
        )
    if outcome == "defect" and reason != "related-defect":
        raise SystemExit("Defect automatic verification must use reason=related-defect.")
    if outcome == "passed" and reason != "all-checks-passed":
        raise SystemExit("Passed automatic verification must use reason=all-checks-passed.")

    pending = {
        check["id"]: check
        for check in plan["checks"]
        if check.get("mode") == "automatic" and check.get("status") == "pending"
    }
    entries = result.get("checks")
    if not isinstance(entries, list):
        raise SystemExit("Automatic verification result requires a checks array.")
    by_id: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit("Each automatic verification result check must be an object.")
        check_id = str(entry.get("id", ""))
        if check_id in by_id:
            raise SystemExit(f"Automatic verification result duplicates check id: {check_id}.")
        if check_id not in pending:
            raise SystemExit(
                f"Automatic verification result references a non-pending check: {check_id or '(empty)'}."
            )
        status = str(entry.get("status", "")).strip()
        if status not in {"passed", "failed", "blocked"}:
            raise SystemExit(f"Automatic verification check {check_id} has an invalid status.")
        by_id[check_id] = {
            "status": status,
            "evidence": _require_evidence(
                entry.get("evidence"), f"Automatic verification check {check_id}"
            ),
        }

    observed_statuses = {entry["status"] for entry in by_id.values()}
    if outcome == "passed":
        if set(by_id) != set(pending) or observed_statuses != {"passed"}:
            raise SystemExit(
                "Passed automatic verification must cover every pending automatic check as passed."
            )
    elif outcome == "defect":
        if "failed" not in observed_statuses:
            raise SystemExit("Defect automatic verification requires at least one failed check.")
    elif reason == "stale-candidate" and by_id:
        raise SystemExit("Stale-candidate verification must not report executed checks.")
    elif reason != "stale-candidate" and "blocked" not in observed_statuses:
        raise SystemExit("Blocked automatic verification requires at least one blocked check.")

    resume_condition = normalize_text(str(result.get("resumeCondition", "")))
    if outcome in {"defect", "blocked"} and not resume_condition:
        raise SystemExit(
            "Defect or blocked automatic verification requires a non-empty resumeCondition."
        )
    attempt_evidence = _require_evidence(
        result.get("evidence"), "Automatic verification attempt"
    )
    now = utc_timestamp()
    for check_id, entry in by_id.items():
        if outcome == "blocked":
            pending[check_id]["lastAttempt"] = {
                "status": entry["status"],
                "evidence": entry["evidence"],
                "completedAt": now,
            }
        else:
            pending[check_id]["status"] = entry["status"]
            pending[check_id]["evidence"] = entry["evidence"]
            pending[check_id]["completedAt"] = now

    attempt = {
        "outcome": outcome,
        "reason": reason,
        "expectedCommit": expected_commit,
        "observedCommit": observed_commit,
        "evidence": attempt_evidence,
        "resumeCondition": resume_condition,
        "completedAt": now,
    }
    plan.setdefault("attempts", []).append(attempt)

    updated = deepcopy(session)
    updated["verification"] = plan
    updated["updatedAt"] = now
    if outcome == "defect":
        updated["state"] = "closed-defect"
        updated["closedDefectAt"] = now
        return updated, "todo"
    if outcome == "blocked":
        updated["state"] = "awaiting-automatic-validation"
        return updated, "done_auto"
    if "manual" in pending_modes(plan):
        updated["state"] = "awaiting-manual-validation"
        return updated, "done_manual"
    updated["state"] = "completed"
    updated["completedAt"] = now
    return updated, "done_verified"

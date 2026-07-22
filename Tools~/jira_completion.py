#!/usr/bin/env python3
"""Versioned Jira completion-baseline and review contracts."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from jira_description import parse_description_contract, top_level_sections, validate_qa_completion_record


COMPLETION_PROPERTY_KEY = "actionfit.ai-jira.completion-session"
COMPLETION_CONTRACT_VERSION = 1
MAX_PROPERTY_BYTES = 32768
BASELINE_HEADINGS = (
    "Goal",
    "Scope",
    "Out of Scope",
    "Completion Criteria",
    "Additional Requirements",
)
REQUIREMENT_HEADINGS = (
    "Goal",
    "Scope",
    "Completion Criteria",
    "Additional Requirements",
)
TERMINAL_PROPERTY_STATES = {
    "completed",
    "closed-incomplete",
    "planned",
}
_ITEM_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+?)\s*$")
_SPACE_PATTERN = re.compile(r"\s+")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    return _SPACE_PATTERN.sub(" ", (value or "").strip())


def _body_items(body: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    for raw_line in (body or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("### "):
            continue
        match = _ITEM_PATTERN.match(raw_line)
        if match:
            if current:
                items.append(normalize_text(" ".join(current)))
            current = [match.group(1)]
        elif current:
            current.append(line)
        else:
            current = [line]
    if current:
        items.append(normalize_text(" ".join(current)))
    return [item for item in items if item]


def requirement_id(section: str, text: str) -> str:
    canonical = f"{normalize_text(section).casefold()}\n{normalize_text(text)}"
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12].upper()
    return f"REQ-{digest}"


def extract_snapshot(
    description: str,
    *,
    allow_original_fallback: bool = False,
    original_fallback: str = "",
) -> dict[str, Any]:
    sections = top_level_sections(description)
    selected = [section for section in sections if section["heading"] in BASELINE_HEADINGS]
    normalized_sections = [
        {
            "heading": section["heading"],
            "body": "\n".join(line.rstrip() for line in section["body"].splitlines()).strip(),
        }
        for section in selected
    ]
    requirements: list[dict[str, str]] = []
    for section in normalized_sections:
        if section["heading"] not in REQUIREMENT_HEADINGS:
            continue
        for item in _body_items(section["body"]):
            requirements.append(
                {
                    "id": requirement_id(section["heading"], item),
                    "section": section["heading"],
                    "text": item,
                }
            )

    if not normalized_sections and allow_original_fallback:
        if sections:
            original = "\n\n".join(
                f'## {section["heading"]}\n{section["body"]}'.strip()
                for section in sections
                if section["heading"] != "QA 확인 필요 사항"
            ).strip()
        else:
            original = "\n".join(
                line.rstrip()
                for line in (description or "").replace("\r\n", "\n").replace("\r", "\n").splitlines()
            ).strip()
        if not original:
            original = normalize_text(original_fallback)
        if original:
            normalized_sections = [{"heading": "Original Request", "body": original}]
            requirements = [
                {
                    "id": "ORIGINAL-" + hashlib.sha256(original.encode("utf-8")).hexdigest()[:12].upper(),
                    "section": "Original Request",
                    "text": normalize_text(original),
                }
            ]

    ids = [item["id"] for item in requirements]
    if len(ids) != len(set(ids)):
        raise SystemExit(
            "Description contains duplicate normalized requirements; make each requirement distinct before sealing."
        )
    canonical = json.dumps(normalized_sections, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "descriptionDigest": "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "sections": normalized_sections,
        "requirements": requirements,
    }


def require_ready_description(description: str) -> dict[str, Any]:
    contract = parse_description_contract(description)
    if contract["state"] != "ready" or contract["autoStart"]["allowed"] is not True:
        reasons = ", ".join(contract["reasons"]) or "Auto Start is not explicitly allowed"
        raise SystemExit(f"Implementation start requires descriptionContract.state=ready: {reasons}.")
    snapshot = extract_snapshot(description)
    if not snapshot["requirements"]:
        raise SystemExit("Implementation start requires at least one sealed requirement.")
    return snapshot


def property_size(value: dict[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def require_property_size(value: dict[str, Any]) -> None:
    size = property_size(value)
    if size > MAX_PROPERTY_BYTES:
        raise SystemExit(
            f"Completion session property is {size} bytes; Jira issue properties allow at most "
            f"{MAX_PROPERTY_BYTES} bytes. Reduce duplicated requirement prose before retrying."
        )


def require_property_identity(value: Any, issue_key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SystemExit("Jira completion session property is missing or invalid.")
    if value.get("version") != COMPLETION_CONTRACT_VERSION:
        raise SystemExit("Jira completion session property uses an unsupported contract version.")
    if str(value.get("issueKey", "")).upper() != issue_key.upper():
        raise SystemExit("Jira completion session property belongs to a different issue.")
    if not normalize_text(str(value.get("state", ""))):
        raise SystemExit("Jira completion session property is missing its state.")
    return value


def _require_requirement_ids(items: Any, label: str) -> set[str]:
    if not isinstance(items, list) or not items:
        raise SystemExit(f"{label} requires a non-empty requirements array.")
    ids = []
    for item in items:
        if not isinstance(item, dict) or not normalize_text(str(item.get("id", ""))):
            raise SystemExit(f"{label} contains an invalid requirement entry.")
        ids.append(str(item["id"]))
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{label} contains duplicate requirement IDs.")
    return set(ids)


def build_planning_property(
    issue_key: str,
    description: str,
    updated: str,
    *,
    planning_id: str,
    summary: str = "",
) -> dict[str, Any]:
    now = utc_timestamp()
    value = {
        "version": COMPLETION_CONTRACT_VERSION,
        "state": "planning",
        "issueKey": issue_key.upper(),
        "planningId": planning_id,
        "preRefinement": extract_snapshot(
            description,
            allow_original_fallback=True,
            original_fallback=summary,
        ),
        "sourceUpdated": updated,
        "capturedUpdated": updated,
        "createdAt": now,
        "updatedAt": now,
    }
    if not value["preRefinement"]["requirements"]:
        raise SystemExit("Planning lock requires a Jira description or summary to seal as the source request.")
    require_property_size(value)
    return value


def build_active_property(
    issue_key: str,
    description: str,
    updated: str,
    *,
    session_id: str,
    branch: str,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    baseline = require_ready_description(description)
    now = utc_timestamp()
    value = {
        "version": COMPLETION_CONTRACT_VERSION,
        "state": "prepared",
        "issueKey": issue_key.upper(),
        "sessionId": session_id,
        "branch": branch,
        "baseline": baseline,
        "capturedUpdated": updated,
        "createdAt": now,
        "updatedAt": now,
    }
    if previous and previous.get("preRefinement"):
        value["preRefinement"] = deepcopy(previous["preRefinement"])
    elif previous and previous.get("approvedPlan", {}).get("preRefinement"):
        value["preRefinement"] = deepcopy(previous["approvedPlan"]["preRefinement"])
    require_property_size(value)
    return value


def with_state(value: dict[str, Any], state: str, **fields: Any) -> dict[str, Any]:
    updated = deepcopy(value)
    updated["state"] = state
    updated["updatedAt"] = utc_timestamp()
    updated.update(fields)
    require_property_size(updated)
    return updated


def read_json_file(path: str, label: str) -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Failed to read {label} JSON: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"{label} JSON root must be an object.")
    return value


def validate_plan_coverage(
    property_value: dict[str, Any],
    approved_description: str,
    coverage: dict[str, Any],
) -> dict[str, Any]:
    if coverage.get("version") != COMPLETION_CONTRACT_VERSION:
        raise SystemExit("Plan coverage uses an unsupported contract version.")
    source_requirements = property_value.get("preRefinement", {}).get("requirements")
    target_snapshot = require_ready_description(approved_description)
    source_ids = _require_requirement_ids(source_requirements, "Planning source snapshot")
    target_ids = _require_requirement_ids(target_snapshot["requirements"], "Approved plan")
    entries = coverage.get("requirements")
    if not isinstance(entries, list):
        raise SystemExit("Plan coverage requires a requirements array.")

    by_source: dict[str, dict[str, Any]] = {}
    allowed = {"retained", "clarified", "removed", "deferred", "out-of-scope"}
    scope_change = False
    for entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit("Each plan coverage requirement must be an object.")
        source_id = str(entry.get("sourceId", ""))
        if source_id in by_source:
            raise SystemExit(f"Plan coverage contains duplicate sourceId: {source_id or '(empty)' }.")
        disposition = str(entry.get("disposition", ""))
        if disposition not in allowed:
            raise SystemExit(f"Plan coverage has invalid disposition for {source_id or '(empty)' }.")
        targets = entry.get("targetIds")
        if not isinstance(targets, list) or any(not isinstance(item, str) or not item for item in targets):
            raise SystemExit(f"Plan coverage targetIds must be a string array for {source_id or '(empty)' }.")
        if len(targets) != len(set(targets)):
            raise SystemExit(f"Plan coverage contains duplicate targetIds for {source_id}.")
        unknown_targets = sorted(set(targets) - target_ids)
        if unknown_targets:
            raise SystemExit(f"Plan coverage references unknown target IDs: {', '.join(unknown_targets)}.")
        if disposition == "retained" and targets != [source_id]:
            raise SystemExit(f"Retained requirement {source_id} must target only its unchanged ID.")
        if disposition == "clarified" and not targets:
            raise SystemExit(f"Clarified requirement {source_id} requires at least one target ID.")
        if disposition in {"removed", "deferred", "out-of-scope"}:
            scope_change = True
            if targets:
                raise SystemExit(f"{disposition} requirement {source_id} cannot declare target IDs.")
            if not normalize_text(str(entry.get("rationale", ""))):
                raise SystemExit(f"{disposition} requirement {source_id} requires a rationale.")
        by_source[source_id] = entry

    observed_ids = set(by_source)
    if observed_ids != source_ids:
        missing = sorted(source_ids - observed_ids)
        unknown = sorted(observed_ids - source_ids)
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unknown:
            details.append("unknown=" + ",".join(unknown))
        raise SystemExit("Plan coverage must map every sealed source requirement exactly once: " + "; ".join(details))
    if scope_change:
        if coverage.get("scopeChangeApproved") is not True:
            raise SystemExit("Scope reduction requires scopeChangeApproved=true after separate user approval.")
        if not normalize_text(str(coverage.get("approvalSummary", ""))):
            raise SystemExit("Scope reduction requires a non-empty approvalSummary.")
    return target_snapshot


def validate_completion_review(
    issue_key: str,
    property_value: dict[str, Any],
    review: dict[str, Any],
    pr_url: str,
) -> None:
    if review.get("version") != COMPLETION_CONTRACT_VERSION:
        raise SystemExit("Completion review uses an unsupported contract version.")
    if str(review.get("issueKey", "")).upper() != issue_key.upper():
        raise SystemExit("Completion review belongs to a different Jira issue.")
    if review.get("sessionId") != property_value.get("sessionId"):
        raise SystemExit("Completion review sessionId does not match the sealed implementation session.")
    baseline = property_value.get("baseline") or {}
    if review.get("baselineDigest") != baseline.get("descriptionDigest"):
        raise SystemExit("Completion review baselineDigest does not match the sealed baseline.")
    if review.get("prUrl") != pr_url:
        raise SystemExit("Completion review prUrl must exactly match --pr-url.")

    expected = _require_requirement_ids(
        baseline.get("requirements"), "Sealed implementation baseline"
    )
    entries = review.get("requirements")
    if not isinstance(entries, list):
        raise SystemExit("Completion review requires a requirements array.")
    observed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit("Each completion review requirement must be an object.")
        requirement_id_value = str(entry.get("id", ""))
        if requirement_id_value in observed:
            raise SystemExit(f"Completion review contains duplicate requirement ID: {requirement_id_value or '(empty)'}.")
        if entry.get("status") != "complete":
            raise SystemExit(f"Completion review requirement {requirement_id_value or '(empty)'} is not complete.")
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not evidence or any(
            not isinstance(item, str) or not normalize_text(item) for item in evidence
        ):
            raise SystemExit(
                f"Completion review requirement {requirement_id_value or '(empty)'} requires concrete evidence."
            )
        observed[requirement_id_value] = entry
    observed_ids = set(observed)
    if observed_ids != expected:
        missing = sorted(expected - observed_ids)
        unknown = sorted(observed_ids - expected)
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unknown:
            details.append("unknown=" + ",".join(unknown))
        raise SystemExit("Completion review must cover every sealed requirement exactly once: " + "; ".join(details))


def validate_completion_gate(
    issue_key: str,
    issue: dict[str, Any],
    progress_status: str,
    property_value: Any,
    review: dict[str, Any],
    pr_url: str | None,
) -> dict[str, Any]:
    parsed = urlparse(pr_url or "")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("Completion requires --pr-url with the created pull request URL.")
    fields = issue.get("fields") or {}
    current_status = str((fields.get("status") or {}).get("name", ""))
    if current_status != progress_status:
        raise SystemExit(
            "Completion requires the configured progress state. "
            f"Expected status={progress_status}, observed status={current_status or '(missing)'}."
        )
    session = require_property_identity(property_value, issue_key)
    if session.get("state") != "active":
        raise SystemExit(
            "Completion requires an active sealed implementation baseline. "
            "Legacy progress issues must finalize incomplete, return to todo, and restart."
        )
    from jira_client import adf_to_text

    description = adf_to_text(fields.get("description"))
    current_snapshot = require_ready_description(description)
    baseline = session.get("baseline") or {}
    if current_snapshot["descriptionDigest"] != baseline.get("descriptionDigest"):
        raise SystemExit(
            "Jira requirements changed after implementation start. Finalize incomplete and restart from the approved plan."
        )
    qa_errors = validate_qa_completion_record(description, issue_key)
    if qa_errors:
        raise SystemExit("Korean QA completion record is incomplete: " + "; ".join(qa_errors))
    validate_completion_review(issue_key, session, review, str(pr_url))
    return session

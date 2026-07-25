#!/usr/bin/env python3
"""Read-only Jira work-item API used by AI Jira tools."""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from jira_core_loader import load_core
from jira_description import parse_description_contract
from jira_statuses import (
    lifecycle_state,
    overlap_status_keys,
    require_statuses,
    status_keys_for_state,
    verification_state,
)


core = load_core()
load_config = core.load_config
adf_to_text = core.adf_to_text

STATE_FILTERS = (
    "todo",
    "progress",
    "all",
    "automatic-validation",
    "manual-validation",
    "verified",
    "development-complete",
)


def configure_output() -> None:
    """Force UTF-8 output so Korean Jira text survives Windows consoles and pipes."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _jql_string(value: Any) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def resolve_statuses(config: dict[str, Any], state: str) -> list[str]:
    if state not in STATE_FILTERS:
        raise ValueError(f"Unsupported state filter: {state}")
    statuses = require_statuses(config)
    return [statuses[key] for key in status_keys_for_state(statuses, state)]


def build_jql(config: dict[str, Any], state: str) -> tuple[str, list[str]]:
    statuses = resolve_statuses(config, state)
    clauses = []
    project = config.get("project_key")
    if project:
        clauses.append(f"project = {_jql_string(project)}")
    clauses.append("assignee = currentUser()")
    if state in {"todo", "progress", "all"}:
        clauses.append("resolution = Unresolved")

    if len(statuses) == 1:
        clauses.append(f"status = {_jql_string(statuses[0])}")
    else:
        joined = ", ".join(_jql_string(status) for status in statuses)
        clauses.append(f"status IN ({joined})")

    return " AND ".join(clauses) + " ORDER BY updated DESC", statuses


def build_overlap_jql(config: dict[str, Any]) -> tuple[str, list[str]]:
    """Build the project-wide Jira overlap query without task-pickup filters."""
    project = config.get("project_key")
    if not project:
        raise SystemExit("Missing Jira project_key for project-wide overlap discovery.")

    mappings = require_statuses(config)
    keys = overlap_status_keys(mappings)
    status_names = [mappings[key] for key in keys]
    joined = ", ".join(_jql_string(status) for status in status_names)
    jql = (
        f"project = {_jql_string(project)} "
        f"AND status IN ({joined}) ORDER BY updated DESC"
    )
    return jql, status_names


class JiraReadApi(core.JiraReadApi):
    """Compatibility name for the Core read-only transport."""


def normalize_issue_links(links: Any, current_key: str) -> list[dict[str, str]]:
    """Return linked-issue evidence from the current issue's perspective."""
    normalized = []
    for link in links or []:
        if not isinstance(link, dict):
            continue
        link_type = link.get("type") or {}
        for field_name, direction in (("inwardIssue", "inward"), ("outwardIssue", "outward")):
            linked_issue = link.get(field_name)
            if not isinstance(linked_issue, dict):
                continue
            key = str(linked_issue.get("key", ""))
            if not key or key.upper() == current_key.upper():
                continue
            values = linked_issue.get("fields") or {}
            normalized.append(
                {
                    "key": key,
                    "direction": direction,
                    "relation": str(link_type.get(direction, "")),
                    "type": str(link_type.get("name", "")),
                    "summary": str(values.get("summary", "")),
                    "status": str((values.get("status") or {}).get("name", "")),
                    "resolution": str((values.get("resolution") or {}).get("name", "")),
                }
            )
    return normalized


def query_work_item(
    config: dict[str, Any],
    issue_key: str,
    api: JiraReadApi | None = None,
) -> dict[str, Any]:
    fields = [
        "summary",
        "status",
        "updated",
        "description",
        "priority",
        "labels",
        "assignee",
        "issuetype",
        "resolution",
        "project",
        "issuelinks",
    ]
    api = api or JiraReadApi(config)
    issue = api.get_issue(issue_key, fields)
    values = issue.get("fields", {})
    key = str(issue.get("key", issue_key))
    base_url = str(config.get("jira_base_url", "")).rstrip("/")
    description = adf_to_text(values.get("description")).strip()
    statuses = require_statuses(config)
    status_name = str((values.get("status") or {}).get("name", ""))
    return {
        "key": key,
        "summary": str(values.get("summary", "")),
        "status": status_name,
        "lifecycleState": lifecycle_state(status_name, statuses),
        "verificationState": verification_state(status_name, statuses),
        "updated": str(values.get("updated", "")),
        "url": f"{base_url}/browse/{key}" if base_url and key else "",
        "description": description,
        "descriptionContract": parse_description_contract(description),
        "priority": str((values.get("priority") or {}).get("name", "")),
        "labels": [str(label) for label in values.get("labels") or []],
        "assignee": str((values.get("assignee") or {}).get("displayName", "")),
        "issueType": str((values.get("issuetype") or {}).get("name", "")),
        "resolution": str((values.get("resolution") or {}).get("name", "")),
        "project": str((values.get("project") or {}).get("key", "")),
        "configuredStatuses": {
            state: str(status)
            for state, status in statuses.items()
        },
        "issueLinks": normalize_issue_links(values.get("issuelinks"), key),
    }


def query_work_items(
    config: dict[str, Any],
    state: str = "all",
    max_results: int = 50,
    api: JiraReadApi | None = None,
    *,
    all_pages: bool = False,
) -> dict[str, Any]:
    if not 1 <= max_results <= 100:
        raise ValueError("max_results must be between 1 and 100")

    jql, statuses = build_jql(config, state)
    api = api or JiraReadApi(config)
    base_url = str(config.get("jira_base_url", "")).rstrip("/")
    items = []
    issue_keys: set[str] = set()
    page_tokens: set[str] = set()
    next_page_token: str | None = None
    page_count = 0
    response: dict[str, Any] = {}
    while True:
        if all_pages:
            response = api.search_issues(
                jql,
                max_results,
                next_page_token=next_page_token,
                fields=["summary", "status", "updated"],
            )
        else:
            response = api.search_issues(jql, max_results)
        if not isinstance(response, dict) or not isinstance(response.get("issues"), list):
            raise SystemExit("Jira work-item search returned a malformed issues payload.")

        page_count += 1
        for issue in response["issues"]:
            fields = issue.get("fields", {})
            status = fields.get("status") or {}
            key = str(issue.get("key", ""))
            status_name = str(status.get("name", ""))
            if not key:
                raise SystemExit("Jira work-item search returned an issue without a key.")
            if key in issue_keys:
                raise SystemExit(f"Jira work-item pagination returned duplicate issue key: {key}")
            issue_keys.add(key)
            configured_statuses = require_statuses(config)
            items.append(
                {
                    "key": key,
                    "summary": str(fields.get("summary", "")),
                    "status": status_name,
                    "lifecycleState": lifecycle_state(status_name, configured_statuses),
                    "verificationState": verification_state(status_name, configured_statuses),
                    "updated": str(fields.get("updated", "")),
                    "url": f"{base_url}/browse/{key}" if base_url and key else "",
                }
            )

        if not all_pages:
            break
        is_last = response.get("isLast")
        returned_token = response.get("nextPageToken")
        if is_last is True:
            if returned_token:
                raise SystemExit(
                    "Jira work-item pagination returned a terminal page with a nextPageToken."
                )
            break
        if is_last is not False or not isinstance(returned_token, str) or not returned_token:
            raise SystemExit(
                "Jira work-item pagination ended without explicit terminal evidence."
            )
        if returned_token in page_tokens:
            raise SystemExit("Jira work-item pagination repeated a nextPageToken.")
        page_tokens.add(returned_token)
        next_page_token = returned_token

    result = {
        "state": state,
        "statuses": statuses,
        "project": config.get("project_key"),
        "jql": jql,
        "returnedCount": len(items),
        "maxResults": max_results,
        "items": items,
    }
    if all_pages:
        result["pageCount"] = page_count
        result["complete"] = True
    if "isLast" in response:
        result["isLast"] = bool(response["isLast"])
    if response.get("nextPageToken"):
        result["nextPageToken"] = response["nextPageToken"]
    return result


def query_overlap_work_items(
    config: dict[str, Any],
    page_size: int = 100,
    api: JiraReadApi | None = None,
) -> dict[str, Any]:
    """Return every configured lifecycle issue in the project for overlap inspection."""
    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be between 1 and 100")

    jql, statuses = build_overlap_jql(config)
    api = api or JiraReadApi(config)
    base_url = str(config.get("jira_base_url", "")).rstrip("/")
    items = []
    issue_keys: set[str] = set()
    page_tokens: set[str] = set()
    next_page_token: str | None = None
    page_count = 0

    while True:
        response = api.search_issues(
            jql,
            page_size,
            next_page_token=next_page_token,
            fields=["summary", "status", "updated", "assignee"],
        )
        if not isinstance(response, dict) or not isinstance(response.get("issues"), list):
            raise SystemExit("Jira overlap search returned a malformed issues payload.")

        page_count += 1
        for issue in response["issues"]:
            fields = issue.get("fields") or {}
            status = fields.get("status") or {}
            key = str(issue.get("key", ""))
            status_name = str(status.get("name", ""))
            if not key:
                raise SystemExit("Jira overlap search returned an issue without a key.")
            if status_name not in statuses:
                raise SystemExit(
                    f"Jira overlap search returned {key} outside configured lifecycle statuses."
                )
            if key in issue_keys:
                raise SystemExit(f"Jira overlap pagination returned duplicate issue key: {key}")
            issue_keys.add(key)
            items.append(
                {
                    "key": key,
                    "summary": str(fields.get("summary", "")),
                    "status": status_name,
                    "assignee": str((fields.get("assignee") or {}).get("displayName", "")),
                    "updated": str(fields.get("updated", "")),
                    "url": f"{base_url}/browse/{key}" if base_url else "",
                }
            )

        is_last = response.get("isLast")
        returned_token = response.get("nextPageToken")
        if is_last is True:
            if returned_token:
                raise SystemExit(
                    "Jira overlap pagination returned a terminal page with a nextPageToken."
                )
            break
        if is_last is not False or not isinstance(returned_token, str) or not returned_token:
            raise SystemExit("Jira overlap pagination ended without explicit terminal evidence.")
        if returned_token in page_tokens:
            raise SystemExit("Jira overlap pagination repeated a nextPageToken.")
        page_tokens.add(returned_token)
        next_page_token = returned_token

    return {
        "scope": "project",
        "states": list(overlap_status_keys(require_statuses(config))),
        "statuses": statuses,
        "project": config.get("project_key"),
        "jql": jql,
        "returnedCount": len(items),
        "pageSize": page_size,
        "pageCount": page_count,
        "complete": True,
        "items": items,
    }


def write_text(result: dict[str, Any], stream: TextIO | None = None) -> None:
    stream = stream or sys.stdout
    items = result.get("items", [])
    if not items:
        stream.write("No Jira work items found.\n")
        return
    for item in items:
        stream.write(
            f'{item["key"]} [{item["status"]}] {item["summary"]}'
            f' (updated: {item["updated"]})\n'
        )


def write_json(result: dict[str, Any], stream: TextIO | None = None) -> None:
    stream = stream or sys.stdout
    json.dump(result, stream, ensure_ascii=False, indent=2)
    stream.write("\n")


def write_issue_text(result: dict[str, Any], stream: TextIO | None = None) -> None:
    stream = stream or sys.stdout
    stream.write(f'{result["key"]} [{result["status"]}] {result["summary"]}\n')
    stream.write(f'Assignee: {result["assignee"] or "(unassigned)"}\n')
    stream.write(f'Priority: {result["priority"] or "(none)"}\n')
    stream.write(f'Updated: {result["updated"]}\n')
    stream.write(f'URL: {result["url"]}\n')
    stream.write("Description:\n")
    stream.write((result["description"] or "(empty)") + "\n")

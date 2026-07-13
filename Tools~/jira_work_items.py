#!/usr/bin/env python3
"""Read-only Jira work-item API used by AI Jira tools."""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Any, TextIO
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_CONFIG = Path("Tools/AI/jira/config.local.json")
STATE_KEYS = {
    "todo": ("todo",),
    "progress": ("progress",),
    "all": ("todo", "progress"),
}


def configure_output() -> None:
    """Force UTF-8 output so Korean Jira text survives Windows consoles and pipes."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def load_config(path: str | None = None) -> dict[str, Any]:
    configured_path = path or os.getenv("AI_JIRA_CONFIG")
    config_path = Path(configured_path) if configured_path else DEFAULT_CONFIG
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    if not config_path.exists():
        raise SystemExit(
            f"Jira config was not found: {config_path}. "
            "Pass --config, set AI_JIRA_CONFIG, or create the ignored project config."
        )

    try:
        with config_path.open("r", encoding="utf-8-sig") as handle:
            config = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Failed to read Jira config as UTF-8 JSON: {config_path}\n{error}") from error

    config["_config_path"] = str(config_path)
    return config


def _jql_string(value: Any) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def resolve_statuses(config: dict[str, Any], state: str) -> list[str]:
    if state not in STATE_KEYS:
        raise ValueError(f"Unsupported state filter: {state}")

    mappings = config.get("statuses", {})
    missing = [key for key in STATE_KEYS[state] if not mappings.get(key)]
    if missing:
        raise SystemExit(f"Missing Jira status mapping(s): {', '.join(missing)}")
    return [str(mappings[key]) for key in STATE_KEYS[state]]


def build_jql(config: dict[str, Any], state: str) -> tuple[str, list[str]]:
    statuses = resolve_statuses(config, state)
    clauses = []
    project = config.get("project_key")
    if project:
        clauses.append(f"project = {_jql_string(project)}")
    clauses.extend(("assignee = currentUser()", "resolution = Unresolved"))

    if len(statuses) == 1:
        clauses.append(f"status = {_jql_string(statuses[0])}")
    else:
        joined = ", ".join(_jql_string(status) for status in statuses)
        clauses.append(f"status IN ({joined})")

    return " AND ".join(clauses) + " ORDER BY updated DESC", statuses


def _resolve_auth(config: dict[str, Any]) -> tuple[str, str]:
    auth = config.get("auth", {})
    email = auth.get("email") or os.getenv(auth.get("email_env", "JIRA_EMAIL"), "")
    token = auth.get("api_token") or os.getenv(auth.get("api_token_env", "JIRA_API_TOKEN"), "")
    if not email or not token:
        raise SystemExit("Missing Jira credentials in environment variables or ignored local config.")
    return str(email), str(token)


class JiraReadApi:
    """Minimal Jira Cloud enhanced-search client with no write methods."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.base_url = str(config.get("jira_base_url", "")).rstrip("/")
        if not self.base_url or "your-domain" in self.base_url:
            raise SystemExit("Set jira_base_url in the ignored Jira config.")

    def search_issues(self, jql: str, max_results: int) -> dict[str, Any]:
        email, token = _resolve_auth(self.config)
        encoded_auth = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
        body = json.dumps(
            {
                "jql": jql,
                "maxResults": max_results,
                "fields": ["summary", "status", "updated"],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            self.base_url + "/rest/api/3/search/jql",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": "Basic " + encoded_auth,
            },
            method="POST",
        )
        try:
            with urlopen(request) as response:
                raw = response.read().decode("utf-8-sig")
                return json.loads(raw) if raw else {}
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise SystemExit(f"Jira search failed: HTTP {error.code} {error.reason}\n{detail}") from error

    def get_issue(self, issue_key: str, fields: list[str]) -> dict[str, Any]:
        email, token = _resolve_auth(self.config)
        encoded_auth = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
        requested_fields = ",".join(fields)
        request = Request(
            f"{self.base_url}/rest/api/3/issue/{quote(issue_key, safe='')}?fields={requested_fields}",
            headers={
                "Accept": "application/json",
                "Authorization": "Basic " + encoded_auth,
            },
            method="GET",
        )
        try:
            with urlopen(request) as response:
                raw = response.read().decode("utf-8-sig")
                return json.loads(raw) if raw else {}
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise SystemExit(
                f"Jira issue lookup failed: HTTP {error.code} {error.reason}\n{detail}"
            ) from error


def adf_to_text(node: Any) -> str:
    """Render the useful textual subset of Atlassian Document Format."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_to_text(item) for item in node)
    if not isinstance(node, dict):
        return str(node)

    node_type = node.get("type")
    if node_type == "text":
        return str(node.get("text", ""))
    if node_type == "hardBreak":
        return "\n"

    rendered = adf_to_text(node.get("content", []))
    if node_type in {"paragraph", "heading", "listItem", "bulletList", "orderedList", "blockquote"}:
        return rendered.rstrip() + "\n"
    return rendered


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
    ]
    api = api or JiraReadApi(config)
    issue = api.get_issue(issue_key, fields)
    values = issue.get("fields", {})
    key = str(issue.get("key", issue_key))
    base_url = str(config.get("jira_base_url", "")).rstrip("/")
    return {
        "key": key,
        "summary": str(values.get("summary", "")),
        "status": str((values.get("status") or {}).get("name", "")),
        "updated": str(values.get("updated", "")),
        "url": f"{base_url}/browse/{key}" if base_url and key else "",
        "description": adf_to_text(values.get("description")).strip(),
        "priority": str((values.get("priority") or {}).get("name", "")),
        "labels": [str(label) for label in values.get("labels") or []],
        "assignee": str((values.get("assignee") or {}).get("displayName", "")),
        "issueType": str((values.get("issuetype") or {}).get("name", "")),
        "resolution": str((values.get("resolution") or {}).get("name", "")),
        "project": str((values.get("project") or {}).get("key", "")),
    }


def query_work_items(
    config: dict[str, Any],
    state: str = "all",
    max_results: int = 50,
    api: JiraReadApi | None = None,
) -> dict[str, Any]:
    if not 1 <= max_results <= 100:
        raise ValueError("max_results must be between 1 and 100")

    jql, statuses = build_jql(config, state)
    api = api or JiraReadApi(config)
    response = api.search_issues(jql, max_results)
    base_url = str(config.get("jira_base_url", "")).rstrip("/")
    items = []
    for issue in response.get("issues", []):
        fields = issue.get("fields", {})
        status = fields.get("status") or {}
        key = str(issue.get("key", ""))
        items.append(
            {
                "key": key,
                "summary": str(fields.get("summary", "")),
                "status": str(status.get("name", "")),
                "updated": str(fields.get("updated", "")),
                "url": f"{base_url}/browse/{key}" if base_url and key else "",
            }
        )

    result = {
        "state": state,
        "statuses": statuses,
        "project": config.get("project_key"),
        "jql": jql,
        "returnedCount": len(items),
        "maxResults": max_results,
        "items": items,
    }
    if "isLast" in response:
        result["isLast"] = bool(response["isLast"])
    if response.get("nextPageToken"):
        result["nextPageToken"] = response["nextPageToken"]
    return result


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

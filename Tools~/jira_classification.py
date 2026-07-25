#!/usr/bin/env python3
"""Compact two-pass structural classification for assigned Jira work."""

from __future__ import annotations

from typing import Any

from jira_description import parse_description_contract
from jira_statuses import ordinary_done_statuses, require_statuses
from jira_work_items import JiraReadApi, adf_to_text, build_jql, normalize_issue_links


CLASSIFICATION_FIELDS = [
    "summary",
    "status",
    "updated",
    "description",
    "project",
    "resolution",
    "issuelinks",
]

BLOCKING_RELATION_MARKERS = (
    "blocked by",
    "depends on",
    "depends upon",
    "requires",
    "선행",
    "의존",
    "차단",
)


def collect_prerequisite_requirements(
    contract: dict[str, Any],
    issue_links: list[dict[str, str]],
) -> list[dict[str, Any]]:
    requirements = [
        {
            "key": str(item.get("key", "")),
            "requiresVerified": bool(item.get("requiresVerified")),
            "source": "description",
        }
        for item in (contract.get("autoStart") or {}).get("prerequisiteRequirements") or []
        if isinstance(item, dict) and item.get("key")
    ]
    known = {item["key"].casefold() for item in requirements}
    for link in issue_links:
        relation = str(link.get("relation", "")).casefold()
        if link.get("direction") != "inward" or not any(
            marker in relation for marker in BLOCKING_RELATION_MARKERS
        ):
            continue
        key = str(link.get("key", ""))
        if not key or key.casefold() in known:
            continue
        known.add(key.casefold())
        requirements.append(
            {"key": key, "requiresVerified": False, "source": "inward-link"}
        )
    return requirements


def _search_all(api: JiraReadApi, jql: str, page_size: int, fields: list[str]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    token: str | None = None
    seen_tokens: set[str] = set()
    while True:
        response = api.search_issues(
            jql,
            page_size,
            next_page_token=token,
            fields=fields,
        )
        page = response.get("issues") if isinstance(response, dict) else None
        if not isinstance(page, list):
            raise SystemExit("Jira compact classification returned a malformed issues payload.")
        issues.extend(page)
        is_last = response.get("isLast")
        next_token = response.get("nextPageToken")
        if is_last is True:
            if next_token:
                raise SystemExit("Jira compact classification terminal page returned a token.")
            return issues
        if is_last is not False or not isinstance(next_token, str) or not next_token:
            raise SystemExit("Jira compact classification lacks explicit terminal evidence.")
        if next_token in seen_tokens:
            raise SystemExit("Jira compact classification repeated a page token.")
        seen_tokens.add(next_token)
        token = next_token


def _prerequisite_jql(keys: list[str]) -> str:
    escaped = [key.replace("\\", "\\\\").replace('"', '\\"') for key in keys]
    return "key IN (" + ", ".join(f'"{key}"' for key in escaped) + ")"


def classify_work_items(
    config: dict[str, Any],
    *,
    state: str = "todo",
    max_results: int = 100,
    api: JiraReadApi | None = None,
) -> dict[str, Any]:
    if not 1 <= max_results <= 100:
        raise ValueError("max_results must be between 1 and 100")
    jql, statuses = build_jql(config, state)
    api = api or JiraReadApi(config)
    issues = _search_all(api, jql, max_results, CLASSIFICATION_FIELDS)
    configured = require_statuses(config)

    records: list[dict[str, Any]] = []
    prerequisite_keys: list[str] = []
    for issue in issues:
        values = issue.get("fields") or {}
        key = str(issue.get("key", ""))
        description = adf_to_text(values.get("description")).strip()
        contract = parse_description_contract(description)
        requirements = collect_prerequisite_requirements(
            contract,
            normalize_issue_links(values.get("issuelinks"), key),
        )
        keys = [str(item.get("key")) for item in requirements if isinstance(item, dict) and item.get("key")]
        for prerequisite_key in keys:
            if prerequisite_key not in prerequisite_keys:
                prerequisite_keys.append(prerequisite_key)
        records.append(
            {
                "key": key,
                "summary": str(values.get("summary", "")),
                "status": str((values.get("status") or {}).get("name", "")),
                "updated": str(values.get("updated", "")),
                "project": str((values.get("project") or {}).get("key", "")),
                "resolution": str((values.get("resolution") or {}).get("name", "")),
                "planState": str(contract.get("state", "needs-plan")),
                "allowed": bool((contract.get("autoStart") or {}).get("allowed")),
                "prerequisiteRequirements": requirements,
                "structuralReasons": [str(value) for value in contract.get("reasons") or []][:12],
            }
        )

    prerequisite_state: dict[str, dict[str, Any]] = {}
    if prerequisite_keys:
        for issue in _search_all(
            api,
            _prerequisite_jql(prerequisite_keys),
            min(100, max_results),
            ["status", "resolution"],
        ):
            values = issue.get("fields") or {}
            key = str(issue.get("key", ""))
            prerequisite_state[key] = {
                "status": str((values.get("status") or {}).get("name", "")),
                "resolution": str((values.get("resolution") or {}).get("name", "")),
            }

    done_statuses = ordinary_done_statuses(configured)
    output = []
    for record in records:
        reasons = list(record.pop("structuralReasons"))
        prereqs = []
        prereqs_complete = True
        for requirement in record.pop("prerequisiteRequirements"):
            key = str(requirement.get("key", ""))
            requires_verified = bool(requirement.get("requiresVerified"))
            observed = prerequisite_state.get(key)
            if observed is None:
                complete = False
                state_name = "unavailable"
            else:
                state_name = observed["status"]
                complete = (
                    state_name == configured.get("done_verified")
                    if requires_verified
                    else bool(observed["resolution"]) or state_name in done_statuses
                )
            prereqs_complete = prereqs_complete and complete
            if not complete:
                reasons.append(f"prerequisite {key} is not complete")
            prereqs.append(
                {
                    "key": key,
                    "requiresVerified": requires_verified,
                    "source": requirement.get("source"),
                    "status": state_name,
                    "complete": complete,
                }
            )

        if record["project"] != config.get("project_key"):
            classification = "blocked"
            reasons.append("candidate project differs from configured project")
        elif not record["allowed"]:
            classification = "blocked"
            reasons.append("Auto Start Allowed is not yes")
        elif not prereqs_complete:
            classification = "blocked"
        elif record["planState"] != "ready":
            classification = "needs-plan"
        else:
            classification = "startable"
        output.append(
            {
                **record,
                "classification": classification,
                "prerequisites": prereqs,
                "reasons": list(dict.fromkeys(reasons))[:12],
            }
        )

    return {
        "version": 1,
        "state": state,
        "statuses": statuses,
        "project": config.get("project_key"),
        "jql": jql,
        "returnedCount": len(output),
        "complete": True,
        "detailPolicy": "full managed plan must be fetched only for the selected issue",
        "items": output,
    }

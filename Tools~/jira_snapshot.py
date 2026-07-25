#!/usr/bin/env python3
"""Bounded issue-centric execution snapshot owned by the AI Jira facade."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from jira_completion import COMPLETION_PROPERTY_KEY
from jira_classification import collect_prerequisite_requirements
from jira_statuses import ordinary_done_statuses, require_statuses
from jira_work_items import JiraReadApi, query_work_item


CommandRunner = Callable[[list[str], Path], tuple[int, str, str]]


def _run(command: list[str], cwd: Path) -> tuple[int, str, str]:
    process = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    return process.returncode, process.stdout, process.stderr


def _bounded_error(value: str) -> str:
    return " ".join(value.strip().split())[:240]


def _session_summary(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    baseline = value.get("baseline") if isinstance(value.get("baseline"), dict) else {}
    verification = value.get("verification") if isinstance(value.get("verification"), dict) else {}
    return {
        "version": value.get("version"),
        "state": value.get("state"),
        "sessionId": value.get("sessionId"),
        "branch": value.get("branch"),
        "descriptionDigest": baseline.get("descriptionDigest"),
        "requirementCount": len(baseline.get("requirements") or []),
        "startedAt": value.get("startedAt"),
        "updatedAt": value.get("updatedAt"),
        "verification": {
            key: verification.get(key)
            for key in ("version", "state", "pendingModes", "commit", "prUrl")
            if key in verification
        },
    }


def _owner_summaries(
    project_root: Path,
    issue_key: str,
    runner: CommandRunner,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    owners: dict[str, Any] = {"branches": [], "pullRequests": [], "worktreeLeases": []}
    unavailable: list[dict[str, str]] = []

    code, stdout, stderr = runner(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes/origin"],
        project_root,
    )
    if code == 0:
        owners["branches"] = [
            line for line in stdout.splitlines() if issue_key.casefold() in line.casefold()
        ][:12]
    else:
        unavailable.append({"owner": "git", "reason": _bounded_error(stderr or stdout)})

    if shutil.which("gh"):
        code, stdout, stderr = runner(
            [
                "gh", "pr", "list", "--state", "all", "--search",
                f"{issue_key} in:title,head", "--json",
                "number,title,state,headRefName,baseRefName,url",
            ],
            project_root,
        )
        if code == 0:
            try:
                parsed = json.loads(stdout)
                owners["pullRequests"] = parsed[:12] if isinstance(parsed, list) else []
            except ValueError:
                unavailable.append({"owner": "AI PullRequest", "reason": "owner output was not JSON"})
        else:
            unavailable.append({"owner": "AI PullRequest", "reason": _bounded_error(stderr or stdout)})
    else:
        unavailable.append({"owner": "AI PullRequest", "reason": "gh CLI is unavailable"})

    tool = project_root / "Packages/com.actionfit.ai-worktrees/Tools/manage_worktree_slots.py"
    if tool.is_file():
        code, stdout, stderr = runner(["python3", str(tool), "status", "--fast", "--json"], project_root)
        if code == 0:
            try:
                report = json.loads(stdout)
                for slot in report.get("slots") or []:
                    lease = slot.get("lease") if isinstance(slot, dict) else None
                    evidence = " ".join(
                        str(value)
                        for value in (
                            slot.get("branch"),
                            (lease or {}).get("branch") if isinstance(lease, dict) else "",
                            (lease or {}).get("task") if isinstance(lease, dict) else "",
                        )
                    )
                    if issue_key.casefold() not in evidence.casefold():
                        continue
                    owners["worktreeLeases"].append(
                        {
                            "slot": slot.get("slot"),
                            "path": slot.get("path"),
                            "branch": slot.get("branch"),
                            "head": slot.get("head"),
                            "lease": {
                                key: lease.get(key)
                                for key in ("state", "task", "branch", "lease_id")
                                if isinstance(lease, dict) and key in lease
                            },
                        }
                    )
            except (AttributeError, ValueError):
                unavailable.append({"owner": "AI Worktrees", "reason": "owner output was not JSON"})
        else:
            unavailable.append({"owner": "AI Worktrees", "reason": _bounded_error(stderr or stdout)})
    else:
        unavailable.append({"owner": "AI Worktrees", "reason": "owner tool is unavailable"})
    return owners, unavailable


def build_snapshot(
    config: dict[str, Any],
    issue_key: str,
    *,
    api: JiraReadApi | None = None,
    project_root: Path | None = None,
    runner: CommandRunner = _run,
) -> dict[str, Any]:
    api = api or JiraReadApi(config)
    root = (project_root or Path.cwd()).resolve()
    issue = query_work_item(config, issue_key, api=api)
    contract = issue["descriptionContract"]
    requirements = collect_prerequisite_requirements(contract, issue["issueLinks"])
    configured = require_statuses(config)
    done_statuses = ordinary_done_statuses(configured)
    prerequisites = []
    blockers = [str(reason) for reason in contract.get("reasons") or []]
    for requirement in requirements:
        key = str(requirement.get("key", ""))
        requires_verified = bool(requirement.get("requiresVerified"))
        try:
            observed = query_work_item(config, key, api=api)
            complete = (
                observed["status"] == configured.get("done_verified")
                if requires_verified
                else bool(observed["resolution"]) or observed["status"] in done_statuses
            )
            prerequisites.append(
                {
                    "key": key,
                    "requiresVerified": requires_verified,
                    "source": requirement.get("source"),
                    "status": observed["status"],
                    "complete": complete,
                }
            )
        except SystemExit as error:
            complete = False
            prerequisites.append(
                {
                    "key": key,
                    "requiresVerified": requires_verified,
                    "source": requirement.get("source"),
                    "status": "unavailable",
                    "complete": False,
                    "diagnostic": _bounded_error(str(error)),
                }
            )
        if not complete:
            blockers.append(f"prerequisite {key} is not complete")

    try:
        session = _session_summary(api.get_issue_property(issue_key, COMPLETION_PROPERTY_KEY))
    except (AttributeError, SystemExit) as error:
        session = None
        session_diagnostic = _bounded_error(str(error))
    else:
        session_diagnostic = ""

    owners, unavailable = _owner_summaries(root, issue_key, runner)
    if session_diagnostic:
        unavailable.append({"owner": "AI Jira completion property", "reason": session_diagnostic})
    return {
        "version": 1,
        "issue": {
            key: issue[key]
            for key in ("key", "summary", "status", "lifecycleState", "verificationState", "updated", "url")
        },
        "planReadiness": {
            "state": contract.get("state"),
            "allowed": bool((contract.get("autoStart") or {}).get("allowed")),
            "structurallyComplete": bool(contract.get("structurallyComplete")),
            "reasons": [str(value) for value in contract.get("reasons") or []][:12],
        },
        "prerequisites": prerequisites,
        "session": session,
        "owners": owners,
        "validation": (session or {}).get("verification") or issue["verificationState"],
        "blockers": list(dict.fromkeys(blockers))[:20],
        "unavailableOwners": unavailable[:12],
        "bounds": {
            "selectedIssueOnly": True,
            "fullDescriptionsIncluded": False,
            "unrelatedTodoIncluded": False,
            "destructiveActions": False,
        },
    }

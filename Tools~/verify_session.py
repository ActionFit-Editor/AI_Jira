#!/usr/bin/env python3
"""Inspect, preflight, or finalize one pinned automatic Jira verification."""

from __future__ import annotations

import argparse
import json

from jira_client import automation, build_client, configure_stdout, load_config
from jira_completion import (
    COMPLETION_PROPERTY_KEY,
    read_json_file,
    require_property_size,
)
from jira_statuses import require_extended_lifecycle, require_statuses
from jira_verification import apply_automatic_result, require_automatic_candidate
from transition_issue import (
    require_transition_targets,
    restore_property,
    transition_and_verify,
)


def _status_name(issue: dict) -> str:
    return str((((issue.get("fields") or {}).get("status") or {}).get("name", "")))


def required_targets_for_status(
    status_name: str,
    statuses: dict[str, str],
) -> list[str]:
    if status_name == statuses["progress"]:
        return [
            statuses["done_auto"],
            statuses["done_manual"],
            statuses["done_verified"],
        ]
    if status_name == statuses["done_auto"]:
        return [
            statuses["todo"],
            statuses["done_manual"],
            statuses["done_verified"],
        ]
    if status_name == statuses["done_manual"]:
        return [statuses["done_verified"]]
    if status_name in {statuses["todo"], statuses["done_verified"]}:
        return []
    raise SystemExit(
        "Verification transition preflight requires a configured lifecycle status. "
        f"Observed status={status_name or '(missing)'}."
    )


def preflight(client, issue_key: str, statuses: dict[str, str]) -> dict:
    issue = client.get_issue(issue_key, fields=["status"])
    observed = _status_name(issue)
    required = required_targets_for_status(observed, statuses)
    if required:
        require_transition_targets(client, issue_key, required)
    return {
        "issueKey": issue_key.upper(),
        "status": observed,
        "requiredDestinations": required,
        "ready": True,
    }


def inspect_candidate(
    client,
    issue_key: str,
    statuses: dict[str, str],
    observed_commit: str | None,
) -> dict:
    issue = client.get_issue(issue_key, fields=["status"])
    session, plan = require_automatic_candidate(
        issue_key,
        _status_name(issue),
        statuses,
        client.get_issue_property(issue_key, COMPLETION_PROPERTY_KEY),
    )
    expected_commit = str(plan["candidate"]["commit"])
    return {
        "issueKey": issue_key.upper(),
        "state": session["state"],
        "status": _status_name(issue),
        "candidate": plan["candidate"],
        "observedCommit": observed_commit.lower() if observed_commit else None,
        "staleCandidate": (
            observed_commit.lower() != expected_commit
            if observed_commit
            else None
        ),
        "pendingAutomaticChecks": [
            check
            for check in plan["checks"]
            if check.get("mode") == "automatic" and check.get("status") == "pending"
        ],
        "pendingManualChecks": [
            check
            for check in plan["checks"]
            if check.get("mode") == "manual" and check.get("status") == "pending"
        ],
    }


def finalize_verification(
    client,
    issue_key: str,
    statuses: dict[str, str],
    observed_commit: str,
    result: dict,
) -> dict:
    issue = client.get_issue(issue_key, fields=["status"])
    previous, _ = require_automatic_candidate(
        issue_key,
        _status_name(issue),
        statuses,
        client.get_issue_property(issue_key, COMPLETION_PROPERTY_KEY),
    )
    updated, target_key = apply_automatic_result(
        issue_key,
        previous,
        result,
        observed_commit,
    )
    target_status = statuses[target_key]
    updated["developmentCompleteStatus"] = target_status
    require_property_size(updated)

    require_transition_targets(
        client,
        issue_key,
        [
            statuses["todo"],
            statuses["done_manual"],
            statuses["done_verified"],
        ],
    )
    try:
        client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, updated)
    except SystemExit as error:
        recovery = restore_property(client, issue_key, previous)
        raise SystemExit(
            f"Automatic verification property update failed; {recovery}. Cause: {error}"
        ) from error

    if target_key == "done_auto":
        return updated
    try:
        transition_and_verify(client, issue_key, target_status)
    except SystemExit as error:
        try:
            observed_issue = client.get_issue(issue_key, fields=["status"])
            if _status_name(observed_issue) == target_status:
                return updated
        except SystemExit:
            pass
        recovery = restore_property(client, issue_key, previous)
        raise SystemExit(
            f"Automatic verification transition failed; {recovery}. Cause: {error}"
        ) from error
    return updated


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(
        description="Inspect, preflight, or finalize one pinned automatic Jira verification."
    )
    parser.add_argument("command", choices=("inspect", "preflight", "finalize"))
    parser.add_argument("issue_key")
    parser.add_argument("--config", help="Path to ignored local Jira config JSON.")
    parser.add_argument(
        "--candidate-commit",
        help="Exact checked-out 40-character commit SHA; optional for inspect and required for finalize.",
    )
    parser.add_argument(
        "--result-file",
        help="Versioned automatic-verification result JSON; required for finalize.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    statuses = require_statuses(config)
    require_extended_lifecycle(statuses)
    client = build_client(args.config)

    if args.command == "preflight":
        result = preflight(client, args.issue_key, statuses)
    else:
        if args.command == "inspect":
            result = inspect_candidate(
                client,
                args.issue_key,
                statuses,
                args.candidate_commit,
            )
        else:
            if not args.candidate_commit:
                raise SystemExit("finalize requires --candidate-commit.")
            options = automation(config)
            if options.get("dry_run", True):
                raise SystemExit(
                    "Automatic verification finalization requires automation.dry_run=false."
                )
            if not options.get("allow_transition"):
                raise SystemExit(
                    "Automatic verification finalization requires automation.allow_transition=true."
                )
            if not args.result_file:
                raise SystemExit("finalize requires --result-file.")
            result = finalize_verification(
                client,
                args.issue_key,
                statuses,
                args.candidate_commit,
                read_json_file(args.result_file, "automatic verification result"),
            )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f'{args.issue_key} verification {args.command}: '
            f'{result.get("developmentCompleteStatus", result.get("status", "ready"))}'
        )


if __name__ == "__main__":
    main()

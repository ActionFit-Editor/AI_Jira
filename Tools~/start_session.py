#!/usr/bin/env python3
"""Seal a Jira implementation baseline and enter the configured progress state."""

from __future__ import annotations

import argparse
import json
import re
from uuid import uuid4

from jira_client import adf_to_text, automation, build_client, configure_stdout, load_config, require_statuses
from jira_completion import (
    COMPLETION_PROPERTY_KEY,
    TERMINAL_PROPERTY_STATES,
    build_active_property,
    require_property_identity,
    with_state,
)
from jira_description import parse_description_contract
from transition_issue import find_transition


def transition_and_verify(client, issue_key: str, target_status: str) -> None:
    transition = find_transition(client.list_transitions(issue_key), target_status)
    if not transition:
        raise SystemExit(f'No transition found for configured status "{target_status}".')
    client.transition_issue(issue_key, str(transition["id"]))
    verified = client.get_issue(issue_key, fields=["status"])
    observed = str((verified.get("fields", {}).get("status") or {}).get("name", ""))
    if observed != target_status:
        raise SystemExit(
            f'{issue_key} transition verification failed: expected "{target_status}", '
            f'observed "{observed or "(missing)"}".'
        )


def restore_property(client, issue_key: str, previous: dict | None) -> str:
    try:
        if previous is None:
            client.delete_issue_property(issue_key, COMPLETION_PROPERTY_KEY)
        else:
            client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, previous)
        return "property restored"
    except SystemExit as error:
        return f"property restore failed: {error}"


def require_prerequisites_done(client, issue_key: str, description: str, done_status: str) -> None:
    contract = parse_description_contract(description)
    for prerequisite in contract["autoStart"]["prerequisiteKeys"]:
        if prerequisite.upper() == issue_key.upper():
            raise SystemExit("A Jira issue cannot list itself as an implementation prerequisite.")
        issue = client.get_issue(prerequisite, fields=["status", "resolution"])
        prerequisite_fields = issue.get("fields", {})
        observed = str((prerequisite_fields.get("status") or {}).get("name", ""))
        resolution = prerequisite_fields.get("resolution")
        if observed != done_status and not resolution:
            raise SystemExit(
                f"Implementation prerequisite {prerequisite} is not done: "
                f"expected={done_status}, observed={observed or '(missing)'}."
            )


def require_approved_plan_match(previous: dict | None, baseline: dict, *, required: bool) -> None:
    approved_plan = (previous or {}).get("approvedPlan")
    if approved_plan is None:
        if required:
            raise SystemExit(
                "Implementation from a planning lock requires a verified approved-plan snapshot."
            )
        if (previous or {}).get("state") == "planned":
            pre_refinement = (previous or {}).get("preRefinement")
            if not isinstance(pre_refinement, dict) or pre_refinement.get(
                "descriptionDigest"
            ) != baseline.get("descriptionDigest"):
                raise SystemExit(
                    "Planned Jira requirements changed without a verified coverage artifact. "
                    "Acquire a new planning lock and replan before implementation."
                )
        return
    candidate = approved_plan.get("baselineCandidate") if isinstance(approved_plan, dict) else None
    if not isinstance(candidate, dict) or candidate.get("descriptionDigest") != baseline.get(
        "descriptionDigest"
    ):
        raise SystemExit(
            "Current Jira requirements do not match the plan covered by the planning session. "
            "Return to todo and replan before implementation."
        )


def start_session(
    client,
    issue_key: str,
    statuses: dict[str, str],
    branch: str,
    *,
    session_id: str,
) -> dict:
    issue_pattern = re.compile(
        rf"(?<![A-Z0-9]){re.escape(issue_key.upper())}(?![A-Z0-9])"
    )
    if not issue_pattern.search(branch.upper()):
        raise SystemExit("Implementation branch must contain the exact Jira issue key.")
    issue = client.get_issue(issue_key, fields=["status", "description", "updated"])
    fields = issue.get("fields") or {}
    status = str((fields.get("status") or {}).get("name", ""))
    description = adf_to_text(fields.get("description"))
    require_prerequisites_done(client, issue_key, description, statuses["done"])

    previous = client.get_issue_property(issue_key, COMPLETION_PROPERTY_KEY)
    if previous is not None:
        previous = require_property_identity(previous, issue_key)
    if status == statuses["todo"]:
        if previous and previous.get("state") not in TERMINAL_PROPERTY_STATES:
            raise SystemExit(
                f"Todo issue has a non-terminal completion session ({previous.get('state')}); "
                "repair or close it before restarting."
            )
    elif status == statuses["progress"]:
        if not previous or previous.get("state") != "planning":
            raise SystemExit(
                "Progress issue has no valid planning lock. Legacy progress issues must finalize "
                "incomplete, return to todo, and restart."
            )
    else:
        raise SystemExit(
            "Implementation start requires configured todo or a valid progress planning lock. "
            f"Observed status={status or '(missing)'}."
        )

    prepared = build_active_property(
        issue_key,
        description,
        str(fields.get("updated", "")),
        session_id=session_id,
        branch=branch,
        previous=previous,
    )
    require_approved_plan_match(
        previous,
        prepared["baseline"],
        required=status == statuses["progress"],
    )
    try:
        client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, prepared)
    except SystemExit as error:
        recovery = restore_property(client, issue_key, previous)
        raise SystemExit(
            f"Implementation baseline preparation failed; {recovery}. Cause: {error}"
        ) from error

    if status == statuses["todo"]:
        try:
            transition_and_verify(client, issue_key, statuses["progress"])
        except SystemExit as error:
            recovery = restore_property(client, issue_key, previous)
            raise SystemExit(f"Implementation start transition failed; {recovery}. Cause: {error}") from error

    active = with_state(prepared, "active", startedAt=prepared["updatedAt"])
    try:
        client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, active)
    except SystemExit as error:
        recovery = []
        if status == statuses["todo"]:
            try:
                transition_and_verify(client, issue_key, statuses["todo"])
                recovery.append("status restored to todo")
            except SystemExit as transition_error:
                recovery.append(f"status restore failed: {transition_error}")
        recovery.append(restore_property(client, issue_key, previous))
        raise SystemExit(
            "Implementation baseline activation failed; " + "; ".join(recovery) + f". Cause: {error}"
        ) from error
    return active


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(
        description="Seal a Jira implementation baseline and enter configured progress."
    )
    parser.add_argument("issue_key")
    parser.add_argument("--config", help="Path to ignored local Jira config JSON.")
    parser.add_argument("--branch", required=True, help="Actual checked-out implementation branch.")
    parser.add_argument("--session-id", help="Explicit UUID for deterministic recovery/testing.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    options = automation(config)
    if options.get("dry_run", True):
        raise SystemExit("Implementation start requires automation.dry_run=false.")
    if not options.get("allow_transition"):
        raise SystemExit("Implementation start requires automation.allow_transition=true.")
    statuses = require_statuses(config)
    client = build_client(args.config)
    session = start_session(
        client,
        args.issue_key,
        statuses,
        args.branch,
        session_id=args.session_id or str(uuid4()),
    )
    if args.json:
        print(json.dumps(session, ensure_ascii=False, indent=2))
    else:
        print(
            f'{args.issue_key} implementation session started -> {statuses["progress"]} '
            f'(sessionId={session["sessionId"]}, baselineDigest={session["baseline"]["descriptionDigest"]})'
        )


if __name__ == "__main__":
    main()

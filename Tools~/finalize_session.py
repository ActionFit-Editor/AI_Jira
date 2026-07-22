#!/usr/bin/env python3
"""Finalize one AI Jira work session to configured done or todo state."""

from __future__ import annotations

import argparse
from datetime import date

from jira_client import adf_to_text, automation, build_client, configure_stdout, load_config, require_statuses
from jira_completion import (
    COMPLETION_PROPERTY_KEY,
    read_json_file,
    require_property_identity,
    utc_timestamp,
    with_state,
)
from jira_description import has_handoff_record, prepend_handoff_record
from transition_issue import complete_issue, find_transition


def require_finalization_gates(options: dict, outcome: str) -> None:
    if options.get("dry_run", True):
        raise SystemExit("Session finalization requires automation.dry_run=false.")
    if not options.get("allow_transition"):
        raise SystemExit("Session finalization requires automation.allow_transition=true.")
    if outcome == "incomplete" and not options.get("allow_description_append"):
        raise SystemExit(
            "Incomplete session finalization requires automation.allow_description_append=true."
        )


def require_progress(issue: dict, progress_status: str) -> None:
    current_status = str((issue.get("fields", {}).get("status") or {}).get("name", ""))
    if current_status != progress_status:
        raise SystemExit(
            "Session finalization requires the configured progress state. "
            f"Expected status={progress_status}, observed status={current_status or '(missing)'}."
        )


def transition_and_verify(client, issue_key: str, target_status: str) -> None:
    transition = find_transition(client.list_transitions(issue_key), target_status)
    if not transition:
        raise SystemExit(
            f'No transition found for configured status "{target_status}". '
            "Use transition_issue.py --list to inspect Jira transitions."
        )
    client.transition_issue(issue_key, str(transition["id"]))
    verified = client.get_issue(issue_key, fields=["status"])
    observed = str((verified.get("fields", {}).get("status") or {}).get("name", ""))
    if observed != target_status:
        raise SystemExit(
            f'{issue_key} transition verification failed: expected "{target_status}", '
            f'observed "{observed or "(missing)"}".'
        )


def finalize_done(
    client,
    issue_key: str,
    statuses: dict[str, str],
    pr_url: str | None,
    review: dict,
) -> None:
    complete_issue(client, issue_key, statuses, pr_url, review)


def finalize_incomplete(
    client,
    issue_key: str,
    statuses: dict[str, str],
    record_date: str,
    *,
    completed_work: str,
    remaining_work: str,
    branch_or_pr: str,
    validation: str,
    blocker_or_approval: str,
    resume_condition: str,
) -> None:
    issue = client.get_issue(issue_key, fields=["status", "description"])
    require_progress(issue, statuses["progress"])
    description = adf_to_text(issue.get("fields", {}).get("description"))
    updated = prepend_handoff_record(
        description,
        issue_key,
        record_date,
        completed_work=completed_work,
        remaining_work=remaining_work,
        branch_or_pr=branch_or_pr,
        validation=validation,
        blocker_or_approval=blocker_or_approval,
        resume_condition=resume_condition,
    )
    client.update_description(issue_key, updated)
    verified_issue = client.get_issue(issue_key, fields=["description"])
    verified_description = adf_to_text(verified_issue.get("fields", {}).get("description")).strip()
    if verified_description != updated.strip() or not has_handoff_record(
        verified_description, issue_key
    ):
        raise SystemExit(
            f"{issue_key} handoff verification failed; the issue remains in configured progress."
        )

    previous_property = client.get_issue_property(issue_key, COMPLETION_PROPERTY_KEY)
    closed_property = None
    if previous_property is not None:
        session = require_property_identity(previous_property, issue_key)
        closed_property = with_state(
            session,
            "closed-incomplete",
            closedIncompleteAt=utc_timestamp(),
            handoffDate=record_date,
        )
        try:
            client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, closed_property)
        except SystemExit as error:
            rollback = "completion property restore not attempted"
            try:
                client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, previous_property)
                rollback = "completion property restored"
            except SystemExit as property_error:
                rollback = f"completion property restore failed: {property_error}"
            raise SystemExit(
                f"{issue_key} handoff is verified, but completion property close failed; "
                f"{rollback}: {error}"
            ) from error

    try:
        transition_and_verify(client, issue_key, statuses["todo"])
    except SystemExit as error:
        rollback = "no completion property to restore"
        if closed_property is not None:
            try:
                client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, previous_property)
                rollback = "completion property restored"
            except SystemExit as property_error:
                rollback = f"completion property restore failed: {property_error}"
        raise SystemExit(
            f"{issue_key} handoff is verified, but todo finalization failed; {rollback}: {error}"
        ) from error


def require_incomplete_arguments(args: argparse.Namespace) -> None:
    missing = [
        flag
        for flag, value in (
            ("--completed-work", args.completed_work),
            ("--remaining-work", args.remaining_work),
            ("--branch-pr", args.branch_pr),
            ("--validation", args.validation),
            ("--blocker-approval", args.blocker_approval),
            ("--resume-condition", args.resume_condition),
        )
        if not value
    ]
    if missing:
        raise SystemExit(
            "Incomplete session finalization requires: " + ", ".join(missing) + "."
        )


def validate_handoff_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise SystemExit("Handoff date must use the exact YYYY-MM-DD format.") from error
    if parsed.isoformat() != value:
        raise SystemExit("Handoff date must use the exact YYYY-MM-DD format.")
    return value


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(
        description="Finalize one AI Jira session to configured done or todo state."
    )
    parser.add_argument("issue_key")
    parser.add_argument("--config", help="Path to ignored local Jira config JSON.")
    parser.add_argument("--outcome", choices=["done", "incomplete"], required=True)
    parser.add_argument("--pr-url", help="Required for done finalization.")
    parser.add_argument("--review-file", help="Required completion-review JSON for done finalization.")
    parser.add_argument("--date", default=date.today().isoformat(), help="Handoff date (YYYY-MM-DD).")
    parser.add_argument("--completed-work")
    parser.add_argument("--remaining-work")
    parser.add_argument("--branch-pr")
    parser.add_argument("--validation")
    parser.add_argument("--blocker-approval")
    parser.add_argument("--resume-condition")
    args = parser.parse_args()

    config = load_config(args.config)
    options = automation(config)
    require_finalization_gates(options, args.outcome)
    statuses = require_statuses(config)
    client = build_client(args.config)

    if args.outcome == "done":
        if not args.review_file:
            raise SystemExit("Done finalization requires --review-file.")
        finalize_done(
            client,
            args.issue_key,
            statuses,
            args.pr_url,
            read_json_file(args.review_file, "completion review"),
        )
        print(f'{args.issue_key} session finalized -> {statuses["done"]}')
        return

    require_incomplete_arguments(args)
    finalize_incomplete(
        client,
        args.issue_key,
        statuses,
        validate_handoff_date(args.date),
        completed_work=args.completed_work,
        remaining_work=args.remaining_work,
        branch_or_pr=args.branch_pr,
        validation=args.validation,
        blocker_or_approval=args.blocker_approval,
        resume_condition=args.resume_condition,
    )
    print(f'{args.issue_key} session finalized -> {statuses["todo"]}')


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Transition a Jira issue to one of the configured AI lifecycle states."""

from __future__ import annotations

import argparse
import hashlib
import json
from uuid import uuid4
from urllib.parse import urlparse

from jira_client import adf_to_text, automation, build_client, configure_stdout, load_config, require_statuses
from jira_completion import (
    COMPLETION_PROPERTY_KEY,
    TERMINAL_PROPERTY_STATES,
    build_planning_property,
    read_json_file,
    require_property_identity,
    validate_completion_gate,
    utc_timestamp,
    with_state,
)
from jira_description import validate_qa_completion_record
from jira_statuses import has_extended_lifecycle
from jira_verification import (
    development_complete_target,
    validate_verification_plan,
)


def find_transition(transitions: list[dict], target_status_name: str) -> dict | None:
    # Jira transition names are actions and do not necessarily match their
    # destination statuses. Prefer the explicit destination so an action named
    # after another state cannot select a self-transition.
    for transition in transitions:
        if transition.get("to", {}).get("name") == target_status_name:
            return transition
    for transition in transitions:
        if transition.get("name") == target_status_name:
            return transition
    return None


def validate_done_handoff(issue_key: str, issue: dict, progress_status: str, pr_url: str | None) -> None:
    parsed = urlparse(pr_url or "")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("Transition to done requires --pr-url with the created pull request URL.")
    fields = issue.get("fields", {})
    current_status = str((fields.get("status") or {}).get("name", ""))
    if current_status != progress_status:
        raise SystemExit(
            "Transition to done requires the configured progress state. "
            f"Expected status={progress_status}, observed status={current_status or '(missing)'}."
        )
    description = adf_to_text(fields.get("description"))
    errors = validate_qa_completion_record(description, issue_key)
    if errors:
        raise SystemExit(
            "Transition to done requires a complete Korean QA record: " + "; ".join(errors)
        )


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


def require_transition_targets(
    client,
    issue_key: str,
    target_statuses: list[str] | tuple[str, ...],
) -> None:
    transitions = client.list_transitions(issue_key)
    missing = [
        target
        for target in target_statuses
        if find_transition(transitions, target) is None
    ]
    if missing:
        raise SystemExit(
            "Jira transition preflight is missing configured destination(s): "
            + ", ".join(missing)
        )


def restore_property(client, issue_key: str, previous: dict | None) -> str:
    try:
        if previous is None:
            client.delete_issue_property(issue_key, COMPLETION_PROPERTY_KEY)
        else:
            client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, previous)
        return "completion property restored"
    except SystemExit as error:
        return f"completion property restore failed: {error}"


def begin_planning(client, issue_key: str, statuses: dict[str, str]) -> dict:
    issue = client.get_issue(issue_key, fields=["summary", "status", "description", "updated"])
    fields = issue.get("fields") or {}
    observed = str((fields.get("status") or {}).get("name", ""))
    if observed != statuses["todo"]:
        raise SystemExit(
            f"Planning lock requires status={statuses['todo']}, observed={observed or '(missing)'}."
        )
    previous = client.get_issue_property(issue_key, COMPLETION_PROPERTY_KEY)
    if previous is not None:
        previous = require_property_identity(previous, issue_key)
        if previous.get("state") not in TERMINAL_PROPERTY_STATES:
            raise SystemExit(f"Issue already has a non-terminal completion session: {previous.get('state')}.")
    planning = build_planning_property(
        issue_key,
        adf_to_text(fields.get("description")),
        str(fields.get("updated", "")),
        planning_id=str(uuid4()),
        summary=str(fields.get("summary", "")),
    )
    try:
        client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, planning)
    except SystemExit as error:
        recovery = restore_property(client, issue_key, previous)
        raise SystemExit(
            f"Planning property preparation failed; {recovery}. Cause: {error}"
        ) from error
    try:
        transition_and_verify(client, issue_key, statuses["progress"])
    except SystemExit as error:
        recovery = restore_property(client, issue_key, previous)
        raise SystemExit(f"Planning transition failed; {recovery}. Cause: {error}") from error

    locked_issue = client.get_issue(issue_key, fields=["status", "updated"])
    locked_fields = locked_issue.get("fields") or {}
    locked_status = str((locked_fields.get("status") or {}).get("name", ""))
    locked_updated = str(locked_fields.get("updated", ""))
    if locked_status != statuses["progress"] or not locked_updated:
        verification_error = (
            "Planning lock read-back is incomplete: "
            f"status={locked_status or '(missing)'}, updated={locked_updated or '(missing)'}."
        )
        recovery = []
        try:
            transition_and_verify(client, issue_key, statuses["todo"])
            recovery.append("status restored to todo")
        except SystemExit as transition_error:
            recovery.append(f"status restore failed: {transition_error}")
        recovery.append(restore_property(client, issue_key, previous))
        raise SystemExit(verification_error + " " + "; ".join(recovery))

    locked = with_state(
        planning,
        "planning",
        capturedUpdated=locked_updated,
        lockAcquiredAt=utc_timestamp(),
    )
    try:
        client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, locked)
    except SystemExit as error:
        recovery = []
        try:
            transition_and_verify(client, issue_key, statuses["todo"])
            recovery.append("status restored to todo")
        except SystemExit as transition_error:
            recovery.append(f"status restore failed: {transition_error}")
        recovery.append(restore_property(client, issue_key, previous))
        raise SystemExit(
            "Planning lock property activation failed; " + "; ".join(recovery) + f". Cause: {error}"
        ) from error
    return locked


def finish_planning(client, issue_key: str, statuses: dict[str, str]) -> dict:
    issue = client.get_issue(issue_key, fields=["status"])
    observed = str((issue.get("fields", {}).get("status") or {}).get("name", ""))
    if observed != statuses["progress"]:
        raise SystemExit(
            f"Planning release requires status={statuses['progress']}, observed={observed or '(missing)'}."
        )
    planning = require_property_identity(
        client.get_issue_property(issue_key, COMPLETION_PROPERTY_KEY), issue_key
    )
    if planning.get("state") != "planning":
        raise SystemExit("Planning release requires an active planning property.")
    planned = with_state(planning, "planned", planningClosedAt=utc_timestamp())
    try:
        client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, planned)
    except SystemExit as error:
        recovery = restore_property(client, issue_key, planning)
        raise SystemExit(
            f"Planning property close failed; {recovery}. Cause: {error}"
        ) from error
    try:
        transition_and_verify(client, issue_key, statuses["todo"])
    except SystemExit as error:
        try:
            client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, planning)
        except SystemExit as property_error:
            raise SystemExit(
                f"Planning release failed and property rollback failed: {property_error}. Original cause: {error}"
            ) from error
        raise
    return planned


def complete_issue(
    client,
    issue_key: str,
    statuses: dict[str, str],
    pr_url: str | None,
    review: dict,
    verification_plan: dict | None = None,
) -> dict:
    issue = client.get_issue(issue_key, fields=["status", "description"])
    property_value = client.get_issue_property(issue_key, COMPLETION_PROPERTY_KEY)
    extended = has_extended_lifecycle(statuses)
    active = validate_completion_gate(
        issue_key,
        issue,
        statuses["progress"],
        property_value,
        review,
        pr_url,
        allow_pending_validation=extended,
    )
    target_status = statuses["done"]
    property_state = "completed"
    normalized_verification = None
    if extended:
        if verification_plan is None:
            raise SystemExit(
                "Extended lifecycle completion requires --verification-plan-file."
            )
        normalized_verification = validate_verification_plan(
            verification_plan,
            issue_key=issue_key,
            session=active,
            pr_url=str(pr_url),
            description=adf_to_text((issue.get("fields") or {}).get("description")),
        )
        target_status, property_state = development_complete_target(
            statuses, normalized_verification
        )
        if property_state == "completed":
            qa_errors = validate_qa_completion_record(
                adf_to_text((issue.get("fields") or {}).get("description")),
                issue_key,
            )
            if qa_errors:
                raise SystemExit(
                    "Verified completion requires no unverified QA items: "
                    + "; ".join(qa_errors)
                )
        else:
            qa_errors = validate_qa_completion_record(
                adf_to_text((issue.get("fields") or {}).get("description")),
                issue_key,
                require_no_unverified=False,
                require_pending_unverified=True,
            )
            if qa_errors:
                raise SystemExit(
                    "Deferred completion requires pending QA items: "
                    + "; ".join(qa_errors)
                )
        require_transition_targets(
            client,
            issue_key,
            [
                statuses["done_auto"],
                statuses["done_manual"],
                statuses["done_verified"],
            ],
        )
    else:
        if verification_plan is not None:
            raise SystemExit(
                "Verification plans require the complete extended lifecycle status mappings."
            )
        require_transition_targets(client, issue_key, [target_status])

    review_digest = "sha256:" + hashlib.sha256(
        json.dumps(review, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    completion_fields = {
        "developmentCompletedAt": utc_timestamp(),
        "prUrl": pr_url,
        "reviewDigest": review_digest,
        "review": review,
        "developmentCompleteStatus": target_status,
    }
    if property_state == "completed":
        completion_fields["completedAt"] = completion_fields["developmentCompletedAt"]
    if normalized_verification is not None:
        completion_fields["verification"] = normalized_verification
    completed = with_state(
        active,
        property_state,
        **completion_fields,
    )
    try:
        client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, completed)
    except SystemExit as error:
        recovery = restore_property(client, issue_key, active)
        raise SystemExit(
            f"Completion property preparation failed; {recovery}. Cause: {error}"
        ) from error
    try:
        transition_and_verify(client, issue_key, target_status)
    except SystemExit as error:
        try:
            observed_issue = client.get_issue(issue_key, fields=["status"])
            observed = str(
                (
                    (observed_issue.get("fields") or {}).get("status") or {}
                ).get("name", "")
            )
            if observed == target_status:
                return completed
        except SystemExit:
            pass
        try:
            client.set_issue_property(issue_key, COMPLETION_PROPERTY_KEY, active)
        except SystemExit as property_error:
            raise SystemExit(
                f"Done transition failed and completion property rollback failed: {property_error}. "
                f"Original cause: {error}"
            ) from error
        raise
    return completed


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Move a Jira issue through configured AI lifecycle states.")
    parser.add_argument("issue_key")
    parser.add_argument("--config", help="Path to ignored local Jira config JSON.")
    parser.add_argument("--to", choices=["todo", "progress", "done"], help="Internal target state.")
    parser.add_argument("--pr-url", help="Required when moving to done after PR creation.")
    parser.add_argument("--review-file", help="Required completion-review JSON when moving to done.")
    parser.add_argument(
        "--verification-plan-file",
        help="Required versioned deferred-validation plan when the extended lifecycle is enabled.",
    )
    parser.add_argument(
        "--purpose",
        choices=["planning"],
        help="Required for transient todo/progress planning-lock transitions.",
    )
    parser.add_argument("--list", action="store_true", help="List available transitions.")
    parser.add_argument("--json", action="store_true", help="Print lifecycle property JSON.")
    args = parser.parse_args()

    config = load_config(args.config)
    statuses = require_statuses(config)
    client = build_client(args.config)
    if args.list or not args.to:
        transitions = client.list_transitions(args.issue_key)
        for transition in transitions:
            print(f'{transition.get("id")}: {transition.get("name")} -> {transition.get("to", {}).get("name", "")}')
        return
    options = automation(config)
    if options.get("dry_run", True):
        raise SystemExit("Lifecycle transitions require automation.dry_run=false.")
    if args.to == "done":
        if not args.review_file:
            raise SystemExit("Transition to done requires --review-file.")
        review = read_json_file(args.review_file, "completion review")
        verification_plan = (
            read_json_file(args.verification_plan_file, "verification plan")
            if args.verification_plan_file
            else None
        )
        result = complete_issue(
            client,
            args.issue_key,
            statuses,
            args.pr_url,
            review,
            verification_plan,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f'{args.issue_key} -> {result["developmentCompleteStatus"]}')
        return
    if args.purpose != "planning":
        raise SystemExit(
            f"Direct transition to {args.to} is forbidden. Use --purpose planning for a transient "
            "planning lock, start for implementation, or finalize --outcome incomplete."
        )
    if args.to == "progress":
        result = begin_planning(client, args.issue_key, statuses)
    else:
        result = finish_planning(client, args.issue_key, statuses)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f'{args.issue_key} -> {statuses[args.to]} (planning)')


if __name__ == "__main__":
    main()

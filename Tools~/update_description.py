#!/usr/bin/env python3
"""Apply gated append, QA prepend, or approved managed-plan Jira updates."""

from __future__ import annotations

import argparse
from datetime import date

from jira_client import adf_to_text, automation, build_client, configure_stdout, load_config
from jira_completion import (
    COMPLETION_PROPERTY_KEY,
    read_json_file,
    require_property_identity,
    utc_timestamp,
    validate_plan_coverage,
    with_state,
)
from jira_description import prepend_qa_record, replace_managed_plan


def read_text(args: argparse.Namespace) -> str:
    if args.text:
        return args.text
    if args.file:
        with open(args.file, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    raise SystemExit("Provide --text or --file.")


def append_requirements(description: str, text: str) -> str:
    block = f"## Additional Requirements\n\n### {date.today().isoformat()}\n{text.strip()}\n"
    if not description.strip():
        return block
    return description.rstrip() + "\n\n" + block


def require_mode_gate(options: dict, mode: str) -> None:
    gate_by_mode = {
        "append-requirements": "allow_description_append",
        "prepend-qa": "allow_description_prepend_qa",
        "replace-plan": "allow_description_plan_refinement",
    }
    gate = gate_by_mode[mode]
    if not options.get(gate):
        raise SystemExit(f"Description mode {mode} requires automation.{gate}=true.")


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Safely update an approved Jira description region.")
    parser.add_argument("issue_key")
    parser.add_argument("--config", help="Path to ignored local Jira config JSON.")
    parser.add_argument(
        "--mode",
        choices=["append-requirements", "prepend-qa", "replace-plan"],
        required=True,
    )
    parser.add_argument("--text")
    parser.add_argument("--file")
    parser.add_argument(
        "--expected-updated",
        help="Required for replace-plan; Jira updated timestamp captured from the approved transient planning lock.",
    )
    parser.add_argument(
        "--coverage-file",
        help="Required plan-coverage JSON for replace-plan.",
    )
    args = parser.parse_args()

    text = read_text(args)
    config = load_config(args.config)
    options = automation(config)
    require_mode_gate(options, args.mode)
    client = build_client(args.config)
    issue = client.get_issue(args.issue_key, fields=["description", "status", "updated"])
    fields = issue.get("fields", {})
    current_updated = str(fields.get("updated", ""))
    current_status = str((fields.get("status") or {}).get("name", ""))
    current = adf_to_text(issue.get("fields", {}).get("description"))
    if args.mode == "append-requirements":
        updated = append_requirements(current, text)
    elif args.mode == "prepend-qa":
        updated = prepend_qa_record(current, args.issue_key, date.today().isoformat(), text)
    else:
        if not args.expected_updated:
            raise SystemExit("replace-plan requires --expected-updated from the planning-lock read.")
        if current_updated != args.expected_updated:
            raise SystemExit(
                "Jira description changed after planning started; refusing to overwrite the managed plan. "
                f"Expected updated={args.expected_updated}, observed updated={current_updated}."
            )
        planning = require_property_identity(
            client.get_issue_property(args.issue_key, COMPLETION_PROPERTY_KEY),
            args.issue_key,
        )
        if planning.get("state") != "planning":
            raise SystemExit("replace-plan requires an active Jira completion planning property.")
        if planning.get("capturedUpdated") != args.expected_updated:
            raise SystemExit(
                "replace-plan expected-updated does not match the sealed planning snapshot."
            )
        if not args.coverage_file:
            raise SystemExit("replace-plan requires --coverage-file.")
        progress_status = str((config.get("statuses") or {}).get("progress", ""))
        if not progress_status or current_status != progress_status:
            raise SystemExit(
                "replace-plan requires the issue to hold the configured progress planning lock. "
                f"Expected status={progress_status or '(missing)'}, observed status={current_status or '(missing)'}."
            )
        try:
            updated = replace_managed_plan(current, text)
            coverage = read_json_file(args.coverage_file, "plan coverage")
            approved_snapshot = validate_plan_coverage(planning, updated, coverage)
        except ValueError as error:
            raise SystemExit(str(error)) from error
    client.update_description(args.issue_key, updated)
    verified_issue = client.get_issue(args.issue_key, fields=["description", "updated"])
    verified = adf_to_text(verified_issue.get("fields", {}).get("description")).strip()
    if verified != updated.strip():
        if args.mode != "replace-plan":
            raise SystemExit(f"{args.issue_key} description verification failed after {args.mode}.")
        recovery = "description restore not attempted"
        try:
            client.update_description(args.issue_key, current)
            restored = client.get_issue(args.issue_key, fields=["description"])
            restored_text = adf_to_text(restored.get("fields", {}).get("description")).strip()
            recovery = (
                "description restored"
                if restored_text == current.strip()
                else "description restore verification failed"
            )
        except SystemExit as error:
            recovery = f"description restore failed: {error}"
        raise SystemExit(
            f"{args.issue_key} description verification failed after replace-plan; {recovery}."
        )
    if args.mode == "replace-plan":
        approved_plan = {
            "baselineCandidate": approved_snapshot,
            "coverage": coverage,
            "capturedUpdated": str(verified_issue.get("fields", {}).get("updated", "")),
            "approvedAt": utc_timestamp(),
        }
        updated_property = with_state(planning, "planning", approvedPlan=approved_plan)
        try:
            client.set_issue_property(args.issue_key, COMPLETION_PROPERTY_KEY, updated_property)
        except SystemExit as property_error:
            recovery = []
            try:
                client.update_description(args.issue_key, current)
                restored = client.get_issue(args.issue_key, fields=["description"])
                restored_text = adf_to_text(restored.get("fields", {}).get("description")).strip()
                recovery.append(
                    "description restored" if restored_text == current.strip() else "description restore verification failed"
                )
            except SystemExit as description_error:
                recovery.append(f"description restore failed: {description_error}")
            try:
                client.set_issue_property(args.issue_key, COMPLETION_PROPERTY_KEY, planning)
                recovery.append("planning property restored")
            except SystemExit as rollback_error:
                recovery.append(f"planning property restore failed: {rollback_error}")
            raise SystemExit(
                "replace-plan property verification failed; "
                + "; ".join(recovery)
                + f". Cause: {property_error}"
            ) from property_error
    print(f"{args.issue_key} description updated with {args.mode}.")


if __name__ == "__main__":
    main()

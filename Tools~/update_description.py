#!/usr/bin/env python3
"""Apply gated append, QA prepend, or approved managed-plan Jira updates."""

from __future__ import annotations

import argparse
from datetime import date

from jira_client import adf_to_text, automation, build_client, configure_stdout, load_config
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
        progress_status = str((config.get("statuses") or {}).get("progress", ""))
        if not progress_status or current_status != progress_status:
            raise SystemExit(
                "replace-plan requires the issue to hold the configured progress planning lock. "
                f"Expected status={progress_status or '(missing)'}, observed status={current_status or '(missing)'}."
            )
        try:
            updated = replace_managed_plan(current, text)
        except ValueError as error:
            raise SystemExit(str(error)) from error
    client.update_description(args.issue_key, updated)
    verified_issue = client.get_issue(args.issue_key, fields=["description"])
    verified = adf_to_text(verified_issue.get("fields", {}).get("description")).strip()
    if verified != updated.strip():
        raise SystemExit(f"{args.issue_key} description verification failed after {args.mode}.")
    print(f"{args.issue_key} description updated with {args.mode}.")


if __name__ == "__main__":
    main()

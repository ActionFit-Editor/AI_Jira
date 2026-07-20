#!/usr/bin/env python3
"""Transition a Jira issue to one of the configured AI lifecycle states."""

from __future__ import annotations

import argparse
from urllib.parse import urlparse

from jira_client import adf_to_text, build_client, configure_stdout, load_config, require_statuses
from jira_description import has_qa_completion_record


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
    if not has_qa_completion_record(description, issue_key):
        raise SystemExit(
            "Transition to done requires a verified Korean QA completion record at the top of the description."
        )


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Move a Jira issue through configured AI lifecycle states.")
    parser.add_argument("issue_key")
    parser.add_argument("--config", help="Path to ignored local Jira config JSON.")
    parser.add_argument("--to", choices=["todo", "progress", "done"], help="Internal target state.")
    parser.add_argument("--pr-url", help="Required when moving to done after PR creation.")
    parser.add_argument("--list", action="store_true", help="List available transitions.")
    args = parser.parse_args()

    config = load_config(args.config)
    statuses = require_statuses(config)
    client = build_client(args.config)
    transitions = client.list_transitions(args.issue_key)
    if args.list or not args.to:
        for transition in transitions:
            print(f'{transition.get("id")}: {transition.get("name")} -> {transition.get("to", {}).get("name", "")}')
        return
    if args.to == "done":
        issue = client.get_issue(args.issue_key, fields=["status", "description"])
        validate_done_handoff(args.issue_key, issue, statuses["progress"], args.pr_url)
    target = statuses[args.to]
    transition = find_transition(transitions, target)
    if not transition:
        raise SystemExit(f'No transition found for configured status "{target}". Use --list to inspect Jira transitions.')
    client.transition_issue(args.issue_key, str(transition["id"]))
    verified = client.get_issue(args.issue_key, fields=["status"])
    observed = str((verified.get("fields", {}).get("status") or {}).get("name", ""))
    if observed != target:
        raise SystemExit(
            f'{args.issue_key} transition verification failed: expected "{target}", observed "{observed}".'
        )
    print(f'{args.issue_key} -> {target}')


if __name__ == "__main__":
    main()

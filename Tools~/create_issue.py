#!/usr/bin/env python3
"""Create a Jira issue with a Korean title and approved mixed-language description."""

from __future__ import annotations

import argparse

from jira_client import build_client, configure_stdout, load_config

from jira_description import parse_description_contract


def read_description(args: argparse.Namespace) -> str:
    if args.description:
        return args.description
    if args.description_file:
        with open(args.description_file, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    raise SystemExit("Provide --description or --description-file.")


def validate_new_description(description: str) -> None:
    contract = parse_description_contract(description)
    if not contract["structurallyComplete"] or contract["autoStart"]["hasUnresolvedDecisions"]:
        reasons = ", ".join(contract["reasons"]) or "managed contract is incomplete"
        raise SystemExit(f"Jira description does not satisfy the managed contract: {reasons}")


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Create a Jira task using the configured project.")
    parser.add_argument("--config", help="Path to ignored local Jira config JSON.")
    parser.add_argument("--summary", required=True, help="Korean Jira issue title.")
    parser.add_argument("--description", help="Approved mixed-language Jira issue description.")
    parser.add_argument("--description-file", help="UTF-8 file containing the approved Jira description.")
    parser.add_argument("--issue-type", help="Override configured issue type.")
    args = parser.parse_args()

    config = load_config(args.config)
    client = build_client(args.config)
    issue_type = args.issue_type or config.get("issue_create", {}).get("issue_type", "Task")
    description = read_description(args)
    validate_new_description(description)
    result = client.create_issue(args.summary, description, issue_type)
    key = result.get("key", "(dry-run)")
    print(f"Created Jira issue: {key}")


if __name__ == "__main__":
    main()

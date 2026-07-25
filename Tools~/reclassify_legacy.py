#!/usr/bin/env python3
"""Inspect, preflight, apply, or rollback one legacy Jira todo reclassification."""

from __future__ import annotations

import argparse
import json

from jira_client import build_client, configure_stdout, load_config, require_statuses
from jira_completion import read_json_file
from jira_legacy_reclassification import (
    apply_reclassification,
    prepare_reclassification,
    rollback_reclassification,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely reclassify exactly one implementation-complete legacy Jira todo."
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)
    for operation in ("inspect", "preflight", "apply"):
        command = subparsers.add_parser(operation)
        command.add_argument("issue_key")
        command.add_argument("--config", help="Path to ignored local Jira config JSON.")
        command.add_argument("--expected-updated", required=True)
        command.add_argument("--review-file", required=True)
        command.add_argument("--verification-plan-file", required=True)
        command.add_argument("--qa-file", required=True)
        command.add_argument("--json", action="store_true")

    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("issue_key")
    rollback.add_argument("--config", help="Path to ignored local Jira config JSON.")
    rollback.add_argument("--migration-id", required=True)
    rollback.add_argument("--expected-updated", required=True)
    rollback.add_argument("--json", action="store_true")
    return parser


def write_result(value: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return
    if value.get("blockers"):
        print(
            f'{value["issueKey"]} {value["operation"]} blocked: '
            + "; ".join(item["message"] for item in value["blockers"])
        )
    elif value.get("rolledBack"):
        print(f'{value["issueKey"]} legacy reclassification rolled back.')
    else:
        print(
            f'{value["issueKey"]} {value["operation"]} -> '
            f'{value.get("targetStatus") or value.get("current", {}).get("status", "")}'
        )


def main() -> None:
    configure_stdout()
    args = build_parser().parse_args()
    config = load_config(args.config)
    statuses = require_statuses(config)
    client = build_client(args.config)

    if args.operation == "rollback":
        result = rollback_reclassification(
            client,
            config,
            statuses,
            args.issue_key,
            migration_id=args.migration_id,
            expected_updated=args.expected_updated,
        )
        write_result(result, args.json)
        return

    review = read_json_file(args.review_file, "legacy review")
    verification_plan = read_json_file(
        args.verification_plan_file, "legacy verification plan"
    )
    qa_artifact = read_json_file(args.qa_file, "legacy QA artifact")
    if args.operation == "apply":
        result = apply_reclassification(
            client,
            config,
            statuses,
            args.issue_key,
            expected_updated=args.expected_updated,
            review_value=review,
            verification_value=verification_plan,
            qa_value=qa_artifact,
        )
    else:
        result, _ = prepare_reclassification(
            client,
            config,
            statuses,
            args.issue_key,
            operation=args.operation,
            expected_updated=args.expected_updated,
            review_value=review,
            verification_value=verification_plan,
            qa_value=qa_artifact,
            enforce_write_gates=args.operation == "preflight",
        )
    write_result(result, args.json)
    if result.get("blockers"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()

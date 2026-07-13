#!/usr/bin/env python3
"""List unresolved Jira work assigned to the current user."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from jira_work_items import configure_output, load_config, query_work_items, write_json, write_text


def positive_result_limit(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError("must be between 1 and 100")
    return number


def build_parser(default_state: str = "all", default_config: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List unresolved Jira work assigned to the authenticated user."
    )
    parser.add_argument(
        "--state",
        choices=("todo", "progress", "all"),
        default=default_state,
        help="Configured workflow states to include; all means todo and progress.",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--max-results", type=positive_result_limit, default=50)
    parser.add_argument(
        "--config",
        default=default_config,
        help="Ignored UTF-8 Jira config path; defaults to Tools/AI/jira/config.local.json.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    default_state: str = "all",
    default_config: str | None = None,
) -> None:
    configure_output()
    args = build_parser(default_state=default_state, default_config=default_config).parse_args(argv)
    config = load_config(args.config)
    result = query_work_items(config, state=args.state, max_results=args.max_results)
    if args.format == "json":
        write_json(result)
    else:
        write_text(result)


if __name__ == "__main__":
    main()

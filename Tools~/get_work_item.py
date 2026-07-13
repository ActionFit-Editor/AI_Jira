#!/usr/bin/env python3
"""Read one Jira work item without changing Jira state."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from jira_work_items import configure_output, load_config, query_work_item, write_issue_text, write_json


def build_parser(default_config: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read one Jira issue and its implementation context.")
    parser.add_argument("issue_key")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--config",
        default=default_config,
        help="Ignored UTF-8 Jira config path; defaults to Tools/AI/jira/config.local.json.",
    )
    return parser


def main(argv: Sequence[str] | None = None, default_config: str | None = None) -> None:
    configure_output()
    args = build_parser(default_config).parse_args(argv)
    result = query_work_item(load_config(args.config), args.issue_key)
    if args.format == "json":
        write_json(result)
    else:
        write_issue_text(result)


if __name__ == "__main__":
    main()

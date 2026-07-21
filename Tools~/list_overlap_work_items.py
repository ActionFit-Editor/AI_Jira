#!/usr/bin/env python3
"""List complete project-wide Jira evidence for read-only overlap inspection."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from jira_work_items import (
    configure_output,
    load_config,
    query_overlap_work_items,
    write_json,
    write_text,
)


def page_size(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError("must be between 1 and 100")
    return number


def build_parser(default_config: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "List every configured todo, progress, and done issue in the Jira project "
            "for read-only overlap inspection."
        )
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--page-size", type=page_size, default=100)
    parser.add_argument(
        "--config",
        default=default_config,
        help="Ignored UTF-8 Jira config path; defaults to Tools/AI/jira/config.local.json.",
    )
    return parser


def main(argv: Sequence[str] | None = None, default_config: str | None = None) -> None:
    configure_output()
    args = build_parser(default_config=default_config).parse_args(argv)
    config = load_config(args.config)
    result = query_overlap_work_items(config, page_size=args.page_size)
    if args.format == "json":
        write_json(result)
    else:
        write_text(result)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Emit bounded classification evidence without full Jira descriptions."""

from __future__ import annotations

import argparse

from jira_classification import classify_work_items
from jira_work_items import STATE_FILTERS, configure_output, load_config, write_json


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", choices=STATE_FILTERS, default="todo")
    parser.add_argument("--max-results", type=int, default=100)
    parser.add_argument("--config")
    args = parser.parse_args()
    write_json(
        classify_work_items(
            load_config(args.config),
            state=args.state,
            max_results=args.max_results,
        )
    )


if __name__ == "__main__":
    main()

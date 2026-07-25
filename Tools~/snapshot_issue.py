#!/usr/bin/env python3
"""Print a bounded Jira execution snapshot for one issue."""

from __future__ import annotations

import argparse
import json

from jira_snapshot import build_snapshot
from jira_work_items import configure_output, load_config


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("issue_key")
    parser.add_argument("--config")
    args = parser.parse_args()
    print(json.dumps(build_snapshot(load_config(args.config), args.issue_key), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

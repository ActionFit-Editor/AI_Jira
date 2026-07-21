#!/usr/bin/env python3
"""Locate and run the AI Jira package's read-only CLI from an installed skill."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def find_project_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "Packages" / "manifest.json").is_file():
            return candidate
    raise SystemExit("Unity project root was not found. Run this command from inside a Unity project.")


def find_tools(project_root: Path) -> Path:
    embedded = project_root / "Packages" / "com.actionfit.ai-jira" / "Tools~"
    if embedded.is_dir():
        return embedded

    cache_root = project_root / "Library" / "PackageCache"
    candidates = sorted(cache_root.glob("com.actionfit.ai-jira@*/Tools~"), reverse=True)
    if candidates:
        return candidates[0]
    raise SystemExit(
        "AI Jira package tools were not found. Install com.actionfit.ai-jira and let Unity resolve packages."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an AI Jira read-only package command.")
    parser.add_argument("command", choices=("list", "detail", "overlap"))
    parser.add_argument("issue_key", nargs="?")
    args, remainder = parser.parse_known_args()

    if args.command == "detail" and not args.issue_key:
        parser.error("detail requires an issue key")
    if args.command in {"list", "overlap"} and args.issue_key:
        parser.error(f"{args.command} does not accept an issue key")

    root = find_project_root(Path.cwd().resolve())
    tools = find_tools(root)
    scripts = {
        "list": "list_work_items.py",
        "detail": "get_work_item.py",
        "overlap": "list_overlap_work_items.py",
    }
    script = tools / scripts[args.command]
    command = [sys.executable, str(script)]
    if args.issue_key:
        command.append(args.issue_key)
    command.extend(remainder)
    raise SystemExit(subprocess.call(command, cwd=root))


if __name__ == "__main__":
    main()

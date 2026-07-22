#!/usr/bin/env python3
"""Locate and run package-owned AI Jira write commands from an installed skill."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


COMMAND_SCRIPTS = {
    "create": "create_issue.py",
    "update-description": "update_description.py",
    "transition": "transition_issue.py",
    "start": "start_session.py",
    "finalize": "finalize_session.py",
}


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
        "AI Jira package write tools were not found. Install com.actionfit.ai-jira and let Unity resolve packages."
    )


def usage() -> str:
    commands = " | ".join(COMMAND_SCRIPTS)
    return f"Usage: ai_jira_write_cli.py <{commands}> [command arguments]"


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print(usage())
        return

    command_name = sys.argv[1]
    script_name = COMMAND_SCRIPTS.get(command_name)
    if script_name is None:
        raise SystemExit(f"Unsupported AI Jira write command: {command_name}\n{usage()}")

    root = find_project_root(Path.cwd().resolve())
    script = find_tools(root) / script_name
    if not script.is_file():
        raise SystemExit(f"AI Jira package write command is missing: {script_name}")

    raise SystemExit(
        subprocess.call([sys.executable, str(script), *sys.argv[2:]], cwd=root)
    )


if __name__ == "__main__":
    main()

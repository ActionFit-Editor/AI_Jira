#!/usr/bin/env python3
"""Locate and run the AI Jira package's initialization CLI from an installed skill."""

from __future__ import annotations

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
    root = find_project_root(Path.cwd().resolve())
    script = find_tools(root) / "jira_init.py"
    raise SystemExit(subprocess.call([sys.executable, str(script), *sys.argv[1:]], cwd=root))


if __name__ == "__main__":
    main()

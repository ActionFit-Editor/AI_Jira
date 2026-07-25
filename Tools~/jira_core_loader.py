#!/usr/bin/env python3
"""Locate AI Jira Core with embedded-before-cache precedence."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def find_core_tools(start: Path | None = None) -> Path:
    origin = (start or Path(__file__)).resolve()
    for candidate in (origin.parent, *origin.parents):
        packages = candidate / "Packages"
        if not packages.is_dir():
            continue
        embedded = packages / "com.actionfit.ai-jira.core" / "Tools~"
        if embedded.is_dir():
            return embedded
        cache = candidate / "Library" / "PackageCache"
        cached = sorted(cache.glob("com.actionfit.ai-jira.core@*/Tools~"), reverse=True)
        if cached:
            return cached[0]
    raise SystemExit(
        "AI Jira Core tools were not found. Install com.actionfit.ai-jira.core and let Unity resolve packages."
    )


def load_core():
    tools = find_core_tools()
    tools_text = str(tools)
    if tools_text not in sys.path:
        sys.path.insert(0, tools_text)
    return importlib.import_module("ai_jira_core")

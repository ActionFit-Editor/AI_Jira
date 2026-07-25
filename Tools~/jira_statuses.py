#!/usr/bin/env python3
"""Shared Jira lifecycle status contract and classification helpers."""

from __future__ import annotations

from typing import Any


BASE_STATUS_KEYS = ("todo", "progress", "done")
EXTENDED_DONE_STATUS_KEYS = ("done_auto", "done_manual", "done_verified")
EXTENDED_STATE_KEYS = {
    "automatic-validation": ("done_auto",),
    "manual-validation": ("done_manual",),
    "verified": ("done_verified",),
    "development-complete": EXTENDED_DONE_STATUS_KEYS,
}


def require_statuses(config: dict[str, Any]) -> dict[str, str]:
    mappings = config.get("statuses") or {}
    missing = [key for key in BASE_STATUS_KEYS if not mappings.get(key)]
    if missing:
        raise SystemExit(
            f"Missing Jira status mapping(s): {', '.join(missing)}. "
            "Fill Tools/AI/jira/config.local.json before running Jira automation."
        )

    configured_extended = [key for key in EXTENDED_DONE_STATUS_KEYS if mappings.get(key)]
    if configured_extended and len(configured_extended) != len(EXTENDED_DONE_STATUS_KEYS):
        missing_extended = [
            key for key in EXTENDED_DONE_STATUS_KEYS if not mappings.get(key)
        ]
        raise SystemExit(
            "Extended Jira verification lifecycle is partial. Configure all of "
            f"{', '.join(EXTENDED_DONE_STATUS_KEYS)} or remove them all. "
            f"Missing: {', '.join(missing_extended)}."
        )

    selected_keys = list(BASE_STATUS_KEYS)
    if configured_extended:
        selected_keys.extend(EXTENDED_DONE_STATUS_KEYS)
    statuses = {key: str(mappings[key]).strip() for key in selected_keys}
    empty = [key for key, value in statuses.items() if not value]
    if empty:
        raise SystemExit(f"Missing Jira status mapping(s): {', '.join(empty)}")

    by_name: dict[str, list[str]] = {}
    for key, value in statuses.items():
        by_name.setdefault(value.casefold(), []).append(key)
    duplicates = [keys for keys in by_name.values() if len(keys) > 1]
    if duplicates:
        rendered = "; ".join("/".join(keys) for keys in duplicates)
        raise SystemExit(
            "Jira lifecycle status mappings must resolve to distinct status names: "
            + rendered
        )
    return statuses


def has_extended_lifecycle(statuses: dict[str, str]) -> bool:
    return all(statuses.get(key) for key in EXTENDED_DONE_STATUS_KEYS)


def require_extended_lifecycle(statuses: dict[str, str]) -> None:
    if not has_extended_lifecycle(statuses):
        raise SystemExit(
            "This operation requires statuses.done_auto, statuses.done_manual, "
            "and statuses.done_verified."
        )


def status_keys_for_state(statuses: dict[str, str], state: str) -> tuple[str, ...]:
    if state == "todo":
        return ("todo",)
    if state == "progress":
        return ("progress",)
    if state == "all":
        return ("todo", "progress")
    keys = EXTENDED_STATE_KEYS.get(state)
    if keys is None:
        raise ValueError(f"Unsupported state filter: {state}")
    require_extended_lifecycle(statuses)
    return keys


def overlap_status_keys(statuses: dict[str, str]) -> tuple[str, ...]:
    if has_extended_lifecycle(statuses):
        return BASE_STATUS_KEYS + EXTENDED_DONE_STATUS_KEYS
    return BASE_STATUS_KEYS


def ordinary_done_statuses(statuses: dict[str, str]) -> set[str]:
    values = {statuses["done"]}
    if has_extended_lifecycle(statuses):
        values.update(statuses[key] for key in EXTENDED_DONE_STATUS_KEYS)
    return values


def lifecycle_state(status_name: str, statuses: dict[str, str]) -> str:
    for key in BASE_STATUS_KEYS:
        if status_name == statuses.get(key):
            return key
    if has_extended_lifecycle(statuses):
        states = {
            "done_auto": "automatic-validation",
            "done_manual": "manual-validation",
            "done_verified": "verified",
        }
        for key, state in states.items():
            if status_name == statuses[key]:
                return state
    return "unknown"


def verification_state(status_name: str, statuses: dict[str, str]) -> dict[str, Any]:
    state = lifecycle_state(status_name, statuses)
    extended = has_extended_lifecycle(statuses)
    return {
        "enabled": extended,
        "state": state if state in EXTENDED_STATE_KEYS else None,
        "developmentComplete": (
            state in EXTENDED_STATE_KEYS
            or (not extended and state == "done")
        ),
    }

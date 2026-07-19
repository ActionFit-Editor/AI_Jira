#!/usr/bin/env python3
"""Diagnose Jira access and bootstrap ignored project-local configuration."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import stat
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from jira_work_items import build_jql, configure_output


DEFAULT_CONFIG = Path("Tools/AI/jira/config.local.json")
TOKEN_URL = "https://id.atlassian.com/manage-profile/security/api-tokens"
CONFIG_TEMPLATE: dict[str, Any] = {
    "jira_base_url": "",
    "project_key": "",
    "statuses": {
        "todo": "",
        "progress": "",
        "done": "",
    },
    "auth": {
        "email": "",
        "api_token": "",
        "email_env": "JIRA_EMAIL",
        "api_token_env": "JIRA_API_TOKEN",
    },
    "automation": {
        "dry_run": True,
    },
}


def find_project_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "Packages" / "manifest.json").is_file():
            return candidate.resolve()
    raise SystemExit("Unity project root was not found. Run this command from inside a Unity project.")


def resolve_config_path(project_root: Path, explicit: str | None = None) -> Path:
    configured = explicit or os.getenv("AI_JIRA_CONFIG")
    path = Path(configured).expanduser() if configured else DEFAULT_CONFIG
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def _relative_display(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("Jira config root must be a JSON object.")
    return value


def _credential_state(config: dict[str, Any]) -> tuple[str, str, str, str]:
    auth = config.get("auth") if isinstance(config.get("auth"), dict) else {}
    email_env = str(auth.get("email_env") or "JIRA_EMAIL")
    token_env = str(auth.get("api_token_env") or "JIRA_API_TOKEN")
    configured_email = str(auth.get("email") or "").strip()
    configured_token = str(auth.get("api_token") or "").strip()
    environment_email = os.getenv(email_env, "").strip()
    environment_token = os.getenv(token_env, "").strip()
    email = configured_email or environment_email
    token = configured_token or environment_token
    email_source = "local-config" if configured_email else "environment" if environment_email else "missing"
    token_source = "local-config" if configured_token else "environment" if environment_token else "missing"
    return email, token, email_source, token_source


def _misplaced_credential_fields(config: dict[str, Any]) -> list[str]:
    """Identify credential values entered into *_env name fields without exposing them."""
    auth = config.get("auth") if isinstance(config.get("auth"), dict) else {}
    configured_email = str(auth.get("email") or "").strip()
    configured_token = str(auth.get("api_token") or "").strip()
    email_env = str(auth.get("email_env") or "JIRA_EMAIL").strip()
    token_env = str(auth.get("api_token_env") or "JIRA_API_TOKEN").strip()

    email_misplaced = not configured_email and "@" in email_env
    token_looks_like_env_name = bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token_env))
    token_misplaced = (
        not configured_token
        and token_env != "JIRA_API_TOKEN"
        and (email_misplaced or not token_looks_like_env_name)
    )

    fields = []
    if email_misplaced:
        fields.append("auth.email_env")
    if token_misplaced:
        fields.append("auth.api_token_env")
    return fields


def _missing_config_fields(config: dict[str, Any]) -> list[str]:
    missing = []
    base_url = str(config.get("jira_base_url") or "").strip()
    parsed = urlparse(base_url)
    if parsed.scheme.lower() != "https" or not parsed.netloc or "your-domain" in base_url:
        missing.append("jira_base_url")
    if not str(config.get("project_key") or "").strip():
        missing.append("project_key")

    statuses = config.get("statuses") if isinstance(config.get("statuses"), dict) else {}
    for key in ("todo", "progress", "done"):
        if not str(statuses.get(key) or "").strip():
            missing.append(f"statuses.{key}")
    return missing


def _authorization_header(email: str, token: str) -> str:
    encoded = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    return "Basic " + encoded


def _request_json(
    url: str,
    email: str,
    token: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    encoded_body = None
    headers = {
        "Accept": "application/json",
        "Authorization": _authorization_header(email, token),
    }
    if body is not None:
        encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = Request(url, data=encoded_body, headers=headers, method=method)
    with urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8-sig")
        return json.loads(raw) if raw else {}


def _http_failure(error: HTTPError, stage: str) -> dict[str, Any]:
    codes = {
        400: ("CONFIG_OR_JQL_INVALID", "Jira rejected the configured project or status query."),
        401: ("AUTHENTICATION_FAILED", "The Atlassian email or API token is invalid or expired."),
        403: ("PERMISSION_DENIED", "The authenticated account cannot access the requested Jira resource."),
        404: ("JIRA_SITE_NOT_FOUND", "The configured Jira site or REST endpoint was not found."),
        429: ("RATE_LIMITED", "Jira temporarily rate-limited the connection check."),
    }
    code, message = codes.get(
        error.code,
        ("JIRA_HTTP_ERROR", "Jira returned an unexpected HTTP error during the connection check."),
    )
    return {
        "connected": False,
        "code": code,
        "message": message,
        "stage": stage,
        "httpStatus": error.code,
    }


def diagnose_connection(project_root: Path, config_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "connected": False,
        "configPath": _relative_display(config_path, project_root),
        "configExists": config_path.is_file(),
        "tokenCreationUrl": TOKEN_URL,
    }
    if not config_path.is_file():
        result.update(
            code="CONFIG_MISSING",
            message="The ignored project-local Jira config does not exist.",
            connectionChecked=False,
        )
        return result

    try:
        config = _read_config(config_path)
    except (OSError, json.JSONDecodeError, ValueError):
        result.update(
            code="CONFIG_INVALID",
            message="The Jira config is not valid UTF-8 JSON.",
            connectionChecked=False,
        )
        return result

    missing_fields = _missing_config_fields(config)
    misplaced_fields = _misplaced_credential_fields(config)
    email, token, email_source, token_source = _credential_state(config)
    result.update(
        emailConfigured=bool(email),
        tokenConfigured=bool(token),
        emailSource=email_source,
        tokenSource=token_source,
    )
    if missing_fields:
        result.update(
            code="CONFIG_INCOMPLETE",
            message="The Jira config still has required project values to fill in.",
            missingFields=missing_fields,
            connectionChecked=False,
        )
        return result
    if misplaced_fields:
        result.update(
            code="CREDENTIALS_MISPLACED",
            message="Credential values appear to be stored in environment-variable-name fields.",
            misplacedFields=misplaced_fields,
            expectedFields=["auth.email", "auth.api_token"],
            connectionChecked=False,
        )
        return result
    if not email or not token:
        result.update(
            code="CREDENTIALS_MISSING",
            message="Jira credentials are missing from the ignored config and environment.",
            connectionChecked=False,
        )
        return result

    base_url = str(config["jira_base_url"]).rstrip("/")
    try:
        _request_json(base_url + "/rest/api/3/myself", email, token)
    except HTTPError as error:
        result.update(_http_failure(error, "authentication"))
        result["connectionChecked"] = True
        return result
    except (URLError, TimeoutError, OSError):
        result.update(
            code="NETWORK_ERROR",
            message="The Jira site could not be reached. Check the URL, network, proxy, VPN, and TLS settings.",
            stage="authentication",
            connectionChecked=True,
        )
        return result

    try:
        jql, statuses = build_jql(config, "all")
        response = _request_json(
            base_url + "/rest/api/3/search/jql",
            email,
            token,
            method="POST",
            body={"jql": jql, "maxResults": 1, "fields": ["key"]},
        )
    except HTTPError as error:
        result.update(_http_failure(error, "project-query"))
        result["connectionChecked"] = True
        return result
    except (URLError, TimeoutError, OSError):
        result.update(
            code="NETWORK_ERROR",
            message="Authentication succeeded, but the configured Jira project query could not be reached.",
            stage="project-query",
            connectionChecked=True,
        )
        return result
    except (SystemExit, ValueError):
        result.update(
            code="CONFIG_OR_JQL_INVALID",
            message="The configured Jira project or status mapping could not build a valid query.",
            stage="project-query",
            connectionChecked=False,
        )
        return result

    result.update(
        connected=True,
        code="CONNECTED",
        message="Jira authentication and the configured project query succeeded.",
        connectionChecked=True,
        project=str(config.get("project_key") or ""),
        statuses=statuses,
        returnedCount=len(response.get("issues") or []),
    )
    return result


def _run_git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(project_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def ensure_local_ignore(project_root: Path, config_path: Path) -> dict[str, Any]:
    git_root_result = _run_git(project_root, "rev-parse", "--show-toplevel")
    if git_root_result.returncode != 0:
        return {"safe": True, "gitRepository": False, "ignoreRequired": False, "tracked": False}

    git_root = Path(git_root_result.stdout.strip()).resolve()
    try:
        relative = config_path.resolve().relative_to(git_root)
    except ValueError:
        return {"safe": True, "gitRepository": True, "ignoreRequired": False, "tracked": False}

    tracked_result = _run_git(project_root, "ls-files", "--error-unmatch", "--", relative.as_posix())
    tracked = tracked_result.returncode == 0
    git_path_result = _run_git(project_root, "rev-parse", "--git-path", "info/exclude")
    if git_path_result.returncode != 0 or not git_path_result.stdout.strip():
        return {
            "safe": False,
            "gitRepository": True,
            "ignoreRequired": True,
            "tracked": tracked,
            "message": "Git local exclude path could not be resolved.",
        }

    exclude_path = Path(git_path_result.stdout.strip())
    if not exclude_path.is_absolute():
        exclude_path = git_root / exclude_path
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    pattern = "/" + relative.as_posix()
    existing = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
    lines = existing.splitlines()
    added = pattern not in lines
    if added:
        prefix = existing
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        exclude_path.write_text(prefix + pattern + "\n", encoding="utf-8")

    return {
        "safe": not tracked,
        "gitRepository": True,
        "ignoreRequired": True,
        "ignoreAdded": added,
        "ignorePattern": pattern,
        "tracked": tracked,
        "message": "The config is already tracked by Git and must be untracked before storing credentials."
        if tracked
        else "The config is protected by the repository's local Git exclude file.",
    }


def create_config(config_path: Path) -> bool:
    if config_path.exists():
        return False
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("x", encoding="utf-8") as handle:
        json.dump(CONFIG_TEMPLATE, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    if os.name != "nt":
        config_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return True


def open_input_location(config_path: Path) -> dict[str, Any]:
    try:
        if sys.platform == "darwin":
            command = ["open", "-R", str(config_path)] if config_path.exists() else ["open", str(config_path.parent)]
        elif os.name == "nt":
            command = ["explorer", f"/select,{config_path}"] if config_path.exists() else ["explorer", str(config_path.parent)]
        else:
            command = ["xdg-open", str(config_path.parent)]
        completed = subprocess.run(command, capture_output=True, check=False)
        if completed.returncode != 0:
            return {"opened": False, "message": "The input location could not be opened automatically."}
        return {"opened": True, "message": "The Jira config input location was opened."}
    except (OSError, ValueError):
        return {"opened": False, "message": "The input location could not be opened automatically."}


def initialize_setup(project_root: Path, config_path: Path, open_folder: bool) -> dict[str, Any]:
    ignore = ensure_local_ignore(project_root, config_path)
    if not ignore.get("safe"):
        return {
            "success": False,
            "code": "CONFIG_TRACKED" if ignore.get("tracked") else "IGNORE_SETUP_FAILED",
            "message": ignore.get("message", "The Jira config could not be protected from Git."),
            "configPath": _relative_display(config_path, project_root),
            "git": ignore,
            "tokenCreationUrl": TOKEN_URL,
        }

    try:
        created = create_config(config_path)
    except OSError:
        return {
            "success": False,
            "code": "CONFIG_CREATE_FAILED",
            "message": "The Jira config file could not be created.",
            "configPath": _relative_display(config_path, project_root),
            "git": ignore,
            "tokenCreationUrl": TOKEN_URL,
        }

    opened = open_input_location(config_path) if open_folder else {"opened": False, "message": "Opening was not requested."}
    diagnosis = diagnose_connection(project_root, config_path)
    return {
        "success": True,
        "code": "SETUP_CONNECTED" if diagnosis.get("connected") else "SETUP_INPUT_REQUIRED",
        "message": "Jira setup is connected." if diagnosis.get("connected") else "Jira local setup is ready for the required values.",
        "configPath": _relative_display(config_path, project_root),
        "configCreated": created,
        "configPreserved": not created,
        "git": ignore,
        "inputLocation": opened,
        "tokenCreationUrl": TOKEN_URL,
        "diagnosis": diagnosis,
    }


def write_result(result: dict[str, Any], output_format: str, stream: TextIO | None = None) -> None:
    stream = stream or sys.stdout
    if output_format == "json":
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        return

    stream.write(f'{result.get("code", "UNKNOWN")}: {result.get("message", "")}\n')
    if result.get("configPath"):
        stream.write(f'Config: {result["configPath"]}\n')
    stream.write(f"Atlassian API token: {TOKEN_URL}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize and diagnose safe project-local Jira access.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "setup"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--config", help="Explicit Jira config path.")
        subparser.add_argument("--format", choices=("text", "json"), default="text")
        if command == "setup":
            subparser.add_argument(
                "--open-folder",
                action="store_true",
                help="Reveal the generated or preserved config in the platform file manager.",
            )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    configure_output()
    args = build_parser().parse_args(argv)
    project_root = find_project_root(Path.cwd().resolve())
    config_path = resolve_config_path(project_root, args.config)
    if args.command == "setup":
        result = initialize_setup(project_root, config_path, args.open_folder)
        write_result(result, args.format)
        return 0 if result.get("success") else 1

    result = diagnose_connection(project_root, config_path)
    write_result(result, args.format)
    return 0 if result.get("connected") else 1


if __name__ == "__main__":
    raise SystemExit(main())

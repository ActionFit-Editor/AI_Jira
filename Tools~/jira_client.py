#!/usr/bin/env python3
"""Small dry-run-first Jira REST client for AI workflow scripts."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from jira_work_items import load_config

WRITE_METHODS = {"POST", "PUT", "DELETE"}
READ_POST_PATHS = {"/rest/api/3/search/jql"}
REQUIRED_STATUSES = ("todo", "progress", "done")
CREATE_ISSUE_TYPE_PAGE_SIZE = 50


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def automation(config: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "dry_run": True,
        "allow_issue_create": False,
        "allow_transition": False,
        "allow_description_append": False,
        "allow_description_prepend_qa": False,
        "allow_description_plan_refinement": False,
        "allow_description_overwrite": False,
        "allow_sprint_add": False,
    }
    values = dict(defaults)
    values.update(config.get("automation", {}))
    return values


def require_statuses(config: dict[str, Any]) -> dict[str, str]:
    statuses = config.get("statuses", {})
    missing = [key for key in REQUIRED_STATUSES if not statuses.get(key)]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(
            f"Missing Jira status mapping(s): {joined}. "
            "Fill Tools/AI/jira/config.local.json before running Jira automation."
        )
    return {key: statuses[key] for key in REQUIRED_STATUSES}


def get_auth(config: dict[str, Any]) -> tuple[str, str]:
    auth = config.get("auth", {})
    email = auth.get("email") or os.getenv(auth.get("email_env", "JIRA_EMAIL"), "")
    token = auth.get("api_token") or os.getenv(auth.get("api_token_env", "JIRA_API_TOKEN"), "")
    if not email or not token:
        raise SystemExit(
            "Missing Jira credentials. Set env vars or ignored Tools/AI/jira/config.local.json."
        )
    return email, token


def to_adf(text: str) -> dict[str, Any]:
    content = []
    for line in text.splitlines() or [""]:
        if line:
            content.append(
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": line}],
                }
            )
        else:
            content.append({"type": "paragraph"})
    return {"type": "doc", "version": 1, "content": content}


def adf_to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    lines: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "text":
                lines.append(str(node.get("text", "")))
            for child in node.get("content", []):
                walk(child)
            if node.get("type") in {"paragraph", "heading"}:
                lines.append("\n")
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    text = "".join(lines)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


class JiraClient:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.base_url = str(config.get("jira_base_url", "")).rstrip("/")
        if not self.base_url or "your-domain" in self.base_url:
            raise SystemExit("Set jira_base_url in Tools/AI/jira/config.local.json.")
        self.options = automation(config)

    @property
    def dry_run(self) -> bool:
        return bool(self.options.get("dry_run", True))

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        method = method.upper()
        is_read_post = method == "POST" and path in READ_POST_PATHS
        if method in WRITE_METHODS and self.dry_run and not is_read_post:
            print(json.dumps({"dry_run": True, "method": method, "path": path, "body": body}, ensure_ascii=False, indent=2))
            return {"dry_run": True}

        email, token = get_auth(self.config)
        auth_bytes = f"{email}:{token}".encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Basic " + base64.b64encode(auth_bytes).decode("ascii"),
        }
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise SystemExit(f"Jira API failed: HTTP {error.code} {error.reason}\n{detail}") from error

    def search_issues(
        self,
        jql: str,
        max_results: int = 10,
        fields: list[str] | None = None,
        reconcile_issue_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields or ["summary", "status", "assignee", "description"],
        }
        if reconcile_issue_ids:
            payload["reconcileIssues"] = reconcile_issue_ids
        return self.request("POST", "/rest/api/3/search/jql", payload)

    def get_issue(self, issue_key: str, fields: list[str] | None = None) -> dict[str, Any]:
        field_arg = ",".join(fields or ["summary", "status", "assignee", "description"])
        return self.request("GET", f"/rest/api/3/issue/{quote(issue_key)}?fields={quote(field_arg)}")

    def get_current_user(self) -> dict[str, Any]:
        return self.request("GET", "/rest/api/3/myself")

    def list_boards(self, project_key: str | None = None) -> list[dict[str, Any]]:
        query = "?maxResults=50"
        if project_key:
            query += f"&projectKeyOrId={quote(str(project_key))}"
        data = self.request("GET", f"/rest/agile/1.0/board{query}")
        return data.get("values", [])

    def list_sprints(self, board_id: int | str, state: str | None = None) -> list[dict[str, Any]]:
        query = "?maxResults=50"
        if state:
            query += f"&state={quote(state)}"
        data = self.request("GET", f"/rest/agile/1.0/board/{quote(str(board_id))}/sprint{query}")
        return data.get("values", [])

    def update_description(self, issue_key: str, description: str) -> dict[str, Any]:
        if self.options.get("allow_description_overwrite"):
            raise SystemExit("Full description overwrite is forbidden by this workflow.")
        if not (
            self.options.get("allow_description_append")
            or self.options.get("allow_description_prepend_qa")
            or self.options.get("allow_description_plan_refinement")
        ):
            raise SystemExit(
                "Description updates require allow_description_append, "
                "allow_description_prepend_qa, or allow_description_plan_refinement."
            )
        return self.request(
            "PUT",
            f"/rest/api/3/issue/{quote(issue_key)}",
            {"fields": {"description": to_adf(description)}},
        )

    def list_transitions(self, issue_key: str) -> list[dict[str, Any]]:
        data = self.request("GET", f"/rest/api/3/issue/{quote(issue_key)}/transitions")
        return data.get("transitions", [])

    def transition_issue(self, issue_key: str, transition_id: str) -> dict[str, Any]:
        if not self.options.get("allow_transition"):
            raise SystemExit("Transition requires allow_transition=true.")
        return self.request(
            "POST",
            f"/rest/api/3/issue/{quote(issue_key)}/transitions",
            {"transition": {"id": transition_id}},
        )

    def resolve_issue_type_id(self, issue_type: str | int | None) -> str:
        project_key = self.config.get("project_key")
        if not project_key:
            raise SystemExit("project_key is required to resolve Jira issue types.")

        selector = str(issue_type).strip() if issue_type is not None else ""
        if not selector:
            raise SystemExit("A non-empty Jira issue type name or id is required.")

        issue_types = self.list_create_issue_types(str(project_key))
        standard_types = [item for item in issue_types if item["subtask"] is False]
        id_matches = [item for item in standard_types if item["id"] == selector]
        name_matches = [
            item
            for item in standard_types
            if item["name"].casefold() == selector.casefold()
        ]
        matches = id_matches or name_matches

        if len(matches) == 1:
            return matches[0]["id"]
        if len(matches) > 1:
            matched = ", ".join(f'{item["name"]} ({item["id"]})' for item in matches)
            raise SystemExit(f"Jira issue type is ambiguous for {selector!r}: {matched}")

        subtask_matches = [
            item
            for item in issue_types
            if item["subtask"] is True
            and (item["id"] == selector or item["name"].casefold() == selector.casefold())
        ]
        if subtask_matches:
            raise SystemExit(
                f"Jira issue type {selector!r} is a subtask type; "
                "create_issue.py creates top-level issues only."
            )

        available = ", ".join(
            f'{item["name"]} ({item["id"]})' for item in standard_types
        ) or "none"
        raise SystemExit(
            f"Jira issue type {selector!r} is not available for project {project_key}. "
            f"Available top-level issue types: {available}"
        )

    def list_create_issue_types(self, project_key: str) -> list[dict[str, Any]]:
        start_at = 0
        issue_types_by_id: dict[str, dict[str, Any]] = {}

        while True:
            path = (
                f"/rest/api/3/issue/createmeta/{quote(project_key, safe='')}/issuetypes"
                f"?startAt={start_at}&maxResults={CREATE_ISSUE_TYPE_PAGE_SIZE}"
            )
            data = self.request("GET", path)
            page = data.get("issueTypes")
            total = data.get("total")
            response_start = data.get("startAt", start_at)
            valid_page = isinstance(page, list)
            valid_total = isinstance(total, int) and not isinstance(total, bool) and total >= 0
            valid_start = (
                isinstance(response_start, int)
                and not isinstance(response_start, bool)
                and response_start == start_at
            )
            if not valid_page or not valid_total or not valid_start:
                raise SystemExit("Jira create metadata returned an invalid issue type page.")

            for item in page:
                if not isinstance(item, dict):
                    raise SystemExit("Jira create metadata returned an invalid issue type entry.")
                issue_type_id = str(item.get("id", "")).strip()
                issue_type_name = str(item.get("name", "")).strip()
                is_subtask = item.get("subtask")
                if not issue_type_id or not issue_type_name or not isinstance(is_subtask, bool):
                    raise SystemExit("Jira create metadata returned an incomplete issue type entry.")

                normalized = {
                    "id": issue_type_id,
                    "name": issue_type_name,
                    "subtask": is_subtask,
                }
                previous = issue_types_by_id.get(issue_type_id)
                if previous is not None and previous != normalized:
                    raise SystemExit(
                        "Jira create metadata returned conflicting entries for "
                        f"issue type id {issue_type_id}."
                    )
                issue_types_by_id[issue_type_id] = normalized

            next_start = start_at + len(page)
            if next_start >= total:
                break
            if not page:
                raise SystemExit(
                    "Jira create metadata pagination stopped before all issue types were returned."
                )
            start_at = next_start

        return list(issue_types_by_id.values())

    def create_issue(self, summary: str, description: str, issue_type: str | None = None) -> dict[str, Any]:
        if not self.options.get("allow_issue_create"):
            raise SystemExit("Issue creation requires allow_issue_create=true.")
        project_key = self.config.get("project_key")
        if not project_key:
            raise SystemExit("project_key is required to create Jira issues.")
        issue_create = self.config.get("issue_create", {})
        target_sprint = self.resolve_issue_create_sprint_before_create(issue_create)
        issue_type_selector = issue_type or issue_create.get("issue_type", "Task")
        issue_type_id = self.resolve_issue_type_id(issue_type_selector)
        labels = issue_create.get("default_labels", [])
        assign_to_current_user = issue_create.get("assign_to_current_user", True)
        expected_assignee_account_id = None
        body = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": to_adf(description),
                "issuetype": {"id": issue_type_id},
                "labels": labels,
            }
        }

        if assign_to_current_user:
            if self.dry_run:
                body["fields"]["assignee"] = {"accountId": "(current authenticated user)"}
            else:
                current_user = self.get_current_user()
                account_id = current_user.get("accountId")
                if not account_id:
                    raise SystemExit("Failed to resolve current Jira user accountId for issue assignee.")
                body["fields"]["assignee"] = {"accountId": account_id}
                expected_assignee_account_id = account_id

        result = self.request("POST", "/rest/api/3/issue", body)
        issue_key = result.get("key")
        if not issue_key:
            return result

        try:
            self.ensure_created_issue_status(issue_key)
            self.add_created_issue_to_active_sprint(issue_key, target_sprint)
            self.verify_created_issue_state(
                issue_key,
                target_sprint,
                expected_assignee_account_id,
                result.get("id"),
            )
        except SystemExit as error:
            self.raise_created_issue_recovery(issue_key, target_sprint, error)
        except Exception as error:
            self.raise_created_issue_recovery(issue_key, target_sprint, error)
        return result

    def ensure_created_issue_status(self, issue_key: str | None) -> None:
        if not issue_key or self.dry_run:
            return

        issue_create = self.config.get("issue_create", {})
        create_status_key = issue_create.get("create_status", "todo")
        target_status = self.resolve_status_name(create_status_key)
        if not target_status:
            return

        issue = self.get_issue(issue_key, fields=["status"])
        current_status = issue.get("fields", {}).get("status", {}).get("name")
        if current_status == target_status:
            return

        for transition in self.list_transitions(issue_key):
            to_status = transition.get("to", {}).get("name")
            if to_status == target_status:
                self.request(
                    "POST",
                    f"/rest/api/3/issue/{quote(issue_key)}/transitions",
                    {"transition": {"id": transition.get("id")}},
                )
                return

        raise SystemExit(
            f"Created issue {issue_key}, but no transition to configured create status was found: {target_status}"
        )

    def resolve_status_name(self, status_key_or_name: str | None) -> str | None:
        if not status_key_or_name:
            return None

        statuses = self.config.get("statuses", {})
        if status_key_or_name in statuses:
            status_name = statuses.get(status_key_or_name)
            if not status_name:
                raise SystemExit(f"Missing Jira status mapping for create_status: {status_key_or_name}")
            return status_name

        return status_key_or_name

    def resolve_issue_create_sprint_before_create(self, issue_create: dict[str, Any]) -> dict[str, Any]:
        if issue_create.get("add_to_active_sprint_after_create", True) is not True:
            raise SystemExit(
                "AI Jira issue creation requires active-sprint placement. "
                "Remove add_to_active_sprint_after_create=false or create the backlog issue manually."
            )

        if not self.options.get("allow_sprint_add"):
            raise SystemExit(
                "AI Jira issue creation requires automation.allow_sprint_add=true; "
                "creation was blocked before the Jira issue request."
            )

        return self.resolve_create_issue_target_sprint(issue_create)

    def add_created_issue_to_active_sprint(
        self,
        issue_key: str | None,
        sprint: dict[str, Any] | None = None,
    ) -> None:
        if not issue_key or self.dry_run:
            return

        if not self.options.get("allow_sprint_add"):
            raise SystemExit(
                "Created issue "
                f"{issue_key}, but active sprint add requires automation.allow_sprint_add=true."
            )

        issue_create = self.config.get("issue_create", {})
        sprint = sprint or self.resolve_create_issue_target_sprint(issue_create)
        sprint_id = sprint.get("id")
        if not sprint_id:
            raise SystemExit(f"Created issue {issue_key}, but active sprint id could not be resolved.")

        self.request(
            "POST",
            f"/rest/agile/1.0/sprint/{quote(str(sprint_id))}/issue",
            {"issues": [issue_key]},
        )

    def verify_created_issue_state(
        self,
        issue_key: str,
        sprint: dict[str, Any],
        expected_assignee_account_id: str | None,
        issue_id: str | int | None,
    ) -> None:
        if self.dry_run:
            return

        issue_create = self.config.get("issue_create", {})
        create_status_key = issue_create.get("create_status", "todo")
        target_status = self.resolve_status_name(create_status_key)
        issue = self.get_issue(issue_key, fields=["status", "assignee"])
        fields = issue.get("fields") or {}
        current_status = (fields.get("status") or {}).get("name")
        if target_status and current_status != target_status:
            raise SystemExit(
                f"Post-create status verification failed: expected {target_status}, got {current_status}."
            )

        if expected_assignee_account_id:
            current_assignee_account_id = (fields.get("assignee") or {}).get("accountId")
            if current_assignee_account_id != expected_assignee_account_id:
                raise SystemExit("Post-create assignee verification failed for the authenticated Jira user.")

        sprint_id = sprint.get("id")
        if not sprint_id:
            raise SystemExit("Post-create sprint verification has no expected sprint id.")
        try:
            numeric_sprint_id = int(sprint_id)
        except (TypeError, ValueError):
            raise SystemExit(f"Post-create sprint verification has an invalid sprint id: {sprint_id}")

        safe_issue_key = issue_key.replace("\\", "\\\\").replace('"', '\\"')
        reconcile_issue_ids = None
        if issue_id is not None:
            try:
                reconcile_issue_ids = [int(issue_id)]
            except (TypeError, ValueError):
                raise SystemExit(f"Created issue {issue_key} returned an invalid Jira issue id: {issue_id}")

        search_result = self.search_issues(
            f'key = "{safe_issue_key}" AND sprint = {numeric_sprint_id}',
            max_results=1,
            fields=["status"],
            reconcile_issue_ids=reconcile_issue_ids,
        )
        matched_keys = {item.get("key") for item in (search_result.get("issues") or [])}
        if issue_key not in matched_keys:
            raise SystemExit(
                f"Post-create sprint verification failed: {issue_key} is not in sprint {sprint_id}."
            )

    def raise_created_issue_recovery(
        self,
        issue_key: str,
        sprint: dict[str, Any],
        error: BaseException,
    ) -> None:
        sprint_id = sprint.get("id") or "unknown"
        sprint_name = sprint.get("name") or f"sprint {sprint_id}"
        raise SystemExit(
            f"Created Jira issue {issue_key}, but required active-sprint completion failed for "
            f"{sprint_name} ({sprint_id}). Manually move {issue_key} to that sprint, verify the "
            f"configured todo status and assignee, then retry the workflow if needed. Cause: {error}"
        ) from error

    def resolve_create_issue_target_sprint(self, issue_create: dict[str, Any]) -> dict[str, Any]:
        configured_sprint_id = issue_create.get("active_sprint_id")
        if configured_sprint_id:
            sprint = self.request("GET", f"/rest/agile/1.0/sprint/{quote(str(configured_sprint_id))}")
            if sprint.get("state") != "active":
                raise SystemExit(
                    f"Configured sprint is not active: {configured_sprint_id} "
                    f"({sprint.get('state')})"
                )
            return sprint

        board_id = issue_create.get("board_id") or self.resolve_single_project_board_id()
        active_sprints = [
            sprint for sprint in self.list_sprints(board_id, state="active")
            if sprint.get("state") == "active"
        ]

        if not active_sprints:
            raise SystemExit(
                f"No active Jira sprint found for board {board_id}. "
                "Set issue_create.active_sprint_id or start a sprint before creating issues."
            )

        if len(active_sprints) > 1:
            names = ", ".join(f'{sprint.get("name")}({sprint.get("id")})' for sprint in active_sprints)
            raise SystemExit(
                f"Multiple active Jira sprints found for board {board_id}: {names}. "
                "Set issue_create.active_sprint_id explicitly."
            )

        return active_sprints[0]

    def resolve_single_project_board_id(self) -> int | str:
        project_key = self.config.get("project_key")
        boards = self.list_boards(project_key)

        if not boards:
            raise SystemExit(
                "No Jira board found for configured project. "
                "Set issue_create.board_id or issue_create.active_sprint_id."
            )

        if len(boards) > 1:
            names = ", ".join(f'{board.get("name")}({board.get("id")})' for board in boards)
            raise SystemExit(
                f"Multiple Jira boards found for configured project: {names}. "
                "Set issue_create.board_id explicitly."
            )

        board_id = boards[0].get("id")
        if not board_id:
            raise SystemExit("Resolved Jira board has no id.")
        return board_id


def build_client(config_path: str | None = None, validate_statuses: bool = False) -> JiraClient:
    config = load_config(config_path)
    if validate_statuses:
        require_statuses(config)
    return JiraClient(config)


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Validate Jira AI automation config.")
    parser.add_argument("--config", help="Path to ignored local Jira config JSON.")
    parser.add_argument("--require-statuses", action="store_true", help="Require todo/progress/done status mappings.")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.require_statuses:
        require_statuses(config)
    options = automation(config)
    print(json.dumps({
        "config_path": config["_config_path"],
        "dry_run": options["dry_run"],
        "allow_sprint_add": options["allow_sprint_add"],
        "allow_description_plan_refinement": options["allow_description_plan_refinement"],
        "status_keys": list(config.get("statuses", {}).keys()),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

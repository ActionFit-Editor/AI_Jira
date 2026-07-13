# AI Guide - AI Jira

This file is shipped inside the UPM package so an AI assistant in a consuming Unity project can understand Jira automation rules without access to the source project's `Docs/AI` folder.

## Package Identity

- Package ID: `com.actionfit.ai-jira`
- Display name: AI Jira
- Repository: `https://github.com/ActionFit-Editor/AI_Jira.git`
- Current package version at generation time: `1.0.8`
- Unity version: `6000.2`

## Purpose

AI Jira provides project-local Codex and Claude skills, a read-only work-item API/CLI, and Jira automation guidance for AI agents: safe issue creation, task discovery, status lifecycle, Korean Jira text rules, description update boundaries, and local secret configuration.

The package owns status-filtered work-item discovery. Consuming projects may keep compatibility entry points at project-local paths such as `Tools/AI/jira/list_my_tasks.py`; write-oriented automation may remain project-local until it is migrated separately.

## Project Router Registration

This package should be listed in `Packages/com.actionfit.custompackagemanager/PACKAGE_AI_GUIDE_ROUTER.md`.

Requested router entry:

- `Packages/com.actionfit.ai-jira/AI_GUIDE.md` - AI Jira defines ActionFit Jira automation rules. Read when creating Jira issues, discovering Jira tasks, changing Jira lifecycle/status behavior, editing Jira REST scripts, or handling Jira local config.

If the router file is not already included in the AI assistant's default reading sequence, the router file is responsible for asking the user to link it from the project's primary AI markdown entry point. Prefer an existing `PROJECT.md` wherever the project keeps it, otherwise use `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or another primary AI markdown entry point.

Read this file when:

- creating or updating Jira issues through AI automation
- changing files under `Packages/com.actionfit.ai-jira/`
- changing project-local Jira automation scripts or compatibility wrappers
- editing Jira config examples, local config rules, status mappings, or write-safety flags
- preparing a release for `com.actionfit.ai-jira`

## Rules

- Jira credentials, board IDs, real base URLs, status names, and user-specific config must stay in ignored local config files or environment variables.
- Jira task discovery must use the developer's own Atlassian account email and API token. If credentials are missing, tell the user to either set their existing token as `JIRA_API_TOKEN` or create one from `https://id.atlassian.com/manage-profile/security/api-tokens`, then set `JIRA_EMAIL` and `JIRA_API_TOKEN` locally.
- Use `Tools~/list_work_items.py` for direct Jira work-list retrieval. `--state todo` reads the configured todo status, `--state progress` reads active implementation, and `--state all` combines todo and progress while excluding completed work.
- Use `Tools~/get_work_item.py <ISSUE-KEY>` for read-only issue details needed to judge implementation scope.
- Work-list queries must remain read-only and include the configured project when present, `assignee = currentUser()`, `resolution = Unresolved`, and descending update order.
- Support both text and structured JSON output. JSON must use UTF-8 with unescaped Korean text and include issue key, title, status, updated time, and browser URL.
- Resolve the ignored config from an explicit `--config`, `AI_JIRA_CONFIG`, or the consuming project's `Tools/AI/jira/config.local.json`, in that order. Read config as UTF-8 with optional BOM and never place credentials inside the package.
- Do not ask the user to paste Jira API tokens into shared chat. If setup help is needed, guide them through environment variables or ignored local config only.
- Default write behavior must remain safe: dry-run enabled unless the user explicitly enables the specific write action.
- New issue creation must assign the issue to the authenticated Jira API user by default. Project-local `Tools/AI/jira/create_issue.py` resolves `/rest/api/3/myself` and writes the returned account id to `assignee` when `issue_create.assign_to_current_user` is true or omitted.
- New issue creation must leave the issue in the configured `todo` status by default. If Jira creates the issue in another initial status, the create script should transition the newly created issue to `issue_create.create_status`, normally `statuses.todo`, before reporting the issue key. Move the issue to `progress` only when implementation actually starts.
- Unless the user explicitly requests backlog placement for that issue, new issue creation must resolve the current active sprint before creating the issue and add the created issue to that sprint by default. Prefer `issue_create.board_id`; use `issue_create.active_sprint_id` only for an intentionally fixed sprint.
- Compatible Jira clients must treat a missing `issue_create.add_to_active_sprint_after_create` value as `true`. An explicit `false` value is allowed only when the user requested backlog placement for that issue. `automation.allow_sprint_add` remains the required write-safety gate; when it is disabled, active-sprint issue creation is blocked rather than downgraded to backlog creation.
- Missing or ambiguous active sprint resolution, disabled sprint writes, or sprint assignment failure is a creation blocker. Do not silently fall back to the backlog. If assignment fails after Jira already created the issue, report the created issue key and the exact failure.
- After creation, re-read the issue and verify both the configured `todo` status and membership in the resolved active sprint before reporting success. Create an issue in the backlog only when the user explicitly requests that exception for the issue.
- Jira-backed development work that produced a PR must move the issue to internal `done` before the final report when Jira writes are enabled. For Cat Merge Cafe, local config should map `statuses.done` to `개발 완료`. If `dry_run`, credentials, `allow_transition`, status mapping, or Jira transitions prevent the move, report the exact blocker.
- AI-created Jira titles, descriptions, appended requirements, and QA notes must be written in Korean.
- Do not overwrite full Jira descriptions. Only append confirmed requirements or prepend QA notes when the local config explicitly allows it.
- Do not add AI-created labels or move issues to a QA status. QA-board movement remains a manual user action after build verification.
- Keep Jira REST calls behind the package/client boundary so projects can replace auth or endpoint details without changing workflow rules.
- Package skill sources live under `Skills~/Codex` and `Skills~/Claude`. The Editor copies them to project-local `.agents/skills` and `.claude/skills`, overlaying only the shared read-only locator from `Skills~/Shared`.
- `jira-todo` must remain read-only. `jira-run` must remain explicit/manual-only through Codex `allow_implicit_invocation: false` and Claude `disable-model-invocation: true`.
- Skill installation must never write to home/global directories, copy credentials, overwrite unknown or modified targets, or delete targets automatically. Managed hashes belong in `UserSettings/AIJira/skill-install-state.json`.
- Package refresh may update only a target whose current directory hash matches the recorded installed hash. Explicit removal may delete only the same unchanged targets and must preserve modified or linked directories.

## Compatibility Boundary

- Existing projects may continue to call `Tools/AI/jira/*.py` compatibility entry points.
- This package owns portable rules and the read-only work-item implementation under `Tools~/`.
- Write-oriented issue creation, description updates, and transitions remain behind project-local compatibility clients until migrated separately.
- `com.actionfit.ai_guide_jira` was a placeholder guide package. Treat `com.actionfit.ai-jira` as the canonical Jira automation package and move dependencies, router entries, and documentation references here instead of installing both.

## Package Tools Menu

- Unity menu root: `Tools/Package/AI Jira/`.
- Keep package commands under this package root.
- `Install or Refresh Agent Skills`: explicitly installs missing skills, refreshes unchanged managed skills, and re-enables automatic installation.
- `Remove Managed Agent Skills`: after confirmation, removes only unchanged managed skills and disables automatic recreation until explicit installation.
- Lower separated entries:
- `README`: opens this package README.
- Do not add README or Setting SO access back to Custom Package Manager package rows or Project Files.

## Release Notes

- Publishing is manual through Custom Package Manager.
- Before reusing a version, check remote Git tags. Published tags are immutable.
- If this package is modified after a version is tagged, bump to the next unused patch version before publishing.

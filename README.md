# AI Jira (com.actionfit.ai-jira)

ActionFit AI agents use this package to understand Jira task discovery, issue creation, lifecycle transitions, and safe local Jira configuration.

## Current Scope

This package is the first package boundary for Jira-related AI guidance. The Cat Merge Cafe project still keeps the active Jira automation scripts under `Tools/AI/jira/` for compatibility while this package is introduced.

## Install

```json
{
  "dependencies": {
    "com.actionfit.ai-jira": "https://github.com/ActionFit-Editor/AI_Jira.git#1.0.6"
  }
}
```

## Unity Menu

- Package root: `Tools > Package > AI Jira`.
- README: `Tools > Package > AI Jira > README`.
- Package commands stay under the same package root and appear above the separated README/Setting SO entries when those entries exist.

## AI Guide

- Read `AI_GUIDE.md` before changing Jira automation rules, local Jira config behavior, issue lifecycle handling, or Jira REST scripts.

## Personal Jira Credentials

Jira task discovery uses the authenticated Atlassian account. Each developer must use their own Jira account email and API token so `assignee = currentUser()` returns that developer's work.

If the developer already has an API token, set it locally:

```bash
export JIRA_EMAIL="name@company.com"
export JIRA_API_TOKEN="your-atlassian-api-token"
```

If the developer does not have an API token, create one from Atlassian Account security:

https://id.atlassian.com/manage-profile/security/api-tokens

After creating the token, copy it immediately and store it in a password manager. Atlassian does not show the token again after creation. Do not commit the token, paste it into shared chat, or store it in a tracked project file.

Project-local scripts may also read ignored `Tools/AI/jira/config.local.json`, but environment variables are preferred for personal credentials.

## Issue Creation Defaults

When `Tools/AI/jira/create_issue.py` creates a Jira issue, the default owner is the authenticated Jira API user. The script resolves `/rest/api/3/myself` and writes that account id to the issue `assignee` field when `issue_create.assign_to_current_user` is true or omitted.

New issues should land in the configured `todo` status by default. If the Jira project workflow creates the issue in another initial status, the create script should immediately transition the issue to `issue_create.create_status`, normally `statuses.todo`, before returning the created issue key. Move issues to `progress` only when implementation actually starts.

New issues are assigned to the current active sprint by default. Backlog placement is an explicit per-issue exception and must not be used as a silent fallback.

Enable the sprint write gate and active-sprint creation default in ignored local config:

```json
{
  "automation": {
    "allow_sprint_add": true
  },
  "issue_create": {
    "add_to_active_sprint_after_create": true,
    "board_id": 3,
    "active_sprint_id": null
  }
}
```

Use `board_id` for normal work so the client resolves the current active sprint immediately before creating the issue. Use `active_sprint_id` only when a fixed sprint is intentionally required. Keep these IDs in ignored local config because board and sprint IDs are project-specific.

Compatible Jira clients treat a missing `add_to_active_sprint_after_create` value as `true`. Set it to `false` only for an issue the user explicitly asked to place in the backlog. If sprint writes are disabled, no active sprint can be resolved unambiguously, or sprint assignment fails, the client must report the blocker instead of silently leaving the issue in the backlog.

After creation, the client must re-read the issue and verify both its configured `todo` status and active sprint assignment before reporting success. If Jira created the issue but later verification fails, report the created issue key and the exact mismatch.

## PR Completion Defaults

For Jira-backed development work, creating a PR is not enough to finish the Jira lifecycle. After the PR URL exists, the AI workflow should prepend Korean QA notes when enabled and move the issue to the configured `done` status. In this project that status is `개발 완료`.

Use:

```bash
python3 Tools/AI/jira/update_description.py MCC-1234 --mode prepend-qa --file qa-notes.md
python3 Tools/AI/jira/transition_issue.py MCC-1234 --to done
```

If Jira writes are disabled, credentials are missing, or the configured transition does not exist, the AI must report the blocker instead of silently leaving the issue in progress.

## Legacy Package

- `com.actionfit.ai_guide_jira` was a placeholder guide package and should not be installed together with this package.
- Use `com.actionfit.ai-jira` as the canonical Jira automation guidance package.

## Migration Notes

- Project-local secrets and board mappings must remain outside the package in ignored local config files.
- Compatibility wrappers should preserve existing project paths until all AI docs and workflows have moved to package-owned routing.

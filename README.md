# AI Jira (com.actionfit.ai-jira)

ActionFit AI agents use this package to understand Jira task discovery, issue creation, lifecycle transitions, and safe local Jira configuration.

## Current Scope

This package is the first package boundary for Jira-related AI guidance. The Cat Merge Cafe project still keeps the active Jira automation scripts under `Tools/AI/jira/` for compatibility while this package is introduced.

## Install

```json
{
  "dependencies": {
    "com.actionfit.ai-jira": "https://github.com/ActionFit-Editor/AI_Jira.git#1.0.4"
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

## Legacy Package

- `com.actionfit.ai_guide_jira` was a placeholder guide package and should not be installed together with this package.
- Use `com.actionfit.ai-jira` as the canonical Jira automation guidance package.

## Migration Notes

- Project-local secrets and board mappings must remain outside the package in ignored local config files.
- Compatibility wrappers should preserve existing project paths until all AI docs and workflows have moved to package-owned routing.

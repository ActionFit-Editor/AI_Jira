# AI Jira (com.actionfit.ai-jira)

ActionFit AI agents use this package for project-local Jira skills, read-only work-item discovery, Jira lifecycle guidance, and safe local automation.

## Current Scope

The package owns Codex and Claude Jira skill content plus the read-only Jira work-item API and CLI. `com.actionfit.custompackagemanager` owns the shared package-skill discovery and installation lifecycle, while Cat Merge Cafe keeps project-local compatibility entry points under `Tools/AI/jira/` and write-oriented automation behind the existing project client.

## Install

```json
{
  "dependencies": {
    "com.actionfit.ai-jira": "https://github.com/ActionFit-Editor/AI_Jira.git#1.0.11"
  }
}
```

## Unity Menu

- Package root: `Tools > Package > AI Jira`.
- README: `Tools > Package > AI Jira > README`.
- Shared skill management: `Tools > Package > Custom Package Manager > Install or Refresh Agent Skills`, `Remove Managed Agent Skills`, and `Add Agent Skill`.

## Codex And Claude Skills

AI Jira registers schema v2 package-owned sources with `skillPrefix: jira`, mandatory `helpSkill: jira-help`, and explicit read-only/write-capable access through `Skills~/manifest.json`. After Unity resolves AI Jira and its Custom Package Manager dependency, the common installer synchronizes them into the consuming project:

- Codex: `.agents/skills/jira-help`, `.agents/skills/jira-todo`, and `.agents/skills/jira-run`.
- Claude: `.claude/skills/jira-help`, `.claude/skills/jira-todo`, and `.claude/skills/jira-run`.

The installer generates `PACKAGE_SKILLS.md` inside each installed `jira-help` from AI Jira package metadata, the manifest, and agent-specific `SKILL.md` descriptions. `jira-help` reads that inventory first, so package identity, every related skill, its `$name` invocation, when-to-use description, and access boundary stay synchronized without a second hard-coded skill list.

`jira-help` explains the generated inventory, read-only and write-capable command families, configuration, safety gates, and Unity menus without executing Jira operations. `jira-todo` queries assigned unresolved `todo` and `progress` issues separately. Only `todo` issues are new-work candidates; `progress` issues and their existing branches, worktrees, or pull requests are overlap and exclusion evidence. A progress issue is never promoted into the recommendation order unless the user explicitly asks about that specific issue, and the skill remains read-only even then. `jira-run` executes only an issue explicitly selected by the user and follows the consuming repository's approval, worktree, validation, PR, and Jira lifecycle rules. Codex disables implicit invocation for `jira-run`; Claude ships it with `disable-model-invocation: true`.

The package copies files instead of creating links so it also supports Claude Code versions before skill-directory symlink support. Installed skills contain only instructions and a read-only package-tool locator; credentials and ignored Jira config are never copied.

Managed state is stored at ignored project-local `UserSettings/ActionFitPackageManager/skill-install-state.json`. A missing managed target is restored, and an unchanged managed target is refreshed when package content changes. Existing unmanaged targets and user-modified managed targets are preserved with a warning. Automatic install never writes to a user home/global skill directory, never deletes a skill, and is skipped in Unity batch mode. Explicit removal deletes only unchanged managed targets and disables automatic recreation until the install/refresh command is used again.

Existing `UserSettings/AIJira/skill-install-state.json` remains in place as migration input. Custom Package Manager adopts a legacy target only when its current hash still matches the recorded installed hash and also preserves a previously disabled automatic-install preference. AI Jira depends on Custom Package Manager `1.1.71` so direct AI Jira installation receives schema v2 inventory generation through the same single installation engine used by every ActionFit package instead of activating a Jira-specific second writer.

## AI Guide

- Read `AI_GUIDE.md` before changing Jira automation rules, local Jira config behavior, issue lifecycle handling, or Jira REST scripts.

## Work-Item API And CLI

Use the package-owned read-only tool from a consuming Unity project root:

```bash
python3 Packages/com.actionfit.ai-jira/Tools~/list_work_items.py --state all
python3 Packages/com.actionfit.ai-jira/Tools~/list_work_items.py --state progress --format json
python3 Packages/com.actionfit.ai-jira/Tools~/list_work_items.py --state todo --max-results 25
python3 Packages/com.actionfit.ai-jira/Tools~/get_work_item.py MCC-1234 --format json
```

`--state all` includes the configured `todo` and `progress` states, not completed work. It remains available for general read-only callers, but `jira-todo` does not use it for candidate selection: the skill calls `--state todo` for recommendations and `--state progress` separately for overlap detection. Every query automatically limits results to the configured project, `assignee = currentUser()`, and unresolved issues, then sorts by most recently updated.

Text output includes the issue key, status, title, and update time. JSON output adds the resolved status filters, JQL, issue URL, pagination metadata when Jira returns it, and preserves Korean text with UTF-8 rather than `\u` escapes.

The Python API is also available for another package-local tool:

```python
from jira_work_items import load_config, query_work_items

result = query_work_items(load_config(), state="progress", max_results=50)
```

Configuration resolution order is `--config`, `AI_JIRA_CONFIG`, then the consuming project's ignored `Tools/AI/jira/config.local.json`. UTF-8 and UTF-8-with-BOM JSON are both accepted. The work-item client exposes only Jira enhanced search and has no write method.

The legacy project command remains compatible and now accepts the same `--state`, `--format`, and `--max-results` options:

```bash
python3 Tools/AI/jira/list_my_tasks.py --state progress --format json
```

Run the package tests without Unity:

```bash
python3 -m unittest discover Packages/com.actionfit.ai-jira/Tests~ -p "test_*.py"
```

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

# AI Guide - AI Jira

This file is shipped inside the UPM package so an AI assistant in a consuming Unity project can understand Jira automation rules without access to the source project's `Docs/AI` folder.

## Package Identity

- Package ID: `com.actionfit.ai-jira`
- Display name: AI Jira
- Repository: `https://github.com/ActionFit-Editor/AI_Jira.git`
- Current package version at generation time: `1.0.2`
- Unity version: `6000.2`

## Purpose

AI Jira defines ActionFit Jira automation guidance for AI agents: safe issue creation, task discovery, status lifecycle, Korean Jira text rules, description update boundaries, and local secret configuration.

This initial package establishes the package boundary. Consuming projects may still keep active scripts at project-local paths such as `Tools/AI/jira/` until compatibility wrappers are added.

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
- Do not ask the user to paste Jira API tokens into shared chat. If setup help is needed, guide them through environment variables or ignored local config only.
- Default write behavior must remain safe: dry-run enabled unless the user explicitly enables the specific write action.
- AI-created Jira titles, descriptions, appended requirements, and QA notes must be written in Korean.
- Do not overwrite full Jira descriptions. Only append confirmed requirements or prepend QA notes when the local config explicitly allows it.
- Do not add AI-created labels or move issues to a QA status. QA-board movement remains a manual user action after build verification.
- Keep Jira REST calls behind the package/client boundary so projects can replace auth or endpoint details without changing workflow rules.

## Compatibility Boundary

- Existing projects may continue to call `Tools/AI/jira/*.py`.
- This package owns the portable rules and future package-local implementation.
- A later migration should add project wrappers or install helpers before moving active scripts out of project-local paths.
- `com.actionfit.ai_guide_jira` was a placeholder guide package. Treat `com.actionfit.ai-jira` as the canonical Jira automation package and move dependencies, router entries, and documentation references here instead of installing both.

## Release Notes

- Publishing is manual through Custom Package Manager.
- Before reusing a version, check remote Git tags. Published tags are immutable.
- If this package is modified after a version is tagged, bump to the next unused patch version before publishing.

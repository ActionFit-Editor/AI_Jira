# AI Jira (com.actionfit.ai-jira)

ActionFit AI agents use this package to understand Jira task discovery, issue creation, lifecycle transitions, and safe local Jira configuration.

## Current Scope

This package is the first package boundary for Jira-related AI guidance. The Cat Merge Cafe project still keeps the active Jira automation scripts under `Tools/AI/jira/` for compatibility while this package is introduced.

## Install

```json
{
  "dependencies": {
    "com.actionfit.ai-jira": "https://github.com/ActionFit-Editor/AI_Jira.git#1.0.1"
  }
}
```

## AI Guide

- Read `AI_GUIDE.md` before changing Jira automation rules, local Jira config behavior, issue lifecycle handling, or Jira REST scripts.

## Legacy Package

- `com.actionfit.ai_guide_jira` was a placeholder guide package and should not be installed together with this package.
- Use `com.actionfit.ai-jira` as the canonical Jira automation guidance package.

## Migration Notes

- Project-local secrets and board mappings must remain outside the package in ignored local config files.
- Compatibility wrappers should preserve existing project paths until all AI docs and workflows have moved to package-owned routing.

# AI Jira (com.actionfit.ai-jira)

ActionFit AI agents use this package to understand Jira task discovery, issue creation, lifecycle transitions, and safe local Jira configuration.

## Current Scope

This package is the first package boundary for Jira-related AI guidance. The Cat Merge Cafe project still keeps the active Jira automation scripts under `Tools/AI/jira/` for compatibility while this package is introduced.

## AI Guide

- Read `AI_GUIDE.md` before changing Jira automation rules, local Jira config behavior, issue lifecycle handling, or Jira REST scripts.

## Migration Notes

- Project-local secrets and board mappings must remain outside the package in ignored local config files.
- Compatibility wrappers should preserve existing project paths until all AI docs and workflows have moved to package-owned routing.

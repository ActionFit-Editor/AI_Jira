---
name: jira-run
description: Implement an explicitly selected Jira issue through validation, a pull request, and configured Jira lifecycle updates.
disable-model-invocation: true
---

# Jira Run

Use this skill only after the user explicitly invokes it with an issue key or explicitly selects an issue from prior triage.

1. Run `python3 scripts/ai_jira_cli.py list --state all --format json`, then `python3 scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json`. Verify the selected key appears in the assigned unresolved list and belongs to the configured project.
2. Read `CLAUDE.md`, `AGENTS.md`, and linked repository rules for Jira, worktrees, tests, commits, and pull requests.
3. Check for an existing branch, worktree, or pull request before creating anything.
4. Restate scope, risk, and validation. Obtain repository-required approval unless the invocation already contains an explicit approved scope.
5. When implementation starts, use only the consuming project's approved Jira write tools to transition to progress. Missing tools or disabled gates are blockers, not permission to call Jira directly.
6. Work in the required isolated worktree, preserve unrelated changes, implement the approved scope, update docs, and validate.
7. Review, commit without an AI co-author trailer, push, and create the pull request.
8. After the PR exists, prepend Korean QA notes only when enabled and transition to internal done. Never move Jira to QA.
9. Report the branch, worktree, PR, Jira state, tests, and blockers in the repository's required format.

Never reveal Jira credentials, overwrite full issue descriptions, make unrelated changes, or use destructive Git commands.

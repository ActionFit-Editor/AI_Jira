---
name: jira-todo
description: Inspect the current developer's unresolved Jira todo and in-progress items, compare them with the repository, and recommend actionable work without changing Jira or project state.
---

# Jira Todo

Use this skill for Jira triage and work recommendations only. It is strictly read-only.

## Workflow

1. From the consuming project root, run `python3 scripts/ai_jira_cli.py list --state all --format json`.
2. For relevant issues, run `python3 scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json`.
3. Read the repository's `AGENTS.md`, `CLAUDE.md`, or linked AI guidance before interpreting implementation scope.
4. Inspect local branches, worktrees, and pull requests with read-only commands when needed to identify duplicate or already-started work.
5. Separate the result into actionable work, blocked work, and possible overlaps or dependencies. Recommend a priority and explain the evidence.

## Boundaries

- Never create, edit, transition, assign, comment on, or otherwise write to Jira.
- Never create a branch or worktree, edit project files, commit, push, or create a pull request.
- Do not expose credentials or print ignored Jira config contents.
- If credentials or config are missing, explain the local setup requirement without asking the user to paste a token into chat.
- Treat the helper output as Jira evidence, then verify repository claims with local read-only inspection.

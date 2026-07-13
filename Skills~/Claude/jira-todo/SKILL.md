---
name: jira-todo
description: Inspect my unresolved Jira todo and in-progress items and recommend actionable work without changing Jira or the project.
---

# Jira Todo

This is a strictly read-only triage skill.

1. From the project root, run `python3 scripts/ai_jira_cli.py list --state all --format json`.
2. Read relevant issue details with `python3 scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json`.
3. Read `CLAUDE.md`, `AGENTS.md`, or linked project AI guidance.
4. Use read-only Git, worktree, and pull-request inspection to find existing or overlapping work.
5. Report actionable items, blockers, dependencies, and a recommended order with supporting evidence.

Never write to Jira, create worktrees or branches, edit files, commit, push, or create pull requests. Never display credentials or ignored config contents. If local Jira setup is missing, explain how to configure it locally without requesting a token in chat.

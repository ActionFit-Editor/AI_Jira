---
name: jira-todo
description: Recommend new work only from my unresolved Jira todo items, using in-progress items solely to detect existing or overlapping work.
---

# Jira Todo

This is a strictly read-only triage skill.

1. From the project root, run `python3 .claude/skills/jira-todo/scripts/ai_jira_cli.py list --state todo --format json`. This is the only source of new-work candidates.
2. Separately run `python3 .claude/skills/jira-todo/scripts/ai_jira_cli.py list --state progress --format json`. Use it only to find already-active, duplicate, overlapping, or unavailable work.
3. Read relevant todo details with `python3 .claude/skills/jira-todo/scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json`. Read progress details only when needed for overlap or dependency analysis.
4. Read `CLAUDE.md`, `AGENTS.md`, or linked project AI guidance.
5. Use read-only Git, worktree, and pull-request inspection to find existing or overlapping work.
6. Report actionable todo items, already-in-progress exclusions, blockers, and dependencies separately. Rank only actionable todo issues with supporting evidence.

Only todo-query issues may be recommended as new work. A progress issue or its existing branch, worktree, or pull request is exclusion evidence, not a reason to recommend continuing it. If the user explicitly asks about a specific progress issue, report its state without turning this read-only skill into implementation. If no todo issue is actionable, say so even when progress issues exist.

Never write to Jira, create worktrees or branches, edit files, commit, push, or create pull requests. Never display credentials or ignored config contents. If local Jira setup is missing, explain how to configure it locally without requesting a token in chat.

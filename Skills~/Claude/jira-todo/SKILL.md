---
name: jira-todo
description: Recommend new work only from my unresolved Jira todo items, using in-progress items solely to detect existing or overlapping work.
---

# Jira Todo

This is a strictly read-only triage skill.

1. From the project root, run `python3 .claude/skills/jira-todo/scripts/ai_jira_cli.py list --state todo --format json`. This is the only source of new-work candidates.
2. Separately run `python3 .claude/skills/jira-todo/scripts/ai_jira_cli.py list --state progress --format json`. Use it only to find active, reserved, stranded-review, duplicate, overlapping, or unavailable work.
3. Read relevant todo details with `python3 .claude/skills/jira-todo/scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json`. Read progress details only when needed for overlap or dependency analysis.
4. Read `CLAUDE.md`, `AGENTS.md`, or linked project AI guidance.
5. Use read-only Git, worktree, lease, Unity-process, and pull-request inspection to find existing, overlapping, or stranded work.
6. Report actionable todo items, progress evidence, blockers, and dependencies separately. Rank only actionable todo issues and classify each progress issue as `active`, `reserved`, or `stranded-review`.

Only todo-query issues may be recommended as new work. For progress, apply deterministic precedence: active when an open PR, dirty worktree, Unity process, or equivalent current-work evidence exists; otherwise reserved when a matching lease exists, regardless of acquisition PID liveness; otherwise stranded-review when only merged/closed PRs or no active work evidence remains. These are exclusion/recovery reports, never reasons to recommend continuing or to expire, release, steal, or call a lease stale. If no todo issue is actionable, say so even when progress issues exist.

Never write to Jira, create worktrees or branches, edit files, commit, push, or create pull requests. Never display credentials or ignored config contents. If local Jira setup is missing, explain how to configure it locally without requesting a token in chat.

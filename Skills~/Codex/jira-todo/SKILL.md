---
name: jira-todo
description: Recommend new work only from assigned unresolved Jira todo items, while using in-progress items solely to detect existing or overlapping work.
---

# Jira Todo

Use this skill for Jira triage and work recommendations only. It is strictly read-only.

## Workflow

1. From the consuming project root, run `python3 .agents/skills/jira-todo/scripts/ai_jira_cli.py list --state todo --format json`. This result is the only source of new-work candidates.
2. Separately run `python3 .agents/skills/jira-todo/scripts/ai_jira_cli.py list --state progress --format json`. Use this result only to identify work that is active, reserved, stranded-review, duplicated, overlapping, or unavailable for new pickup.
3. Read relevant todo issue details with `python3 .agents/skills/jira-todo/scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json`. Read a progress issue's details only when needed to evaluate an overlap or dependency.
4. Read the repository's `AGENTS.md`, `CLAUDE.md`, or linked AI guidance before interpreting implementation scope.
5. Inspect local branches, worktrees, leases, Unity processes, and pull requests with read-only commands when needed to identify duplicate, already-started, or stranded work.
6. Report actionable work, progress evidence, blocked work, and overlaps or dependencies as separate groups. Rank only actionable todo issues and explain the evidence. Classify each progress issue as `active`, `reserved`, or `stranded-review`.

## Candidate Rules

- Only issues returned by the `todo` query may appear as actionable or recommended new work.
- Issues returned by the `progress` query must be reported only as already active, excluded, overlapping, or dependency context.
- Apply deterministic precedence: `active` when an open PR, dirty worktree, Unity process, or equivalent current-work evidence exists; otherwise `reserved` when a matching lease exists, regardless of whether its acquisition PID still exists; otherwise `stranded-review` when only merged/closed PRs or no active work evidence remains.
- An existing branch, worktree, or pull request for a progress issue confirms that it should be excluded; it is not a reason to recommend continuing that issue.
- Never expire, release, steal, or call a lease stale from PID liveness. Stranded-review is a recovery report, not automatic mutation authority.
- If the user explicitly asks to resume or inspect a specific progress issue, report its state and repository evidence without turning this read-only skill into an implementation workflow.
- When no todo issue is actionable, say so even if progress issues exist.

## Boundaries

- Never create, edit, transition, assign, comment on, or otherwise write to Jira.
- Never create a branch or worktree, edit project files, commit, push, or create a pull request.
- Do not expose credentials or print ignored Jira config contents.
- If credentials or config are missing, explain the local setup requirement without asking the user to paste a token into chat.
- Treat the helper output as Jira evidence, then verify repository claims with local read-only inspection.

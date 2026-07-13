---
name: jira-run
description: Implement an explicitly selected Jira issue through an isolated worktree, validation, pull request, and configured Jira lifecycle updates.
---

# Jira Run

Use this skill only when the user explicitly invokes it and identifies the Jira issue or explicitly selects one from a prior read-only result.

## Workflow

1. Run `python3 scripts/ai_jira_cli.py list --state all --format json`, then `python3 scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json`. Confirm the selected key appears in the assigned unresolved list and belongs to the configured project.
2. Read the repository's `AGENTS.md`, `CLAUDE.md`, and linked project guidance, including its Jira, worktree, validation, commit, and pull-request rules.
3. Check existing branches, worktrees, and pull requests for the issue before creating anything.
4. Restate the implementation scope, risk, and validation plan. Obtain any approval required by the repository workflow; an invocation that already contains an explicit approved scope can satisfy this step.
5. When implementation actually starts, use the consuming project's Jira write tools to move the issue to the configured progress status. If those tools or their write gates are unavailable, report the blocker instead of inventing a direct Jira write.
6. Create the required isolated worktree, implement only the approved scope, update relevant documentation, and run proportionate tests.
7. Review the diff, commit without an AI co-author trailer, push, and create the pull request according to repository guidance.
8. After the PR exists, add Korean QA notes only when the project-local write gate allows it, then move Jira to the configured internal done status. Never move the issue to QA.
9. Report the branch, worktree, PR, Jira status, tests, and any remaining blocker in the repository's required format.

## Boundaries

- This skill is manual-only; never select and start work merely because an issue appears actionable.
- Never expose credentials or copy Jira secrets into package or tracked files.
- Preserve unrelated user changes and do not use destructive Git commands.
- Do not overwrite full Jira descriptions. Use only project-approved append/prepend operations.
- If issue scope conflicts with repository guidance or existing work, stop before writes and explain the conflict.

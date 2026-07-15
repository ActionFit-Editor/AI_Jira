---
name: jira-run
description: Implement an explicitly selected Jira issue through planning refinement when needed, an isolated worktree, validation, pull request, Korean QA completion notes, and configured Jira lifecycle updates.
---

# Jira Run

Use this skill only when the user explicitly invokes it and identifies the Jira issue or explicitly selects one from a prior read-only result.

## Workflow

1. Run `python3 scripts/ai_jira_cli.py list --state all --format json`, then `python3 scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json`. Confirm the selected key appears in the assigned unresolved list and belongs to the configured project.
2. Read the repository's `AGENTS.md`, `CLAUDE.md`, and linked project guidance, including its Jira, worktree, validation, commit, and pull-request rules.
3. Check existing branches, worktrees, and pull requests for the issue before creating anything.
4. Read `descriptionContract`. Restate the implementation scope, risk, and validation plan. Obtain any approval required by the repository workflow; an invocation that already contains an explicit approved scope can satisfy this step.
5. If the contract is `needs-plan` and the issue is in todo, re-read it, move it to progress as a planning lock, verify the status, capture `updated`, and follow the `jira-plan` mixed-language refinement protocol. After full-draft approval, update only through `update_description.py --mode replace-plan --expected-updated ...`. Return to todo for plan only; keep progress only when the user approved implementation. Roll back to todo after update failure when possible, never expire or steal a lock, and leave an interrupted planning session in progress.
6. If the issue is ready and still in todo, move it to the configured progress status only when implementation starts. If Jira tools or matching write gates are unavailable, report the blocker instead of calling Jira directly.
7. Create the required isolated worktree, implement only the approved scope, update relevant documentation, and run proportionate tests.
8. Review the diff, commit without an AI co-author trailer, push, and create the pull request according to repository guidance.
9. After the PR exists, add Korean QA notes only when the project-local write gate allows it, verify the completion record, then move Jira to the configured internal done status with the PR URL. Never move the issue to QA.
10. Report the branch, worktree, PR, Jira status, tests, and any remaining blocker in the repository's required format.

## Boundaries

- This skill is manual-only; never select and start work merely because an issue appears actionable.
- Never expose credentials or copy Jira secrets into package or tracked files.
- Preserve unrelated user changes and do not use destructive Git commands.
- Do not perform unrestricted Jira description overwrites. Use only project-approved append, QA prepend, or optimistic-concurrency managed-plan operations.
- Do not migrate existing Jira descriptions in bulk, publish packages, deploy, or perform production operations.
- If issue scope conflicts with repository guidance or existing work, stop before writes and explain the conflict.

---
name: jira-run
description: Implement an explicitly selected Jira issue through a complete Korean planning approval view backed by the exact mixed-language Jira draft when refinement is needed, validation, a pull request, Korean QA completion notes, and configured Jira lifecycle updates.
disable-model-invocation: true
---

# Jira Run

Use this skill only after the user explicitly invokes it with an issue key or explicitly selects an issue from prior triage.

1. Run `python3 scripts/ai_jira_cli.py list --state all --format json`, then `python3 scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json`. Verify the selected key appears in the assigned unresolved list and belongs to the configured project.
2. Immediately announce the selected issue with the exact standalone user-visible line `🎫 Jira: <ISSUE-KEY>`. This announcement must happen before any Jira write, worktree preparation, or repository mutation.
3. Read `CLAUDE.md`, `AGENTS.md`, and linked repository rules for Jira, worktrees, tests, commits, and pull requests.
4. Check for an existing branch, worktree, or pull request before creating anything, then resolve the canonical implementation branch. Before a progress transition or worktree acquisition, verify that the planned canonical branch name contains the exact selected issue key. Stop on a mismatch. A needs-plan planning lock does not create a branch solely for visibility; defer the branch check until implementation is approved.
5. Read `descriptionContract`, then restate scope, risk, and validation. Obtain repository-required approval unless the invocation already contains an explicit approved scope.
6. If the contract needs plan and the issue is todo, transition it to progress as a planning lock only after the visible Jira announcement, verify and capture `updated`, then prepare and retain the canonical Jira Plan mixed-language draft. Read `references/korean-approval-preview.md`, show its complete Korean approval view, and explain that approval writes the corresponding pre-preview canonical draft. Update only with `update_description.py --mode replace-plan --expected-updated ...` using that draft; return to todo for plan only, keep progress for approved implementation, and attempt rollback on update failure. Never expire or steal a lock. If canonical state is unavailable or uncertain, regenerate both representations and obtain approval again.
7. For ready todo work, transition to progress only when the announced, Jira-key-verified branch/worktree plan exists and implementation starts. Missing tools or disabled gates are blockers, not permission to call Jira directly.
8. Work in the required isolated worktree. Before repository edits, read the actual checked-out branch and verify that it still contains the exact selected issue key; stop if it differs from the canonical plan. Then preserve unrelated changes, implement the approved scope, update docs, and validate.
9. Review, commit without an AI co-author trailer, push, and create the pull request.
10. After the PR exists, prepend Korean QA notes, verify the completion record, and transition to internal done with the PR URL. Never move Jira to QA.
11. Report the issue key, branch, worktree, PR, Jira state, tests, and blockers in the repository's required format.

Never reveal Jira credentials, perform unrestricted issue-description overwrites or bulk migrations, make unrelated changes, publish or deploy, or use destructive Git commands.

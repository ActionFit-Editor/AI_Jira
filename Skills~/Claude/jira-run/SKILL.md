---
name: jira-run
description: Implement an explicitly selected Jira issue through planning refinement when needed, validation, a pull request, Korean QA completion notes, and configured Jira lifecycle updates.
disable-model-invocation: true
---

# Jira Run

Use this skill only after the user explicitly invokes it with an issue key or explicitly selects an issue from prior triage.

1. Run `python3 scripts/ai_jira_cli.py list --state all --format json`, then `python3 scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json`. Verify the selected key appears in the assigned unresolved list and belongs to the configured project.
2. Read `CLAUDE.md`, `AGENTS.md`, and linked repository rules for Jira, worktrees, tests, commits, and pull requests.
3. Check for an existing branch, worktree, or pull request before creating anything.
4. Read `descriptionContract`, then restate scope, risk, and validation. Obtain repository-required approval unless the invocation already contains an explicit approved scope.
5. If the contract needs plan and the issue is todo, transition it to progress as a planning lock, verify and capture `updated`, then follow the Jira Plan mixed-language approval flow. Update only with `update_description.py --mode replace-plan --expected-updated ...`; return to todo for plan only, keep progress for approved implementation, and attempt rollback on update failure. Never expire or steal a lock.
6. For ready todo work, transition to progress only when implementation starts. Missing tools or disabled gates are blockers, not permission to call Jira directly.
7. Work in the required isolated worktree, preserve unrelated changes, implement the approved scope, update docs, and validate.
8. Review, commit without an AI co-author trailer, push, and create the pull request.
9. After the PR exists, prepend Korean QA notes, verify the completion record, and transition to internal done with the PR URL. Never move Jira to QA.
10. Report the branch, worktree, PR, Jira state, tests, and blockers in the repository's required format.

Never reveal Jira credentials, perform unrestricted issue-description overwrites or bulk migrations, make unrelated changes, publish or deploy, or use destructive Git commands.

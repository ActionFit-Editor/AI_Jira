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
6. If the contract needs plan and the issue is todo, capture its todo `updated` value and keep it in todo while preparing and retaining the canonical Jira Plan mixed-language draft. Read `references/korean-approval-preview.md`, show its complete Korean approval view, and obtain full-draft approval. Only in the approved continuation may you re-read and require the same todo status and captured `updated`; mismatch requires regeneration and reapproval without transition. After a match, transition to progress as a transient planning lock, verify and capture post-transition `updated`, then update with `update_description.py --mode replace-plan --expected-updated ...`. Return to todo for plan only or continue immediately for approved implementation. Attempt rollback after update failure and never expire or steal a lock. Approval waiting, revisions, and uncertain canonical state remain todo; regenerate both representations and obtain approval again when canonical state is uncertain.
7. For ready todo work, transition to progress only when the announced, Jira-key-verified branch/worktree plan exists and implementation starts. Missing tools or disabled gates are blockers, not permission to call Jira directly.
8. Work in the required isolated worktree. Before repository edits, read the actual checked-out branch and verify that it still contains the exact selected issue key; stop if it differs from the canonical plan. Then preserve unrelated changes, implement the approved scope, update docs, and validate.
9. Review, commit without an AI co-author trailer, push, and create the pull request. Resume an incomplete open PR only after Jira returns to todo and no active lease owns it; never reuse a merged or closed PR branch.
10. After the PR exists, prepend Korean QA notes, verify the completion record, and run `Tools/AI/jira/finalize_session.py <ISSUE-KEY> --outcome done --pr-url <PR-URL>` using the PR URL. Never move Jira to QA.
11. If work is incomplete, unclear, approval-blocked, or stopped after a partial PR, run `finalize_session.py --outcome incomplete` with every Korean handoff field, verify the handoff and todo status, and follow lease-release rules. A PR alone never proves completion.
12. Report the issue key, branch, worktree, PR, Jira state, tests, and blockers in the repository's required format.

Never produce a normal final response while the selected issue remains progress. Only an explicit Jira/finalization failure or abrupt process failure may leave it there; report the exact partial state and recovery action.

Never reveal Jira credentials, perform unrestricted issue-description overwrites or bulk migrations, make unrelated changes, publish or deploy, or use destructive Git commands.

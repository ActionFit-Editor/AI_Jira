---
name: jira-run
description: Implement an explicitly selected Jira issue after collaboratively resolving material implementation decisions, with validation, a pull request, Korean QA completion notes, and configured Jira lifecycle updates.
disable-model-invocation: true
---

# Jira Run

Use this skill only after the user explicitly invokes it with an issue key or explicitly selects an issue from prior triage.

1. Run `python3 scripts/ai_jira_cli.py list --state all --format json`, then `python3 scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json`. Verify the selected key appears in the assigned unresolved list and belongs to the configured project.
2. Immediately announce the selected issue with the exact standalone user-visible line `🎫 Jira: <ISSUE-KEY>`. This announcement must happen before any Jira write, worktree preparation, or repository mutation.
3. Read `CLAUDE.md`, `AGENTS.md`, and linked repository rules for Jira, worktrees, tests, commits, and pull requests.
4. Check for an existing branch, worktree, or pull request before creating anything, then resolve the canonical implementation branch. Before a progress transition or worktree acquisition, verify that the planned canonical branch name contains the exact selected issue key. Stop on a mismatch. A needs-plan planning lock does not create a branch solely for visibility; defer the branch check until implementation is approved.
5. Read `descriptionContract`, `references/planning-decision-collaboration.md`, and `references/completion-baseline-gate.md`, then restate scope, risk, and validation. Apply convention precedence and resolve newly exposed material alternatives before implementation. A ready issue with explicit confirmed decisions and one convention-supported path proceeds without an unnecessary question; otherwise keep todo and complete bounded question rounds, re-scans, and decision closure.
6. If the contract needs plan, read `references/korean-approval-preview.md`, retain the approved canonical draft and Korean approval view, acquire a sealed planning lock with `transition --to progress --purpose planning --json`, compare every source requirement, and pass an exact plan-coverage artifact to `update-description --mode replace-plan --expected-updated ... --coverage-file ...` as defined by `references/completion-baseline-gate.md`. Removed, deferred, or out-of-scope work requires separate explicit replanning approval; a partial PR never narrows the parent issue. Use `transition --to todo --purpose planning` for plan only or continue to implementation start. Attempt rollback after failure and never expire or steal a lock.
7. Start implementation only through `python3 .claude/skills/jira-run/scripts/ai_jira_write_cli.py start <ISSUE-KEY> --branch <ACTUAL-BRANCH> --json`, preserving its session ID, digest, and requirement IDs. Never use a generic progress transition. Legacy progress without a baseline must finalize incomplete, return to todo, and restart.
8. Work in the required isolated worktree. Before repository edits, read the actual checked-out branch and verify that it still contains the exact selected issue key; stop if it differs from the canonical plan. Then preserve unrelated changes, implement the approved scope, update docs, and validate.
9. Review, commit without an AI co-author trailer, push, and create the pull request. Resume an incomplete open PR only after Jira returns to todo and no active lease owns it; never reuse a merged or closed PR branch.
10. After the PR exists, compare every sealed requirement with the diff and validation, create the completion-review JSON from `references/completion-baseline-gate.md`, prepend and verify all five Korean QA fields, and run `finalize <ISSUE-KEY> --outcome done --pr-url <PR-URL> --review-file <REVIEW-JSON>`. Partial, deferred, or evidence-free work must finalize incomplete. Never move Jira to QA.
11. If work is incomplete, unclear, approval-blocked, or stopped after a partial PR, run the package locator's `finalize <ISSUE-KEY> --outcome incomplete` command with every Korean handoff field, verify the handoff and todo status, and follow lease-release rules. A PR alone never proves completion.
12. Report the issue key, branch, worktree, PR, Jira state, tests, and blockers in the repository's required format.

Approval waiting stays in todo. Before the transient planning lock, capture `updated`, require the same todo status, and regenerate/reapprove if it changed. Before repository edits, verify the actual checked-out branch and that the planned canonical branch name contains the exact issue key. Done requires verified QA, the exact PR URL, and the completion review. A normal final response must use `--outcome done` or `--outcome incomplete`; a PR alone never proves completion. Resume an open PR only with no active lease, and never reuse a merged or closed PR branch.

Never produce a normal final response while the selected issue remains progress. Only an explicit Jira/finalization failure or abrupt process failure may leave it there; report the exact partial state and recovery action.

Never reveal Jira credentials, perform unrestricted issue-description overwrites or bulk migrations, make unrelated changes, publish or deploy, or use destructive Git commands.

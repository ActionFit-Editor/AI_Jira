---
name: jira-run
description: Implement an explicitly selected Jira issue after collaboratively resolving material implementation decisions, using an isolated worktree, validation, pull request, Korean QA completion notes, and configured Jira lifecycle updates.
---

# Jira Run

Use this skill only when the user explicitly invokes it and identifies the Jira issue or explicitly selects one from a prior read-only result.

## Workflow

1. Run `python3 scripts/ai_jira_cli.py list --state all --format json`, then `python3 scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json`. Confirm the selected key appears in the assigned unresolved list and belongs to the configured project.
2. Immediately announce the selected issue in user-visible commentary with the exact standalone line `🎫 Jira: <ISSUE-KEY>`. This announcement must happen before any Jira write, worktree preparation, or repository mutation.
3. Read the repository's `AGENTS.md`, `CLAUDE.md`, and linked project guidance, including its Jira, worktree, validation, commit, and pull-request rules.
4. Check existing branches, worktrees, and pull requests for the issue before creating anything, then resolve the canonical implementation branch. Before a progress transition or worktree acquisition, verify that the planned canonical branch name contains the exact selected issue key. Stop on a mismatch instead of editing on a branch for another issue. A needs-plan planning lock does not create a branch solely for title visibility; perform this branch check only when implementation is approved.
5. Read `descriptionContract`, `references/planning-decision-collaboration.md`, `references/completion-baseline-gate.md`, and `references/risk-proportional-validation-plan.md`. Restate the implementation scope, risk, required validation, conditional escalation triggers, intentionally excluded expensive validation, and selected Unity evidence level. Apply convention precedence and resolve any newly exposed material alternative before implementation. A ready issue with explicit confirmed decisions and one convention-supported path may proceed without an unnecessary question. Otherwise keep todo and complete the bounded question, re-scan, and decision-closure flow. An invocation that already contains an explicit approved scope satisfies this step only when no material decision remains.
6. If the contract is `needs-plan` and the issue is in todo, capture its todo `updated` value and keep it in todo while following the `jira-plan` canonical-storage protocol. Read `references/korean-approval-preview.md`, retain the exact mixed-language draft, show its complete Korean approval view, and obtain full-draft approval. Only in the approved continuation may you re-read and require the same todo status and captured `updated`; mismatch requires regeneration and reapproval without transition. After a match, acquire the sealed planning lock through `transition --to progress --purpose planning --json`, compare every returned source requirement against the draft, and create the exact plan-coverage artifact required by `references/completion-baseline-gate.md`. Call `update-description --mode replace-plan --expected-updated ... --coverage-file ...`. Any removed, deferred, or out-of-scope source requirement needs separate explicit replanning approval; a partial PR never narrows the parent issue. Return through `transition --to todo --purpose planning` for plan only; otherwise continue to the implementation start command. Roll back after failure when possible and never expire or steal a lock.
7. When implementation starts, seal it through `python3 .agents/skills/jira-run/scripts/ai_jira_write_cli.py start <ISSUE-KEY> --branch <ACTUAL-BRANCH> --json`; never use a generic progress transition. Preserve the returned session ID, baseline digest, and requirement IDs for final review. A legacy progress issue without a baseline must finalize incomplete, return to todo, and restart. If the package-owned command or matching write gates are unavailable, report the blocker instead of calling Jira directly.
8. Create the required isolated worktree. Before repository edits, read the actual checked-out branch and verify that it still contains the exact selected issue key; stop if it differs from the canonical plan. Then implement only the approved scope, update relevant documentation, and run the required risk-proportional validation. Apply a conditional escalation only when its recorded trigger is present. Do not run a Player build absent from the approved `Validation Plan` without additional user approval, and never infer signing, upload, distribution, deployment, credential, or runner-secret approval from generic QA or completion wording.
9. Review the diff, commit without an AI co-author trailer, push, and create the pull request according to repository guidance. An incomplete open PR may be resumed only for the same issue after Jira returns to todo and no active lease owns it. Never reuse a merged or closed PR branch; create a new follow-up branch and PR.
10. After the PR exists, semantically compare every sealed requirement with the full diff and validation evidence. Create the exact completion-review JSON from `references/completion-baseline-gate.md`, with every ID `complete` and concrete evidence. Add and verify the five-field Korean QA completion record through `update-description`, then run `finalize <ISSUE-KEY> --outcome done --pr-url <PR-URL> --review-file <REVIEW-JSON>` and verify the completed property plus configured done. Never move the issue to QA.
11. If work is incomplete, unclear, approval-blocked, or stopped after a partial PR, run the package locator's `finalize <ISSUE-KEY> --outcome incomplete` command with every Korean handoff field, verify the handoff and configured todo status, then follow repository lease-release rules. A PR alone never proves completion.
12. Report the issue key, branch, worktree, PR, Jira status, tests, and any remaining blocker in the repository's required format.

Approval waiting stays in todo. If the same todo status, captured `updated`, or canonical draft is lost, regenerate the Korean approval view before taking a transient planning lock. Done requires the verified QA fields, the exact PR URL, and the completion review.

Do not produce a normal final response while the selected issue remains in progress. Only an explicit Jira API/finalization failure or abrupt process failure may leave it there; report the exact partial state and recovery action.

## Boundaries

- This skill is manual-only; never select and start work merely because an issue appears actionable.
- Never expose credentials or copy Jira secrets into package or tracked files.
- Preserve unrelated user changes and do not use destructive Git commands.
- Do not perform unrestricted Jira description overwrites. Use only project-approved append, QA prepend, or optimistic-concurrency managed-plan operations.
- Never treat a partial implementation, partial PR, deferred requirement, or narrowed plan as completion. Use incomplete finalization unless separately approved replanning changed the sealed scope before implementation.
- Do not migrate existing Jira descriptions in bulk, publish packages, deploy, or perform production operations.
- If issue scope conflicts with repository guidance or existing work, stop before writes and explain the conflict.

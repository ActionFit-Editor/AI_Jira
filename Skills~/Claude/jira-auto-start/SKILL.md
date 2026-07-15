---
name: jira-auto-start
description: Classify every assigned unresolved Jira todo as startable, needs-plan, blocked, or approval-required; execute the first startable issue or collaboratively refine the first needs-plan issue under a planning lock when none can start. Use when the user asks Jira to find and automatically advance one eligible task.
disable-model-invocation: true
---

# Jira Auto Start

Select and execute exactly one bounded Jira task. Explicit invocation authorizes one eligible task, not sensitive, destructive, production, publishing, deployment, or ambiguous work.

1. Run `python3 .claude/skills/jira-auto-start/scripts/ai_jira_cli.py list --state todo --format json`. Only these issues may become new work.
2. Separately run `python3 .claude/skills/jira-auto-start/scripts/ai_jira_cli.py list --state progress --format json` and use it only for overlap, dependency, and exclusion evidence.
3. Read every todo detail in query order with `python3 .claude/skills/jira-auto-start/scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json`, including `issueLinks` and `configuredStatuses`.
4. Read repository guidance and inspect branches, worktrees, and pull requests with read-only commands.
5. Treat only inward blocking/dependency relations (`is blocked by`, `depends on`, `requires`, or equivalent localized text) and keys explicitly listed under `선행 작업`, `Prerequisite`, or `Dependencies` as prerequisites. Never infer a prerequisite from arbitrary keys, related/duplicate links, or outward `blocks` relations.
6. Read every prerequisite detail. Count it complete only when `resolution` is non-empty or `status` equals `configuredStatuses.done`; missing, unreadable, todo, progress, or unknown states make the candidate blocked. No declared prerequisite passes as `none declared`.
7. Use `descriptionContract` plus clarity, local-completeness, safety, prerequisite, and overlap evidence to classify every todo as `startable`, `needs-plan`, `blocked`, or `approval-required`. Reserve approval-required for publishing, deployment, production, credentials, and separate sensitive/destructive approval. Show every result and reason in query order.
8. Select the first startable issue. If none exists, select the first needs-plan issue. If only blocked or approval-required issues remain, perform no writes.
9. Announce the selected key, classification, scope, risks, and validation. Invocation confirms one startable issue only; needs-plan still requires complete-draft and continuation approval.
10. For needs-plan, re-read todo, transition to progress as a planning lock, verify and capture `updated`, then follow the Jira Plan mixed-language contract without creating a worktree. Ask for plan only or plan update and auto-start approval. Update only with `update_description.py --mode replace-plan --expected-updated ...`. Return to todo for plan only or keep progress and continue for approved implementation. On failure, attempt verified todo rollback; never expire or steal an interrupted lock.
11. Resolve the canonical branch and isolated worktree. Transition a directly startable issue to progress only when implementation starts; a refined issue already holds the lock.
12. Implement, validate, review, commit without an AI co-author trailer, push, and create the PR under repository rules.
13. After the PR exists, prepend Korean QA notes, verify the completion record, transition to internal done with the PR URL, and report the issue, branch, worktree, PR, Jira state, tests, and blockers. Never move Jira to QA.

If work becomes unclear after the progress transition, stop speculative changes, leave the issue in progress, and report the blocker. Never select progress/done/resolved/other-assignee work, start multiple issues, bypass Jira gates, merge, publish, deploy, bulk-migrate descriptions, expose credentials, perform unrestricted description overwrites, or use destructive Git commands. Use `$jira-run` for an already selected key. Do not change `$jira-todo`; it remains the read-only overall todo view.

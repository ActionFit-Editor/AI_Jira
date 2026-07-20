---
name: jira-auto-start
description: Classify every assigned unresolved Jira todo as startable, needs-plan, blocked, or approval-required; execute the first startable issue or refine the first needs-plan issue through a complete Korean approval view backed by the exact mixed-language Jira draft when none can start. Use when the user asks Jira to find and automatically advance one eligible task.
---

# Jira Auto Start

Advance exactly one bounded Jira task. Treat explicit invocation as approval to select one eligible issue, not as broad approval for sensitive, destructive, production, publishing, deployment, or ambiguous work.

## Discover Candidates

1. From the consuming project root, run `python3 .agents/skills/jira-auto-start/scripts/ai_jira_cli.py list --state todo --format json`. Only these issues may become new work.
2. Separately run `python3 .agents/skills/jira-auto-start/scripts/ai_jira_cli.py list --state progress --format json`. Use these issues only as overlap, dependency, exclusion, and stranded-progress recovery evidence.
3. Read every todo candidate with `python3 .agents/skills/jira-auto-start/scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json` in query order. Use its `issueLinks` and `configuredStatuses` as prerequisite evidence.
4. Read `AGENTS.md`, `CLAUDE.md`, and linked repository guidance before judging scope.
5. Inspect branches, worktrees, leases, Unity processes, and pull requests with read-only commands to detect existing, overlapping, or stranded work. Classify each progress issue with deterministic precedence: `active` when an open PR, dirty worktree, Unity process, or equivalent current-work evidence exists; otherwise `reserved` when a matching lease exists, regardless of acquisition PID liveness; otherwise `stranded-review` when only merged/closed PRs or no active work evidence remains. Never expire, release, or steal a lease during discovery.

## Resolve Prerequisites

Recognize a prerequisite only from explicit evidence:

- An `issueLinks` relation shown from the candidate's perspective as `is blocked by`, `depends on`, `depends upon`, `requires`, or an equivalent configured/localized blocking relation such as `선행`, `의존`, or `차단됨`.
- An issue key explicitly listed as a prerequisite in a description section labeled `선행 작업`, `Prerequisite`, or `Dependencies`.

Do not treat arbitrary Jira keys, related links, duplicate links, or an outward relation such as `blocks` or `is required by` as prerequisites. If a prerequisite statement has no unambiguous issue key or the relation direction is unclear, classify the candidate as blocked.

Read every declared prerequisite through `detail <ISSUE-KEY>`. Count it complete only when its `resolution` is non-empty or its `status` exactly equals `configuredStatuses.done`. A prerequisite in todo, progress, an unknown state, or an unreadable issue makes the candidate blocked. A candidate with no declared prerequisite passes this gate as `none declared`.

## Classify Every Candidate

Use `descriptionContract` from issue detail as deterministic description evidence, then add repository, prerequisite, overlap, and safety evidence. Assign exactly one result:

- `startable`: `descriptionContract.state` is `ready`, every declared prerequisite is complete, the local scope is bounded and verifiable, and no safety or overlap gate remains.
- `needs-plan`: the contract reports `needs-plan`, required scope or validation is missing, or a product decision remains but can be resolved with the user without external input.
- `blocked`: `Allowed` is false, a prerequisite is incomplete or ambiguous, required local input is unavailable, or active work overlaps.
- `approval-required`: publishing, deployment, production access, credentials, or a separately approved sensitive/destructive operation is required.

A `startable` candidate must satisfy every condition below:

- It came from the assigned unresolved `todo` query and belongs to the configured project.
- Its title and description define a clear outcome, bounded repository scope, and verifiable completion condition without relying on the title alone.
- The required source, data, and project guidance are locally available, and the work can be completed with existing authorized tools.
- Every explicitly declared prerequisite was found and completed under the rule above.
- It needs no unresolved product choice, missing asset, external data, credential, production access, manual third-party operation, deployment, or separately approved sensitive/destructive change.
- It does not duplicate or materially overlap a progress issue, existing branch, leased worktree, or open pull request.

Reject rather than reinterpret an issue whose safe implementation depends on assumptions. Before selecting work, show every todo candidate in query order with its key, classification, prerequisite keys and observed states, and all reasons. Continue immediately after this report without waiting for another selection choice.

## Select Deterministically

Select the first `startable` issue in the todo query's existing order. If none is startable, select the first `needs-plan` issue in that order and use the planning-lock workflow below. If only `blocked` or `approval-required` issues remain, stop without writes. Do not promote a progress issue, reorder candidates by guessed business value, or advance more than one issue in a single invocation.

Announce the selected issue first with the exact standalone user-visible commentary line `🎫 Jira: <ISSUE-KEY>`, then report its classification, understood scope, material risks, and validation plan. The standalone Jira line must appear before any Jira write, worktree preparation, or repository mutation. The explicit skill invocation satisfies normal requirement confirmation only for one `startable` bounded issue. A `needs-plan` issue still requires explicit approval of the complete refined description and whether to stop after planning or continue into implementation.

## Refine A Needs-Plan Issue

1. Re-read the selected issue and require its status to equal `configuredStatuses.todo`.
2. Capture the todo issue's `updated` value. While it remains in todo, prepare the canonical `jira-plan` storage draft: Korean Jira title and QA section, English `Auto Start`, `Goal`, `Scope`, `Out of Scope`, `Completion Criteria`, `Validation Plan`, and `Dependencies and Risks` content.
3. Read `references/korean-approval-preview.md`, retain that exact canonical draft, show its complete Korean approval view, and ask for explicit approval of either **plan only** or **plan update and auto-start**. Explain that approval writes the corresponding canonical mixed-language draft.
4. After approval, re-read and require the same todo status and captured `updated` value. If either differs, regenerate and reapprove without transitioning. After a match, move it to `progress` through `python3 .agents/skills/jira-auto-start/scripts/ai_jira_write_cli.py transition`, verify the transient planning lock, and capture its post-transition `updated` value. Do not create a branch or worktree for plan-only work.
5. Call the same locator's `update-description` command with `--mode replace-plan`, a temporary file, and the captured `--expected-updated` value, remove the file, then re-read and verify the managed contract.
6. For plan only, transition back to `todo` through the locator, verify, and stop. For plan update and auto-start, continue immediately with implementation and do not end the invocation in `progress`.

If the update fails after lock acquisition, attempt to return to `todo` and verify. If rollback also fails, report both failures as an exceptional stranded-progress case. Never expire or steal a planning lock automatically. Approval waiting, revision discussion, and uncertain canonical state remain in todo; regenerate both representations and request approval again before any Jira write.

## Execute The Selected Issue

1. Recheck existing branches and pull requests for the selected key and choose the canonical branch according to repository guidance. Before a progress transition or worktree acquisition, verify that the planned canonical branch name contains the exact selected issue key. Stop on a mismatch. Do not create a branch for a needs-plan issue until implementation is approved.
2. For a directly startable issue, transition Jira through `python3 .agents/skills/jira-auto-start/scripts/ai_jira_write_cli.py transition` to the configured progress status only after the visible Jira announcement and Jira-key-verified branch/worktree plan exist and implementation is immediately starting. A refined issue already holds the verified planning lock.
3. Prepare the required isolated worktree. Before repository edits, read the actual checked-out branch and verify that it still contains the exact selected issue key; stop if it differs from the canonical plan.
4. Use only the package-owned write locator and enabled consuming-project gates. Missing tools, dry-run mode, or disabled gates are blockers; never call Jira directly to bypass them.
5. Implement only the selected issue, preserve unrelated changes, update required documentation, and run proportionate validation.
6. Review the complete diff, commit without an AI co-author trailer, push, and create the pull request using repository rules. Reuse an incomplete open PR only for the same issue after Jira has returned to todo and no active lease owns it. Never reuse a merged or closed PR branch; create a new follow-up branch and PR.
7. After the PR exists, prepend Korean QA notes through the locator's `update-description` command when enabled, verify the QA completion record, then run its `finalize <ISSUE-KEY> --outcome done --pr-url <PR-URL>` command and verify configured done. Never move the issue to QA.
8. If work is incomplete, unclear, approval-blocked, or stopped after a partial PR, run the locator's `finalize <ISSUE-KEY> --outcome incomplete` command with every Korean handoff field, verify the handoff and configured todo status, then follow repository lease-release rules. A PR alone never proves completion.
9. Report the selected issue key, branch, worktree, PR, Jira state, validation, and remaining blockers in the repository's required format.

Do not produce a normal final response while the selected issue remains in progress. Only an explicit Jira API/finalization failure or abrupt process failure may leave it there; report the exact partial state and recovery command instead of claiming a normal completion.

## Boundaries

- Never select from `progress`, `done`, another assignee, another configured project, or a resolved issue.
- Never create a second task, run several candidates in parallel, merge a PR, publish a package, deploy, migrate existing Jira descriptions in bulk, or perform production operations.
- Never expose credentials, print ignored Jira config, perform an unrestricted Jira description overwrite, or use destructive Git commands.
- Use `$jira-run` when the user already selected a specific issue. Use `$jira-todo` when the user wants recommendations without implementation.
- Do not change `$jira-todo`; it remains the read-only overall todo view.

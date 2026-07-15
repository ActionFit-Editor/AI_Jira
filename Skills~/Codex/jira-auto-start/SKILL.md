---
name: jira-auto-start
description: Classify every assigned unresolved Jira todo as startable, needs-plan, blocked, or approval-required; execute the first startable issue or collaboratively refine the first needs-plan issue under a planning lock when none can start. Use when the user asks Jira to find and automatically advance one eligible task.
---

# Jira Auto Start

Advance exactly one bounded Jira task. Treat explicit invocation as approval to select one eligible issue, not as broad approval for sensitive, destructive, production, publishing, deployment, or ambiguous work.

## Discover Candidates

1. From the consuming project root, run `python3 .agents/skills/jira-auto-start/scripts/ai_jira_cli.py list --state todo --format json`. Only these issues may become new work.
2. Separately run `python3 .agents/skills/jira-auto-start/scripts/ai_jira_cli.py list --state progress --format json`. Use these issues only as overlap, dependency, and exclusion evidence.
3. Read every todo candidate with `python3 .agents/skills/jira-auto-start/scripts/ai_jira_cli.py detail <ISSUE-KEY> --format json` in query order. Use its `issueLinks` and `configuredStatuses` as prerequisite evidence.
4. Read `AGENTS.md`, `CLAUDE.md`, and linked repository guidance before judging scope.
5. Inspect branches, worktrees, and pull requests with read-only commands to detect existing or overlapping work.

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

Announce the selected key, its classification, understood scope, material risks, and validation plan before any write. The explicit skill invocation satisfies normal requirement confirmation only for one `startable` bounded issue. A `needs-plan` issue still requires explicit approval of the complete refined description and whether to stop after planning or continue into implementation.

## Refine A Needs-Plan Issue

1. Re-read the selected issue and require its status to equal `configuredStatuses.todo`.
2. Move it to `progress` through the project transition tool, re-read it, verify the planning lock, and capture its `updated` value. Do not create a branch or worktree yet.
3. Follow the `jira-plan` mixed-language contract: Korean Jira title and QA section, English `Auto Start`, `Goal`, `Scope`, `Out of Scope`, `Completion Criteria`, `Validation Plan`, and `Dependencies and Risks` content.
4. Show the complete draft and ask for explicit approval of either **plan only** or **plan update and auto-start**.
5. After approval, call the project `update_description.py --mode replace-plan` with a temporary file and the captured `--expected-updated` value, remove the file, then re-read and verify the managed contract.
6. For plan only, transition back to `todo`, verify, and stop. For plan update and auto-start, keep `progress` and continue with implementation.

If the update fails, attempt to return to `todo` and verify. If rollback also fails, leave the issue in `progress` and report both failures. Never expire or steal a planning lock automatically. An interrupted planning session remains in `progress` until the user explicitly resumes or releases it, and every other session must continue excluding progress issues.

## Execute The Selected Issue

1. Recheck existing branches and pull requests for the selected key and choose the canonical branch according to repository guidance.
2. Prepare the required isolated worktree. For a directly startable issue, transition Jira to the configured progress status only when the branch/worktree plan exists and implementation is immediately starting. A refined issue already holds the verified planning lock.
3. Use only consuming-project Jira write tools and enabled gates. Missing tools, dry-run mode, or disabled gates are blockers; never call Jira directly to bypass them.
4. Implement only the selected issue, preserve unrelated changes, update required documentation, and run proportionate validation.
5. Review the complete diff, commit without an AI co-author trailer, push, and create the pull request using repository rules.
6. After the PR exists, prepend Korean QA notes when enabled, verify the QA completion record, then transition Jira to the configured internal done status with the PR URL. Never move the issue to QA.
7. Report the selected issue, branch, worktree, PR, Jira state, validation, and remaining blockers in the repository's required format.

If work becomes unclear or blocked after the progress transition, stop before speculative changes, leave the issue in progress, and report the exact blocker.

## Boundaries

- Never select from `progress`, `done`, another assignee, another configured project, or a resolved issue.
- Never create a second task, run several candidates in parallel, merge a PR, publish a package, deploy, migrate existing Jira descriptions in bulk, or perform production operations.
- Never expose credentials, print ignored Jira config, perform an unrestricted Jira description overwrite, or use destructive Git commands.
- Use `$jira-run` when the user already selected a specific issue. Use `$jira-todo` when the user wants recommendations without implementation.
- Do not change `$jira-todo`; it remains the read-only overall todo view.

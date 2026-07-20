---
name: jira-plan
description: Collaboratively resolve material implementation decisions, show the complete approved plan in Korean while retaining the exact mixed-language Jira storage draft, then create a new todo issue or safely refine an existing todo issue without implementing it.
---

# Jira Plan

Turn a new idea into one approved Jira todo issue, or refine one explicitly selected todo issue under a transient approved write lock. Do not implement the planned work in this skill or end a normal invocation with the issue in progress.

## Research And Discuss

1. Read `AGENTS.md`, `CLAUDE.md`, and linked repository guidance before proposing project work.
2. Inspect relevant source, documentation, and configuration with read-only commands so the plan reflects the current repository rather than assumptions.
3. When Jira access is configured, run `python3 .agents/skills/jira-plan/scripts/ai_jira_cli.py list --state todo --format json` and `python3 .agents/skills/jira-plan/scripts/ai_jira_cli.py list --state progress --format json`. Read details only when needed to identify a likely duplicate, dependency, or overlap.
4. Read `references/planning-decision-collaboration.md` and apply its convention precedence, bounded question rounds, delegation lifetime, re-scan, and decision-closure rules.
5. Resolve the goal, current problem, included and excluded scope, ordered implementation approach, completion conditions, validation, dependencies, risks, and rollout or migration implications without silently selecting among material alternatives.
6. Do not prepare the approval-ready full plan until every material decision is resolved and the user explicitly confirms decision closure.

Do not edit repository files, create a worktree, or start implementation while planning. New-issue planning remains read-only. Existing-issue discussion and approval waiting also remain in todo; only the approved managed-description write may use the transient planning lock described below.

## Prepare The Jira Draft

Write the canonical Jira storage title in Korean. Keep `## QA 확인 필요 사항` and all of its content in Korean. Write every other managed heading and its content in English. Preserve technical identifiers such as class names, file paths, commands, config keys, and branch names.

Use this complete description structure:

```md
## QA 확인 필요 사항

### 계획
- 확인 항목:

---

## Auto Start
- Allowed: yes
- Prerequisites: none
- Decisions Required: none

## Goal

## Scope

## Out of Scope

## Completion Criteria

## Validation Plan

## Dependencies and Risks
```

Keep the three `Auto Start` fields and every managed heading. Give every English section content and use `None.` when a section has no applicable item. Use `none` when no prerequisite or decision exists. Leave the Korean `확인 항목:` value blank when there is no planned QA check. Do not add default fields for allowed paths, forbidden paths, external state, or sensitive/destructive work; infer those boundaries from repository guidance and the actual scope.

Make implementation steps ordered and concrete. Make completion conditions observable and validation steps executable. Identify unresolved decisions instead of hiding them in the plan.

After decision closure, record confirmed material choices and their rationale under `## Scope` as `### Confirmed Decisions` according to `references/planning-decision-collaboration.md`. Then read `references/korean-approval-preview.md` and follow its dual-representation contract. Prepare and retain the exact canonical storage draft first, then show its complete Korean approval view without displaying the English storage body by default. Ask for explicit approval of the requested Jira create or managed-plan update and explain that approval writes the corresponding pre-preview canonical mixed-language draft. Decision closure, discussion, partial approval, or approval of only the approach does not authorize a Jira write.

## Refine An Existing Needs-Plan Issue

Use this path only for an explicitly selected assigned unresolved todo issue whose description needs planning.

1. Re-read the issue and require its status to equal `configuredStatuses.todo`.
2. Capture the todo issue's `updated` value, then discuss the missing scope or decisions while it stays in todo. Follow `references/planning-decision-collaboration.md` until decision closure, prepare the complete canonical mixed-language description above, follow `references/korean-approval-preview.md`, show its complete Korean approval view, and ask for explicit plan-update approval.
3. After explicit approval, re-read the issue and require the same todo status and `updated` value from the captured approved todo snapshot. If they differ, regenerate and reapprove without transitioning. Only after a match may you move it to `progress`, re-read it, verify the transient planning lock, and capture the post-transition `updated` value.
4. Write the retained draft to a temporary UTF-8 file outside the repository and call `python3 .agents/skills/jira-plan/scripts/ai_jira_write_cli.py update-description <ISSUE-KEY> --mode replace-plan --file <path> --expected-updated <captured-value>`. Remove the temporary file.
5. Re-read the issue, verify the approved managed contract, transition it back to `todo`, and verify the final status before responding.

The package-owned command must preserve existing Korean QA completion records and unmanaged sections. If the managed update fails after the transient lock, attempt to return the issue to `todo`, re-read it, and report both failures if rollback also fails. Never expire or steal a planning lock automatically. Waiting for approval, requested revisions, and lost canonical state must remain in todo. Only an abrupt process failure or Jira failure may exceptionally strand the issue in progress, and that failure must be reported for recovery.

## Create After Approval

1. Reuse the exact canonical title and description prepared before the approved Korean preview without silently revising or back-translating them.
2. Call `python3 .agents/skills/jira-plan/scripts/ai_jira_write_cli.py create` with `--summary` and a temporary UTF-8 `--description-file` outside the repository, then remove that temporary file. Do not call Jira REST directly.
3. Let the package-owned command enforce assignment to the authenticated user, configured todo status, active-sprint behavior, issue-type ID resolution, dry-run mode, and write gates.
4. Report the created issue key and URL, or the exact blocker when configuration, credentials, sprint resolution, or write gates prevent creation.
5. Leave the issue in todo. Do not create a branch, leave it in progress, implement, commit, push, or open a pull request.

Do not implement the planned issue in this invocation.

If a likely duplicate exists, present it and obtain the user's decision before creating another issue. If the user supplies an existing issue key, refine it only through the project-approved plan-specific operation above; never perform an unrestricted description overwrite.

## Boundaries

- Create at most one new issue per approved draft.
- Never create labels, epics, subtasks, Jira Advanced Roadmaps Plans, or backlog exceptions unless the user explicitly requests them and repository tooling supports them.
- Never expose credentials or print ignored Jira config contents.
- Never migrate existing Jira descriptions in bulk.
- Never write Jira when the exact canonical draft behind the approved Korean view is unavailable or uncertain; regenerate both representations and obtain approval again.
- Use `$jira-run` or `$jira-auto-start` in a later invocation when the user wants implementation.

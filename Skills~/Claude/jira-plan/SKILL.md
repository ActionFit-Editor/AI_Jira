---
name: jira-plan
description: Research and discuss a development plan, obtain explicit approval for a Korean Jira title and mixed-language managed description, then create a new todo issue or safely refine an existing planning-locked issue without implementing it. Use for new Jira-ready plans and todo issues classified as needs-plan.
disable-model-invocation: true
---

# Jira Plan

Turn one new idea into an approved Jira todo issue, or refine one explicitly selected needs-plan issue under a planning lock. Never implement in this skill.

1. Read `CLAUDE.md`, `AGENTS.md`, and linked repository guidance. Inspect relevant source and documentation without editing repository files.
2. When Jira is configured, query todo and progress separately through `.claude/skills/jira-plan/scripts/ai_jira_cli.py` and read details only to detect duplicates, dependencies, or overlap.
3. Ask only material questions and recommend a choice when tradeoffs exist. Resolve the goal, current problem, included and excluded scope, ordered implementation, completion conditions, validation, dependencies, risks, and migration implications.
4. Draft a Korean title. Keep `## QA 확인 필요 사항`, one `### 계획`, and QA content in Korean; write `## Auto Start`, `## Goal`, `## Scope`, `## Out of Scope`, `## Completion Criteria`, `## Validation Plan`, and `## Dependencies and Risks` plus their content in English. Require `Allowed`, `Prerequisites`, and `Decisions Required`, using `none` when applicable. Give every English section content and use `None.` when no item applies. Keep technical identifiers unchanged and translate explanations for the user when requested.
5. Show the complete final draft and obtain explicit creation approval. Discussion or partial approval is insufficient.
6. After approval, call only `Tools/AI/jira/create_issue.py` with `--summary` and a temporary UTF-8 `--description-file` outside the repository, then remove that file. Let the tool enforce current-user assignment, todo status, sprint defaults, dry-run mode, and write gates.
7. Report the issue key and URL or the exact configuration/write blocker. Leave the issue in todo and do not implement or transition it.

For an explicitly selected needs-plan issue, re-read todo status, transition it to progress as a planning lock, verify the state, and capture `updated`. Show the complete mixed-language draft and ask whether approval is for plan only or plan update and implementation. After approval, call only `Tools/AI/jira/update_description.py <ISSUE-KEY> --mode replace-plan --file <temp-file> --expected-updated <captured-value>`, remove the file, and re-read the contract. Return to todo for plan only; leave progress for the invoking run/auto-start workflow when implementation was approved. On update failure, attempt a verified todo rollback and report both failures if rollback fails. Never expire or steal a planning lock; interrupted planning stays progress until the user resumes or releases it.

If a likely duplicate exists, obtain the user's decision before creating another issue. Never create more than one issue, labels, epics, subtasks, Jira Advanced Roadmaps Plans, backlog exceptions, or bulk description migrations. Never create a worktree, edit repository files, implement, commit, push, open a PR, expose credentials, perform an unrestricted description overwrite, or call Jira REST directly.

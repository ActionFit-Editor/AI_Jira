---
name: jira-help
description: Explain the AI Jira package, its installed related skills, read-only query commands, project-local write commands, configuration, safety gates, and Unity menus. Use when the user asks for Jira help, available skills or commands, package usage, setup, or capability differences.
---

# Jira Help

Provide a concise help response in the user's language. Default to Korean for a Korean request. Do not query Jira or change Jira, Git, or project state unless the user separately requests an operation.

## Required Inventory

Read `PACKAGE_SKILLS.md` in this installed skill directory before answering. It is generated from the package identity, schema v2 manifest, and each agent-specific `SKILL.md` frontmatter. Treat its package summary, complete related-skill list, `$name` invocations, descriptions, and access boundaries as authoritative. If it is missing, explain that `Install or Refresh Agent Skills` must be run instead of reconstructing a potentially stale list.

## Response Contents

Explain these sections in this order:

1. **Package overview**: use the generated package ID, display name, and summary. Add that the package installs project-local Jira skills and a read-only work-item CLI, while Jira writes remain behind consuming-project tools and local safety gates.
2. **Installed skills**: include every row from the generated inventory and preserve each skill's description, when-to-use guidance, access boundary, and exact `$name` invocation. Do not maintain a second hard-coded skill list here.
3. **Commands**: describe the command, whether it is read-only or write-capable, and its main effect. Use the catalog below.
4. **Configuration and safety**: mention ignored local config, environment credentials, write gates, and secret-handling rules.
5. **Unity menus**: list the skill install, removal, scaffolding, and README entries.

## Command Catalog

Run installed read-only commands from the consuming project root:

```bash
python3 .agents/skills/jira-help/scripts/ai_jira_cli.py list --state todo --format json
python3 .agents/skills/jira-help/scripts/ai_jira_cli.py list --state progress --format json
python3 .agents/skills/jira-help/scripts/ai_jira_cli.py list --state all --format json
python3 .agents/skills/jira-help/scripts/ai_jira_cli.py detail MCC-1234 --format json
```

- `list --state todo`: read-only; list assigned unresolved new-work candidates.
- `list --state progress`: read-only; list assigned unresolved work already in development.
- `list --state all`: read-only; combine todo and progress for raw inspection, not `jira-todo` candidate ranking.
- `detail <ISSUE-KEY>`: read-only; return one issue's description and implementation context.

When the consuming project provides `Tools/AI/jira/`, explain these write-capable commands without running them by default:

```bash
python3 Tools/AI/jira/create_issue.py --summary "제목" --description "설명"
python3 Tools/AI/jira/update_description.py MCC-1234 --mode append-requirements --text "Keep the current behavior."
python3 Tools/AI/jira/update_description.py MCC-1234 --mode prepend-qa --text "QA 확인 내용"
python3 Tools/AI/jira/update_description.py MCC-1234 --mode replace-plan --file approved-description.md --expected-updated "2026-07-15T02:22:47.217+0000"
python3 Tools/AI/jira/transition_issue.py MCC-1234 --to todo
python3 Tools/AI/jira/transition_issue.py MCC-1234 --to progress
python3 Tools/AI/jira/transition_issue.py MCC-1234 --to done --pr-url "https://github.com/org/repo/pull/123"
python3 Tools/AI/jira/transition_issue.py MCC-1234 --list
python3 Tools/AI/jira/finalize_session.py MCC-1234 --outcome done --pr-url "https://github.com/org/repo/pull/123"
python3 Tools/AI/jira/finalize_session.py MCC-1234 --outcome incomplete --completed-work "분석 완료" --remaining-work "구현 및 검증" --branch-pr "MCC-1234-work / PR 없음" --validation "미실행" --blocker-approval "승인 대기" --resume-condition "승인 후 구현 재개"
```

- `create_issue.py`: write; validate the managed description contract, require the current active sprint, then report success only after the assigned issue's active-sprint membership and todo status are verified.
- `update_description.py`: write; append confirmed English requirements, prepend Korean QA notes, or replace only an explicitly approved managed plan under optimistic-concurrency and planning-lock checks.
- `transition_issue.py --to todo|progress|done`: write; move an issue through the configured AI lifecycle only when the matching transition gate is enabled. Done also requires a PR URL and a verified QA completion record.
- `transition_issue.py --list`: read-only; list transitions currently available for the issue.
- `finalize_session.py`: write; make a normal session terminal. `done` reuses the PR and QA completion guards, while `incomplete` verifies one Korean handoff record and returns the issue to configured todo using `allow_description_append` plus `allow_transition`.
- Recommend each command's `--help` for exact flags in the installed version.

## Configuration And Safety

- Resolve ignored project configuration from `Tools/AI/jira/config.local.json`, an explicit `--config`, or `AI_JIRA_CONFIG` as documented by the package.
- Keep `JIRA_EMAIL` and `JIRA_API_TOKEN` in environment variables or ignored local config. Never display or request a token in shared chat.
- State that write commands may be blocked by `dry_run` or individual `allow_*` gates. Access to a command is not authorization to run it.
- Explain that Jira titles and QA content are Korean while other newly managed description content is English; existing issues are not migrated in bulk.
- Explain that `jira-plan`, `jira-auto-start`, and `jira-run` show complete planning approval views in Korean while retaining the exact mixed-language storage draft prepared before the preview. Approval writes that canonical draft unchanged, never a back-translation of the Korean view. A revision or lost canonical state requires a regenerated complete Korean view and new approval.
- Explain that plan discussion and approval waiting stay in todo. Progress is transient active ownership: normal run/auto-start termination must finalize to done or return incomplete work to todo with a Korean handoff. Read-only triage reports progress as active, reserved, or stranded-review and never steals a lease.
- Explain that `jira-run` and `jira-auto-start` announce `🎫 Jira: <ISSUE-KEY>` before writes and verify the planned and checked-out branch names contain the selected key. When asked about terminal titles, show `[tui]` with `terminal_title = ["spinner", "git-branch", "project"]`, distinguish user-global `~/.codex/config.toml` from trusted project `.codex/config.toml`, and note that Codex derives the project and full branch from the working directory. Do not claim key-only extraction, pre-branch conditional display, or raw OSC output.
- Read the consuming repository's `AGENTS.md`, `CLAUDE.md`, and linked Jira guidance before advising a state-changing workflow.

## Unity Menus

- `Tools > Package > Custom Package Manager > Install or Refresh Agent Skills`
- `Tools > Package > Custom Package Manager > Remove Managed Agent Skills`
- `Tools > Package > Custom Package Manager > Add Agent Skill`
- `Tools > Package > AI Jira > README`

Explain that refresh updates only unchanged package-managed skills and preserves user-modified or unmanaged skill directories.

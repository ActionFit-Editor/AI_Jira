---
name: jira-help
description: Explain the AI Jira package, its installed related skills, package-owned read and write command locators, consuming-project configuration, safety gates, and Unity menus. Use when the user asks for Jira help, available skills or commands, package usage, setup, or capability differences.
---

# Jira Help

Provide a concise help response in the user's language. Do not query Jira or change Jira, Git, or project state unless the user separately requests an operation.

Read `PACKAGE_SKILLS.md` in this installed skill directory before answering. It is generated from the package identity, schema v2 manifest, and agent-specific `SKILL.md` frontmatter. Treat its package summary, complete related-skill list, exact `$name` invocations, descriptions, and access boundaries as authoritative. If it is missing, tell the user to run `Install or Refresh Agent Skills` instead of reconstructing a stale list.

Explain:

1. The generated package ID, display name, and summary; add that the package installs project-local Jira skills plus read-only and write locators while consuming-project configuration owns write authorization.
2. Every generated related-skill row, including its description/when-to-use guidance, read-only or write-capable boundary, and exact invocation. Do not maintain a second hard-coded skill list here.
3. Each command's read-only or write-capable nature, main effect, configuration, and safety gate.
4. Unity skill installation, removal, scaffolding, and README menus.

Read-only installed commands:

```bash
python3 .claude/skills/jira-help/scripts/ai_jira_cli.py list --state todo --format json
python3 .claude/skills/jira-help/scripts/ai_jira_cli.py list --state progress --format json
python3 .claude/skills/jira-help/scripts/ai_jira_cli.py list --state all --format json
python3 .claude/skills/jira-help/scripts/ai_jira_cli.py detail MCC-1234 --format json
```

- `todo` lists new-work candidates, `progress` lists already-active work, `all` combines both for raw inspection, and `detail` returns one issue's implementation context.
- Never use `all` as the `jira-todo` candidate source.

Package-owned write commands:

```bash
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py create --summary "제목" --description "설명"
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py update-description MCC-1234 --mode append-requirements --text "Keep the current behavior."
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py update-description MCC-1234 --mode prepend-qa --text "QA 확인 내용"
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py update-description MCC-1234 --mode replace-plan --file approved-description.md --expected-updated "2026-07-15T02:22:47.217+0000"
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py transition MCC-1234 --to todo
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py transition MCC-1234 --to progress
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py transition MCC-1234 --to done --pr-url "https://github.com/org/repo/pull/123"
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py transition MCC-1234 --list
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py finalize MCC-1234 --outcome done --pr-url "https://github.com/org/repo/pull/123"
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py finalize MCC-1234 --outcome incomplete --completed-work "분석 완료" --remaining-work "구현 및 검증" --branch-pr "MCC-1234-work / PR 없음" --validation "미실행" --blocker-approval "승인 대기" --resume-condition "승인 후 구현 재개"
```

Explain that the `create` command validates the managed contract and resolves exactly one non-subtask Jira type to `issuetype.id` before any create write.

Explain that create validates the managed contract, requires the current active sprint, and reports success only after the authenticated assignee, active-sprint membership, and todo status are verified. Create, description update, transition, and finalization commands write only when project configuration and matching `allow_*` gates permit them. Managed plan replacement uses a transient progress lock after approval. `finalize done` requires a PR URL and verified Korean QA completion record; `incomplete` requires every Korean handoff field, verifies it, and returns to todo using `allow_description_append` plus `allow_transition`. `transition --list` is read-only. Jira titles and QA content are Korean, other newly managed description content is English, and existing issues are not bulk-migrated. `jira-plan`, `jira-auto-start`, and `jira-run` show complete approval views in Korean while retaining the exact pre-preview mixed-language storage draft; approval writes that draft unchanged, never a back-translation. A revision or lost canonical state requires regeneration and new approval. Approval waiting stays todo, and normal run/auto-start termination reaches done or todo rather than lingering in progress. Read-only triage reports progress as active, reserved, or stranded-review without stealing leases. Explain that `jira-run` and `jira-auto-start` announce `🎫 Jira: <ISSUE-KEY>` before writes and verify the planned and checked-out branch names contain that key. When asked about Codex terminal titles, show `[tui]` with `terminal_title = ["spinner", "git-branch", "project"]` and clearly label it as Codex-specific user or trusted-project configuration, not Claude behavior; do not claim key-only extraction, pre-branch conditional display, or raw OSC output. Recommend `--help` for exact installed flags.

Keep credentials in environment variables or ignored local config, never display or request Jira tokens in chat, and read repository guidance before advising writes. List these menus:

- `Tools > Package > Custom Package Manager > Install or Refresh Agent Skills`
- `Tools > Package > Custom Package Manager > Remove Managed Agent Skills`
- `Tools > Package > Custom Package Manager > Add Agent Skill`
- `Tools > Package > AI Jira > README`

Explain that refresh preserves user-modified and unmanaged skills.

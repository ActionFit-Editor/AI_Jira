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
python3 .claude/skills/jira-help/scripts/ai_jira_cli.py overlap --format json
python3 .claude/skills/jira-help/scripts/ai_jira_cli.py detail MCC-1234 --format json
```

- `todo` lists new-work candidates, `progress` lists already-active work, `all` combines both for raw inspection, and `detail` returns one issue's implementation context.
- `overlap` is read-only and lists every assignee's issues in exactly configured todo, progress, and done across every enhanced-search page for explicit project-wide duplicate-work analysis. It never feeds task recommendation or automatic pickup.
- Never use `all` as the `jira-todo` candidate source.

Package-owned write commands:

```bash
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py create --summary "제목" --description "설명"
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py create --summary "나중에 계획할 작업" --title-only-needs-plan
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py update-description MCC-1234 --mode append-requirements --text "Keep the current behavior."
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py update-description MCC-1234 --mode prepend-qa --text "QA 확인 내용"
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py transition MCC-1234 --to progress --purpose planning --json
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py update-description MCC-1234 --mode replace-plan --file approved-description.md --expected-updated "2026-07-15T02:22:47.217+0000" --coverage-file plan-coverage.json
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py transition MCC-1234 --to todo --purpose planning
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py start MCC-1234 --branch MCC-1234-work --json
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py transition MCC-1234 --to done --pr-url "https://github.com/org/repo/pull/123" --review-file completion-review.json
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py transition MCC-1234 --list
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py finalize MCC-1234 --outcome done --pr-url "https://github.com/org/repo/pull/123" --review-file completion-review.json
python3 .claude/skills/jira-help/scripts/ai_jira_write_cli.py finalize MCC-1234 --outcome incomplete --completed-work "분석 완료" --remaining-work "구현 및 검증" --branch-pr "MCC-1234-work / PR 없음" --validation "미실행" --blocker-approval "승인 대기" --resume-condition "승인 후 구현 재개"
```

Explain that normal `create` validates the managed contract. Explicit `--title-only-needs-plan` rejects description arguments and omits the Jira description so the todo is classified as `needs-plan`; it requires an explicit exact-title request or approval and never bypasses normal planning decisions or approval. Both modes resolve exactly one non-subtask Jira type to `issuetype.id` before any create write.

Explain that create validates the managed contract, requires the current active sprint, and verifies assignee, sprint, and todo. Read `references/completion-baseline-gate.md`: planning transitions require `--purpose planning`, replacement requires exact source coverage and separate approval for scope reduction, and every implementation uses `start` to seal a versioned Jira property. Done requires an unchanged active baseline, matching PR, exact completion-review JSON, and all five Korean QA fields; incomplete closes the baseline and returns todo. Legacy progress must finalize incomplete before restart, and a partial PR never narrows the parent issue. `transition --list` is read-only. Also explain the shared decision protocol, retained mixed-language canonical draft, Korean approval view, terminal finalization, non-stealing triage, visible Jira announcement, branch-key verification, credentials, and Codex-only terminal-title boundary. Recommend `--help` for exact installed flags.

Name `allow_description_append` and `allow_transition` as incomplete-finalization gates. Explain that `jira-run` and `jira-auto-start` announce `🎫 Jira: <ISSUE-KEY>` before writes. For Codex terminal-title help, show `terminal_title = ["spinner", "git-branch", "project"]`, and explicitly state that key-only extraction and raw OSC output are unsupported.

Explain that all planning entry points show complete approval views in Korean while retaining the exact pre-preview mixed-language storage draft; the write payload is never a back-translation of that view. A revision or lost canonical state requires regeneration and new approval.

Explain the one-to-three-question rounds, how every alternative states its difference, advantages, and disadvantages, and that broad recommendation delegation expires with the current planning invocation.

Keep credentials in environment variables or ignored local config, never display or request Jira tokens in chat, and read repository guidance before advising writes. List these menus:

- `Tools > Package > Custom Package Manager > Install or Refresh Agent Skills`
- `Tools > Package > Custom Package Manager > Remove Managed Agent Skills`
- `Tools > Package > Custom Package Manager > Add Agent Skill`
- `Tools > Package > AI Jira > README`

Explain that refresh preserves user-modified and unmanaged skills.

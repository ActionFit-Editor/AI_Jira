---
name: jira-help
description: Explain the AI Jira package, its installed related skills, read-only query commands, project-local write commands, configuration, safety gates, and Unity menus. Use when the user asks for Jira help, available skills or commands, package usage, setup, or capability differences.
---

# Jira Help

Provide a concise help response in the user's language. Do not query Jira or change Jira, Git, or project state unless the user separately requests an operation.

Read `PACKAGE_SKILLS.md` in this installed skill directory before answering. It is generated from the package identity, schema v2 manifest, and agent-specific `SKILL.md` frontmatter. Treat its package summary, complete related-skill list, exact `$name` invocations, descriptions, and access boundaries as authoritative. If it is missing, tell the user to run `Install or Refresh Agent Skills` instead of reconstructing a stale list.

Explain:

1. The generated package ID, display name, and summary; add that the package installs project-local Jira skills and a read-only work-item CLI while consuming-project tools own gated Jira writes.
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

Optional consuming-project commands under `Tools/AI/jira/`:

```bash
python3 Tools/AI/jira/create_issue.py --summary "제목" --description "설명"
python3 Tools/AI/jira/update_description.py MCC-1234 --mode append-requirements --text "추가 요구사항"
python3 Tools/AI/jira/update_description.py MCC-1234 --mode prepend-qa --text "QA 확인 내용"
python3 Tools/AI/jira/transition_issue.py MCC-1234 --to progress
python3 Tools/AI/jira/transition_issue.py MCC-1234 --to done
python3 Tools/AI/jira/transition_issue.py MCC-1234 --list
```

Explain that create, description update, and transition commands write only when project configuration and matching `allow_*` gates permit them. `--list` is read-only. Recommend `--help` for exact installed flags.

Keep credentials in environment variables or ignored local config, never display or request Jira tokens in chat, and read repository guidance before advising writes. List these menus:

- `Tools > Package > Custom Package Manager > Install or Refresh Agent Skills`
- `Tools > Package > Custom Package Manager > Remove Managed Agent Skills`
- `Tools > Package > Custom Package Manager > Add Agent Skill`
- `Tools > Package > AI Jira > README`

Explain that refresh preserves user-modified and unmanaged skills.

---
name: jira-help
description: Explain the AI Jira package, installed Jira skills, read-only query commands, project-local write commands, configuration, safety gates, and Unity menus. Use when the user asks for Jira help, available Jira commands, package usage, setup, or the difference between jira-help, jira-todo, and jira-run.
---

# Jira Help

Provide a concise help response in the user's language. Default to Korean for a Korean request. Do not query Jira or change Jira, Git, or project state unless the user separately requests an operation.

## Response Contents

Explain these sections in this order:

1. **Package overview**: `com.actionfit.ai-jira` installs project-local Jira skills and provides a read-only work-item CLI. Jira write operations remain behind consuming-project tools and local safety gates.
2. **Installed skills**:
   - `jira-help`: explain package capabilities, commands, configuration, and safety without executing them.
   - `jira-todo`: read-only triage; recommend new work only from `todo` and use `progress` only for overlap or exclusion context.
   - `jira-run`: manual-only implementation of a user-selected issue through the repository's Jira, worktree, validation, PR, and completion workflow.
3. **Commands**: describe the command, whether it is read-only or write-capable, and its main effect. Use the catalog below.
4. **Configuration and safety**: mention ignored local config, environment credentials, write gates, and secret-handling rules.
5. **Unity menus**: list the skill install, removal, and README entries.

Show the skill invocation examples:

```text
$jira-help
$jira-todo
$jira-run MCC-1234
```

Explain that `jira-run` requires an explicitly selected issue.

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
python3 Tools/AI/jira/update_description.py MCC-1234 --mode append-requirements --text "추가 요구사항"
python3 Tools/AI/jira/update_description.py MCC-1234 --mode prepend-qa --text "QA 확인 내용"
python3 Tools/AI/jira/transition_issue.py MCC-1234 --to progress
python3 Tools/AI/jira/transition_issue.py MCC-1234 --to done
python3 Tools/AI/jira/transition_issue.py MCC-1234 --list
```

- `create_issue.py`: write; create an assigned issue using project defaults and, when configured, place it in the active sprint and todo status.
- `update_description.py`: write; append confirmed requirements or prepend QA notes without overwriting the full description.
- `transition_issue.py --to progress|done`: write; move an issue through the configured AI lifecycle only when the matching transition gate is enabled.
- `transition_issue.py --list`: read-only; list transitions currently available for the issue.
- Recommend each command's `--help` for exact flags in the installed version.

## Configuration And Safety

- Resolve ignored project configuration from `Tools/AI/jira/config.local.json`, an explicit `--config`, or `AI_JIRA_CONFIG` as documented by the package.
- Keep `JIRA_EMAIL` and `JIRA_API_TOKEN` in environment variables or ignored local config. Never display or request a token in shared chat.
- State that write commands may be blocked by `dry_run` or individual `allow_*` gates. Access to a command is not authorization to run it.
- Read the consuming repository's `AGENTS.md`, `CLAUDE.md`, and linked Jira guidance before advising a state-changing workflow.

## Unity Menus

- `Tools > Package > Custom Package Manager > Install or Refresh Agent Skills`
- `Tools > Package > Custom Package Manager > Remove Managed Agent Skills`
- `Tools > Package > AI Jira > README`

Explain that refresh updates only unchanged package-managed skills and preserves user-modified or unmanaged skill directories.

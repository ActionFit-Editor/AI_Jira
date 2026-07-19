---
name: jira-init
description: "Diagnose Jira access, create and protect missing project-local configuration, open the input location, and guide Atlassian API-token setup without exposing secrets. Use when the user asks to initialize Jira, verify access, fix Jira connection failures, create local Jira config, or learn how to obtain and store credentials safely."
disable-model-invocation: true
---

# Jira Init

Initialize Jira access from the consuming Unity project root. This is a write-capable local setup workflow, but every Jira request made by this skill is read-only.

1. Read repository instructions and linked Jira guidance. Never print or request a Jira API token in chat.
2. Diagnose first:

```bash
python3 .claude/skills/jira-init/scripts/ai_jira_init.py status --format json
```

3. If `CONNECTED`, report the configured project and statuses and stop. An empty work result is still connected.
4. For missing or invalid setup, explicit `$jira-init` invocation authorizes only the bounded local setup below: clone-local Git exclusion, no-overwrite template creation, restrictive permissions where supported, and revealing the input location.

```bash
python3 .claude/skills/jira-init/scripts/ai_jira_init.py setup --open-folder --format json
```

5. Explain only reported missing values. The template requires `jira_base_url`, `project_key`, and exact `statuses.todo`, `statuses.progress`, and `statuses.done`. Credentials may use ignored `auth.email`/`auth.api_token` fields or `JIRA_EMAIL`/`JIRA_API_TOKEN` environment variables.
6. For a missing token, tell the user to sign in to the Atlassian account used by `currentUser()`, open `https://id.atlassian.com/manage-profile/security/api-tokens`, create and label a token, copy it once to a password manager, and enter it only in ignored local config or environment.
7. Tell the user which file was opened, wait for them to save it, rerun `status --format json`, and report the verified result.

Interpret `CONFIG_MISSING`, `CONFIG_INCOMPLETE`, and `CONFIG_INVALID` as local setup problems; `CREDENTIALS_MISSING` as missing local credentials; `CREDENTIALS_MISPLACED` as actual credential values entered in `auth.email_env` or `auth.api_token_env` instead of `auth.email` and `auth.api_token`; `AUTHENTICATION_FAILED` as an invalid or expired pair; `PERMISSION_DENIED` as missing Jira/project access; `JIRA_SITE_NOT_FOUND` as an incorrect site; `CONFIG_OR_JQL_INVALID` as a project/status mismatch; `NETWORK_ERROR` as DNS/proxy/VPN/firewall/TLS failure; and `RATE_LIMITED` as a retry-later condition. Never echo misplaced values. Stop on `CONFIG_TRACKED`; local exclude cannot untrack a credential file.

Do not create, edit, transition, or delete Jira issues. Do not overwrite config, untrack files, edit tracked `.gitignore`, expose secret values, or open the token page automatically. A nonzero diagnostic exit for missing setup is expected and should be handled from its structured JSON.

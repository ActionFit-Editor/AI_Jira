---
name: jira-init
description: "Diagnose Jira access, create and protect missing project-local configuration, open the input location, and guide Atlassian API-token setup without exposing secrets. Use when the user asks to initialize Jira, verify access, fix Jira connection failures, create local Jira config, or learn how to obtain and store credentials safely."
---

# Jira Init

Initialize Jira access from the consuming Unity project root. This is a write-capable local setup workflow, but every Jira request made by this skill is read-only.

## Workflow

1. Read the consuming repository's `AGENTS.md`, `CLAUDE.md`, primary AI router, and linked Jira guidance when present. Never print or request a Jira API token in chat.
2. Run the package-owned diagnostic first:

```bash
python3 .agents/skills/jira-init/scripts/ai_jira_init.py status --format json
```

3. If the result code is `CONNECTED`, report the configured project and statuses, then stop. An empty assigned-work result is still a successful connection.
4. If configuration or credentials are missing or invalid, run setup without asking another confirmation because explicit `$jira-init` invocation authorizes only these bounded local actions: add the config path to the clone-local Git exclude file, create the missing template without overwriting an existing file, restrict its permissions where supported, and reveal it in the platform file manager.

```bash
python3 .agents/skills/jira-init/scripts/ai_jira_init.py setup --open-folder --format json
```

5. Explain only the fields identified by `missingFields`. The standard template requires `jira_base_url`, `project_key`, exact `statuses.todo`, `statuses.progress`, and `statuses.done` values. It also accepts either `auth.email` plus `auth.api_token` in the ignored file or the `JIRA_EMAIL` plus `JIRA_API_TOKEN` environment variables.
6. For a missing token, give these steps:
   - Sign in to the Atlassian account that should own `currentUser()` queries.
   - Open `https://id.atlassian.com/manage-profile/security/api-tokens`.
   - Create and label an API token, copy it once, and store it in a password manager.
   - Enter it only in the ignored local config or environment. Never place it in tracked files, command examples containing a real value, logs, or chat.
7. Tell the user exactly which local file was opened and wait for them to save it. Then rerun `status --format json` and report the verified outcome.

## Failure Handling

- `CONFIG_MISSING`, `CONFIG_INCOMPLETE`, `CONFIG_INVALID`: run or repeat setup and identify the missing or malformed local values.
- `CREDENTIALS_MISSING`: explain the token steps and both supported local storage options.
- `CREDENTIALS_MISPLACED`: the user entered credential values in `auth.email_env` or `auth.api_token_env`; tell them to move the values to `auth.email` and `auth.api_token`, restore the `_env` fields to environment-variable names, and never echo either value.
- `AUTHENTICATION_FAILED`: the email/token pair is invalid or expired; create or replace the token locally.
- `PERMISSION_DENIED`: authentication worked but the account lacks Jira/project access; ask a Jira administrator for access without changing permissions.
- `JIRA_SITE_NOT_FOUND`: verify the exact HTTPS Atlassian site URL.
- `CONFIG_OR_JQL_INVALID`: verify the project key and exact Jira workflow status display names.
- `NETWORK_ERROR`: check DNS, proxy, VPN, firewall, and TLS access before changing credentials.
- `RATE_LIMITED`: wait for the Jira rate limit to recover, then retry the same read-only check.
- `CONFIG_TRACKED`: stop. Do not store credentials until the user has intentionally removed the config from Git tracking; local exclude alone cannot untrack it.

## Safety Boundaries

- Do not create, update, transition, or delete Jira issues.
- Do not overwrite an existing config or automatically untrack a file.
- Do not read token values back to the conversation. Report only whether email/token are configured and whether they came from environment or ignored local config.
- Do not edit the tracked repository `.gitignore`; setup uses the clone-local Git exclude file.
- Do not open the token page automatically. Provide its exact HTTPS URL so the user controls Atlassian sign-in and token creation.
- A nonzero `status` exit caused by missing setup is an expected diagnostic result, not an infrastructure failure.

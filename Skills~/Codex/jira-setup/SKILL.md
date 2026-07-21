---
name: jira-setup
description: Prepare or validate ignored, secret-free Jira project configuration after explicit approval and verify read-only Jira connectivity without enabling writes or exposing credentials. Use when AI Jira is being initialized or its local configuration and environment authentication are incomplete.
---

# Set Up Jira Access

This is a write-capable local-configuration workflow. It may create one ignored project file, but it must never collect, print, copy, or persist a Jira API token.

1. Read `PACKAGE_SKILLS.md`, the package `README.md` and `AI_GUIDE.md`, and the consuming repository's Jira, branch, worktree, ignore, and credential rules. Resolve the exact project root and configuration precedence: explicit `--config`, `AI_JIRA_CONFIG`, then `Tools/AI/jira/config.local.json`.
2. Inspect only safe metadata:
   - whether the selected config file exists and is a regular file;
   - whether Git ignores the exact local path, using `git check-ignore -v -- <path>`;
   - whether the configured email/token environment-variable names are present, reporting booleans only;
   - safe config validation output from `jira_client.py --require-statuses`, never raw file contents or auth values.
3. If an existing config validates and the environment variables are present, run the read-only verification in step 7 and stop without rewriting it. Never replace, merge, normalize, or migrate an existing local config automatically.
4. For a missing config, gather the non-secret project values: Jira base URL, project key, exact todo/progress/done status names, issue type, active board or intentionally fixed sprint choice, target integration branch, and worktree root. Resolve values from explicit project documentation or the user; do not guess ambiguous Jira workflow names or IDs.
5. Prepare and show the complete secret-free JSON plan. It must reference `JIRA_EMAIL` and `JIRA_API_TOKEN` by environment-variable name only, start with `automation.dry_run: true`, keep every `allow_*` write gate false, and preserve project-specific branch/worktree settings. List the exact local path, ignored status, reversibility, and the fact that deleting or replacing an existing config would require separate approval.
6. After explicit approval of that exact plan, create only the missing ignored config atomically. Stop if the path is tracked, not ignored, outside the project, a link, or already appeared since planning. A missing ignore rule requires a separately reviewed narrow ignore change; never add a broad credential or directory ignore rule as an implementation detail. Ask the user to set credentials outside chat through their local shell or approved secret manager, and check only whether the variables are non-empty.
7. Validate without Jira writes:

```bash
python3 Packages/com.actionfit.ai-jira/Tools~/jira_client.py \
  --config "<ignored-config>" --require-statuses
python3 .agents/skills/jira-setup/scripts/ai_jira_cli.py \
  list --state todo --format json
```

Use the equivalent `.claude` locator for Claude. Keep `dry_run` and every write gate disabled. Report the config path, safe status/gate summary, authenticated read success or categorized failure, and any missing user action without reproducing issue content beyond what the user requested.

Never request a token in chat, print environment values, write credentials into JSON, modify shell profiles or home configuration, enable Jira writes, create or transition issues, change a sprint, overwrite an existing config, or delete local configuration. Those are separate operations with their own authorization and safety gates.

# AI Guide - AI Jira

This file is shipped inside the UPM package so an AI assistant in a consuming Unity project can understand Jira automation rules without access to the source project's `Docs/AI` folder.

## Package Identity

- Package ID: `com.actionfit.ai-jira`
- Display name: AI Jira
- Repository: `https://github.com/ActionFit-Editor/AI_Jira.git`
- Current package version at generation time: `1.0.26`
- Unity version: `6000.2`

## Purpose

AI Jira provides project-local Codex and Claude help, triage, planning, automatic bounded pickup, and explicit-run skills; a read-only work-item API/CLI; package-owned write clients; and Jira automation guidance for AI agents: safe issue creation, task discovery, terminal session finalization, mixed-language managed descriptions, transient planning locks, bounded description updates, and local secret configuration.

The package owns status-filtered work-item discovery and the common write implementation under `Tools~/`. Installed write-capable skills call `Skills~/Shared/scripts/ai_jira_write_cli.py`, which locates an embedded package before `Library/PackageCache`. Consuming projects may keep compatibility entry points at project-local paths such as `Tools/AI/jira/*.py`; local configuration and credentials remain outside the package.

## Project Router Registration

This package should be listed in `Packages/com.actionfit.custompackagemanager/PACKAGE_AI_GUIDE_ROUTER.md`.

Requested router entry:

- `Packages/com.actionfit.ai-jira/AI_GUIDE.md` - AI Jira defines ActionFit Jira automation rules. Read when creating Jira issues, discovering Jira tasks, changing Jira lifecycle/status behavior, editing Jira REST scripts, or handling Jira local config.

If the router file is not already included in the AI assistant's default reading sequence, the router file is responsible for asking the user to link it from the project's primary AI markdown entry point. Prefer an existing `PROJECT.md` wherever the project keeps it, otherwise use `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or another primary AI markdown entry point.

Read this file when:

- creating or updating Jira issues through AI automation
- changing files under `Packages/com.actionfit.ai-jira/`
- changing project-local Jira automation scripts or compatibility wrappers
- editing Jira config examples, local config rules, status mappings, or write-safety flags
- preparing a release for `com.actionfit.ai-jira`

## Rules

- Jira credentials, board IDs, real base URLs, status names, and user-specific config must stay in ignored local config files or environment variables.
- Jira task discovery must use the developer's own Atlassian account email and API token. If credentials are missing, tell the user to either set their existing token as `JIRA_API_TOKEN` or create one from `https://id.atlassian.com/manage-profile/security/api-tokens`, then set `JIRA_EMAIL` and `JIRA_API_TOKEN` locally.
- Use `Tools~/list_work_items.py` for direct Jira work-list retrieval. `--state todo` reads the configured todo status, `--state progress` reads approved plan writes or active implementation and recovery evidence, and `--state all` combines todo and progress while excluding completed work.
- `jira-todo` must query `todo` and `progress` separately. Only `todo` results may be recommended as new work. Classify progress evidence from Jira, branch, PR, worktree, lease, and Unity-process state with deterministic precedence: `active` first, otherwise `reserved`, otherwise `stranded-review`. A matching lease is reserved regardless of acquisition PID liveness only when active evidence is absent. Never expire, release, or steal it automatically.
- `jira-auto-start` must query `todo` and `progress` separately, evaluate every todo issue in query order, and report each issue as `startable`, `needs-plan`, `blocked`, or `approval-required` with evidence. It executes the first startable issue; only when none is startable may it acquire a planning lock for the first needs-plan issue. It may recognize prerequisites only from inward blocking/dependency links or issue keys explicitly listed in a prerequisite section; arbitrary references and outward `blocks` links are not prerequisites. Every declared prerequisite must be read and have either a non-empty resolution or the configured `done` status. Missing, unreadable, todo, progress, unknown, or ambiguous prerequisites make the candidate blocked.
- `jira-run` and `jira-auto-start` must emit the exact standalone user-visible line `🎫 Jira: <ISSUE-KEY>` immediately after selecting the issue and before any Jira write, worktree preparation, or repository mutation. Resolve the canonical implementation branch and require its name to contain the exact selected issue key before progress transition or worktree acquisition, then verify the actual checked-out branch again before repository edits. Stop on either mismatch instead of working on another issue's branch.
- Planning-only and read-only Jira flows must keep the relevant issue key visible in their response, but must not create a branch or worktree solely to populate a terminal title.
- Codex terminal-title visibility is an optional user or trusted-project configuration layered on the existing Jira branch contract. Under `[tui]`, set `terminal_title = ["spinner", "git-branch", "project"]`; it displays the full Git branch, so `<ISSUE-KEY>-<slug>` naturally exposes the key. AI Jira must not mutate user-global Codex configuration during normal task execution, emit raw OSC title sequences, promise key-only extraction, or claim a Jira key can appear before an implementation branch exists. Claude follows the announcement and branch-verification semantics without claiming Codex TUI ownership.
- The remaining automatic-pickup gate requires `descriptionContract.state=ready`, a bounded issue, and no unresolved external input, separate sensitive/destructive approval, publishing, deployment, production operation, or overlap with active work. Explicit invocation counts as requirement confirmation only for one startable issue. A needs-plan issue still requires explicit approval of its complete refined description and whether to stop after planning or continue implementation.
- An open PR, dirty worktree, Unity process, or equivalent current-work evidence makes a progress issue active. Only when active evidence is absent does a matching lease make it reserved. With neither active nor reserved evidence, only merged/closed PRs or no active work makes it stranded-review. None of these classifications make progress eligible for new-work recommendation.
- Keep `--state all` available for general read-only API callers, but do not use it as the `jira-todo` candidate source.
- `jira-help` must read its generated `PACKAGE_SKILLS.md` first and use it as the authoritative package identity and complete related-skill inventory. It then explains each generated `$name` invocation, frontmatter description/when-to-use guidance, read-only/write-capable boundary, package-owned list/detail/write locators, compatibility commands, configuration, write gates, and Custom Package Manager menus without executing operations by default.
- Use `Tools~/get_work_item.py <ISSUE-KEY>` for read-only issue details needed to judge implementation scope.
- Work-list queries must remain read-only and include the configured project when present, `assignee = currentUser()`, `resolution = Unresolved`, and descending update order.
- Support both text and structured JSON output. JSON must use UTF-8 with unescaped Korean text and include issue key, title, status, updated time, and browser URL. Issue-detail JSON also exposes `configuredStatuses`, normalized `issueLinks`, and a deterministic `descriptionContract` with managed-section completeness, Auto Start fields, prerequisite keys, unresolved-decision evidence, and `ready`/`needs-plan`/`blocked` state.
- Resolve the ignored config from an explicit `--config`, `AI_JIRA_CONFIG`, or the consuming project's `Tools/AI/jira/config.local.json`, in that order. Read config as UTF-8 with optional BOM and never place credentials inside the package.
- Do not ask the user to paste Jira API tokens into shared chat. If setup help is needed, guide them through environment variables or ignored local config only.
- Installing or refreshing this package must only make write code available. It must not enable Jira writes, modify ignored config, grant Jira permissions, or bypass explicit user approval.
- Default write behavior must remain safe: dry-run enabled unless the user explicitly enables the specific write action. Keep `allow_issue_create`, `allow_sprint_add`, `allow_description_append`, `allow_description_prepend_qa`, `allow_description_plan_refinement`, and `allow_transition` independently disabled by default. Managed plan replacement uses `allow_description_plan_refinement`.
- New issue creation must assign the issue to the authenticated Jira API user by default. Package-owned `Tools~/create_issue.py` resolves `/rest/api/3/myself` and writes the returned account id to `assignee` when `issue_create.assign_to_current_user` is true or omitted.
- Package-owned issue creation must reject a description whose managed contract is structurally incomplete or still contains unresolved decisions before sending a Jira write.
- Resolve `--issue-type` through paginated `/rest/api/3/issue/createmeta/<PROJECT>/issuetypes` metadata. Accept exactly one top-level issue type selected by exact ID or case-insensitive exact name, reject subtasks, ambiguous names, unknown selectors, and malformed metadata before creation, and send only the verified `issuetype.id` in the create payload.
- New issue creation must leave the issue in the configured `todo` status by default. If Jira creates the issue in another initial status, the create script should transition the newly created issue to `issue_create.create_status`, normally `statuses.todo`, before reporting the issue key. Move the issue to `progress` only when implementation actually starts or after needs-plan approval for the immediate managed-plan write.
- `jira-plan`, `jira-auto-start`, and `jira-run` must prepare the canonical mixed-language Jira storage draft before producing any plan approval output. They show the complete approval view in Korean, preserve technical identifiers, explain that approval writes the corresponding canonical draft, and hide the English storage body unless the user explicitly asks for it. The exact pre-preview canonical draft is the only valid create or `replace-plan` payload; never reconstruct it by translating the Korean view back into English.
- Before preparing that canonical draft, every planning path in `jira-plan`, `jira-auto-start`, and `jira-run` must read `references/planning-decision-collaboration.md`. Resolve direction through explicit user requirements, repository or API-owner guidance, this package guide, then one consistent existing pattern. Ask one to three related questions only when multiple reasonable material approaches remain. For every alternative, explain how it differs plus its concrete advantages and disadvantages before recommending one with a rationale. Record answers and rationale, and re-scan after every answer. Do not produce an approval-ready full plan until no material decision remains and the user confirms decision closure. Recommendation delegation applies to the displayed bundle by default; explicit broader delegation expires with the current planning invocation and never removes separate sensitive, destructive, publish, deploy, or production approval.
- Persist confirmed material choices and rationale under `## Scope` as `### Confirmed Decisions`; render that nested heading as `### 확정된 결정` in the complete Korean approval view. Keep `Decisions Required` non-`none` while a material decision remains. Do not add a new top-level managed section, enum, persistent state store, or CLI solely for decision collaboration.
- A requested revision invalidates prior approval: update the canonical draft first, regenerate the complete Korean approval view, and request approval again. If interruption or context loss makes the canonical draft unavailable or uncertain, regenerate both representations and reapprove before any Jira write. New-issue and existing needs-plan discussion stay in `todo`. After approval, recheck the todo snapshot, acquire a transient progress lock, capture post-transition `updated`, and call only the package-owned `replace-plan` operation through the installed locator. Plan-only returns to todo; plan-and-implementation continues immediately. Update failure attempts todo rollback. Locks never expire or get stolen automatically.
- New issue creation through the normal AI Jira path must resolve the current active sprint before creating the issue and add the created issue to that sprint. Prefer `issue_create.board_id`; use `issue_create.active_sprint_id` only for an intentionally fixed sprint. Create intentional backlog exceptions manually outside the normal AI creation path.
- Compatible Jira clients must treat a missing `issue_create.add_to_active_sprint_after_create` value as `true` and reject an explicit `false` before the Jira create request. `automation.allow_sprint_add` remains the required write-safety gate; when it is disabled, active-sprint issue creation is blocked rather than downgraded to backlog creation.
- Missing or ambiguous active sprint resolution, disabled sprint writes, or sprint assignment failure is a creation blocker. Do not silently fall back to the backlog. If assignment fails after Jira already created the issue, report the created issue key and the exact failure.
- After creation, re-read the issue and verify the authenticated assignee, configured `todo` status, and membership in the resolved active sprint before reporting success. Use enhanced JQL search with `reconcileIssues` for stronger read-after-write consistency when the create response includes the issue id. If Jira already created the issue before a later failure, report the issue key, expected sprint, mismatch, and manual recovery action without deleting the issue.
- A normal `jira-run` or `jira-auto-start` response is forbidden while the selected issue remains in configured progress. Completed work must prepend and verify the Korean QA completion record, then use the package-owned finalizer through the installed locator with the PR URL to reach internal `done`. Incomplete, unclear, approval-blocked, or partial-PR work must upsert one Korean handoff, verify it, and use the finalizer to return to `todo`. Only abrupt process failure or a reported Jira/finalization failure may exceptionally leave progress.
- Handoff headings must not match the issue-specific QA completion pattern. Preserve the QA plan, completion history, managed plan, and unmanaged sections. Reuse existing `allow_description_append` and `allow_transition`; do not add a broad overwrite gate.
- An incomplete open PR may be resumed only for the same issue after Jira is todo and no active lease owns it. Never reuse a merged or closed PR branch; create a follow-up branch and PR. A PR alone never proves completion.
- AI-created Jira titles are Korean. `## QA 확인 필요 사항`, its plan, and completion records are Korean and stay at the top. Every other newly managed description heading and body, including appended requirements, is English. Preserve technical identifiers, translate for the user when requested, and never bulk-migrate existing issues.
- Do not perform unrestricted full-description overwrites. Append requirements, prepend QA, or replace only the approved managed plan when the matching local gate allows it. Managed replacement requires the progress planning lock and matching Jira `updated` value and must preserve prior QA completion records and unmanaged sections.
- Do not add AI-created labels or move issues to a QA status. QA-board movement remains a manual user action after build verification.
- Keep Jira REST calls behind the package/client boundary so projects can replace auth or endpoint details without changing workflow rules.
- Package skill sources live under `Skills~/Codex` and `Skills~/Claude` and use schema v2 `Skills~/manifest.json` with `skillPrefix: jira`, mandatory `helpSkill: jira-help`, and explicit `access`. `Skills~/Shared/references/korean-approval-preview.md` owns the dual-representation approval contract for both agents. Custom Package Manager copies registered sources to project-local `.agents/skills` and `.claude/skills`, overlays shared files from `Skills~/Shared`, and generates the managed `PACKAGE_SKILLS.md` only inside installed `jira-help` targets.
- `jira-help` and `jira-todo` must remain read-only. `jira-plan`, `jira-auto-start`, and `jira-run` are write-capable and must remain explicit/manual-only through Codex `allow_implicit_invocation: false` and Claude `disable-model-invocation: true`.
- AI Jira depends on `com.actionfit.custompackagemanager` `1.1.106` so schema v2 installation and generated inventory have one shared owner. Do not restore an AI Jira automatic bootstrap or a second package-specific menu writer.
- Skill installation must never write to home/global directories, copy credentials, overwrite unknown or modified targets, or delete targets automatically. New managed hashes belong in `UserSettings/ActionFitPackageManager/skill-install-state.json`; the preserved `UserSettings/AIJira/skill-install-state.json` is migration input only.
- Package refresh may update only a target whose current directory hash matches the recorded installed hash. Explicit removal may delete only the same unchanged targets and must preserve modified or linked directories.

## Compatibility Boundary

- Existing projects may continue to call `Tools/AI/jira/*.py` compatibility entry points, including `finalize_session.py` when present.
- The old `AiJiraSkillInstallService` remains source-compatible but has no automatic bootstrap or menu caller. Custom Package Manager owns active discovery, installation, refresh, removal, collision handling, and legacy ownership migration.
- This package owns portable rules and read/write implementations under `Tools~/`.
- Installed `jira-plan`, `jira-run`, and `jira-auto-start` skills use the package-owned write locator. Existing project-local entry points remain compatible and must not have their ignored config moved or overwritten.
- `com.actionfit.ai_guide_jira` was a placeholder guide package. Treat `com.actionfit.ai-jira` as the canonical Jira automation package and move dependencies, router entries, and documentation references here instead of installing both.

## Package Tools Menu

- Unity menu root: `Tools/Package/AI Jira/`.
- `README`: opens this package README.
- Skill install, refresh, and removal commands live under `Tools/Package/Custom Package Manager/` because the common manager owns every package's registered skills.
- Do not add README or Setting SO access back to Custom Package Manager package rows or Project Files.

## Release Notes

- Publishing is manual through Custom Package Manager.
- Before reusing a version, check remote Git tags. Published tags are immutable.
- If this package is modified after a version is tagged, bump to the next unused patch version before publishing.

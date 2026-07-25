# Completion Baseline Gate

Use this contract for every `jira-run` and `jira-auto-start` implementation and every existing-issue plan refinement. The deterministic commands enforce structural identity and exact coverage. They do not replace the agent's semantic comparison of the user's original request, the approved Jira plan, the implementation diff, and validation evidence.

## Planning Lock And Coverage

Before refining an existing issue, keep discussion and approval waiting in todo and retain the exact approved canonical draft. After approval and the unchanged-todo check:

1. Run `ai_jira_write_cli.py transition <ISSUE-KEY> --to progress --purpose planning --json`. The command seals the normalized pre-refinement description, or the Jira summary for a title-only issue, in a versioned Jira issue property before it enters progress. Preserve the returned source requirement IDs.
2. Compare every sealed source requirement with the approved draft. Create a UTF-8 plan-coverage JSON file outside the repository:

```json
{
  "version": 1,
  "scopeChangeApproved": false,
  "approvalSummary": "",
  "requirements": [
    {
      "sourceId": "ORIGINAL-OR-REQ-ID",
      "disposition": "retained",
      "targetIds": ["UNCHANGED-REQ-ID"],
      "rationale": ""
    }
  ]
}
```

Every source ID must occur exactly once. Allowed dispositions are `retained`, `clarified`, `removed`, `deferred`, and `out-of-scope`. `retained` targets only the same stable ID; `clarified` targets one or more approved-plan IDs. A removed, deferred, or moved-out-of-scope source requirement targets nothing and requires a rationale, a separate explicit user replanning approval, `scopeChangeApproved: true`, and a non-empty `approvalSummary`. Approval of a partial PR never authorizes narrowing the parent Jira issue.

3. Run `update-description ... --mode replace-plan --expected-updated <SEALED-VALUE> --coverage-file <COVERAGE-JSON>`. The command rejects missing, duplicate, unknown, or uncovered IDs and compensates the description when the property update fails.
4. For plan only, run `transition <ISSUE-KEY> --to todo --purpose planning`. For approved immediate implementation, keep the planning lock and run the implementation-start command below. Remove temporary draft and coverage files only after verified success or after preserving enough recovery evidence.

## Implementation Start

Never use a generic progress transition to start implementation. After the canonical branch and worktree plan exists, run:

```bash
ai_jira_write_cli.py start <ISSUE-KEY> --branch <ACTUAL-BRANCH> --json
```

The command requires real write gates, a ready description, explicit Auto Start permission, complete prerequisites, an issue-key-bearing branch, and todo or a valid planning lock. It seals the approved Goal, Scope, Out of Scope, Completion Criteria, Additional Requirements, stable requirement IDs, description digest, Jira updated value, branch, session ID, and timestamps before implementation proceeds. Read-after-write verification is mandatory.

A progress issue without a valid planning property is legacy/unsealed. It must not be sealed in place or completed. Finalize it as incomplete, return it to todo, then run `start` from the current approved description. An incomplete finalization closes any active baseline so it cannot be reused.

## Completion Review

After the PR exists and repository validation is complete, compare the full sealed baseline with the diff, tests, documentation, PR, and Jira scope. Create a UTF-8 completion-review JSON file outside the repository:

```json
{
  "version": 1,
  "issueKey": "MCC-1234",
  "sessionId": "UUID-FROM-START",
  "baselineDigest": "sha256:DIGEST-FROM-START",
  "prUrl": "https://github.com/org/repo/pull/123",
  "requirements": [
    {
      "id": "REQ-ID-FROM-START",
      "status": "complete",
      "evidence": ["Concrete file, test, command result, or PR evidence"]
    }
  ]
}
```

Every sealed requirement ID must occur exactly once. Only `complete` is accepted; missing, duplicate, unknown, incomplete, deferred, unverified, or evidence-free entries fail closed. The issue key, session ID, baseline digest, and PR URL must exactly match the active baseline and finalizer arguments. The finalizer persists the validated review and its digest in the Jira property.

When all three extended status mappings are configured, also create a versioned verification-plan JSON outside the repository. It pins the candidate PR, sealed branch, and exact 40-character commit SHA and records every remaining or already completed functional check:

```json
{
  "version": 1,
  "issueKey": "MCC-1234",
  "candidate": {
    "prUrl": "https://github.com/org/repo/pull/123",
    "branch": "MCC-1234-task",
    "commit": "0123456789abcdef0123456789abcdef01234567"
  },
  "checks": [
    {
      "id": "AUTO-EDITOR-001",
      "mode": "automatic",
      "description": "Verify the approved Editor behavior.",
      "evidenceLevel": "editor-simulated",
      "status": "pending"
    },
    {
      "id": "MANUAL-UX-001",
      "mode": "manual",
      "description": "Review the subjective presentation.",
      "evidenceLevel": "manual",
      "status": "pending"
    }
  ]
}
```

The plan may use `automated`, `editor-simulated`, `remote-assisted`, `player-build`, or `device-verified` for automatic checks and `manual` for manual checks. Player/device levels must occur explicitly in the approved Jira `Validation Plan`. Do not include commands, shell, or script fields. Automatic checks take precedence over manual checks.

Prepend exactly one issue-specific Korean QA completion record containing non-empty `변경 요약`, `검증 결과`, `미검증 항목`, `QA 확인 항목`, and `위험 영역`. In legacy mode, and whenever no verification check remains, `미검증 항목` must be `없음`. In extended mode it names the deferred automatic/manual checks. Then run:

```bash
ai_jira_write_cli.py finalize <ISSUE-KEY> --outcome done --pr-url <PR-URL> --review-file <REVIEW-JSON>
```

Add `--verification-plan-file <VERIFICATION-PLAN-JSON>` in extended mode. The finalizer also requires progress, an active baseline, an unchanged current requirement digest, matching PR evidence, transition preflight, and structured QA. It selects automatic-validation when any automatic check is pending, manual-validation when only manual checks are pending, or verified when none remain. Legacy mode keeps the configured `done` behavior. Direct `transition --to done` applies the same review gate. Remove temporary review and verification files only after the property and selected status are verified.

If any requirement is not complete, use `finalize --outcome incomplete` with every handoff field. Never describe partial work, a partial PR, or a narrowed implementation as completion.

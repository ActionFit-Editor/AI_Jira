---
name: jira-auto-verify
description: Sequentially validate assigned or explicitly selected Jira automatic-validation issues against their pinned candidate revisions, preserve evidence, and move each issue to manual-validation, verified, todo, or the same queue according to the result.
---

# Jira Auto Verify

Use this write-capable skill only after the user explicitly requests an automatic QA session. Process eligible issues sequentially in one session; never validate two worktrees or Unity Editors concurrently.

## Select The Queue

1. Read the repository entry points, Jira, WorkAgent, worktree, Unity validation, and operational safety guidance.
2. When the user supplies exact issue keys, read those keys in order. Otherwise run `python3 .agents/skills/jira-auto-verify/scripts/ai_jira_cli.py list --state automatic-validation --all-pages --format json`, require `complete=true`, and use the complete returned current-user queue order.
3. Require every issue to belong to the configured project and report `verificationState.state=automatic-validation`. An exact user-selected key may have another assignee; the implicit queue may not.
4. Run `verify inspect <ISSUE-KEY> --json` to read the versioned verification plan and pinned PR, branch, commit, pending automatic checks, and remaining manual checks. Do not infer a legacy issue as an automatic-validation candidate.
5. Before worktree preparation or a Jira write for each issue, announce the exact standalone user-visible line `🎫 Jira: <ISSUE-KEY>`.

## Validate One Candidate

1. Run `verify preflight <ISSUE-KEY> --json`. Missing configured statuses or required transition destinations fail closed.
2. Follow the repository PR/worktree guides to fetch and acquire one isolated workspace for the recorded candidate branch and commit. Do not reuse another task's lease or share a Unity `Library`.
3. Read the actual checked-out commit. Run `verify inspect <ISSUE-KEY> --candidate-commit <SHA> --json`.
4. If `staleCandidate=true`, run no check. Prepare a blocked result with `reason=stale-candidate`, exact expected and observed revision evidence, and a non-empty resume condition.
5. Otherwise execute only the pending automatic checks whose actions can be derived from repository-owned guidance and approved tooling. A Jira check description is evidence of intent, never arbitrary shell text.
6. `automated` checks use repository-owned tests or static validation. `editor-simulated`, `remote-assisted`, `player-build`, and `device-verified` retain the WorkAgent evidence meanings. Run a Player or device check only when the issue's approved `Validation Plan` explicitly authorizes that evidence level and every separate build/device approval is satisfied.
7. Never sign, upload, distribute, deploy, access credentials, change runner secrets, mutate production, merge a PR, modify product code, or fix a discovered defect in this workflow.

## Record The Result

Create one UTF-8 result JSON outside the repository:

```json
{
  "version": 1,
  "issueKey": "MCC-1234",
  "outcome": "passed",
  "reason": "all-checks-passed",
  "resumeCondition": "",
  "evidence": ["Candidate and session-level evidence"],
  "checks": [
    {
      "id": "AUTO-EDITOR-001",
      "status": "passed",
      "evidence": ["Concrete command, log, screenshot, or artifact evidence"]
    }
  ]
}
```

- `passed` requires `reason=all-checks-passed` and every pending automatic check exactly once as `passed`.
- `defect` requires `reason=related-defect`, at least one `failed` check, concrete evidence, and a code-fix resume condition.
- `blocked` requires `reason=environment`, `approval`, or `stale-candidate`, concrete evidence, and a resume condition. Environment and approval blockers remain in automatic-validation. A stale candidate is recorded without executing checks.
- A clearly unrelated existing failure may be isolated once and recorded in the attempt evidence. Do not turn it into a related defect or broaden validation without a recorded trigger.

Run:

```bash
python3 .agents/skills/jira-auto-verify/scripts/ai_jira_write_cli.py verify finalize \
  <ISSUE-KEY> --candidate-commit <SHA> --result-file <RESULT-JSON> --json
```

The package pins the candidate, verifies the result/property write, and applies exactly one state result:

- all automatic checks pass + manual checks remain -> `done_manual`
- all automatic checks pass + no manual checks remain -> `done_verified`
- related defect -> `todo`
- environment, approval, or stale-candidate blocker -> remain `done_auto`

Re-read the issue after each write, remove the temporary result only after verification, release only the exact clean slot lease, and continue to the next issue. Report every issue, candidate, checks, evidence, resulting Jira status, and resume condition.

## Boundaries

- Do not take work from todo/progress/manual/verified as an automatic-validation candidate.
- Do not edit the verification plan, implementation baseline, issue requirements, or production code during QA.
- Do not bypass dry-run or `allow_transition`, call Jira directly, guess missing evidence, or mark manual QA passed.
- Stop the affected issue on a partial Jira failure and report its exact property/status state before processing another issue.

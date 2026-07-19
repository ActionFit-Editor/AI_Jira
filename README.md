# AI Jira (com.actionfit.ai-jira)

ActionFit AI agent가 프로젝트 로컬 Jira plan, 읽기 전용 작업 항목 검색, 범위가 제한된 자동 작업 선택, Jira lifecycle 가이드와 안전한 local 자동화에 사용하는 패키지입니다.

## 현재 범위

이 패키지는 Codex 및 Claude Jira skill 콘텐츠, 안전한 연결 초기화·진단 도구와 읽기 전용 Jira 작업 항목 API/CLI를 소유합니다. 공유 package skill 검색 및 설치 lifecycle은 `com.actionfit.custompackagemanager`가 소유하고, Cat Merge Cafe는 `Tools/AI/jira/` 아래의 프로젝트 로컬 호환 entry point와 기존 프로젝트 client 뒤의 쓰기 자동화를 유지합니다.

## 설치

```json
{
  "dependencies": {
    "com.actionfit.ai-jira": "https://github.com/ActionFit-Editor/AI_Jira.git#1.0.24"
  }
}
```

## Unity 메뉴

- 패키지 root: `Tools > Package > AI Jira`
- README: `Tools > Package > AI Jira > README`
- 공유 skill 관리: `Tools > Package > Custom Package Manager > Install or Refresh Agent Skills`, `Remove Managed Agent Skills`, `Add Agent Skill`

## Codex 및 Claude Skill

AI Jira는 `Skills~/manifest.json`을 통해 `skillPrefix: jira`, 필수 `helpSkill: jira-help`와 명시적인 read-only/write-capable access를 가진 schema v2 package-owned source를 등록합니다. Unity가 AI Jira와 Custom Package Manager 의존성을 해석하면 공통 installer가 사용하는 프로젝트에 동기화합니다.

- Codex: `.agents/skills/jira-help`, `.agents/skills/jira-init`, `.agents/skills/jira-todo`, `.agents/skills/jira-plan`, `.agents/skills/jira-auto-start`, `.agents/skills/jira-run`
- Claude: `.claude/skills/jira-help`, `.claude/skills/jira-init`, `.claude/skills/jira-todo`, `.claude/skills/jira-plan`, `.claude/skills/jira-auto-start`, `.claude/skills/jira-run`

Installer는 AI Jira package metadata, manifest와 agent별 `SKILL.md` description으로 설치된 각 `jira-help` 안에 `PACKAGE_SKILLS.md`를 생성합니다. `jira-help`는 이 inventory를 먼저 읽으므로 두 번째 hard-coded skill 목록 없이 package identity, 모든 관련 skill, `$name` 호출, 사용 시점 description과 access 경계가 동기화됩니다.

`jira-help`는 Jira 작업을 실행하지 않고 생성 inventory, read-only/write-capable 명령군, 설정, safety gate와 Unity 메뉴를 설명합니다. `jira-init`은 Jira 접근을 읽기 전용으로 진단하고, 연결 정보가 부족하면 기존 파일을 덮어쓰지 않는 Git 제외 local config를 준비해 입력 위치를 엽니다. `jira-todo`는 할당된 미해결 `todo`와 `progress` issue를 별도로 조회합니다. 새 작업 후보는 `todo` issue뿐입니다. Progress issue는 branch, pull request, worktree, lease 및 Unity process 증거에 따라 `active`, `reserved`, `stranded-review`로 보고하지만 추천 순서에서는 제외합니다. Acquisition PID 생존 여부만으로 lease를 오래됐다고 판단하지 않으며 triage가 lease를 해제하거나 가져가지 않습니다.

`jira-plan`은 개발 아이디어를 조사하고 논의하며 canonical 혼합 언어 Jira 저장 draft를 준비한 뒤 할당된 `todo` issue 하나를 생성하기 전에 완전한 한국어 승인 view를 만듭니다. 기존 needs-plan 논의와 승인 대기도 todo에 유지합니다. 승인된 managed-plan 쓰기에서만 짧고 검증된 progress lock을 사용하고 plan-only 작업은 응답 전에 todo로 돌아갑니다. `jira-auto-start`는 할당된 모든 미해결 todo를 분류하고 시작 가능한 첫 항목을 실행하며, 시작 가능한 항목이 없을 때만 첫 needs-plan 항목의 refinement를 제안합니다. Jira resolution이 설정되거나 status가 설정된 `done`과 일치할 때만 prerequisite 완료로 판단합니다. 민감·파괴적·publish·deployment·production·credential 작업은 별도 승인을 유지합니다. `jira-run`도 명시적으로 선택한 issue를 같은 승인 protocol로 처리합니다.

일반 `jira-run`과 `jira-auto-start` session은 선택 issue가 progress인 채로 끝날 수 없습니다. 완료 작업은 설정된 done 전환 전에 PR URL과 검증된 한국어 QA 완료 기록이 필요합니다. 미완료, 불명확 또는 승인 차단 작업은 한국어 handoff 기록 하나를 쓰고 설정된 todo로 돌아갑니다. 갑작스러운 process 실패, Jira 장애 또는 finalization 실패에서만 예외적으로 progress가 남을 수 있으며 읽기 전용 triage가 lease를 변경하지 않고 복구 증거를 표시합니다.

모든 plan 승인 entry point는 사용자에게 보이는 전체 plan을 한국어로 표시하고 기술 식별자를 보존합니다. Jira에는 한국어 title/QA section과 영어 managed section을 저장합니다. 승인은 preview 전에 준비한 정확한 canonical storage draft를 쓰며 한국어 view를 다시 영어로 번역하지 않습니다. 수정 요청은 canonical draft를 먼저 업데이트하고 완전한 한국어 view를 다시 생성해 새 승인을 요구합니다. 중단 또는 context 손실로 canonical draft가 없거나 불확실하면 Jira에 쓰지 않고 두 표현을 다시 생성해 재확인합니다. 영어 저장 본문은 사용자가 명시적으로 요청할 때만 표시합니다.

네 write-capable skill은 모두 manual-only입니다. `jira-init`의 쓰기 범위는 보호된 local config 준비와 입력 위치 열기로 제한되고 Jira 요청은 읽기 전용입니다. Codex는 암시적 호출을 비활성화하고 Claude는 `disable-model-invocation: true`로 제공합니다.

## 표시되는 Jira 사용자 정보

`jira-run`과 `jira-auto-start`는 Jira 쓰기, worktree 준비 또는 저장소 변경 전에 선택 issue를 정확한 독립 행 `🎫 Jira: <ISSUE-KEY>`로 출력합니다. 구현 전에는 계획한 canonical branch가 정확히 해당 key를 포함해야 하며 파일 편집 전에 실제 checkout branch도 다시 확인합니다. 일치하지 않으면 다른 issue branch 작업을 허용하지 않고 workflow를 중단합니다.

Codex는 지원되는 Git branch title 항목을 통해 terminal 창 또는 tab title에도 Jira key를 표시할 수 있습니다.

```toml
[tui]
terminal_title = ["spinner", "git-branch", "project"]
```

프로젝트 전체에 적용하려면 user-global `~/.codex/config.toml`, 저장소가 해당 경로를 안전하게 소유할 수 있는 신뢰 프로젝트에서는 `.codex/config.toml`에 설정합니다. 설정에는 프로젝트 경로가 없으며 Codex가 현재 작업 디렉터리에서 `project`와 `git-branch`를 해석합니다. Title은 full branch(전체 branch)를 표시하므로 기존 `<ISSUE-KEY>-<short-english-slug>` branch 계약이 Jira key를 노출합니다. Jira key만 추출하거나 branch 생성 전 조건부 표시하는 기능은 지원하지 않으며 AI Jira는 일반 작업 중 raw OSC title sequence를 출력하거나 global Codex 설정을 변경하지 않습니다.

Planning-only 및 read-only 흐름은 응답에 관련 Jira key를 표시하지만 title 표시만을 위해 branch 또는 worktree를 만들지 않습니다. Claude도 같은 안내 및 branch-key 검증 규칙을 따르지만 Codex terminal-title 동작을 제공한다고 주장하지 않습니다. TUI 설정 변경 후 새 Codex session이 필요할 수 있습니다.

이 패키지는 link 대신 파일을 복사하므로 skill directory symlink 지원 이전 Claude Code 버전도 지원합니다. 설치 skill에는 지침과 읽기 전용 package tool locator만 포함하며 자격 증명과 Git에서 제외된 Jira config는 복사하지 않습니다.

Managed state는 Git에서 제외된 project-local `UserSettings/ActionFitPackageManager/skill-install-state.json`에 저장합니다. 누락된 managed target은 복원하고 패키지 콘텐츠 변경 시 변경되지 않은 managed target을 refresh합니다. 기존 unmanaged target과 사용자가 수정한 managed target은 경고와 함께 보존합니다. 자동 설치는 user home/global skill 디렉터리에 쓰거나 skill을 삭제하지 않으며 Unity batch mode에서 건너뜁니다. 명시적 제거는 변경되지 않은 managed target만 삭제하고 install/refresh 명령을 다시 사용할 때까지 자동 재생성을 비활성화합니다.

기존 `UserSettings/AIJira/skill-install-state.json`은 migration 입력으로 제자리에 유지합니다. Custom Package Manager는 현재 hash가 기록된 installed hash와 여전히 일치할 때만 legacy target을 인수하고 이전에 비활성화한 자동 설치 설정도 보존합니다. AI Jira는 Custom Package Manager `1.1.106`에 의존하므로 AI Jira 직접 설치도 Jira 전용 두 번째 writer 대신 모든 ActionFit 패키지가 사용하는 하나의 설치 engine을 통해 schema v2 inventory를 생성합니다.

## AI 가이드

- Jira 자동화 규칙, local Jira config 동작, issue lifecycle 처리 또는 Jira REST script를 변경하기 전에 `AI_GUIDE.md`를 읽습니다.

## Jira 연결 초기화

설치된 skill에서 `$jira-init`을 호출하면 먼저 Jira 인증과 설정된 프로젝트 query를 읽기 전용으로 확인합니다. 누락된 설정이 있으면 기존 파일을 덮어쓰지 않고 `Tools/AI/jira/config.local.json` template을 만들며, clone-local Git exclude와 제한된 파일 권한을 적용한 뒤 입력 위치를 엽니다.

```bash
python3 .agents/skills/jira-init/scripts/ai_jira_init.py status --format json
python3 .agents/skills/jira-init/scripts/ai_jira_init.py setup --open-folder --format json
```

Claude 설치본은 같은 명령을 `.claude/skills/jira-init/scripts/ai_jira_init.py`에서 실행합니다. `status`는 `CONFIG_MISSING`, `CONFIG_INCOMPLETE`, `CREDENTIALS_MISSING`, `CREDENTIALS_MISPLACED`, `AUTHENTICATION_FAILED`, `PERMISSION_DENIED`, `CONFIG_OR_JQL_INVALID`, `NETWORK_ERROR`, `RATE_LIMITED`, `CONNECTED` 같은 구조화된 결과를 반환합니다. `setup`은 기존 config를 보존하며 이미 Git에서 추적되는 config를 자동으로 untrack하지 않습니다.

API token은 Atlassian 계정 보안 페이지에서 생성합니다.

https://id.atlassian.com/manage-profile/security/api-tokens

Token은 생성 직후 password manager에 보관하고, Git에서 제외된 local config 또는 `JIRA_API_TOKEN` 환경 변수에만 입력합니다. Skill과 CLI는 token 값을 출력하거나 shared chat에 요청하지 않습니다.

## 작업 항목 API 및 CLI

사용하는 Unity 프로젝트 root에서 패키지 소유 읽기 전용 도구를 실행합니다.

```bash
python3 Packages/com.actionfit.ai-jira/Tools~/list_work_items.py --state all
python3 Packages/com.actionfit.ai-jira/Tools~/list_work_items.py --state progress --format json
python3 Packages/com.actionfit.ai-jira/Tools~/list_work_items.py --state todo --max-results 25
python3 Packages/com.actionfit.ai-jira/Tools~/get_work_item.py MCC-1234 --format json
```

`--state all`은 완료 작업이 아니라 설정된 `todo`와 `progress` 상태를 포함합니다. 일반 read-only 호출에서 사용할 수 있지만 `jira-todo`는 후보 선택에 사용하지 않습니다. 추천에는 `--state todo`, overlap 감지에는 별도로 `--state progress`를 호출합니다. 모든 query는 결과를 설정된 프로젝트, `assignee = currentUser()`, 미해결 issue로 자동 제한하고 최근 업데이트 순으로 정렬합니다. Detail JSON에는 `configuredStatuses`, 정규화된 `issueLinks`, `descriptionContract`가 포함됩니다. Contract는 managed section 완전성, 세 Auto Start field, 명시적 prerequisite key, unresolved decision과 결정론적 `ready`, `needs-plan`, `blocked` description 상태를 보고합니다. 저장소 안전, overlap과 외부 승인은 상위 skill이 판단합니다.

Text 출력에는 issue key, status, title, update time이 포함됩니다. JSON 출력에는 해석된 status filter, JQL, issue URL과 Jira가 반환한 pagination metadata가 추가되며 한국어를 `\u` escape가 아닌 UTF-8로 보존합니다.

다른 package-local 도구에서도 Python API를 사용할 수 있습니다.

```python
from jira_work_items import load_config, query_work_items

result = query_work_items(load_config(), state="progress", max_results=50)
```

설정 해석 순서는 `--config`, `AI_JIRA_CONFIG`, 사용하는 프로젝트에서 Git 제외된 `Tools/AI/jira/config.local.json`입니다. UTF-8과 BOM이 있는 UTF-8 JSON을 모두 허용합니다. Work-item client는 Jira enhanced search만 노출하고 write method는 제공하지 않습니다.

직접 입력할 자격증명은 `auth.email`, `auth.api_token`에 저장합니다. `auth.email_env`, `auth.api_token_env`는 실제 자격증명이 아니라 환경변수 이름을 지정하는 필드이며, 값을 잘못 넣으면 `CREDENTIALS_MISPLACED`로 안전하게 진단합니다.

Legacy 프로젝트 명령도 호환성을 유지하며 같은 `--state`, `--format`, `--max-results` option을 받습니다.

```bash
python3 Tools/AI/jira/list_my_tasks.py --state progress --format json
```

Unity 없이 패키지 test를 실행합니다.

```bash
python3 -m unittest discover Packages/com.actionfit.ai-jira/Tests~ -p "test_*.py"
```

## 관리되는 설명 계약

AI가 생성하는 Jira title은 한국어입니다. QA heading, 계획 QA 확인 항목과 완료 기록도 한국어이며 상단에 유지합니다. 그 밖의 새 managed heading과 본문은 영어입니다.

```md
## QA 확인 필요 사항

### 계획
- 확인 항목:

---

## Auto Start
- Allowed: yes
- Prerequisites: none
- Decisions Required: none

## 목표

## 범위

## 제외 범위

## 완료 기준

## 검증 계획

## 의존성과 위험
```

한국어 `### 계획` 하나, Auto Start field 세 개와 모든 영어 heading을 정확히 유지합니다. 각 영어 section에는 내용이 있어야 하며 해당 항목이 없으면 `None.`을 사용합니다.

위 managed description이 canonical Jira 저장 표현입니다. 생성 또는 needs-plan refinement 승인을 요청하기 전에 `jira-plan`, `jira-auto-start`, `jira-run`이 `Skills~/Shared/references/korean-approval-preview.md`를 사용해 완전한 한국어 대화 view를 만듭니다. 해당 view는 운영 식별자를 보존하면서 managed heading, field label, control value와 설명을 번역합니다. Preview 전 canonical draft만 허용된 write payload입니다.

기존 Jira description을 bulk migration하지 않습니다. Needs-plan issue는 협업과 승인 중 todo에 유지합니다. 사용자가 완전한 한국어 view와 대응 canonical draft를 승인하면 workflow가 변경되지 않은 todo snapshot을 다시 확인하고 일시적 progress lock을 얻습니다. 이후 독립 `allow_description_plan_refinement` gate, 캡처한 전환 후 Jira `updated` 값과 검증된 progress status를 사용해 managed plan만 업데이트할 수 있습니다.

```bash
python3 Tools/AI/jira/update_description.py MCC-1234 \
  --mode replace-plan \
  --file approved-description.md \
  --expected-updated "2026-07-15T02:22:47.217+0000"
```

이 작업은 기존 QA 완료 기록과 unmanaged top-level section을 보존합니다. Plan-only 작업은 todo로 돌아갑니다. Plan-and-implementation은 즉시 계속하며 이후 done 또는 todo로 finalize해야 합니다. Update 실패 시 todo rollback을 시도하고 lock은 자동 만료되거나 탈취되지 않습니다. Progress triage는 결정론적 우선순위를 적용합니다. Active work 증거가 우선이고, 없으면 일치 lease를 reserved로 처리하며, merged/closed PR만 있거나 active work 증거가 없으면 stranded-review로 분류합니다.

프로젝트 `create_issue.py`는 Jira write 전에 이 managed contract를 검증하므로 불완전하거나 unresolved인 새 draft는 잘못된 todo 작업을 만들지 않고 로컬에서 실패합니다.

## 개인 Jira 자격 증명

Jira 작업 검색은 인증된 Atlassian 계정을 사용합니다. `assignee = currentUser()`가 해당 개발자의 작업을 반환하도록 각 개발자는 자신의 Jira 계정 email과 API token을 사용해야 합니다.

API token이 이미 있으면 로컬 환경에 설정합니다.

```bash
export JIRA_EMAIL="name@company.com"
export JIRA_API_TOKEN="your-atlassian-api-token"
```

API token이 없으면 Atlassian Account security에서 생성합니다.

https://id.atlassian.com/manage-profile/security/api-tokens

Token 생성 직후 복사해 password manager에 보관합니다. Atlassian은 생성 후 token을 다시 보여주지 않습니다. Token을 commit하거나 공유 chat에 붙여 넣거나 추적되는 프로젝트 파일에 저장하지 않습니다.

Project-local script는 Git에서 제외된 `Tools/AI/jira/config.local.json`도 읽을 수 있지만 개인 자격 증명은 환경 변수를 권장합니다.

## 이슈 생성 기본값

`Tools/AI/jira/create_issue.py`가 Jira issue를 만들 때 기본 owner는 인증된 Jira API 사용자입니다. `issue_create.assign_to_current_user`가 true이거나 생략되면 script가 `/rest/api/3/myself`를 해석하고 해당 account ID를 issue `assignee` 필드에 씁니다.

새 issue는 기본적으로 설정된 `todo` status에 생성해야 합니다. Jira 프로젝트 workflow가 다른 초기 status로 issue를 만들면 create script가 생성 issue key를 반환하기 전에 즉시 `issue_create.create_status`, 일반적으로 `statuses.todo`로 전환해야 합니다. 실제 구현을 시작할 때만 issue를 `progress`로 옮깁니다.

일반 AI Jira 경로로 만드는 새 issue는 현재 active sprint에 속해야 합니다. 해당 경로는 backlog 배치를 지원하지 않으므로 의도적인 backlog 예외는 `Tools/AI/jira/create_issue.py` 밖에서 수동 생성합니다.

Git에서 제외된 local config에서 sprint write gate와 active sprint 생성 기본값을 활성화합니다.

```json
{
  "automation": {
    "allow_sprint_add": true
  },
  "issue_create": {
    "add_to_active_sprint_after_create": true,
    "board_id": 3,
    "active_sprint_id": null
  }
}
```

일반 작업은 `board_id`를 사용해 client가 issue 생성 직전에 현재 active sprint를 해석하게 합니다. 고정 sprint가 의도적으로 필요할 때만 `active_sprint_id`를 사용합니다. Board 및 sprint ID는 프로젝트별 값이므로 Git에서 제외된 local config에 보관합니다.

호환 Jira client는 누락된 `add_to_active_sprint_after_create` 값을 `true`로 처리하고 Jira create 요청 전에 명시적 `false`를 거부합니다. Sprint write가 비활성화되었거나 active sprint를 모호함 없이 해석할 수 없으면 backlog로 낮추지 않고 생성을 차단합니다.

생성 후 client는 issue를 다시 읽고 인증 assignee, 설정된 `todo` status와 예상 sprint membership을 검증한 뒤 성공을 보고해야 합니다. Create response가 숫자 issue ID를 제공하면 `reconcileIssues`가 있는 enhanced JQL search를 사용해 membership 검사에 더 강한 read-after-write 일관성을 확보합니다. Jira가 issue를 만들었지만 sprint 할당 또는 이후 검증이 실패하면 issue를 삭제하지 않고 생성 key, 예상 sprint, 정확한 불일치와 수동 복구 작업을 보고합니다.

## 세션 마무리

Jira 기반 개발 작업은 PR 생성만으로 Jira lifecycle이 끝나지 않습니다. PR URL이 생긴 뒤 활성화된 경우 한국어 QA note를 앞에 추가하고 설정된 done으로 finalize합니다. 미완료 작업은 현재 한국어 handoff 기록과 함께 todo로 finalize합니다.

Use:

```bash
python3 Tools/AI/jira/update_description.py MCC-1234 --mode prepend-qa --file qa-notes.md
python3 Tools/AI/jira/finalize_session.py MCC-1234 --outcome done --pr-url "https://github.com/org/repo/pull/123"
python3 Tools/AI/jira/finalize_session.py MCC-1234 --outcome incomplete \
  --completed-work "분석 완료" --remaining-work "구현 및 검증" \
  --branch-pr "MCC-1234-work / PR 없음" --validation "미실행" \
  --blocker-approval "승인 대기" --resume-condition "승인 후 구현 재개"
```

Done은 progress, issue별 한국어 QA 완료 기록, PR URL, transition과 결과 status를 검증합니다. Incomplete에는 `allow_description_append`와 `allow_transition`이 필요하며 QA 완료 pattern을 만족할 수 없는 heading을 upsert하고 description과 todo를 검증합니다. Description update와 transition은 별도 Jira 작업이므로 transition 실패 후에도 검증된 handoff가 남을 수 있습니다. 해당 부분 결과와 복구 작업을 명시적으로 보고합니다.

미완료 open PR은 Jira가 todo로 돌아오고 active lease가 소유하지 않을 때만 같은 issue로 재개할 수 있습니다. Merge 또는 close된 PR branch는 재사용하지 않으며 후속 작업은 최신 integration branch에서 새 PR로 시작합니다.

## 레거시 패키지

- `com.actionfit.ai_guide_jira`는 placeholder guide 패키지였으므로 이 패키지와 함께 설치하면 안 됩니다.
- Canonical Jira 자동화 guide 패키지로 `com.actionfit.ai-jira`를 사용합니다.

## 마이그레이션 참고 사항

- Project-local secret과 board mapping은 패키지 밖의 Git 제외 local config 파일에 유지해야 합니다.
- 모든 AI 문서와 workflow가 패키지 소유 routing으로 이동할 때까지 compatibility wrapper가 기존 프로젝트 경로를 보존해야 합니다.

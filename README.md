# AI Jira (com.actionfit.ai-jira)

ActionFit AI agent가 프로젝트 로컬 Jira plan, 읽기 전용 작업 항목 검색, 범위가 제한된 자동 작업 선택, Jira lifecycle 가이드와 안전한 local 자동화에 사용하는 패키지입니다.

## 현재 범위

이 패키지는 Codex 및 Claude Jira skill 콘텐츠, 읽기 전용 작업 항목 API/CLI, 안전한 공통 쓰기 client와 설치된 패키지를 찾는 write locator를 소유합니다. 위험도 기반 작업 분류·soft budget·Unity 증거 수준은 직접 의존하는 `com.actionfit.ai-workagent`가 소유하고 AI Jira가 기존 `Validation Plan`에 적용합니다. 공유 package skill 검색 및 설치 lifecycle은 `com.actionfit.custompackagemanager`가 소유합니다. 소비 프로젝트의 `Tools/AI/jira/` 경로는 기존 호출을 위한 호환 entry point로 계속 사용할 수 있지만, 새로 설치한 skill은 패키지 소유 locator를 사용합니다.

패키지 설치나 skill refresh는 쓰기 코드를 제공할 뿐 Jira 쓰기 권한을 자동으로 활성화하지 않습니다. 실제 변경에는 사용자 승인, 인증된 Jira 계정 권한, `dry_run: false`, 작업별 `allow_*` gate가 모두 필요합니다.

## 설치

```json
{
  "dependencies": {
    "com.actionfit.ai-jira": "https://github.com/ActionFit-Editor/AI_Jira.git#1.0.32"
  }
}
```

## Unity 메뉴

- 패키지 root: `Tools > Package > AI Jira`
- README: `Tools > Package > AI Jira > README`
- 공유 skill 관리: `Tools > Package > Custom Package Manager > Install or Refresh Agent Skills`, `Remove Managed Agent Skills`, `Add Agent Skill`

## Codex 및 Claude Skill

AI Jira는 `Skills~/manifest.json`을 통해 `skillPrefix: jira`, 필수 `helpSkill: jira-help`와 명시적인 read-only/write-capable access를 가진 schema v2 package-owned source를 등록합니다. Unity가 AI Jira와 Custom Package Manager 의존성을 해석하면 공통 installer가 사용하는 프로젝트에 동기화합니다.

- Codex: `.agents/skills/jira-help`, `.agents/skills/jira-setup`, `.agents/skills/jira-todo`, `.agents/skills/jira-plan`, `.agents/skills/jira-auto-start`, `.agents/skills/jira-run`
- Claude: `.claude/skills/jira-help`, `.claude/skills/jira-setup`, `.claude/skills/jira-todo`, `.claude/skills/jira-plan`, `.claude/skills/jira-auto-start`, `.claude/skills/jira-run`

Installer는 AI Jira package metadata, manifest와 agent별 `SKILL.md` description으로 설치된 각 `jira-help` 안에 `PACKAGE_SKILLS.md`를 생성합니다. `jira-help`는 이 inventory를 먼저 읽으므로 두 번째 hard-coded skill 목록 없이 package identity, 모든 관련 skill, `$name` 호출, 사용 시점 description과 access 경계가 동기화됩니다.

`jira-help`는 Jira 작업을 실행하지 않고 생성 inventory, read-only/write-capable 명령군, 설정, safety gate와 Unity 메뉴를 설명합니다. `jira-todo`는 할당된 미해결 `todo`와 `progress` issue를 별도로 조회합니다. 새 작업 후보는 `todo` issue뿐입니다. Progress issue는 branch, pull request, worktree, lease 및 Unity process 증거에 따라 `active`, `reserved`, `stranded-review`로 보고하지만 추천 순서에서는 제외합니다. Acquisition PID 생존 여부만으로 lease를 오래됐다고 판단하지 않으며 triage가 lease를 해제하거나 가져가지 않습니다.

`jira-plan`은 명시적으로 요청된 제목 전용 needs-plan을 나중에 계획할 `todo`로 접수하거나, 개발 아이디어를 조사하고 논의하며 canonical 혼합 언어 Jira 저장 draft를 준비한 뒤 `todo` issue 하나를 생성하기 전에 완전한 한국어 승인 view를 만듭니다. 제목 전용 접수는 정확한 한국어 제목 승인 후 설명 없이 생성하며 일반 planning 결정을 우회하는 fallback으로 사용하지 않습니다. 기존 needs-plan 논의와 승인 대기도 todo에 유지합니다. 승인된 managed-plan 쓰기에서만 짧고 검증된 progress lock을 사용하고 plan-only 작업은 응답 전에 todo로 돌아갑니다. `jira-auto-start`는 할당된 모든 미해결 todo를 분류하고 시작 가능한 첫 항목을 실행하며, 시작 가능한 항목이 없을 때만 첫 needs-plan 항목의 refinement를 제안합니다. Jira resolution이 설정되거나 status가 설정된 `done`과 일치할 때만 prerequisite 완료로 판단합니다. 민감·파괴적·publish·deployment·production·credential 작업은 별도 승인을 유지합니다. `jira-run`도 명시적으로 선택한 issue를 같은 승인 protocol로 처리합니다.

`jira-plan`, `jira-auto-start`, `jira-run`의 planning 경로는 `Skills~/Shared/references/planning-decision-collaboration.md`를 공유합니다. 사용자 요구, 저장소/API-owner 지침, 패키지 가이드, 일관된 기존 패턴 순으로 한 가지 방식을 결정할 수 있으면 불필요한 질문을 하지 않습니다. 반대로 컨벤션으로 결정되지 않는 합리적인 방식이 여러 개면 한 회차에 연관 질문 1~3개를 제시하고, 각 선택지의 차이·장점·단점을 같은 기준으로 설명한 뒤 추천안과 근거를 안내합니다. 답변 뒤에는 전체 범위를 다시 탐색합니다. 미해결 결정이 있는 동안에는 approval-ready plan을 만들지 않으며, 확정 결정·적용 컨벤션·에이전트 가정 요약에 대한 종료 확인 뒤에만 canonical draft를 준비합니다. 추천 위임은 기본적으로 현재 질문 묶음에만 적용되고, 명시적인 광범위 위임도 현재 planning invocation에서 끝납니다.

세 스킬은 `Skills~/Shared/references/risk-proportional-validation-plan.md`를 함께 읽습니다. 기존 `## Validation Plan` 안에서 필수 검증, 조건부 확대 trigger, 의도적으로 제외한 고비용 검증을 구분하며 새 top-level heading이나 schema field는 추가하지 않습니다.

- UI·presentation은 `editor-simulated`가 기본입니다.
- 실제 touch·sensor가 요구사항에 영향을 줄 때만 `remote-assisted`를 선택하며 Unity Remote 실행은 여전히 Editor 증거입니다.
- native plugin, mobile SDK, platform define/asmdef, IL2CPP/AOT, PlayerSettings, Gradle/Xcode, Addressables/Build Pipeline, Editor에서 재현 불가능한 결함이 있을 때만 `player-build`를 계획합니다.
- 영향받은 platform만 빌드하며 Android와 iOS 모두는 공통 mobile boundary 근거가 있어야 합니다.
- 일반적인 “모바일 QA”는 Player build 승인이 아니며 승인된 `Validation Plan`에 없던 build는 추가 승인이 필요합니다.
- 명확히 무관한 기존 실패는 한 번만 격리하고, signing·AAB/IPA 배포·TestFlight·Google Play·Slack upload·deployment·credential·runner secret은 기존 별도 승인을 유지합니다.

일반 `jira-run`과 `jira-auto-start` 구현은 `start` 명령이 Jira issue property에 요구사항 ID, 설명 digest, branch와 session ID를 봉인한 뒤 시작합니다. Done은 동일 baseline, PR, 모든 요구사항의 구체적 evidence가 있는 completion-review JSON과 다섯 필드의 한국어 QA 완료 기록이 모두 일치할 때만 허용됩니다. 미봉인 legacy progress, 일부 구현, 범위 축소, deferred 항목은 완료할 수 없으며 incomplete로 todo에 돌아간 뒤 다시 착수해야 합니다.

모든 plan 승인 entry point는 사용자에게 보이는 전체 plan을 한국어로 표시하고 기술 식별자를 보존합니다. Jira에는 한국어 title/QA section과 영어 managed section을 저장합니다. 승인은 preview 전에 준비한 정확한 canonical storage draft를 쓰며 한국어 view를 다시 영어로 번역하지 않습니다. 수정 요청은 canonical draft를 먼저 업데이트하고 완전한 한국어 view를 다시 생성해 새 승인을 요구합니다. 중단 또는 context 손실로 canonical draft가 없거나 불확실하면 Jira에 쓰지 않고 두 표현을 다시 생성해 재확인합니다. 영어 저장 본문은 사용자가 명시적으로 요청할 때만 표시합니다.

네 write-capable skill도 Codex 기본 컨텍스트에 포함됩니다. 컨텍스트 노출만으로 Jira 쓰기나 작업 착수가 승인되지는 않으며 기존 사용자 승인, `dry_run`, 작업별 `allow_*` gate와 lifecycle 검증을 모두 유지합니다. Claude는 기존 `disable-model-invocation: true`를 유지합니다.

## 표시되는 Jira 사용자 정보

`jira-run`과 `jira-auto-start`는 Jira 쓰기, worktree 준비 또는 저장소 변경 전에 선택 issue를 정확한 독립 행 `🎫 Jira: <ISSUE-KEY>`로 출력합니다. 구현 전에는 계획한 canonical branch가 정확히 해당 key를 포함해야 하며 파일 편집 전에 실제 checkout branch도 다시 확인합니다. 일치하지 않으면 다른 issue branch 작업을 허용하지 않고 workflow를 중단합니다.

Codex는 지원되는 Git branch title 항목을 통해 terminal 창 또는 tab title에도 Jira key를 표시할 수 있습니다.

```toml
[tui]
terminal_title = ["spinner", "git-branch", "project"]
```

프로젝트 전체에 적용하려면 user-global `~/.codex/config.toml`, 저장소가 해당 경로를 안전하게 소유할 수 있는 신뢰 프로젝트에서는 `.codex/config.toml`에 설정합니다. 설정에는 프로젝트 경로가 없으며 Codex가 현재 작업 디렉터리에서 `project`와 `git-branch`를 해석합니다. Title은 full branch를 표시하므로 기존 `<ISSUE-KEY>-<short-english-slug>` branch 계약이 Jira key를 노출합니다. Jira key만 추출하거나 branch 생성 전 조건부 표시하는 기능은 지원하지 않으며 AI Jira는 일반 작업 중 raw OSC title sequence를 출력하거나 global Codex 설정을 변경하지 않습니다.

Planning-only 및 read-only 흐름은 응답에 관련 Jira key를 표시하지만 title 표시만을 위해 branch 또는 worktree를 만들지 않습니다. Claude도 같은 안내 및 branch-key 검증 규칙을 따르지만 Codex terminal-title 동작을 제공한다고 주장하지 않습니다. TUI 설정 변경 후 새 Codex session이 필요할 수 있습니다.

이 패키지는 link 대신 파일을 복사하므로 skill directory symlink 지원 이전 Claude Code 버전도 지원합니다. 설치 skill에는 지침과 읽기·쓰기 package tool locator를 포함하지만 자격 증명과 Git에서 제외된 Jira config는 복사하지 않습니다. Locator는 embedded package를 먼저, `Library/PackageCache`를 다음으로 찾습니다.

Managed state는 Git에서 제외된 project-local `UserSettings/ActionFitPackageManager/skill-install-state.json`에 저장합니다. 누락된 managed target은 복원하고 패키지 콘텐츠 변경 시 변경되지 않은 managed target을 refresh합니다. 기존 unmanaged target과 사용자가 수정한 managed target은 경고와 함께 보존합니다. 자동 설치는 user home/global skill 디렉터리에 쓰거나 skill을 삭제하지 않으며 Unity batch mode에서 건너뜁니다. 명시적 제거는 변경되지 않은 managed target만 삭제하고 install/refresh 명령을 다시 사용할 때까지 자동 재생성을 비활성화합니다.

기존 `UserSettings/AIJira/skill-install-state.json`은 migration 입력으로 제자리에 유지합니다. Custom Package Manager는 현재 hash가 기록된 installed hash와 여전히 일치할 때만 legacy target을 인수하고 이전에 비활성화한 자동 설치 설정도 보존합니다. AI Jira는 WorkAgent `0.1.1`과 Custom Package Manager `1.1.106`에 직접 의존하므로 실행 정책 owner를 항상 해석하고, Jira 전용 두 번째 writer 대신 모든 ActionFit 패키지가 사용하는 하나의 설치 engine을 통해 schema v2 inventory를 생성합니다.

## AI 가이드

- Jira 자동화 규칙, local Jira config 동작, issue lifecycle 처리 또는 Jira REST script를 변경하기 전에 `AI_GUIDE.md`를 읽습니다.

## 작업 항목 API 및 CLI

사용하는 Unity 프로젝트 root에서 패키지 소유 읽기 전용 도구를 실행합니다.

```bash
python3 Packages/com.actionfit.ai-jira/Tools~/list_work_items.py --state all
python3 Packages/com.actionfit.ai-jira/Tools~/list_work_items.py --state progress --format json
python3 Packages/com.actionfit.ai-jira/Tools~/list_work_items.py --state todo --max-results 25
python3 Packages/com.actionfit.ai-jira/Tools~/list_overlap_work_items.py --format json
python3 Packages/com.actionfit.ai-jira/Tools~/get_work_item.py MCC-1234 --format json
```

쓰기 가능한 skill은 설치된 agent 경로의 locator를 호출합니다. `create`, `update-description`, `transition`, `start`, `finalize`가 package-owned `Tools~` 구현으로 전달되며 embedded와 PackageCache 설치를 모두 지원합니다.

```bash
python3 .agents/skills/jira-plan/scripts/ai_jira_write_cli.py create --help
python3 .agents/skills/jira-plan/scripts/ai_jira_write_cli.py create --summary "나중에 계획할 작업" --title-only-needs-plan
python3 .agents/skills/jira-run/scripts/ai_jira_write_cli.py update-description --help
python3 .agents/skills/jira-run/scripts/ai_jira_write_cli.py transition --help
python3 .agents/skills/jira-run/scripts/ai_jira_write_cli.py start --help
python3 .agents/skills/jira-run/scripts/ai_jira_write_cli.py finalize --help
```

Claude 설치에서는 같은 명령의 `.claude/skills/...` 경로를 사용합니다. Locator 제공 자체는 쓰기 승인이 아니며, 각 명령은 소비 프로젝트의 인증·설정·gate를 다시 검사합니다.

`--state all`은 완료 작업이 아니라 설정된 `todo`와 `progress` 상태를 포함합니다. 일반 read-only 호출에서 사용할 수 있지만 `jira-todo`는 후보 선택에 사용하지 않습니다. 추천에는 `--state todo`, 현재 작업 충돌 감지에는 별도로 `--state progress`를 호출합니다. 이 일반 work-list query는 설정된 프로젝트, `assignee = currentUser()`, 미해결 issue로 자동 제한하고 최근 업데이트 순으로 정렬합니다.

전용 `list_overlap_work_items.py` 또는 설치된 `ai_jira_cli.py overlap --format json`은 리팩터링 같은 프로젝트 전체 중복 검사에만 사용합니다. 모든 담당자의 이슈 중 정확히 설정된 `todo`, `progress`, `done` 상태를 끝 페이지까지 조회하며 다른 QA/future 상태는 포함하지 않습니다. `project_key`, 세 상태 매핑, 인증, 권한 또는 terminal pagination 증거가 하나라도 없으면 `complete=true`를 반환하지 않고 실패합니다. 이 결과는 `jira-todo` 추천이나 자동 착수 입력으로 사용하지 않습니다. 이후 의미 기반 중복 판정은 호출 패키지가 각 이슈 상세를 읽고 직접 수행합니다.

Detail JSON에는 `configuredStatuses`, 정규화된 `issueLinks`, `descriptionContract`가 포함됩니다. Contract는 managed section 완전성, 세 Auto Start field, 명시적 prerequisite key, unresolved decision과 결정론적 `ready`, `needs-plan`, `blocked` description 상태를 보고합니다. 저장소 안전, overlap과 외부 승인은 상위 skill이 판단합니다.

Text 출력에는 issue key, status, title, update time이 포함됩니다. JSON 출력에는 해석된 status filter, JQL, issue URL과 Jira가 반환한 pagination metadata가 추가되며 한국어를 `\u` escape가 아닌 UTF-8로 보존합니다.

다른 package-local 도구에서도 Python API를 사용할 수 있습니다.

```python
from jira_work_items import load_config, query_work_items

result = query_work_items(load_config(), state="progress", max_results=50)
```

설정 해석 순서는 `--config`, `AI_JIRA_CONFIG`, 사용하는 프로젝트에서 Git 제외된 `Tools/AI/jira/config.local.json`입니다. UTF-8과 BOM이 있는 UTF-8 JSON을 모두 허용합니다. Work-item client는 Jira enhanced search만 노출하고 write method는 제공하지 않습니다.

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

기존 Jira description을 bulk migration하지 않습니다. Needs-plan issue는 협업과 승인 중 todo에 유지합니다. 승인 후 `transition --to progress --purpose planning --json`이 원본 description 또는 title-only summary를 versioned Jira issue property에 먼저 봉인합니다. 새 plan은 모든 source requirement ID를 정확히 한 번 매핑하는 coverage JSON이 필요합니다. 삭제·deferred·out-of-scope 이동은 별도 replanning 승인, rationale, `scopeChangeApproved: true` 없이는 차단되며 partial PR 승인은 부모 issue 범위 축소 승인이 아닙니다.

```bash
python3 .agents/skills/jira-plan/scripts/ai_jira_write_cli.py update-description MCC-1234 \
  --mode replace-plan \
  --file approved-description.md \
  --expected-updated "2026-07-15T02:22:47.217+0000" \
  --coverage-file plan-coverage.json
```

이 작업은 기존 QA 완료 기록과 unmanaged top-level section을 보존하고 description/property write 실패를 보상합니다. Plan-only는 `transition --to todo --purpose planning`으로 돌아갑니다. 구현은 generic progress transition 대신 `start MCC-1234 --branch MCC-1234-work --json`을 사용합니다. `start`는 approved Goal, Scope, Out of Scope, Completion Criteria, Additional Requirements, stable ID, digest, branch, session ID와 timestamp를 봉인하고 read-after-write를 검증합니다. Baseline 없는 legacy progress는 제자리에서 봉인하거나 완료할 수 없고 incomplete → todo → start 순서로 복구합니다.

Package-owned `create_issue.py`의 일반 생성은 Jira write 전에 이 managed contract를 검증하므로 불완전하거나 unresolved인 새 draft는 잘못된 todo 작업을 만들지 않고 로컬에서 실패합니다. 명시적인 `--title-only-needs-plan`만 예외이며 `--description` 또는 `--description-file`과 함께 사용하면 차단하고 Jira description 필드를 생략합니다. 따라서 생성 issue는 이후 조회에서 `descriptionContract.state=needs-plan`으로 분류됩니다. 이 모드는 정확한 제목의 명시적 생성 승인과 중복 확인이 필요한 향후 planning 접수이며, 일반 plan의 결정·승인 절차를 우회하지 않습니다.

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

Package-owned script는 사용하는 프로젝트에서 Git 제외된 `Tools/AI/jira/config.local.json`을 읽을 수 있지만 개인 자격 증명은 환경 변수를 권장합니다.

명시적인 `$jira-setup`은 기존 config를 덮어쓰지 않습니다. config가 없을 때만 Jira URL, project/status/board와 branch/worktree 값을 포함한 비밀값 없는 전체 계획을 보여주고 승인받은 뒤 Git에서 제외된 파일을 생성합니다. 인증은 `JIRA_EMAIL`, `JIRA_API_TOKEN` 환경 변수 이름으로만 참조하고 `dry_run: true`와 모든 `allow_*: false`를 유지한 상태에서 read-only 연결만 검증합니다.

## 이슈 생성 기본값

Package-owned `Tools~/create_issue.py`가 Jira issue를 만들 때 기본 owner는 인증된 Jira API 사용자입니다. `issue_create.assign_to_current_user`가 true이거나 생략되면 script가 `/rest/api/3/myself`를 해석하고 해당 account ID를 issue `assignee` 필드에 씁니다.

`--issue-type`은 Jira create metadata에서 해석합니다. 정확한 top-level type ID 또는 대소문자를 구분하지 않는 정확한 이름 하나만 허용하고, subtask·중복 이름·알 수 없는 값·잘못된 metadata는 생성 전에 차단합니다. Create payload에는 검증된 `issuetype.id`만 전송합니다.

새 issue는 기본적으로 설정된 `todo` status에 생성해야 합니다. Jira 프로젝트 workflow가 다른 초기 status로 issue를 만들면 create script가 생성 issue key를 반환하기 전에 즉시 `issue_create.create_status`, 일반적으로 `statuses.todo`로 전환해야 합니다. 실제 구현을 시작할 때만 issue를 `progress`로 옮깁니다.

제목 전용 needs-plan도 같은 owner, issue type, todo, active sprint, dry-run 및 `allow_*` gate 계약을 사용합니다. 차이는 승인된 정확한 한국어 title만 보내고 description을 만들지 않는다는 점뿐이며, 같은 invocation에서 refinement나 구현을 시작하지 않습니다.

일반 AI Jira 경로로 만드는 새 issue는 현재 active sprint에 속해야 합니다. 해당 경로는 backlog 배치를 지원하지 않으므로 의도적인 backlog 예외는 package-owned create 명령 밖에서 수동 생성합니다.

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
python3 .agents/skills/jira-run/scripts/ai_jira_write_cli.py update-description MCC-1234 --mode prepend-qa --file qa-notes.md
python3 .agents/skills/jira-run/scripts/ai_jira_write_cli.py finalize MCC-1234 --outcome done \
  --pr-url "https://github.com/org/repo/pull/123" \
  --review-file completion-review.json
python3 .agents/skills/jira-run/scripts/ai_jira_write_cli.py finalize MCC-1234 --outcome incomplete \
  --completed-work "분석 완료" --remaining-work "구현 및 검증" \
  --branch-pr "MCC-1234-work / PR 없음" --validation "미실행" \
  --blocker-approval "승인 대기" --resume-condition "승인 후 구현 재개"
```

Done은 active baseline과 현재 요구사항 digest가 같은지 확인하고, review의 issue key·session ID·baseline digest·PR URL이 정확히 일치하는지 검증합니다. 모든 sealed requirement는 중복 없이 `complete`와 구체적인 evidence를 가져야 합니다. 한국어 QA 기록은 `변경 요약`, `검증 결과`, `미검증 항목`, `QA 확인 항목`, `위험 영역`이 모두 비어 있지 않아야 하고 done에서는 `미검증 항목: 없음`이어야 합니다. 검증된 review와 digest는 Jira property에 보존됩니다. Incomplete는 handoff를 검증하고 기존 baseline을 닫은 뒤 todo로 돌아갑니다.

미완료 open PR은 Jira가 todo로 돌아오고 active lease가 소유하지 않을 때만 같은 issue로 재개할 수 있습니다. Merge 또는 close된 PR branch는 재사용하지 않으며 후속 작업은 최신 integration branch에서 새 PR로 시작합니다.

## 레거시 패키지

- `com.actionfit.ai_guide_jira`는 placeholder guide 패키지였으므로 이 패키지와 함께 설치하면 안 됩니다.
- Canonical Jira 자동화 guide 패키지로 `com.actionfit.ai-jira`를 사용합니다.

## 마이그레이션 참고 사항

- Project-local secret과 board mapping은 패키지 밖의 Git 제외 local config 파일에 유지해야 합니다.
- 기존 프로젝트 경로의 compatibility entry point는 제거하지 않으며 package-owned 구현을 호출하는 wrapper 또는 기존 호환 구현으로 계속 동작해야 합니다.

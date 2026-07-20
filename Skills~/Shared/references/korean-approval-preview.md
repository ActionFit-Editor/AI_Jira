# Korean Jira Plan Approval Preview

Use this contract whenever a Jira workflow must ask the user to approve a new managed plan or a needs-plan refinement. The conversational Korean preview and the Jira storage draft are two representations of the same plan.

## Source Of Truth

1. Prepare the complete canonical storage title and description first.
2. Keep the canonical Jira title and `## QA 확인 필요 사항` content in Korean. Keep every other managed heading, field, value, and body in English according to the managed-description contract.
3. Derive a complete Korean approval preview from that canonical draft. Do not use a summary or omit repeated details.
4. Keep the exact canonical draft available until the approved Jira write finishes.
5. After approval, pass the pre-preview canonical title and description unchanged through `ai_jira_write_cli.py create` or `ai_jira_write_cli.py update-description --mode replace-plan`. Never translate the Korean preview back into a Jira payload.

## Korean Presentation

Start the preview with this notice or an equivalent complete statement in Korean:

> 아래 내용은 사용자가 승인할 한글 표시본입니다. 승인하면 이 표시본을 만들기 전에 준비한 동일한 의미의 Jira 저장용 혼합 언어 원문을 그대로 등록하거나 갱신합니다.

Do not show the English storage body by default. Show it only when the user explicitly asks to inspect it.

Use these user-visible mappings:

| Canonical storage text | Korean approval view |
| --- | --- |
| `## Auto Start` | `## 자동 착수` |
| `Allowed` | `허용 여부` |
| `Prerequisites` | `선행 작업` |
| `Decisions Required` | `결정 필요 사항` |
| `## Goal` | `## 목표` |
| `## Scope` | `## 범위` |
| `### Confirmed Decisions` | `### 확정된 결정` |
| `## Out of Scope` | `## 제외 범위` |
| `## Completion Criteria` | `## 완료 기준` |
| `## Validation Plan` | `## 검증 계획` |
| `## Dependencies and Risks` | `## 의존성과 위험` |
| `yes` | `예` |
| `no` | `아니요` |
| `none` or `None.` | `없음` |

Keep the Korean title, `## QA 확인 필요 사항`, `### 계획`, and QA content as written. Translate every explanatory sentence and list item in the other managed sections into natural Korean. Preserve technical identifiers exactly, including issue keys, file paths, URLs, commands, code symbols, class and member names, config keys, branch names, status names, package IDs, and literal values whose spelling is operationally significant.

The Korean preview must contain every managed section and field from the canonical draft in the same order. Do not soften requirements, merge distinct list items, or hide risks and exclusions.

End with a Korean approval request that names the authorized action, such as issue creation, plan-only update, plan update and auto-start, or plan update and implementation. State that approval writes the corresponding canonical mixed-language storage draft, not the Korean preview.

## Revisions

Treat any requested change as invalidating the previous preview and approval:

1. Update the canonical storage draft first.
2. Regenerate the complete Korean approval preview from the updated canonical draft.
3. Request explicit approval again for the intended action.

Never patch only the Korean preview and never reuse approval from an older preview.

## Interruption Recovery

If conversation interruption, context compaction, or state loss makes the exact canonical draft unavailable or makes its equality with the preview uncertain, do not write Jira. Rebuild the canonical draft, regenerate the complete Korean preview, and obtain new explicit approval. Existing planning-lock, `expected-updated`, write-gate, active-sprint, and rollback rules remain unchanged.

#!/usr/bin/env python3
"""Deterministic AI Jira description contract parsing and safe managed merges."""

from __future__ import annotations

import re
from typing import Any


QA_HEADING = "## QA 확인 필요 사항"
AUTO_START_HEADING = "Auto Start"
PLAN_HEADINGS = (
    AUTO_START_HEADING,
    "Goal",
    "Scope",
    "Out of Scope",
    "Completion Criteria",
    "Validation Plan",
    "Dependencies and Risks",
)
LEGACY_PLAN_HEADINGS = {
    "자동 실행",
    "배경",
    "목표",
    "작업 범위",
    "제외 범위",
    "구현 계획",
    "완료 조건",
    "검증 계획",
    "의존성 및 위험",
}
AUTO_START_FIELDS = ("Allowed", "Prerequisites", "Decisions Required")
NONE_VALUES = {"none", "n/a", "not applicable"}
YES_VALUES = {"yes", "true"}
NO_VALUES = {"no", "false"}
FIELD_PATTERN = re.compile(
    r"(?mi)^\s*-?\s*(Allowed|Prerequisites|Decisions Required)\s*:\s*(.*?)\s*$"
)
ISSUE_KEY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b", re.IGNORECASE)
QA_COMPLETION_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}\s*/\s*([A-Z][A-Z0-9]+-\d+)$", re.IGNORECASE)
QA_COMPLETION_FIELDS = (
    "변경 요약",
    "검증 결과",
    "미검증 항목",
    "QA 확인 항목",
    "위험 영역",
)
HANDOFF_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}\s*/\s*([A-Z][A-Z0-9]+-\d+)\s*/\s*작업 인계$",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _heading_spans(text: str, level: int) -> list[dict[str, Any]]:
    marker = "#" * level + " "
    spans = []
    offset = 0
    active_fence = ""
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\n")
        stripped = content.strip()
        fence_match = re.match(r"^(`{3,}|~{3,})", stripped)
        if fence_match:
            fence = fence_match.group(1)
            if not active_fence:
                active_fence = fence[0]
            elif fence[0] == active_fence:
                active_fence = ""
        elif not active_fence and content.startswith(marker):
            heading = content[len(marker):].strip()
            if heading and not heading.startswith("#"):
                spans.append(
                    {
                        "heading": heading,
                        "start": offset,
                        "heading_end": offset + len(content),
                    }
                )
        offset += len(line)
    return spans


def _without_fenced_blocks(text: str) -> str:
    lines = []
    active_fence = ""
    for line in (text or "").splitlines():
        stripped = line.strip()
        fence_match = re.match(r"^(`{3,}|~{3,})", stripped)
        if fence_match:
            fence = fence_match.group(1)
            if not active_fence:
                active_fence = fence[0]
            elif fence[0] == active_fence:
                active_fence = ""
            lines.append("")
        else:
            lines.append("" if active_fence else line)
    return "\n".join(lines)


def _top_sections(text: str) -> list[dict[str, Any]]:
    normalized = _normalize(text)
    matches = _heading_spans(normalized, 2)
    sections = []
    for index, match in enumerate(matches):
        end = matches[index + 1]["start"] if index + 1 < len(matches) else len(normalized)
        sections.append(
            {
                "heading": match["heading"],
                "start": match["start"],
                "end": end,
                "body": normalized[match["heading_end"]:end].strip(),
                "raw": normalized[match["start"]:end].strip(),
            }
        )
    return sections


def _section_map(text: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for section in _top_sections(text):
        result.setdefault(section["heading"], section)
    return result


def top_level_sections(description: str) -> list[dict[str, str]]:
    """Expose fence-aware top-level heading bodies for related Jira contracts."""
    return [
        {"heading": section["heading"], "body": section["body"]}
        for section in _top_sections(description)
    ]


def _is_none(value: str) -> bool:
    return value.strip().lower().rstrip(".") in NONE_VALUES


def parse_description_contract(description: str) -> dict[str, Any]:
    """Return deterministic structural readiness without guessing repository safety."""
    normalized = _normalize(description)
    sections = _top_sections(normalized)
    by_heading = _section_map(normalized)
    heading_counts = {
        heading: sum(1 for section in sections if section["heading"] == heading)
        for heading in PLAN_HEADINGS
    }
    qa_sections = [section for section in sections if section["heading"] == QA_HEADING[3:]]
    qa_plan_count = 0
    if len(qa_sections) == 1:
        qa_plan_count = sum(1 for heading, _ in _qa_entries(qa_sections[0]["body"]) if heading == "계획")
    missing_sections = [heading for heading in PLAN_HEADINGS if heading not in by_heading]
    duplicate_sections = [heading for heading, count in heading_counts.items() if count > 1]
    empty_sections = [
        heading
        for heading in PLAN_HEADINGS[1:]
        if heading in by_heading and not by_heading[heading]["body"].strip()
    ]

    auto_body = _without_fenced_blocks(by_heading.get(AUTO_START_HEADING, {}).get("body", ""))
    field_matches = list(FIELD_PATTERN.finditer(auto_body))
    fields = {match.group(1): match.group(2).strip() for match in field_matches}
    duplicate_fields = [
        field for field in AUTO_START_FIELDS
        if sum(1 for match in field_matches if match.group(1) == field) > 1
    ]
    missing_fields = [field for field in AUTO_START_FIELDS if not fields.get(field)]
    invalid_fields = []

    allowed_raw = fields.get("Allowed", "")
    allowed_value = allowed_raw.lower()
    allowed: bool | None
    if allowed_value in YES_VALUES:
        allowed = True
    elif allowed_value in NO_VALUES:
        allowed = False
    else:
        allowed = None
        if allowed_raw:
            invalid_fields.append("Allowed")

    prerequisites_raw = fields.get("Prerequisites", "")
    prerequisite_keys = [] if _is_none(prerequisites_raw) else [
        key.upper() for key in ISSUE_KEY_PATTERN.findall(prerequisites_raw)
    ]
    ambiguous_prerequisites = bool(
        prerequisites_raw and not _is_none(prerequisites_raw) and not prerequisite_keys
    )
    if ambiguous_prerequisites:
        invalid_fields.append("Prerequisites")

    decisions_raw = fields.get("Decisions Required", "")
    unresolved_decisions = bool(decisions_raw and not _is_none(decisions_raw))

    structural_reasons = []
    if len(qa_sections) != 1:
        structural_reasons.append("QA heading must appear exactly once")
    if qa_sections and not normalized.startswith(QA_HEADING):
        structural_reasons.append("QA heading must be the first description heading")
    if qa_plan_count != 1:
        structural_reasons.append("Korean QA plan subsection must appear exactly once")
    if missing_sections:
        structural_reasons.append("missing managed sections")
    if duplicate_sections:
        structural_reasons.append("duplicate managed sections")
    if empty_sections:
        structural_reasons.append("empty managed sections")
    if missing_fields:
        structural_reasons.append("missing Auto Start fields")
    if invalid_fields:
        structural_reasons.append("invalid Auto Start fields")
    if duplicate_fields:
        structural_reasons.append("duplicate Auto Start fields")

    structurally_complete = not structural_reasons
    if allowed is False and structurally_complete and not unresolved_decisions:
        state = "blocked"
    elif not structurally_complete or unresolved_decisions:
        state = "needs-plan"
    else:
        state = "ready"

    return {
        "version": 1,
        "state": state,
        "structurallyComplete": structurally_complete,
        "qaAtTop": normalized.startswith(QA_HEADING),
        "qaHeadingCount": len(qa_sections),
        "qaPlanCount": qa_plan_count,
        "missingSections": missing_sections,
        "duplicateSections": duplicate_sections,
        "emptySections": empty_sections,
        "autoStart": {
            "allowed": allowed,
            "allowedRaw": allowed_raw,
            "prerequisitesRaw": prerequisites_raw,
            "prerequisiteKeys": prerequisite_keys,
            "ambiguousPrerequisites": ambiguous_prerequisites,
            "decisionsRequiredRaw": decisions_raw,
            "hasUnresolvedDecisions": unresolved_decisions,
            "missingFields": missing_fields,
            "invalidFields": sorted(set(invalid_fields)),
            "duplicateFields": duplicate_fields,
        },
        "reasons": structural_reasons + (["unresolved decisions remain"] if unresolved_decisions else []),
    }


def _split_qa_and_rest(description: str) -> tuple[str, str]:
    normalized = _normalize(description)
    sections = _top_sections(normalized)
    qa_sections = [section for section in sections if section["heading"] == QA_HEADING[3:]]
    if not qa_sections:
        return "", normalized
    if len(qa_sections) != 1 or qa_sections[0]["start"] != 0:
        raise ValueError("QA heading must appear exactly once at the top before a managed update.")
    qa = qa_sections[0]
    return qa["body"].removesuffix("---").rstrip(), normalized[qa["end"]:].strip()


def _qa_entries(body: str) -> list[tuple[str, str]]:
    cleaned = re.sub(r"(?m)^---\s*$", "", body or "").strip()
    matches = _heading_spans(cleaned, 3)
    entries = []
    for index, match in enumerate(matches):
        end = matches[index + 1]["start"] if index + 1 < len(matches) else len(cleaned)
        entries.append((match["heading"], cleaned[match["heading_end"]:end].strip()))
    return entries


def _render_qa(completions: list[tuple[str, str]], plan: tuple[str, str]) -> str:
    blocks = []
    for heading, body in completions:
        blocks.append(f"### {heading}\n{body}".rstrip())
    blocks.append(f"### {plan[0]}\n{plan[1]}".rstrip())
    return f"{QA_HEADING}\n\n" + "\n\n---\n\n".join(blocks) + "\n\n---"


def _merge_qa(current_body: str, approved_body: str) -> str:
    current_entries = _qa_entries(current_body)
    approved_entries = _qa_entries(approved_body)
    approved_plan = next((entry for entry in approved_entries if entry[0] == "계획"), None)
    if approved_plan is None:
        raise ValueError("Approved description must include the Korean QA plan subsection.")

    completions: list[tuple[str, str]] = []
    seen = set()
    for entry in current_entries + approved_entries:
        if entry[0] == "계획" or entry[0] in seen:
            continue
        completions.append(entry)
        seen.add(entry[0])
    return _render_qa(completions, approved_plan)


def _unmanaged_fragments(description: str) -> list[str]:
    normalized = _normalize(description)
    sections = _top_sections(normalized)
    fragments = []
    if not sections:
        return [normalized] if normalized else []
    preamble = normalized[:sections[0]["start"]].strip()
    if preamble:
        fragments.append(preamble)
    managed = set(PLAN_HEADINGS) | LEGACY_PLAN_HEADINGS | {QA_HEADING[3:]}
    fragments.extend(section["raw"] for section in sections if section["heading"] not in managed)
    return fragments


def replace_managed_plan(current: str, approved: str) -> str:
    """Replace approved QA-plan/managed sections while preserving QA history and unknown sections."""
    contract = parse_description_contract(approved)
    if not contract["structurallyComplete"] or contract["autoStart"]["hasUnresolvedDecisions"]:
        reasons = ", ".join(contract["reasons"]) or "description is not ready"
        raise ValueError(f"Approved description does not satisfy the managed contract: {reasons}")

    current_qa, _ = _split_qa_and_rest(current)
    approved_qa, approved_rest = _split_qa_and_rest(approved)
    merged = _merge_qa(current_qa, approved_qa) + "\n\n" + approved_rest

    approved_sections = _top_sections(approved)
    approved_headings = {section["heading"] for section in approved_sections}
    preserved = []
    for fragment in _unmanaged_fragments(current):
        fragment_sections = _top_sections(fragment)
        if fragment_sections and fragment_sections[0]["heading"] in approved_headings:
            continue
        if fragment.strip() and fragment.strip() not in merged:
            preserved.append(fragment)
    if preserved:
        merged = merged.rstrip() + "\n\n" + "\n\n".join(preserved)
    return merged.rstrip() + "\n"


def prepend_qa_record(description: str, issue_key: str, record_date: str, text: str) -> str:
    """Insert or replace today's issue QA record while keeping one QA heading and the plan."""
    normalized = _normalize(description)
    current_qa, rest = _split_qa_and_rest(normalized)
    entries = _qa_entries(current_qa)
    plan = next((entry for entry in entries if entry[0] == "계획"), ("계획", "- 확인 항목:"))
    record_heading = f"{record_date} / {issue_key.upper()}"
    completions = [(record_heading, text.strip())]
    completions.extend(
        entry for entry in entries if entry[0] not in {"계획", record_heading}
    )
    updated = _render_qa(completions, plan)
    if rest:
        updated += "\n\n" + rest
    return updated.rstrip() + "\n"


def _handoff_value(value: str) -> str:
    return " ".join((value or "").split()) or "없음"


def prepend_handoff_record(
    description: str,
    issue_key: str,
    record_date: str,
    *,
    completed_work: str,
    remaining_work: str,
    branch_or_pr: str,
    validation: str,
    blocker_or_approval: str,
    resume_condition: str,
) -> str:
    """Insert one current Korean work handoff without creating a QA completion record."""
    normalized = _normalize(description)
    current_qa, rest = _split_qa_and_rest(normalized)
    entries = _qa_entries(current_qa)
    plan = next((entry for entry in entries if entry[0] == "계획"), ("계획", "- 확인 항목:"))
    issue_key = issue_key.upper()
    record_heading = f"{record_date} / {issue_key} / 작업 인계"
    record_body = "\n".join(
        (
            "- 작업 상태: 미완료",
            f"- 완료한 작업: {_handoff_value(completed_work)}",
            f"- 남은 작업: {_handoff_value(remaining_work)}",
            f"- 브랜치/PR: {_handoff_value(branch_or_pr)}",
            f"- 검증: {_handoff_value(validation)}",
            f"- 차단/승인: {_handoff_value(blocker_or_approval)}",
            f"- 재개 조건: {_handoff_value(resume_condition)}",
        )
    )

    completions = [(record_heading, record_body)]
    for entry in entries:
        if entry[0] == "계획":
            continue
        match = HANDOFF_PATTERN.match(entry[0])
        if match and match.group(1).upper() == issue_key:
            continue
        completions.append(entry)

    updated = _render_qa(completions, plan)
    if rest:
        updated += "\n\n" + rest
    return updated.rstrip() + "\n"


def has_handoff_record(description: str, issue_key: str) -> bool:
    try:
        qa_body, _ = _split_qa_and_rest(description)
    except ValueError:
        return False
    expected = issue_key.upper()
    for heading, _ in _qa_entries(qa_body):
        match = HANDOFF_PATTERN.match(heading)
        if match and match.group(1).upper() == expected:
            return True
    return False


def has_qa_completion_record(description: str, issue_key: str) -> bool:
    try:
        qa_body, _ = _split_qa_and_rest(description)
    except ValueError:
        return False
    expected = issue_key.upper()
    for heading, _ in _qa_entries(qa_body):
        match = QA_COMPLETION_PATTERN.match(heading)
        if match and match.group(1).upper() == expected:
            return True
    return False


def validate_qa_completion_record(description: str, issue_key: str) -> list[str]:
    """Return deterministic errors for the issue's latest structured Korean QA record."""
    try:
        qa_body, _ = _split_qa_and_rest(description)
    except ValueError:
        return ["QA heading must appear exactly once at the top"]
    expected = issue_key.upper()
    matching = []
    for heading, body in _qa_entries(qa_body):
        match = QA_COMPLETION_PATTERN.match(heading)
        if match and match.group(1).upper() == expected:
            matching.append(body)
    if len(matching) != 1:
        return [f"exactly one completion record is required for {expected}"]

    values: dict[str, str] = {}
    duplicates: set[str] = set()
    field_pattern = re.compile(
        r"^\s*-\s*(변경 요약|검증 결과|미검증 항목|QA 확인 항목|위험 영역)\s*:\s*(.*?)\s*$"
    )
    for line in matching[0].splitlines():
        match = field_pattern.match(line)
        if not match:
            continue
        field = match.group(1)
        if field in values:
            duplicates.add(field)
        values[field] = match.group(2).strip()

    errors = []
    for field in QA_COMPLETION_FIELDS:
        if field in duplicates:
            errors.append(f"duplicate field: {field}")
        elif not values.get(field):
            errors.append(f"missing or empty field: {field}")
    if values.get("미검증 항목", "").rstrip(".").strip() != "없음":
        errors.append("미검증 항목 must be 없음 before completion")
    return errors

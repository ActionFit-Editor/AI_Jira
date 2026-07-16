from __future__ import annotations

import json
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
APPROVAL_REFERENCE = PACKAGE_ROOT / "Skills~" / "Shared" / "references" / "korean-approval-preview.md"
APPROVAL_FIXTURE = PACKAGE_ROOT / "Tests~" / "Fixtures~" / "korean_approval_preview.json"


class JiraActionSkillTests(unittest.TestCase):
    def test_manifest_registers_new_write_capable_skills_for_both_agents(self) -> None:
        manifest = json.loads((PACKAGE_ROOT / "Skills~" / "manifest.json").read_text(encoding="utf-8"))
        by_name = {skill["name"]: skill for skill in manifest["skills"]}

        for name in ("jira-plan", "jira-auto-start", "jira-run"):
            self.assertEqual("write-capable", by_name[name]["access"])
            self.assertEqual({"codex", "claude"}, set(by_name[name]["agents"]))
            self.assertTrue(by_name[name]["includeShared"])

    def test_shared_korean_approval_reference_owns_dual_representation_contract(self) -> None:
        contents = APPROVAL_REFERENCE.read_text(encoding="utf-8")

        for storage, preview in (
            ("`## Auto Start`", "`## 자동 착수`"),
            ("`Allowed`", "`허용 여부`"),
            ("`Prerequisites`", "`선행 작업`"),
            ("`Decisions Required`", "`결정 필요 사항`"),
            ("`## Goal`", "`## 목표`"),
            ("`## Scope`", "`## 범위`"),
            ("`## Out of Scope`", "`## 제외 범위`"),
            ("`## Completion Criteria`", "`## 완료 기준`"),
            ("`## Validation Plan`", "`## 검증 계획`"),
            ("`## Dependencies and Risks`", "`## 의존성과 위험`"),
        ):
            self.assertIn(storage, contents)
            self.assertIn(preview, contents)

        self.assertIn("Prepare the complete canonical storage title and description first", contents)
        self.assertIn("Never translate the Korean preview back into a Jira payload", contents)
        self.assertIn("Do not show the English storage body by default", contents)
        self.assertIn("Regenerate the complete Korean approval preview", contents)
        self.assertIn("context compaction", contents)

    def test_every_planning_entry_point_reads_shared_approval_reference(self) -> None:
        for agent in ("Codex", "Claude"):
            for name in ("jira-plan", "jira-auto-start", "jira-run"):
                contents = self._read_skill(agent, name)

                self.assertIn("references/korean-approval-preview.md", contents)
                self.assertIn("canonical", contents.lower())
                self.assertIn("Korean approval view", contents)
                self.assertIn("regenerate", contents.lower())

    def test_auto_start_classifies_all_todo_and_handles_planning_lock(self) -> None:
        for agent, helper in (("Codex", ".agents"), ("Claude", ".claude")):
            contents = self._read_skill(agent, "jira-auto-start")

            self.assertIn(
                f"python3 {helper}/skills/jira-auto-start/scripts/ai_jira_cli.py list --state todo --format json",
                contents,
            )
            self.assertIn(
                f"python3 {helper}/skills/jira-auto-start/scripts/ai_jira_cli.py list --state progress --format json",
                contents,
            )
            self.assertNotIn("list --state all", contents)
            self.assertIn("exactly one", contents)
            self.assertIn("first startable", contents.lower())
            self.assertIn("needs-plan", contents)
            self.assertIn("blocked", contents)
            self.assertIn("approval-required", contents)
            self.assertIn("descriptionContract", contents)
            self.assertIn("planning lock", contents.lower())
            self.assertIn("replace-plan", contents)
            self.assertIn("expected-updated", contents)
            self.assertIn("configuredStatuses.done", contents)
            self.assertIn("every todo", contents)
            self.assertIn("prerequisite", contents.lower())
            self.assertIn("transition", contents.lower())
            self.assertIn("pull request", contents.lower())

    def test_plan_requires_full_draft_approval_and_stops_before_implementation(self) -> None:
        for agent in ("Codex", "Claude"):
            contents = self._read_skill(agent, "jira-plan")

            self.assertIn("## QA 확인 필요 사항", contents)
            self.assertIn("## Auto Start", contents)
            self.assertIn("## Goal", contents)
            self.assertIn("## Completion Criteria", contents)
            self.assertIn("## Validation Plan", contents)
            self.assertIn("Korean", contents)
            self.assertIn("English", contents)
            self.assertIn("explicit", contents.lower())
            self.assertIn("Tools/AI/jira/create_issue.py", contents)
            self.assertIn("--description-file", contents)
            self.assertIn("replace-plan", contents)
            self.assertIn("planning lock", contents.lower())
            self.assertIn("Leave the issue in todo", contents)
            self.assertIn("do not implement", contents.lower())

    def test_run_skills_require_verified_qa_and_pr_for_done(self) -> None:
        for agent in ("Codex", "Claude"):
            contents = self._read_skill(agent, "jira-run")

            self.assertIn("descriptionContract", contents)
            self.assertIn("replace-plan", contents)
            self.assertIn("planning lock", contents.lower())
            self.assertIn("QA", contents)
            self.assertIn("PR URL", contents)

    def test_run_and_auto_start_announce_and_verify_visible_jira_identity(self) -> None:
        for agent in ("Codex", "Claude"):
            for name in ("jira-run", "jira-auto-start"):
                contents = self._read_skill(agent, name)

                self.assertIn("`🎫 Jira: <ISSUE-KEY>`", contents)
                self.assertIn("before any Jira write, worktree preparation, or repository mutation", contents)
                self.assertIn("planned canonical branch name contains the exact selected issue key", contents)
                self.assertIn("actual checked-out branch", contents)
                self.assertIn("before repository edits", contents.lower())

    def test_package_docs_explain_codex_terminal_title_boundary(self) -> None:
        for path in (PACKAGE_ROOT / "README.md", PACKAGE_ROOT / "AI_GUIDE.md"):
            contents = path.read_text(encoding="utf-8")

            self.assertIn('terminal_title = ["spinner", "git-branch", "project"]', contents)
            self.assertIn("full", contents.lower())
            self.assertIn("branch", contents.lower())
            self.assertIn("raw OSC", contents)
            self.assertIn("Planning", contents)
            self.assertIn("read-only", contents)

    def test_help_skills_explain_visible_identity_configuration(self) -> None:
        for agent in ("Codex", "Claude"):
            contents = self._read_skill(agent, "jira-help")

            self.assertIn("`🎫 Jira: <ISSUE-KEY>`", contents)
            self.assertIn('terminal_title = ["spinner", "git-branch", "project"]', contents)
            self.assertIn("key-only extraction", contents)
            self.assertIn("raw OSC", contents)

    def test_representative_approval_fixtures_preserve_complete_korean_view_and_payload_source(self) -> None:
        fixture = json.loads(APPROVAL_FIXTURE.read_text(encoding="utf-8"))
        canonical = fixture["canonicalDraft"]
        preview = fixture["koreanApprovalView"]

        for heading in (
            "## 자동 착수",
            "## 목표",
            "## 범위",
            "## 제외 범위",
            "## 완료 기준",
            "## 검증 계획",
            "## 의존성과 위험",
        ):
            self.assertIn(heading, preview)

        for field in ("허용 여부: 예", "선행 작업: MCC-1500", "결정 필요 사항: 없음"):
            self.assertIn(field, preview)

        for identifier in (
            "MCC-1500",
            "Packages/com.actionfit.ai-jira/Skills~/Shared/references/korean-approval-preview.md",
            "Tools/AI/jira/update_description.py",
            "update_description.py --mode replace-plan",
            "python3 -m unittest discover -s Packages/com.actionfit.ai-jira/Tests~ -p 'test_*.py'",
        ):
            self.assertIn(identifier, canonical["description"])
            self.assertIn(identifier, preview)

        scenarios = {scenario["name"]: scenario for scenario in fixture["scenarios"]}
        self.assertEqual(
            {
                "new_issue",
                "plan_only_refinement",
                "plan_update_and_auto_start",
                "revision_request",
                "interrupted_canonical_state",
            },
            set(scenarios),
        )
        for name in ("new_issue", "plan_only_refinement", "plan_update_and_auto_start"):
            self.assertTrue(scenarios[name]["writeAllowed"])
            self.assertEqual("canonicalDraft", scenarios[name]["writePayloadSource"])

        for name in ("revision_request", "interrupted_canonical_state"):
            self.assertFalse(scenarios[name]["writeAllowed"])
            self.assertFalse(scenarios[name]["previousApprovalValid"])

        self.assertIn("제외해줘", scenarios["revision_request"]["userInput"])
        self.assertEqual("regenerate-and-reapprove", scenarios["revision_request"]["approvedAction"])
        self.assertFalse(scenarios["interrupted_canonical_state"]["canonicalAvailable"])
        self.assertIn("context compaction", scenarios["interrupted_canonical_state"]["recoveryEvidence"])

    def test_codex_write_skills_disable_implicit_invocation(self) -> None:
        for name in ("jira-plan", "jira-auto-start", "jira-run"):
            path = PACKAGE_ROOT / "Skills~" / "Codex" / name / "agents" / "openai.yaml"
            metadata = path.read_text(encoding="utf-8")

            self.assertIn("allow_implicit_invocation: false", metadata)

    def test_claude_write_skills_disable_model_invocation(self) -> None:
        for name in ("jira-plan", "jira-auto-start", "jira-run"):
            contents = self._read_skill("Claude", name)
            self.assertIn("disable-model-invocation: true", contents)

    @staticmethod
    def _read_skill(agent: str, name: str) -> str:
        path = PACKAGE_ROOT / "Skills~" / agent / name / "SKILL.md"
        return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

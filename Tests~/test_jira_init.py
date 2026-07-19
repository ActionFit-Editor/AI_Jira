from __future__ import annotations

import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PACKAGE_ROOT / "Tools~"
sys.path.insert(0, str(TOOLS_DIR))

import jira_init


class FakeResponse:
    def __init__(self, value: dict) -> None:
        self.payload = json.dumps(value).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class JiraInitTests(unittest.TestCase):
    def test_setup_creates_protected_no_secret_template_and_local_ignore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._create_project(Path(directory))
            config_path = root / jira_init.DEFAULT_CONFIG

            result = jira_init.initialize_setup(root, config_path, open_folder=False)

            self.assertTrue(result["success"])
            self.assertTrue(result["configCreated"])
            self.assertEqual("SETUP_INPUT_REQUIRED", result["code"])
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual("", config["auth"]["email"])
            self.assertEqual("", config["auth"]["api_token"])
            self.assertEqual("JIRA_API_TOKEN", config["auth"]["api_token_env"])
            self.assertTrue(config["automation"]["dry_run"])
            if os.name != "nt":
                self.assertEqual(0o600, stat.S_IMODE(config_path.stat().st_mode))

            exclude_path = self._git_path(root, "info/exclude")
            self.assertIn("/Tools/AI/jira/config.local.json", exclude_path.read_text(encoding="utf-8"))
            self.assertEqual("CONFIG_INCOMPLETE", result["diagnosis"]["code"])

    def test_setup_preserves_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._create_project(Path(directory))
            config_path = root / jira_init.DEFAULT_CONFIG
            config_path.parent.mkdir(parents=True)
            original = self._config()
            config_path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")

            result = jira_init.initialize_setup(root, config_path, open_folder=False)

            self.assertTrue(result["success"])
            self.assertFalse(result["configCreated"])
            self.assertTrue(result["configPreserved"])
            self.assertEqual(original, json.loads(config_path.read_text(encoding="utf-8")))

    def test_setup_blocks_a_tracked_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._create_project(Path(directory))
            config_path = root / jira_init.DEFAULT_CONFIG
            config_path.parent.mkdir(parents=True)
            config_path.write_text(json.dumps(self._config()), encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(root), "add", "Tools/AI/jira/config.local.json"],
                check=True,
                capture_output=True,
            )

            result = jira_init.initialize_setup(root, config_path, open_folder=False)

            self.assertFalse(result["success"])
            self.assertEqual("CONFIG_TRACKED", result["code"])

    def test_connection_check_verifies_auth_and_project_without_exposing_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._create_project(Path(directory))
            config_path = root / jira_init.DEFAULT_CONFIG
            config_path.parent.mkdir(parents=True)
            config = self._config()
            config["auth"] = {"email": "developer@example.com", "api_token": "secret-token"}
            config_path.write_text(json.dumps(config), encoding="utf-8")

            with patch.object(
                jira_init,
                "urlopen",
                side_effect=[FakeResponse({"accountId": "account"}), FakeResponse({"issues": []})],
            ):
                result = jira_init.diagnose_connection(root, config_path)

            rendered = json.dumps(result)
            self.assertTrue(result["connected"])
            self.assertEqual("CONNECTED", result["code"])
            self.assertEqual("IF", result["project"])
            self.assertEqual("local-config", result["tokenSource"])
            self.assertNotIn("secret-token", rendered)
            self.assertNotIn("developer@example.com", rendered)

    def test_authentication_failure_does_not_echo_response_body(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._create_project(Path(directory))
            config_path = root / jira_init.DEFAULT_CONFIG
            config_path.parent.mkdir(parents=True)
            config = self._config()
            config["auth"] = {"email": "developer@example.com", "api_token": "secret-token"}
            config_path.write_text(json.dumps(config), encoding="utf-8")
            error = HTTPError(
                "https://example.atlassian.net/rest/api/3/myself",
                401,
                "Unauthorized",
                {},
                io.BytesIO(b"secret-token must never be echoed"),
            )

            with patch.object(jira_init, "urlopen", side_effect=error):
                result = jira_init.diagnose_connection(root, config_path)

            rendered = json.dumps(result)
            self.assertEqual("AUTHENTICATION_FAILED", result["code"])
            self.assertEqual("authentication", result["stage"])
            self.assertNotIn("secret-token", rendered)

    def test_misplaced_credentials_are_diagnosed_without_echoing_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._create_project(Path(directory))
            config_path = root / jira_init.DEFAULT_CONFIG
            config_path.parent.mkdir(parents=True)
            config = self._config()
            config["auth"] = {
                "email_env": "developer@example.com",
                "api_token_env": "secret-token-value",
            }
            config_path.write_text(json.dumps(config), encoding="utf-8")

            with patch.object(jira_init, "urlopen") as request:
                result = jira_init.diagnose_connection(root, config_path)

            rendered = json.dumps(result)
            self.assertEqual("CREDENTIALS_MISPLACED", result["code"])
            self.assertEqual(
                ["auth.email_env", "auth.api_token_env"], result["misplacedFields"]
            )
            self.assertEqual(["auth.email", "auth.api_token"], result["expectedFields"])
            self.assertFalse(result["connectionChecked"])
            request.assert_not_called()
            self.assertNotIn("secret-token-value", rendered)
            self.assertNotIn("developer@example.com", rendered)

    def test_skill_sources_document_setup_token_and_manual_invocation(self) -> None:
        for agent, root_name in (("Codex", ".agents"), ("Claude", ".claude")):
            contents = (PACKAGE_ROOT / "Skills~" / agent / "jira-init" / "SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                f"python3 {root_name}/skills/jira-init/scripts/ai_jira_init.py status --format json",
                contents,
            )
            self.assertIn("setup --open-folder --format json", contents)
            self.assertIn(jira_init.TOKEN_URL, contents)
            self.assertIn("CONFIG_TRACKED", contents)
            self.assertIn("AUTHENTICATION_FAILED", contents)
            self.assertIn("CREDENTIALS_MISPLACED", contents)
            self.assertIn("read-only", contents)

        codex_metadata = (
            PACKAGE_ROOT / "Skills~" / "Codex" / "jira-init" / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")
        claude_skill = (
            PACKAGE_ROOT / "Skills~" / "Claude" / "jira-init" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("allow_implicit_invocation: false", codex_metadata)
        self.assertIn("disable-model-invocation: true", claude_skill)

        manifest = json.loads((PACKAGE_ROOT / "Skills~" / "manifest.json").read_text(encoding="utf-8"))
        registration = {entry["name"]: entry for entry in manifest["skills"]}["jira-init"]
        self.assertEqual("write-capable", registration["access"])
        self.assertEqual({"codex", "claude"}, set(registration["agents"]))
        self.assertTrue(registration["includeShared"])

    @staticmethod
    def _create_project(root: Path) -> Path:
        packages = root / "Packages"
        packages.mkdir(parents=True)
        (packages / "manifest.json").write_text('{"dependencies": {}}\n', encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
        return root

    @staticmethod
    def _git_path(root: Path, relative: str) -> Path:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-path", relative],
            check=True,
            capture_output=True,
            text=True,
        )
        path = Path(result.stdout.strip())
        return path if path.is_absolute() else root / path

    @staticmethod
    def _config() -> dict:
        return {
            "jira_base_url": "https://example.atlassian.net",
            "project_key": "IF",
            "statuses": {
                "todo": "해야 할 일",
                "progress": "개발 진행 중",
                "done": "개발 완료",
            },
            "auth": {
                "email_env": "JIRA_EMAIL",
                "api_token_env": "JIRA_API_TOKEN",
            },
        }


if __name__ == "__main__":
    unittest.main()

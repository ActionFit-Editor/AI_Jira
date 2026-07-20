from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
LOCATOR_PATH = PACKAGE_ROOT / "Skills~" / "Shared" / "scripts" / "ai_jira_write_cli.py"


def load_locator():
    spec = importlib.util.spec_from_file_location("ai_jira_write_cli_under_test", LOCATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load AI Jira write locator for tests.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AiJiraWriteCliTests(unittest.TestCase):
    def test_embedded_package_tools_are_preferred(self) -> None:
        locator = load_locator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "Packages").mkdir()
            (root / "Packages" / "manifest.json").write_text("{}", encoding="utf-8")
            embedded = root / "Packages" / "com.actionfit.ai-jira" / "Tools~"
            embedded.mkdir(parents=True)
            cached = root / "Library" / "PackageCache" / "com.actionfit.ai-jira@hash" / "Tools~"
            cached.mkdir(parents=True)

            self.assertEqual(root, locator.find_project_root(embedded))
            self.assertEqual(embedded, locator.find_tools(root))

    def test_package_cache_tools_are_used_when_package_is_downloaded(self) -> None:
        locator = load_locator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "Packages").mkdir()
            (root / "Packages" / "manifest.json").write_text("{}", encoding="utf-8")
            cached = root / "Library" / "PackageCache" / "com.actionfit.ai-jira@hash" / "Tools~"
            cached.mkdir(parents=True)

            self.assertEqual(cached, locator.find_tools(root))

    def test_every_command_dispatches_to_package_owned_script(self) -> None:
        locator = load_locator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "Packages").mkdir()
            (root / "Packages" / "manifest.json").write_text("{}", encoding="utf-8")
            tools = root / "Packages" / "com.actionfit.ai-jira" / "Tools~"
            tools.mkdir(parents=True)
            for script_name in locator.COMMAND_SCRIPTS.values():
                (tools / script_name).write_text("", encoding="utf-8")

            for command_name, script_name in locator.COMMAND_SCRIPTS.items():
                with self.subTest(command=command_name):
                    with patch.object(locator.Path, "cwd", return_value=root), patch.object(
                        locator.subprocess, "call", return_value=0
                    ) as subprocess_call, patch.object(
                        sys, "argv", [str(LOCATOR_PATH), command_name, "--help"]
                    ):
                        with self.assertRaises(SystemExit) as raised:
                            locator.main()

                    self.assertEqual(0, raised.exception.code)
                    subprocess_call.assert_called_once_with(
                        [sys.executable, str(tools / script_name), "--help"],
                        cwd=root,
                    )


if __name__ == "__main__":
    unittest.main()

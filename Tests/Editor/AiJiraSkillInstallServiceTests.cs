#if UNITY_EDITOR
using System;
using System.IO;
using NUnit.Framework;

namespace ActionFit.AiJira.Editor.Tests
{
    public class AiJiraSkillInstallServiceTests
    {
        private string _root;
        private string _sourceRoot;
        private string _projectRoot;
        private string _statePath;
        private string _tempRoot;

        [SetUp]
        public void SetUp()
        {
            _root = Path.Combine(Path.GetTempPath(), "AiJiraSkillTests", Guid.NewGuid().ToString("N"));
            _sourceRoot = Path.Combine(_root, "package", "Skills~");
            _projectRoot = Path.Combine(_root, "project");
            _statePath = Path.Combine(_projectRoot, "UserSettings", "AIJira", "skill-install-state.json");
            _tempRoot = Path.Combine(_projectRoot, "Temp", "AIJiraSkills");
            Directory.CreateDirectory(_projectRoot);

            WriteSource("Codex", "jira-todo", "codex todo");
            WriteSource("Codex", "jira-run", "codex run");
            WriteSource("Claude", "jira-todo", "claude todo");
            WriteSource("Claude", "jira-run", "claude run");
            WriteFile(Path.Combine(_sourceRoot, "Shared", "scripts", "ai_jira_cli.py"), "shared helper");
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_root)) Directory.Delete(_root, true);
        }

        [Test]
        public void FirstInstallAndRepeatAreIdempotent()
        {
            AiJiraSkillInstallResult first = Install();
            AiJiraSkillInstallResult second = Install();

            Assert.That(first.Installed, Is.EqualTo(4));
            Assert.That(second.Unchanged, Is.EqualTo(4));
            Assert.That(second.Installed + second.Updated, Is.Zero);
            Assert.That(File.ReadAllText(Target(".agents", "jira-todo", "scripts", "ai_jira_cli.py")),
                Is.EqualTo("shared helper"));
        }

        [Test]
        public void PackageUpdateRefreshesOnlyUnmodifiedManagedSkill()
        {
            Install();
            WriteSource("Codex", "jira-todo", "updated todo");

            AiJiraSkillInstallResult result = Install();

            Assert.That(result.Updated, Is.EqualTo(1));
            Assert.That(result.Unchanged, Is.EqualTo(3));
            Assert.That(File.ReadAllText(Target(".agents", "jira-todo", "SKILL.md")),
                Is.EqualTo("updated todo"));
        }

        [Test]
        public void UserModifiedTargetIsPreservedDuringRefresh()
        {
            Install();
            string target = Target(".agents", "jira-run", "SKILL.md");
            File.WriteAllText(target, "user customization");
            WriteSource("Codex", "jira-run", "package update");

            AiJiraSkillInstallResult result = Install();

            Assert.That(result.Warnings, Has.Count.EqualTo(1));
            Assert.That(File.ReadAllText(target), Is.EqualTo("user customization"));
        }

        [Test]
        public void MissingManagedTargetIsRestored()
        {
            Install();
            Directory.Delete(Target(".claude", "jira-todo"), true);

            AiJiraSkillInstallResult result = Install();

            Assert.That(result.Installed, Is.EqualTo(1));
            Assert.That(File.Exists(Target(".claude", "jira-todo", "SKILL.md")), Is.True);
        }

        [Test]
        public void RemoveDeletesOnlyUnchangedManagedTargets()
        {
            Install();
            string modified = Target(".claude", "jira-run", "SKILL.md");
            File.WriteAllText(modified, "keep me");

            AiJiraSkillInstallResult result = AiJiraSkillInstallService.RemoveManaged(
                _projectRoot, _statePath, _tempRoot);

            Assert.That(result.Removed, Is.EqualTo(3));
            Assert.That(result.Warnings, Has.Count.EqualTo(1));
            Assert.That(File.ReadAllText(modified), Is.EqualTo("keep me"));
            Assert.That(Directory.Exists(Target(".agents", "jira-todo")), Is.False);
            Assert.That(AiJiraSkillInstallService.IsAutoInstallEnabled(_statePath), Is.False);

            Install();
            Assert.That(AiJiraSkillInstallService.IsAutoInstallEnabled(_statePath), Is.True);
        }

        [Test]
        public void ExistingUnmanagedTargetIsNeverAdoptedOrOverwritten()
        {
            string target = Target(".agents", "jira-todo", "SKILL.md");
            WriteFile(target, "existing user skill");

            AiJiraSkillInstallResult result = Install();

            Assert.That(result.Installed, Is.EqualTo(3));
            Assert.That(result.Warnings, Has.Count.EqualTo(1));
            Assert.That(File.ReadAllText(target), Is.EqualTo("existing user skill"));
        }

        [Test]
        public void FileAtTargetPathIsPreserved()
        {
            string target = Target(".agents", "jira-todo");
            WriteFile(target, "existing file");

            AiJiraSkillInstallResult result = Install();

            Assert.That(result.Installed, Is.EqualTo(3));
            Assert.That(result.Warnings, Has.Count.EqualTo(1));
            Assert.That(File.ReadAllText(target), Is.EqualTo("existing file"));
        }

        private AiJiraSkillInstallResult Install()
        {
            return AiJiraSkillInstallService.InstallOrRefresh(
                _sourceRoot, _projectRoot, _statePath, _tempRoot);
        }

        private void WriteSource(string agent, string skill, string contents)
        {
            WriteFile(Path.Combine(_sourceRoot, agent, skill, "SKILL.md"), contents);
        }

        private string Target(string agentDirectory, string skill, params string[] children)
        {
            string path = Path.Combine(_projectRoot, agentDirectory, "skills", skill);
            foreach (string child in children) path = Path.Combine(path, child);
            return path;
        }

        private static void WriteFile(string path, string contents)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path) ?? throw new InvalidOperationException());
            File.WriteAllText(path, contents);
        }
    }
}
#endif

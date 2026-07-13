#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace ActionFit.AiJira.Editor
{
    public sealed class AiJiraSkillInstallResult
    {
        public int Installed { get; internal set; }
        public int Updated { get; internal set; }
        public int Removed { get; internal set; }
        public int Unchanged { get; internal set; }
        public List<string> Warnings { get; } = new List<string>();
    }

    public static class AiJiraSkillInstallService
    {
        private const string SharedSource = "Shared";

        private static readonly SkillTarget[] Targets =
        {
            new SkillTarget("Codex/jira-help", ".agents/skills/jira-help"),
            new SkillTarget("Codex/jira-todo", ".agents/skills/jira-todo"),
            new SkillTarget("Codex/jira-run", ".agents/skills/jira-run"),
            new SkillTarget("Claude/jira-help", ".claude/skills/jira-help"),
            new SkillTarget("Claude/jira-todo", ".claude/skills/jira-todo"),
            new SkillTarget("Claude/jira-run", ".claude/skills/jira-run"),
        };

        public static AiJiraSkillInstallResult InstallOrRefresh(
            string sourceRoot,
            string projectRoot,
            string statePath,
            string tempRoot)
        {
            ValidateRoots(sourceRoot, projectRoot);
            Directory.CreateDirectory(tempRoot);
            SkillInstallState state = LoadState(statePath);
            state.autoInstallEnabled = 1;
            var result = new AiJiraSkillInstallResult();

            try
            {
                foreach (SkillTarget target in Targets)
                {
                    string sourcePath = Path.Combine(sourceRoot, target.SourceRelativePath);
                    if (!Directory.Exists(sourcePath))
                    {
                        result.Warnings.Add($"Package skill source was not found: {sourcePath}");
                        continue;
                    }

                    string stagedPath = Path.Combine(tempRoot, "stage-" + Guid.NewGuid().ToString("N"));
                    BuildStagedSkill(sourcePath, Path.Combine(sourceRoot, SharedSource), stagedPath);
                    string stagedHash = ComputeDirectoryHash(stagedPath);
                    string targetPath = Path.Combine(projectRoot, target.TargetRelativePath);
                    SkillInstallEntry entry = state.Find(target.TargetRelativePath);

                    if (File.Exists(targetPath))
                    {
                        Directory.Delete(stagedPath, true);
                        result.Warnings.Add($"Preserved file at skill target path: {target.TargetRelativePath}");
                        continue;
                    }

                    if (!Directory.Exists(targetPath))
                    {
                        state.Set(target.TargetRelativePath, stagedHash);
                        // Recording ownership first is safe because a missing target can always be retried.
                        SaveState(statePath, state);
                        ReplaceDirectory(stagedPath, targetPath, tempRoot);
                        result.Installed++;
                        continue;
                    }

                    if (IsReparsePoint(targetPath))
                    {
                        Directory.Delete(stagedPath, true);
                        result.Warnings.Add($"Preserved linked skill directory: {target.TargetRelativePath}");
                        continue;
                    }

                    string currentHash = ComputeDirectoryHash(targetPath);
                    if (entry == null)
                    {
                        Directory.Delete(stagedPath, true);
                        result.Warnings.Add($"Preserved user-managed or modified skill: {target.TargetRelativePath}");
                        continue;
                    }

                    if (!string.Equals(currentHash, entry.installedHash, StringComparison.Ordinal))
                    {
                        if (string.Equals(currentHash, stagedHash, StringComparison.Ordinal))
                        {
                            // Recover ownership after a prior target replacement succeeded but state saving failed.
                            state.Set(target.TargetRelativePath, stagedHash);
                            Directory.Delete(stagedPath, true);
                            result.Unchanged++;
                            continue;
                        }

                        Directory.Delete(stagedPath, true);
                        result.Warnings.Add($"Preserved user-managed or modified skill: {target.TargetRelativePath}");
                        continue;
                    }

                    if (string.Equals(currentHash, stagedHash, StringComparison.Ordinal))
                    {
                        Directory.Delete(stagedPath, true);
                        result.Unchanged++;
                        continue;
                    }

                    ReplaceDirectory(stagedPath, targetPath, tempRoot);
                    state.Set(target.TargetRelativePath, stagedHash);
                    result.Updated++;
                }

                SaveState(statePath, state);
                return result;
            }
            finally
            {
                DeleteStagingDirectories(tempRoot);
                DeleteDirectoryIfEmpty(tempRoot);
            }
        }

        public static AiJiraSkillInstallResult RemoveManaged(
            string projectRoot,
            string statePath,
            string tempRoot)
        {
            if (string.IsNullOrWhiteSpace(projectRoot)) throw new ArgumentException("Project root is required.");
            SkillInstallState state = LoadState(statePath);
            state.autoInstallEnabled = 0;
            var result = new AiJiraSkillInstallResult();

            foreach (SkillTarget target in Targets)
            {
                string targetPath = Path.Combine(projectRoot, target.TargetRelativePath);
                SkillInstallEntry entry = state.Find(target.TargetRelativePath);
                if (entry == null || !Directory.Exists(targetPath)) continue;

                if (IsReparsePoint(targetPath))
                {
                    result.Warnings.Add($"Preserved linked skill directory during removal: {target.TargetRelativePath}");
                    continue;
                }

                string currentHash = ComputeDirectoryHash(targetPath);
                if (!string.Equals(currentHash, entry.installedHash, StringComparison.Ordinal))
                {
                    result.Warnings.Add($"Preserved modified skill during removal: {target.TargetRelativePath}");
                    continue;
                }

                Directory.Delete(targetPath, true);
                state.Remove(target.TargetRelativePath);
                result.Removed++;
                DeleteDirectoryIfEmpty(Path.GetDirectoryName(targetPath));
            }

            SaveState(statePath, state);
            DeleteDirectoryIfEmpty(tempRoot);
            return result;
        }

        public static bool IsAutoInstallEnabled(string statePath)
        {
            return !File.Exists(statePath) || LoadState(statePath).autoInstallEnabled != 0;
        }

        public static string ComputeDirectoryHash(string directory)
        {
            if (!Directory.Exists(directory)) return string.Empty;
            using var payload = new MemoryStream();
            foreach (string path in Directory.GetFiles(directory, "*", SearchOption.AllDirectories)
                         .OrderBy(value => value, StringComparer.Ordinal))
            {
                string relativePath = path.Substring(directory.Length).TrimStart(Path.DirectorySeparatorChar)
                    .Replace(Path.DirectorySeparatorChar, '/');
                byte[] nameBytes = Encoding.UTF8.GetBytes(relativePath + "\n");
                payload.Write(nameBytes, 0, nameBytes.Length);
                byte[] lengthBytes = BitConverter.GetBytes(new FileInfo(path).Length);
                payload.Write(lengthBytes, 0, lengthBytes.Length);
                byte[] contentBytes = File.ReadAllBytes(path);
                payload.Write(contentBytes, 0, contentBytes.Length);
            }
            using SHA256 hash = SHA256.Create();
            return BitConverter.ToString(hash.ComputeHash(payload.ToArray()))
                .Replace("-", string.Empty).ToLowerInvariant();
        }

        private static bool IsReparsePoint(string path)
        {
            return (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0;
        }

        private static void ValidateRoots(string sourceRoot, string projectRoot)
        {
            if (string.IsNullOrWhiteSpace(sourceRoot) || !Directory.Exists(sourceRoot))
            {
                throw new DirectoryNotFoundException($"Skill source root was not found: {sourceRoot}");
            }
            if (string.IsNullOrWhiteSpace(projectRoot) || !Directory.Exists(projectRoot))
            {
                throw new DirectoryNotFoundException($"Project root was not found: {projectRoot}");
            }
        }

        private static void BuildStagedSkill(string sourcePath, string sharedPath, string stagedPath)
        {
            CopyDirectory(sourcePath, stagedPath);
            if (Directory.Exists(sharedPath)) CopyDirectory(sharedPath, stagedPath);
        }

        private static void CopyDirectory(string source, string destination)
        {
            Directory.CreateDirectory(destination);
            foreach (string directory in Directory.GetDirectories(source, "*", SearchOption.AllDirectories))
            {
                Directory.CreateDirectory(Path.Combine(destination, directory.Substring(source.Length + 1)));
            }
            foreach (string file in Directory.GetFiles(source, "*", SearchOption.AllDirectories))
            {
                string destinationPath = Path.Combine(destination, file.Substring(source.Length + 1));
                Directory.CreateDirectory(Path.GetDirectoryName(destinationPath) ?? destination);
                File.Copy(file, destinationPath, true);
            }
        }

        private static void ReplaceDirectory(string stagedPath, string targetPath, string tempRoot)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(targetPath) ?? throw new InvalidOperationException());
            if (!Directory.Exists(targetPath))
            {
                Directory.Move(stagedPath, targetPath);
                return;
            }

            string backupPath = Path.Combine(tempRoot, "backup-" + Guid.NewGuid().ToString("N"));
            Directory.Move(targetPath, backupPath);
            try
            {
                Directory.Move(stagedPath, targetPath);
                Directory.Delete(backupPath, true);
            }
            catch
            {
                if (Directory.Exists(targetPath)) Directory.Delete(targetPath, true);
                if (Directory.Exists(backupPath)) Directory.Move(backupPath, targetPath);
                throw;
            }
        }

        private static SkillInstallState LoadState(string statePath)
        {
            if (!File.Exists(statePath)) return new SkillInstallState();
            try
            {
                return JsonUtility.FromJson<SkillInstallState>(File.ReadAllText(statePath, Encoding.UTF8))
                       ?? new SkillInstallState();
            }
            catch (Exception exception)
            {
                Debug.LogWarning($"[AI Jira] Ignoring invalid managed-skill state: {exception.Message}");
                return new SkillInstallState();
            }
        }

        private static void SaveState(string statePath, SkillInstallState state)
        {
            string directory = Path.GetDirectoryName(statePath) ?? throw new InvalidOperationException();
            Directory.CreateDirectory(directory);
            string temporaryPath = statePath + ".tmp";
            File.WriteAllText(temporaryPath, JsonUtility.ToJson(state, true), new UTF8Encoding(false));
            if (File.Exists(statePath)) File.Delete(statePath);
            File.Move(temporaryPath, statePath);
        }

        private static void DeleteDirectoryIfEmpty(string path)
        {
            if (!string.IsNullOrWhiteSpace(path) && Directory.Exists(path)
                && !Directory.EnumerateFileSystemEntries(path).Any())
            {
                Directory.Delete(path);
            }
        }

        private static void DeleteStagingDirectories(string tempRoot)
        {
            if (!Directory.Exists(tempRoot)) return;
            foreach (string path in Directory.GetDirectories(tempRoot, "stage-*", SearchOption.TopDirectoryOnly))
            {
                Directory.Delete(path, true);
            }
        }

        [Serializable]
        private sealed class SkillInstallState
        {
            public int autoInstallEnabled = 1;
            public List<SkillInstallEntry> entries = new List<SkillInstallEntry>();

            public SkillInstallEntry Find(string targetPath)
            {
                if (entries == null) entries = new List<SkillInstallEntry>();
                return entries.FirstOrDefault(entry => entry.targetPath == targetPath);
            }

            public void Set(string targetPath, string installedHash)
            {
                SkillInstallEntry entry = Find(targetPath);
                if (entry == null)
                {
                    entry = new SkillInstallEntry { targetPath = targetPath };
                    entries.Add(entry);
                }
                entry.installedHash = installedHash;
            }

            public void Remove(string targetPath)
            {
                if (entries == null) entries = new List<SkillInstallEntry>();
                entries.RemoveAll(entry => entry.targetPath == targetPath);
            }
        }

        [Serializable]
        private sealed class SkillInstallEntry
        {
            public string targetPath;
            public string installedHash;
        }

        private sealed class SkillTarget
        {
            public SkillTarget(string sourceRelativePath, string targetRelativePath)
            {
                SourceRelativePath = sourceRelativePath;
                TargetRelativePath = targetRelativePath;
            }

            public string SourceRelativePath { get; }
            public string TargetRelativePath { get; }
        }
    }

    [InitializeOnLoad]
    internal static class AiJiraSkillBootstrap
    {
        private const string StateRelativePath = "UserSettings/AIJira/skill-install-state.json";
        private const string TempRelativePath = "Temp/AIJiraSkills";

        static AiJiraSkillBootstrap()
        {
            if (!Application.isBatchMode) EditorApplication.delayCall += InstallAutomatically;
        }

        internal static AiJiraSkillInstallResult InstallOrRefresh()
        {
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            UnityEditor.PackageManager.PackageInfo package = UnityEditor.PackageManager.PackageInfo.FindForAssembly(
                typeof(AiJiraSkillBootstrap).Assembly);
            if (package == null) throw new InvalidOperationException("AI Jira package path could not be resolved.");
            return AiJiraSkillInstallService.InstallOrRefresh(
                Path.Combine(package.resolvedPath, "Skills~"),
                projectRoot,
                Path.Combine(projectRoot, StateRelativePath),
                Path.Combine(projectRoot, TempRelativePath));
        }

        internal static AiJiraSkillInstallResult RemoveManaged()
        {
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            return AiJiraSkillInstallService.RemoveManaged(
                projectRoot,
                Path.Combine(projectRoot, StateRelativePath),
                Path.Combine(projectRoot, TempRelativePath));
        }

        private static void InstallAutomatically()
        {
            try
            {
                string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
                string statePath = Path.Combine(projectRoot, StateRelativePath);
                if (!AiJiraSkillInstallService.IsAutoInstallEnabled(statePath)) return;
                LogResult("automatic install", InstallOrRefresh());
            }
            catch (Exception exception)
            {
                Debug.LogWarning($"[AI Jira] Agent skill installation failed: {exception}");
            }
        }

        internal static void LogResult(string operation, AiJiraSkillInstallResult result)
        {
            if (result.Installed + result.Updated + result.Removed > 0)
            {
                Debug.Log($"[AI Jira] Agent skill {operation}: installed={result.Installed}, "
                          + $"updated={result.Updated}, removed={result.Removed}, unchanged={result.Unchanged}");
            }
            foreach (string warning in result.Warnings) Debug.LogWarning("[AI Jira] " + warning);
        }
    }
}
#endif

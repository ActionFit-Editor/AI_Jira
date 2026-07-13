#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;
using ActionFit.AiJira.Editor;

public static class AiJiraPackageMenu
{
    private const string MenuRoot = "Tools/Package/AI Jira/";
    private const string ReadmePath = "Packages/com.actionfit.ai-jira/README.md";
    private const int InstallPriority = 21;
    private const int RemovePriority = 22;
    private const int ReadmePriority = 901;

    [MenuItem(MenuRoot + "Install or Refresh Agent Skills", false, InstallPriority)]
    private static void InstallOrRefreshAgentSkills()
    {
        try
        {
            AiJiraSkillInstallResult result = AiJiraSkillBootstrap.InstallOrRefresh();
            AiJiraSkillBootstrap.LogResult("install or refresh", result);
            EditorUtility.DisplayDialog(
                "AI Jira Agent Skills",
                $"Installed: {result.Installed}\nUpdated: {result.Updated}\n"
                + $"Unchanged: {result.Unchanged}\nPreserved: {result.Warnings.Count}",
                "OK");
        }
        catch (System.Exception exception)
        {
            Debug.LogException(exception);
            EditorUtility.DisplayDialog("AI Jira Agent Skills", exception.Message, "OK");
        }
    }

    [MenuItem(MenuRoot + "Remove Managed Agent Skills", false, RemovePriority)]
    private static void RemoveManagedAgentSkills()
    {
        if (!EditorUtility.DisplayDialog(
                "Remove AI Jira Agent Skills",
                "Remove only unchanged skills managed by this package? Modified skills will be preserved.",
                "Remove Managed Skills",
                "Cancel"))
        {
            return;
        }

        try
        {
            AiJiraSkillInstallResult result = AiJiraSkillBootstrap.RemoveManaged();
            AiJiraSkillBootstrap.LogResult("removal", result);
            EditorUtility.DisplayDialog(
                "AI Jira Agent Skills",
                $"Removed: {result.Removed}\nPreserved: {result.Warnings.Count}",
                "OK");
        }
        catch (System.Exception exception)
        {
            Debug.LogException(exception);
            EditorUtility.DisplayDialog("AI Jira Agent Skills", exception.Message, "OK");
        }
    }

    [MenuItem(MenuRoot + "README", false, ReadmePriority)]
    private static void OpenReadme()
    {
        var readme = AssetDatabase.LoadAssetAtPath<TextAsset>(ReadmePath);
        if (readme == null)
        {
            EditorUtility.DisplayDialog("Package README", $"README was not found.\n{ReadmePath}", "OK");
            return;
        }

        Selection.activeObject = readme;
        AssetDatabase.OpenAsset(readme);
    }
}
#endif

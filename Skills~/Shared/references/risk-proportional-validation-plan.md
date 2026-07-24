# Risk-Proportional Jira Validation

`com.actionfit.ai-workagent` owns the portable task classification, soft execution budget, delegation boundary, existing-failure handling, Unity evidence levels, and escalation rules. AI Jira consumes that contract; it does not redefine the task classes or replace Jira lifecycle, approval, sealed-baseline, completion-review, or write-gate behavior.

Locate and read the installed WorkAgent `AI_GUIDE.md` from the embedded `Packages/com.actionfit.ai-workagent/` path first or the matching `Library/PackageCache/com.actionfit.ai-workagent@*/` path. The direct package dependency guarantees the owner is available to AI Jira consumers.

## Validation Plan Mapping

Keep the existing `## Validation Plan` top-level section. Do not add a new top-level managed heading or schema field. Within that section, make all three categories explicit:

1. **Required validation**: the focused checks and selected Unity evidence level required by the approved scope.
2. **Conditional escalation triggers**: the exact task evidence, owner guidance, approved Jira requirement, or newly discovered regression signal that would justify broader validation.
3. **Intentionally excluded expensive validation**: full regression, Player builds, device verification, signing, upload, distribution, deployment, or other expensive work that has no current trigger or approval.

For `routine` work, default to the main agent, affected static checks, targeted tests, one final diff review, and only the owner-required Unity compile or Editor check. A plan may use stronger validation when repository or owner evidence requires it, but must record that evidence.

## Unity Evidence And Escalation

- `editor-simulated`: the default for UI and presentation work using Editor Play Mode, Device Simulator or project preview, screenshots, interactions, and Console evidence.
- `remote-assisted`: optional Unity Remote evidence only when physical touch, stylus, camera, location, accelerometer, gyroscope, compass, or similar device input materially affects the requirement and a device plus user participation are available. Execution still occurs in the Editor.
- `player-build`: an unsigned Android or iOS Player artifact only for a native plugin, mobile SDK, platform define or asmdef constraint, IL2CPP/AOT behavior, PlayerSettings, Gradle/Xcode configuration, Addressables or Build Pipeline behavior, or an Editor-unreproducible defect.
- `device-verified`: installed-device, native SDK, performance, or end-to-end platform evidence.

Neither `editor-simulated` nor `remote-assisted` proves native behavior, platform defines, IL2CPP/AOT, Player packaging, or real-device performance. Generic “mobile QA” wording does not authorize a Player build.

Build only the affected platform. Build Android and iOS only when the approved scope proves a shared mobile boundary. A Player build absent from the approved Jira `Validation Plan` requires additional user approval before execution.

## Failure And Operational Boundaries

- Isolate a clearly unrelated existing failure at most once, record the evidence, and stop pursuing it when isolation proves it is outside the task.
- Do not escalate to a full suite or Player build solely because of an unrelated failure.
- Keep an unisolated or plausibly related failure as a blocker.
- Signing, AAB/IPA distribution, TestFlight, Google Play, Slack artifact upload, deployment, credentials, and runner-secret work always require their existing separate explicit approval. Generic QA, completion, or mobile-check wording never authorizes them.

During execution, compare each expensive action with the approved `Validation Plan`. Run required validation, apply a conditional escalation only when its recorded trigger is now present, and preserve intentionally excluded work. If a new Player build or operational action requires approval, keep or return Jira to its normal approval-safe terminal state instead of bypassing the gate.

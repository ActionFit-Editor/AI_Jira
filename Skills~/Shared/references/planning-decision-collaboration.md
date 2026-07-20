# Planning Decision Collaboration

Use this contract whenever `jira-plan`, `jira-run`, or `jira-auto-start` researches, creates, or refines a plan. Apply it before producing an approval-ready plan or treating an implementation approach as confirmed.

An existing `ready` issue with a complete previously approved plan does not require another decision-closure confirmation merely because `jira-run` or `jira-auto-start` begins implementation. Reopen discovery only when current repository inspection exposes a new material decision or conflicts with the recorded plan.

## Discover Material Decisions

Resolve implementation direction in this order:

1. explicit user requirements
2. repository or API-owner guidance
3. the installed package guide
4. one consistent existing code pattern

When this precedence produces one safe answer, apply it without asking the user. Include the governing rule in the closure summary as an applied convention. Do not invent alternatives merely to create a question.

Treat a choice as material when its answer can change scope, user-visible or public behavior, implementation sequence, ownership boundaries, persisted data, security or destructive impact, migration or rollout, completion criteria, or validation. Technical implementation details are material when the precedence above does not choose one answer and multiple reasonable approaches remain. Local expression-level details that do not change those outcomes are not material.

If guidance conflicts, no level produces one answer, or several established patterns remain reasonable, keep the decision unresolved and ask the user. Never silently omit an alternative from the plan and later encode it as an assumption.

## Collaborate In Bounded Rounds

1. Ask one to three related material questions in one round.
2. Present only genuine alternatives and allow the user to provide a different answer.
3. For every presented alternative, use comparable labels to explain:
   - **Difference**: how its behavior, structure, sequence, ownership, or operational result differs from the other alternatives;
   - **Advantages**: the concrete benefits and conditions where it fits well; and
   - **Disadvantages**: the costs, limitations, risks, or follow-up burden.
4. Recommend one alternative after the comparison and explain why its advantages and disadvantages best fit the known requirements and conventions. Do not describe only the recommendation or use generic claims that do not distinguish the choices.
5. Record each answer as a confirmed choice with its core rationale.
6. Re-scan the full intended scope after every answer because one choice may reveal another material decision.
7. Continue until no material decision remains unresolved.

While a material decision remains unresolved, show decision progress only. Do not prepare or display the approval-ready full plan, create its Jira write payload, request full-plan approval, or perform a Jira plan write. Existing-issue discussion and approval waiting stay in todo under the normal planning-lock contract.

## Recommendation Delegation

A reply that selects a recommendation, such as `A` or `추천안`, creates `current-question-bundle` delegation for only the currently displayed questions. A later newly discovered decision requires another question.

The user may explicitly delegate later recommendations too. That broader delegation:

- applies only within the current planning invocation;
- expires on a new task, a new planning invocation, or loss of the canonical planning context;
- never becomes a persistent user preference; and
- still records each selected recommendation and rationale before re-scanning.

Delegation never authorizes access to credentials or sensitive data, destructive work, publishing, deployment, production changes, or another operation that repository guidance requires the user to approve separately.

## Close Decision Discovery

When no material decision remains, show a closure summary containing:

- confirmed decisions and their core rationale;
- repository, API-owner, package, and existing-pattern conventions that determined an approach without a question; and
- material assumptions the agent resolved because they did not require a user choice.

Obtain explicit decision-closure confirmation before preparing the complete canonical Jira draft and Korean approval view. Decision closure is not Jira write approval. If the user revises a decision or a new material decision appears, reopen discovery and invalidate the prior closure and any derived approval preview.

Set `Decisions Required` to `none` only after discovery is closed with no unresolved material decision. The existing managed-description validator remains the final write guard; this contract prevents agents from hiding choices before that validator can see them.

## Preserve Confirmed Decisions

When material choices were confirmed, add `### Confirmed Decisions` under the canonical English `## Scope` section. Record each selected approach and its core rationale in English. In the complete Korean approval view, render the nested heading as `### 확정된 결정` and translate its explanatory text while preserving technical identifiers.

Do not add a new top-level managed heading, enum, persistent decision store, or Jira CLI for this behavior.

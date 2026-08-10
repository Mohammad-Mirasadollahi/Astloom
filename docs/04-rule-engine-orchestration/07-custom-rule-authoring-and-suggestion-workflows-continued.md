---
doc_id: as.doc.rules.custom-rule-authoring-and-suggestion-workflows-continued
title: 07 - Custom Rule Authoring And Suggestion Workflows (Continued)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/04-rule-engine-orchestration/07-custom-rule-authoring-and-suggestion-workflows.md`
  — remaining sections after the soft size budget.
tags:
- standard
- rules
phase: 04-rule-engine-orchestration
canonical_path: docs/04-rule-engine-orchestration/07-custom-rule-authoring-and-suggestion-workflows-continued.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 07 - Custom Rule Authoring And Suggestion Workflows (Continued)

## Purpose

Continuation of `docs/04-rule-engine-orchestration/07-custom-rule-authoring-and-suggestion-workflows.md` — remaining sections after the soft size budget.

## Example - Deferred Batch Documentation Rule

Observed conversation pattern:

- User does not want memory updates, documentation updates, or review actions after every tiny change.
- User prefers batch completion followed by review, documentation, and memory consolidation.

Suggested rule:

```yaml
rule_id: workflow.batch.defer_review_and_docs
scope:
  workspace_id: engineering-main
condition:
  work_batch_active: true
  change_size: small_or_incremental
action:
  defer_documentation_until_batch_end: true
  defer_memory_consolidation_until_batch_end: true
  run_code_review_after_batch: true
risk: medium
activation: approval_required
```

Expected behavior:

- The agent avoids noisy updates during active implementation.
- At batch completion, the system runs review, updates documentation, and consolidates useful memory.

## Example - HR Feature Profile Rule

Observed conversation pattern:

- HR users need policy memory, onboarding tasks, approvals, and feedback.
- HR users do not need code graph, code review, parser diagnostics, or CI internals.

Suggested rule:

```yaml
rule_id: domain.hr.hide_engineering_features
scope:
  domain_pack: hr-operations
condition:
  user_domain: hr
action:
  feature_profile:
    code_intelligence: hidden
    code_review: hidden
    ci_cd: hidden
    knowledge_base: enabled
    approval_workflows: enabled
    task_management: enabled
risk: medium
activation: approval_required
```

Expected behavior:

- HR users see a focused interface.
- Engineering features remain available to engineering workspaces.
- Backend authorization still prevents hidden features from running without permission.

## Rule Evaluation Requirements

Every rule evaluation should produce structured evidence.

Required fields:

- rule version.
- effective scope.
- input facts.
- matched conditions.
- action selected.
- confidence.
- risk.
- explanation.
- related memory signals.
- related conversation evidence.
- override status.
- resulting event.

## Rule Conflict Handling

Rules may conflict. The rule engine must resolve conflicts deterministically.

Conflict examples:

- organization enables a feature but project disables it.
- domain pack hides a feature but admin role enables it.
- memory profile recommends retrieval but project isolation blocks it.
- rule suggestion proposes automation but security rule requires approval.

Resolution principles:

- deny overrides allow for security-sensitive actions.
- narrower scope overrides broader scope unless security policy says otherwise.
- explicit project isolation overrides convenience composition.
- approval_required overrides automatic execution.
- hidden UI state does not override backend authorization.
- conflict resolution must be explained and logged.

## Admin Console Requirements

The admin console should expose rule workflows.

Required views:

- active rule catalog.
- suggested rule inbox.
- **guided intake wizard** (organization context, scope, narrative, constraints).
- **requirements digest and coverage map** (post-analysis).
- **challenge queue** (one challenge per step with options and evidence).
- **LLM rule assistant panel** (draft, variants, explain, revise) bound to a candidate or active rule.
- rule editor.
- condition builder.
- action builder.
- scope selector.
- dry-run tester.
- conflict viewer.
- activation approval screen.
- rule version history.
- rollback screen.
- rule impact report.
- **intake session history and pack export**.

## API And Contract Requirements

The implementation should expose contracts for:

- creating rule drafts.
- creating rule suggestions.
- **starting and updating guided intake sessions** (`intake_session` create, append narrative, set scope).
- **running intake analysis** (gap analysis, candidate generation, challenge catalog build).
- **resolving challenges** (adopt, customize, defer, reject) with audit payload.
- **LLM-assisted rule draft and revise** (per `candidate_rule_id` or `rule_id`, with schema-validated response).
- approving rules.
- rejecting rules.
- testing rules against examples.
- evaluating rules during workflows.
- listing effective rules for a scope.
- explaining why a rule applied.
- comparing proposed rules with existing rules.
- exporting rule packs.
- importing rule packs (with optional re-run of challenge catalog for target scope).
- **listing intake session status, challenges pending, and session impact report**.

Suggested event types (see `04-data-contracts-and-events.md` for ownership):

- `RuleIntakeSessionStarted`, `RuleIntakeAnalysisCompleted`, `RuleChallengePresented`, `RuleChallengeResolved`, `RuleLlmDraftProposed`, `RuleLlmRevisionProposed`.

## Acceptance Criteria

Custom rule authoring and suggestion workflows are acceptable when:

- users can create scoped rules without source code changes.
- **users can start a guided intake session, describe business requirements and a desired process narrative, and receive a requirements digest plus candidate rules.**
- **the system presents challenges one at a time with options, evidence, and risk tradeoffs; user selections are audited and drive which rules proceed.**
- **for adopted or customized challenges, LLM-managed authoring produces schema-valid rule drafts and revisions; humans approve before activation.**
- conversation-derived rule suggestions include evidence, confidence, risk, and proposed scope.
- rules can be dry-run before activation.
- rule conflicts are deterministic and explainable.
- non-engineering domains can define focused feature profiles without changing core services.
- engineering remains the primary first-party domain with the richest default rule packs.
- all rule changes are versioned, auditable, and reversible.


## Related Documents

- Parent document: `docs/04-rule-engine-orchestration/07-custom-rule-authoring-and-suggestion-workflows.md`

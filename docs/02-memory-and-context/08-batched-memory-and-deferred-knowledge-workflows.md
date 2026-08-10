---
doc_id: as.doc.memory.batched-memory-and-deferred-knowledge-workflows
title: 08 - Batched Memory And Deferred Knowledge Workflows
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom must avoid creating long-term memory, documentation updates, review tasks,
  and reminders for every small agent action.
tags:
- standard
- memory
phase: 02-memory-and-context
canonical_path: docs/02-memory-and-context/08-batched-memory-and-deferred-knowledge-workflows.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
placeholder: 1
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 08 - Batched Memory And Deferred Knowledge Workflows

## 08 - Batched Memory And Deferred Knowledge Workflows
## Purpose

Astloom must avoid creating long-term memory, documentation updates, review tasks, and reminders for every small agent action. An agent may run many commands, make several exploratory edits, adjust one line multiple times, or test alternative approaches before the actual work is complete. If the system reacts to each micro-action, it creates noisy memory, fragmented documentation, premature code review, duplicate tasks, and unnecessary token consumption.

The platform should capture raw evidence continuously, but defer expensive or durable knowledge work until a meaningful boundary is reached. The LLM and orchestration layer should classify what can be batched, what must run immediately, and what should wait until the agent reaches a stable state.

## Corrected Requirement

The raw user requirement can be formalized as follows:

Astloom must separate raw event capture from durable knowledge actions. Every meaningful action can be recorded as evidence, but memory consolidation, documentation generation, code review, FAQ promotion, and long-term memory promotion should usually be deferred and executed as a batch after the work reaches a completion boundary. The LLM should analyze the current work pattern and decide whether to defer, execute immediately, or wait for more evidence. Small line-level changes should not trigger immediate documentation unless they affect public contracts, security, compliance, production behavior, or another high-risk boundary.

This behavior must be configurable, explainable, auditable, and overrideable by users with permission.

## Professional Audience

This design is written for:

- software engineers implementing event capture, memory consolidation, docs sync, review orchestration, rule evaluation, and worker pipelines.
- product designers defining batch state UX, deferred action UX, review timing, and operator controls.
- architects reviewing event-driven boundaries, idempotency, policy bypass, and batching thresholds.
- operators inspecting active batches, failed consolidations, and deferred reviews.
- security reviewers validating which actions can never be deferred.

## Problem Statement

Bad behavior:

- every small code edit creates a durable MemoryItem.
- every changed line triggers documentation generation.
- every command creates a separate reminder or task.
- every partial thought becomes long-term semantic memory.
- agents receive repeated memory reminders while they are still working.
- documentation is generated from intermediate state instead of final state.
- code review runs before tests or final edits complete.
- token usage increases because the same small actions are summarized repeatedly.

Expected behavior:

- capture raw events cheaply and append-only.
- group related actions into a WorkBatch.
- infer whether the work is exploratory, implementation, review, documentation, test, or repair.
- defer memory consolidation, documentation generation, and code review until a meaningful boundary.
- run immediate guardrails only for high-risk situations.
- consolidate once from final evidence.
- document once from final code and graph state.
- review once using the complete batch context.

## Goals

- Reduce memory noise.
- Reduce premature documentation updates.
- Reduce duplicate code reviews and tasks.
- Preserve raw evidence for audit.
- Let LLM classify batching behavior from work context.
- Execute durable knowledge actions at stable boundaries.
- Allow security and policy events to bypass batching.
- Give users visibility and control over active batches.
- Keep batching decisions configurable and explainable.

## Non-Goals

- Do not hide raw activity from audit.
- Do not delay security violations, secret detection, destructive action approvals, or high-risk policy blocks.
- Do not let batching silently drop evidence.
- Do not let the LLM make irreversible batching decisions without policy boundaries.
- Do not use batching as an excuse to skip documentation, review, or memory consolidation.

## Core Objects

### WorkBatch

A WorkBatch groups related actions into a meaningful unit of work.

A WorkBatch should include:

- batch_id.
- tenant_id.
- workspace_id.
- project_id.
- project_group_id when applicable.
- actor_ref.
- actor_type.
- task_ref.
- session_ref.
- objective_summary.
- batch_type.
- lifecycle_state.
- start_time.
- last_activity_at.
- end_time.
- changed_files.
- changed_symbols.
- commands_run.
- tests_run.
- decisions_detected.
- risks_detected.
- memory_candidates.
- documentation_candidates.
- review_candidates.
- boundary_signals.
- evidence_refs.
- readiness_score.
- risk_score.
- defer_policy_ref.

### DeferredAction

DeferredAction represents work that should run later.

Examples:

- memory_consolidation.
- documentation_generation.
- code_review.
- architecture_quality_scan.
- impact_report.
- task_decomposition.
- faq_promotion.
- long_term_memory_promotion.

A DeferredAction should include:

- action_id.
- batch_id.
- action_type.
- target_refs.
- reason_for_deferral.
- trigger_condition.
- max_wait_until.
- priority.
- risk_level.
- status.
- owner.

### BatchDecision

BatchDecision records why the system deferred or executed an action.

Fields:

- decision_id.
- batch_id.
- decision_source.
- decision_type.
- defer_or_execute.
- confidence.
- reason.
- boundary_condition.
- immediate_action_required.
- scoring_profile_version.

## Batch Types

The system should classify batches.

Batch types:

- exploratory_editing.
- feature_implementation.
- bug_fix.
- refactor.
- documentation_update.
- code_review_preparation.
- test_repair.
- incident_response.
- connector_setup.
- configuration_change.
- unknown.

Batch type affects thresholds. For example, exploratory editing should defer documentation aggressively, while incident response should produce audit summaries sooner.

## Lifecycle State Machine

WorkBatch lifecycle states:

- open.
- active.
- waiting_for_quiet_period.
- ready_for_consolidation.
- consolidating.
- waiting_for_review.
- completed.
- canceled.
- failed.

State transition examples:

- open to active when the first related action is recorded.
- active to waiting_for_quiet_period when edits stop but no explicit completion exists.
- active to ready_for_consolidation when task complete, PR created, tests pass, or explicit checkpoint occurs.
- ready_for_consolidation to consolidating when memory/docs/review workers start.
- consolidating to waiting_for_review when documentation or review requires human approval.
- consolidating to completed when all required deferred actions finish.
- any active state to failed when consolidation or required deferred action fails.

## Boundary Detection

A meaningful boundary is a signal that the work is stable enough for durable actions.

Strong boundary signals:

- task marked complete.
- agent final response produced.
- explicit checkpoint command.
- commit created.
- pull request created.
- tests pass after relevant changes.
- review requested by user.
- documentation requested by user.
- quiet period after edits.
- CI run completed.
- issue status changed to ready for review.

Weak boundary signals:

- one file saved.
- one command run.
- one line changed.
- temporary test failure.
- intermediate agent thought.
- draft answer produced.

Weak signals should usually update raw evidence and batch state, not trigger durable knowledge work.

## LLM Responsibility

The LLM should classify work context and recommend batching behavior through structured output.

The LLM should decide:

- whether current activity belongs to an existing WorkBatch.
- whether a new WorkBatch should be opened.
- whether the work is exploratory or stable.
- whether memory consolidation should be deferred.
- whether documentation generation should be deferred.
- whether code review should be deferred.
- whether immediate guardrails must run.
- which boundary condition should trigger deferred actions.

LLM output contract:

    BatchDecisionOutput:
        batch_action
        batch_type
        defer_or_execute
        deferred_actions
        immediate_actions
        boundary_condition
        max_wait_time
        confidence
        risk_level
        reason
        evidence_refs

Allowed batch_action values:

- attach_to_existing_batch.
- open_new_batch.
- mark_ready_for_consolidation.
- force_immediate_action.
- split_batch.
- merge_batches.
- cancel_batch.

## Decision Policy

The LLM recommendation must be constrained by policy.

Policy can override LLM output when:

- secret detection is triggered.
- destructive action is requested.
- authentication or authorization logic changes.
- production config changes.
- public API contract changes.
- compliance or billing logic changes.
- user explicitly requests immediate review.
- batch exceeds maximum duration or size.

The LLM can recommend deferral, but policy decides whether deferral is allowed.

## Readiness Scoring

Batch readiness should be scored with a versioned BatchPolicyProfile.

Recommended factors:

- time_since_last_edit.
- explicit_completion_signal.
- tests_finished.
- tests_passing.
- semantic_coherence.
- number_of_related_changes.
- file_change_stability.
- risk_level.
- documentation_impact.
- code_graph_impact.
- user_instruction_strength.
- review_boundary_signal.
- max_duration_pressure.

Example explanation:

- readiness is low because edits are still active and tests have not run.
- readiness is medium because no edits occurred for 10 minutes but tests are missing.
- readiness is high because task is complete, tests passed, and changed files are semantically related.
- immediate review is required because authorization middleware changed.

## Deferred Memory Consolidation

Memory consolidation should usually happen at batch boundary.

Consolidation should:

- summarize final outcome.
- identify durable decisions.
- identify current truth changes.
- discard noisy intermediate attempts.
- preserve evidence references.
- update or supersede old memory.
- create FAQ candidates when repeated questions were resolved.
- record confidence, scope, and freshness.

The system should not create long-term memory for every command, failed attempt, or minor edit.

## Deferred Documentation Generation

Documentation generation should usually wait until the batch stabilizes.

Flow:

1. capture changed files and symbols continuously.
2. update candidate documentation impact list.
3. wait for boundary signal.
4. query code graph from final state.
5. identify stale or missing documentation.
6. generate one documentation update or draft set.
7. attach evidence and confidence.
8. request review when public, high-risk, or security-sensitive behavior changed.

A single line change should not trigger immediate documentation unless it changes public contract, security behavior, compliance behavior, production configuration, or an already documented invariant.

## Deferred Code Review

Code review should run at a meaningful boundary.

Preferred triggers:

- task completed.
- PR created.
- tests passed.
- explicit review request.
- quiet period plus coherent changed files.
- high-risk change detected.

Review context should include:

- final diff.
- changed symbols.
- changed contracts.
- related Decisions.
- related Tasks and Issues.
- test results.
- unresolved questions.
- docs drift findings.
- rule evaluation results.
- previous corrections.

## Related Documents

- Continued in `docs/02-memory-and-context/08-batched-memory-and-deferred-knowledge-workflows-continued.md`

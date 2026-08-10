---
doc_id: as.doc.memory.data-contracts-and-events-continued
title: Memory and Context - Data Contracts and Events (Continued)
doc_type: contract
status: active
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/02-memory-and-context/04-data-contracts-and-events.md` — remaining
  sections after the soft size budget.
tags:
- contract
- memory
phase: 02-memory-and-context
canonical_path: docs/02-memory-and-context/04-data-contracts-and-events-continued.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Memory and Context - Data Contracts and Events (Continued)

## Purpose

Continuation of `docs/02-memory-and-context/04-data-contracts-and-events.md` — remaining sections after the soft size budget.

## Work Batch Events

Recommended events:

- batch.opened
- batch.activity_recorded
- batch.boundary_signal_detected
- batch.deferred_action_created
- batch.ready_for_consolidation
- batch.consolidation_started
- batch.consolidation_completed
- batch.documentation_generation_requested
- batch.code_review_requested
- batch.immediate_action_triggered
- batch.completed
- batch.canceled
- batch.failed

## Feedback And Correction Contracts

The platform must support explicit user correction from the web interface. Corrections must be structured so they can affect memory confidence, retrieval feedback, rules, tasks, documentation drafts, and future agent behavior.

### FeedbackRecord

Recommended contract:

    FeedbackRecord:
        feedback_id
        tenant_id
        workspace_id
        project_id
        project_group_id
        target_type
        target_ref
        correction_type
        corrected_value
        reason
        created_by
        created_at
        affected_memory_refs
        affected_question_refs
        affected_rule_refs
        affected_task_refs
        affected_doc_refs
        status
        audit_ref

Allowed correction types:

- wrong_answer
- wrong_memory
- stale_memory
- wrong_scope
- wrong_task_decomposition
- wrong_rule_interpretation
- wrong_documentation_draft
- wrong_code_impact_analysis
- wrong_connector_mapping
- missing_context
- unsafe_action

Contract rules:

- FeedbackRecord must be scoped.
- Corrections must not mutate previous evidence destructively.
- Corrections should create audit events.
- Corrections may lower confidence, supersede memory, create Tasks, create Gaps, or request review.
- High-risk corrections require approval when they alter rules, security behavior, or shared memory.

## Feedback Events

Recommended events:

- feedback.created
- feedback.applied_to_memory
- feedback.applied_to_question_answer
- feedback.rule_improvement_suggested
- feedback.task_reopened
- feedback.gap_created
- feedback.review_requested
- feedback.rejected

Event rules:

- Every feedback event must include scope and target reference.
- Events that affect retrieval ranking must include old and new confidence signals.
- Events that affect rules must include rule version or suggested new version.


## Related Documents

- Parent document: `docs/02-memory-and-context/04-data-contracts-and-events.md`

---
doc_id: as.doc.common-context.data-contracts-and-events
title: 04 - Common Context Data Contracts And Events
doc_type: contract
status: active
schema_version: '1.0'
owner: platform-docs
summary: Contracts should be published through `backend/packages/common-context/contracts`
  and versioned through the schema registry.
tags:
- contract
- common-context
phase: 12-common-context-reuse
canonical_path: docs/12-common-context-reuse/04-data-contracts-and-events.md
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

# 04 - Common Context Data Contracts And Events


## Purpose

Contracts should be published through `backend/packages/common-context/contracts` and versioned through the schema registry.

## Contract Families

Contracts should be published through `backend/packages/common-context/contracts` and versioned through the schema registry.

Required families:

- CommonItemRequest and CommonItemResponse
- CommonItemVersion
- CommonContextScope
- ApplicabilityRule
- ReuseScoreBreakdown
- ContextBundleRequest
- ContextBundleResponse
- CommonContextConflict
- CommonContextAuditRecord
- CommonContextUsageMetric

## Event Names

- `CommonItemCreated`
- `CommonItemUpdated`
- `CommonItemApproved`
- `CommonItemRejected`
- `CommonItemPromotedFromRepeatedInstruction`
- `CommonItemDeprecated`
- `CommonItemSuppressedForScope`
- `CommonContextBundleResolved`
- `CommonContextConflictDetected`
- `CommonContextEffectivenessRecorded`

## Event Metadata

Every event must include event_id, event_type, event_version, occurred_at, actor_id, project_id, scope_type, scope_id, correlation_id, causation_id, source_service, and audit_record_id.

## Compatibility Rules

Contracts must be additive by default. Breaking changes require a new event version, migration notes, SDK generation updates, contract tests, and release notes.

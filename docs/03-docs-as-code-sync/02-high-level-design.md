---
doc_id: as.doc.docs-sync.high-level-design
title: Docs As Code Sync - High-Level Design
doc_type: hld
status: draft
schema_version: '1.0'
owner: platform-docs
summary: This HLD defines the system-level architecture for Docs As Code Sync. It explains
  the architectural intent, actors, components, data ownership, runtime flows, integration
  boundaries, operational expectations, and acceptance criteria. It is written for architects,
  senior engineers.
tags:
- hld
- docs-sync
phase: 03-docs-as-code-sync
canonical_path: docs/03-docs-as-code-sync/02-high-level-design.md
lifecycle_lane: future
concern_lane: design
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Docs As Code Sync - High-Level Design

## Purpose

This HLD defines the system-level architecture for Docs As Code Sync. It explains the architectural intent, actors, components, data ownership, runtime flows, integration boundaries, operational expectations, and acceptance criteria. It is written for architects, senior engineers, product designers, reviewers, and operators who need enough context to implement the phase without relying on hidden assumptions.

## Document flow

```mermaid
flowchart TD
  reader[Reader] --> doc[This document]
  doc --> next[Related docs or implementation]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Reader | Opens this design document | Understands scope and constraints |
| 2 | Reader | Follows the Mermaid flow | Sees primary component interactions |
| 3 | Reader | Uses Related Documents / linked symbols | Reaches deeper design or implementation |


## Mission

Keep documentation synchronized with code, decisions, tasks, and code graph changes through anchors, metadata, drift detection, and reviewable documentation drafts.

## Scope

The HLD covers:

- user and agent-facing responsibilities.
- service and component boundaries.
- data ownership and event ownership.
- high-level runtime flows.
- integration points with other Astloom phases.
- security, observability, reliability, and product-state requirements.
- acceptance criteria that prove the architecture is ready for implementation planning.

## Non-Goals

- It does not define framework-specific code structure.
- It does not define database migration syntax.
- It does not define command handlers, event handlers, persistence internals, or algorithm implementation details.
- It does not allow cross-project data access unless explicitly permitted by ProjectGroup policy.

## Primary Actors

- developer.
- documentation agent.
- docs-sync-service.
- code-graph-service.
- core-data-service.
- admin-console.
- reviewer.

## Product And Engineering Capabilities

- documentation graph.
- AST anchoring.
- frontmatter validation.
- doc coverage indexing.
- drift detection.
- documentation draft generation.
- review task creation.

## High-Level Architectural Decisions

- The phase must expose behavior through service APIs, events, and documented contracts rather than shared database access.
- All records and queries must carry tenant, workspace, and project or ProjectGroup scope.
- Durable state changes must produce audit-friendly events with correlation and causation metadata.
- High-risk behavior must be reviewable through admin-console and auditable through audit-service.
- Documentation, memory, tasks, and reports must link back to source evidence.
- Batchable work should be deferred until meaningful boundaries unless policy requires immediate action.

## Component Model

The high-level component set is:

- docs-sync-service.
- doc-indexer.
- frontmatter-validator.
- anchor-resolver.
- drift-detector.
- doc-draft-generator.
- doc-task-router.

## Component Responsibilities

- docs-sync-service: owns the docs sync service responsibility inside the Docs As Code Sync boundary.
- doc-indexer: owns the doc indexer responsibility inside the Docs As Code Sync boundary.
- frontmatter-validator: owns the frontmatter validator responsibility inside the Docs As Code Sync boundary.
- anchor-resolver: owns the anchor resolver responsibility inside the Docs As Code Sync boundary.
- drift-detector: owns the drift detector responsibility inside the Docs As Code Sync boundary.
- doc-draft-generator: owns the doc draft generator responsibility inside the Docs As Code Sync boundary.
- doc-task-router: owns the doc task router responsibility inside the Docs As Code Sync boundary.

## Data Ownership

The phase owns or materially affects these data objects:

- Document.
- DocumentAnchor.
- DocFlag.
- DocCoverageRecord.
- DriftFinding.
- DocumentationDraft.
- DocOwner.

Ownership rules:

- The owning service controls writes and lifecycle transitions for its entities.
- Other services consume public APIs, events, SDKs, or projections.
- Reports, memory retrieval, graph traversal, and prompt assembly must apply scope before selecting data.
- Audit records preserve evidence but do not become the write path for domain objects.

## High-Level Runtime Flows

The primary runtime flows are:

1. code symbol change to drift finding.
2. missing docs to draft and Task.
3. frontmatter validation to CI gate.
4. approved doc update to memory and graph refresh.

## Integration Boundaries

This phase integrates with:

- core-data-service for Activities, WorkLogs, Decisions, Issues, Tasks, and evidence references.
- memory-service when durable facts, retrieval context, repeated questions, or feedback are created.
- code-graph-service when code symbols, graph edges, ownership, or impact analysis are required.
- docs-sync-service when documentation anchors, drift findings, or documentation drafts are involved.
- rule-engine-service when policies, risk scoring, approvals, or escalations are required.
- broker-service for event delivery, replay, retry, and dead-letter behavior.
- admin-console for review, correction, approval, diagnostics, and operational control.
- audit-service for immutable evidence and compliance export.

## Security And Scope Model

Security requirements:

- All commands and queries require actor identity and scope.
- Project isolation is enforced before retrieval, ranking, aggregation, or prompt assembly.
- Cross-project access requires ProjectGroup policy and audit evidence.
- Sensitive fields are redacted before logs, prompts, reports, and external events.
- High-risk actions require approval or rule-engine evaluation.

## Observability Model

The phase must emit:

- structured logs with service, operation, scope, actor, correlation ID, and result.
- metrics for throughput, latency, failure count, retry count, and backlog.
- traces across API, worker, broker, persistence, and external calls.
- audit events for durable state changes, review decisions, corrections, and cross-project access.
- diagnostics that show effective config without secrets.

## Reliability And Failure Model

Reliability requirements:

- Commands that can be retried must be idempotent.
- Event consumers must tolerate duplicate and delayed delivery.
- Failed broker deliveries must move to retry and then dead-letter with evidence.
- Partial workflow failure must create visible operational state, Task, Gap, or alert.
- High-risk failure modes must not be hidden inside logs only.

## Product States

User-facing and operator-facing states should include:

- Document: indexed, valid, invalid_frontmatter, stale, missing_anchor, archived.
- DriftFinding: detected, triaged, task_created, fixed, ignored.
- DocumentationDraft: generated, waiting_for_review, approved, rejected, published.

Additional UI states:

- loading.
- empty.
- permission_denied.
- degraded.
- failed.
- pending_review.
- partial_data.
- project_scope_warning.

## HLD Edge Cases

The architecture must explicitly handle:

- renamed symbol.
- generated code should not require docs.
- private helper below documentation threshold.
- doc anchor stale after refactor.
- conflicting owners.

## HLD Acceptance Criteria

The HLD is complete when:

- actors, components, and data ownership are explicit.
- all major runtime flows have a named source, processor, output, and audit trail.
- cross-service communication happens through APIs, events, or contracts.
- project scope is enforced before data retrieval or aggregation.
- observability, security, and failure handling requirements are defined.
- product states and operator controls are clear enough for product design and implementation planning.
- implementation planning can derive commands, queries, events, state machines, and tests from this document.

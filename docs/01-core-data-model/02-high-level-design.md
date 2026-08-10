---
doc_id: as.doc.core.high-level-design
title: Core Data Model - High-Level Design
doc_type: hld
status: draft
schema_version: '1.0'
owner: platform-docs
summary: This HLD defines the system-level architecture for Core Data Model. It explains the
  architectural intent, actors, components, data ownership, runtime flows, integration boundaries,
  operational expectations, and acceptance criteria. It is written for architects, senior
  engineers, .
tags:
- hld
- core
phase: 01-core-data-model
canonical_path: docs/01-core-data-model/02-high-level-design.md
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

# Core Data Model - High-Level Design

## Purpose

This HLD defines the system-level architecture for Core Data Model. It explains the architectural intent, actors, components, data ownership, runtime flows, integration boundaries, operational expectations, and acceptance criteria. It is written for architects, senior engineers, product designers, reviewers, and operators who need enough context to implement the phase without relying on hidden assumptions.

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

Provide the canonical work record model for activities, work logs, decisions, issues, tasks, relationships, evidence, and lifecycle transitions.

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

- agent runtime.
- developer.
- reviewer.
- project owner.
- rule-engine-service.
- memory-service.
- docs-sync-service.
- audit-service.
- admin-console.

## Product And Engineering Capabilities

- record atomic activities.
- summarize work logs.
- record decisions and alternatives.
- separate issues from executable tasks.
- track dependencies and ownership.
- preserve evidence and audit references.

## High-Level Architectural Decisions

- The phase must expose behavior through service APIs, events, and documented contracts rather than shared database access.
- All records and queries must carry tenant, workspace, and project or ProjectGroup scope.
- Durable state changes must produce audit-friendly events with correlation and causation metadata.
- High-risk behavior must be reviewable through admin-console and auditable through audit-service.
- Documentation, memory, tasks, and reports must link back to source evidence.
- Batchable work should be deferred until meaningful boundaries unless policy requires immediate action.

## Component Model

The high-level component set is:

- core-data-service.
- activity-ingestion-api.
- worklog-service.
- decision-service.
- issue-service.
- task-service.
- relationship-service.
- evidence-service.
- audit-publisher.

## Component Responsibilities

- core-data-service: owns the core data service responsibility inside the Core Data Model boundary.
- activity-ingestion-api: owns the activity ingestion api responsibility inside the Core Data Model boundary.
- worklog-service: owns the worklog service responsibility inside the Core Data Model boundary.
- decision-service: owns the decision service responsibility inside the Core Data Model boundary.
- issue-service: owns the issue service responsibility inside the Core Data Model boundary.
- task-service: owns the task service responsibility inside the Core Data Model boundary.
- relationship-service: owns the relationship service responsibility inside the Core Data Model boundary.
- evidence-service: owns the evidence service responsibility inside the Core Data Model boundary.
- audit-publisher: owns the audit publisher responsibility inside the Core Data Model boundary.

## Data Ownership

The phase owns or materially affects these data objects:

- Activity.
- WorkLog.
- Decision.
- Issue.
- Task.
- EvidenceRef.
- ActorRef.
- Relationship.
- LifecycleTransition.

Ownership rules:

- The owning service controls writes and lifecycle transitions for its entities.
- Other services consume public APIs, events, SDKs, or projections.
- Reports, memory retrieval, graph traversal, and prompt assembly must apply scope before selecting data.
- Audit records preserve evidence but do not become the write path for domain objects.

## High-Level Runtime Flows

The primary runtime flows are:

1. agent action to Activity to audit event.
2. completed session to WorkLog and SemanticFact candidate.
3. Issue discovery to executable Task decomposition.
4. Decision supersession and downstream notification.

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

- Task: proposed, ready, in_progress, blocked, review, done, canceled, reopened.
- Issue: open, triaged, accepted, mitigated, closed, deferred.
- Decision: proposed, active, superseded, rejected, expired.

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

- duplicate activity retry.
- decision conflict.
- task dependency cycle.
- missing evidence.
- cross-project scope mismatch.
- partial agent failure.

## HLD Acceptance Criteria

The HLD is complete when:

- actors, components, and data ownership are explicit.
- all major runtime flows have a named source, processor, output, and audit trail.
- cross-service communication happens through APIs, events, or contracts.
- project scope is enforced before data retrieval or aggregation.
- observability, security, and failure handling requirements are defined.
- product states and operator controls are clear enough for product design and implementation planning.
- implementation planning can derive commands, queries, events, state machines, and tests from this document.

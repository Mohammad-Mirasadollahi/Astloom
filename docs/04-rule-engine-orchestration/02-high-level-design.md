---
doc_id: as.doc.rules.high-level-design
title: Rule Engine And Orchestration - High-Level Design
doc_type: hld
status: draft
schema_version: '1.0'
owner: platform-docs
summary: This HLD defines the system-level architecture for Rule Engine And Orchestration.
tags:
- hld
- rules
phase: 04-rule-engine-orchestration
canonical_path: docs/04-rule-engine-orchestration/02-high-level-design.md
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

# Rule Engine And Orchestration - High-Level Design

## Purpose

This HLD defines the system-level architecture for Rule Engine And Orchestration. It explains the architectural intent, actors, components, data ownership, runtime flows, integration boundaries, operational expectations, and acceptance criteria. It is written for architects, senior engineers, product designers, reviewers, and operators who need enough context to implement the phase without relying on hidden assumptions.

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

Coordinate agents and humans through deterministic rules, semantic policy checks, anomaly detection, task routing, approvals, and escalation workflows.

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

- rule-engine-service.
- agent runtime.
- developer.
- security reviewer.
- project owner.
- admin-console.
- broker-service.

## Product And Engineering Capabilities

- policy registry.
- deterministic pre-checks.
- LLM judge integration.
- risk scoring.
- escalation routing.
- task routing.
- anomaly detection.
- shadow-mode rules.

## High-Level Architectural Decisions

- The phase must expose behavior through service APIs, events, and documented contracts rather than shared database access.
- All records and queries must carry tenant, workspace, and project or ProjectGroup scope.
- Durable state changes must produce audit-friendly events with correlation and causation metadata.
- High-risk behavior must be reviewable through admin-console and auditable through audit-service.
- Documentation, memory, tasks, and reports must link back to source evidence.
- Batchable work should be deferred until meaningful boundaries unless policy requires immediate action.

## Component Model

The high-level component set is:

- rule-engine-service.
- policy-registry.
- deterministic-evaluator.
- semantic-evaluator.
- risk-scorer.
- escalation-router.
- anomaly-detector.
- task-router.

## Component Responsibilities

- rule-engine-service: owns the rule engine service responsibility inside the Rule Engine And Orchestration boundary.
- policy-registry: owns the policy registry responsibility inside the Rule Engine And Orchestration boundary.
- deterministic-evaluator: owns the deterministic evaluator responsibility inside the Rule Engine And Orchestration boundary.
- semantic-evaluator: owns the semantic evaluator responsibility inside the Rule Engine And Orchestration boundary.
- risk-scorer: owns the risk scorer responsibility inside the Rule Engine And Orchestration boundary.
- escalation-router: owns the escalation router responsibility inside the Rule Engine And Orchestration boundary.
- anomaly-detector: owns the anomaly detector responsibility inside the Rule Engine And Orchestration boundary.
- task-router: owns the task router responsibility inside the Rule Engine And Orchestration boundary.

## Data Ownership

The phase owns or materially affects these data objects:

- Rule.
- RuleVersion.
- RuleEvaluation.
- PolicyEvidence.
- RiskScore.
- Escalation.
- ApprovalRequest.
- AnomalySignal.

Ownership rules:

- The owning service controls writes and lifecycle transitions for its entities.
- Other services consume public APIs, events, SDKs, or projections.
- Reports, memory retrieval, graph traversal, and prompt assembly must apply scope before selecting data.
- Audit records preserve evidence but do not become the write path for domain objects.

## High-Level Runtime Flows

The primary runtime flows are:

1. changed code to deterministic and semantic evaluation.
2. high-risk finding to approval request.
3. rule violation to Task routing.
4. false positive feedback to rule improvement suggestion.

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

- Rule: draft, shadow, active, disabled, deprecated.
- Evaluation: pending, running, passed, failed, escalated, errored.
- Approval: requested, approved, rejected, expired, canceled.

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

- LLM judge low confidence.
- conflicting rules.
- approval timeout.
- false positive spike.
- rule disabled without permission.
- missing evidence.

## HLD Acceptance Criteria

The HLD is complete when:

- actors, components, and data ownership are explicit.
- all major runtime flows have a named source, processor, output, and audit trail.
- cross-service communication happens through APIs, events, or contracts.
- project scope is enforced before data retrieval or aggregation.
- observability, security, and failure handling requirements are defined.
- product states and operator controls are clear enough for product design and implementation planning.
- implementation planning can derive commands, queries, events, state machines, and tests from this document.

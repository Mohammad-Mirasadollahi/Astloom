---
doc_id: as.doc.rule-engine.phase-4-api-contract
title: Rule Engine Service Phase 4 API Contract
doc_type: contract
status: active
schema_version: '1.0'
owner: rule-engine-service
summary: This contract documents the Phase 4 vertical slice for Rule Engine and Orchestration.
  The service owns scoped Rules, RuleEvaluations, ApprovalRequests, ImpactMaps, RoutedTasks,
  AnomalySignals, rule feedback, and rule-engine outbox events.
tags:
- api
- contract
- phase-4
- rule-engine
phase: phase-4
canonical_path: backend/services/rule-engine-service/docs/phase-4-api-contract.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
doc_version: 1.0.1
updated_at: 2026-08-10
linked_symbols: []
---

# Rule Engine Service Phase 4 API Contract

Path: `backend/services/rule-engine-service/docs/phase-4-api-contract.md`

## Purpose

This contract documents the Phase 4 vertical slice for Rule Engine and Orchestration. The service owns scoped Rules, RuleEvaluations, ApprovalRequests, ImpactMaps, RoutedTasks, AnomalySignals, rule feedback, and rule-engine outbox events.

## Scope Headers

Every command and scoped query uses:

- `X-Tenant-Id`
- `X-Workspace-Id`
- `X-Actor-Id` for commands
- `X-Correlation-Id` when a caller needs deterministic trace linkage
- `Idempotency-Key` for retryable commands

All endpoints are scoped under `/api/v1/projects/{project_id}` and return snake_case JSON fields.

## Commands

- `POST /api/v1/projects/{project_id}/rules`
- `POST /api/v1/projects/{project_id}/rules/{rule_id}:update-version`
- `POST /api/v1/projects/{project_id}/evaluations`
- `POST /api/v1/projects/{project_id}/evaluations:shadow`
- `POST /api/v1/projects/{project_id}/approvals`
- `POST /api/v1/projects/{project_id}/approvals/{approval_id}:resolve`
- `POST /api/v1/projects/{project_id}/task-routes`
- `POST /api/v1/projects/{project_id}/rule-feedback`

## Queries

- `GET /api/v1/projects/{project_id}/evaluations`
- `GET /api/v1/projects/{project_id}/evaluations/{evaluation_id}:explain`
- `GET /api/v1/projects/{project_id}/approval-queue`
- `GET /api/v1/projects/{project_id}/anomalies`
- `GET /api/v1/projects/{project_id}/rule-health`

## Event Types

The development outbox emits versioned rule-engine-service events:

- `RuleCreated`
- `RuleUpdated`
- `RuleEvaluationCompleted`
- `RuleViolationDetected`
- `ApprovalRequested`
- `ApprovalResolved`
- `TaskRouted`
- `AnomalyDetected`
- `RuleFeedbackRecorded`
- `ImpactMapCreated`

Each event contains `event_id`, `event_type`, `event_version`, `occurred_at`, `producer`, scope fields, `actor_ref`, `correlation_id`, `causation_id`, `idempotency_key`, `payload`, and `evidence_refs`.

## Compatibility

This is an active Phase 4 contract. Breaking changes require a new contract note, matching tests, and a migration or compatibility statement before promotion to shared contracts.

## Related Documents

- `backend/docs/API_NAMING_AND_CONTRACT_STANDARD.md` — HTTP naming and contract conventions
- Sibling service design docs under `docs/` for the owning phase vertical slice

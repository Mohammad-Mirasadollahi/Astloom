---
doc_id: as.doc.core-data.phase-1-api-contract
title: Phase 1 API Contract
doc_type: contract
status: active
schema_version: '1.0'
owner: core-data-service
summary: 'All commands require `X-Tenant-Id`, `X-Workspace-Id`, `X-Actor-Id`, and `Idempotency-Key`.
  Version: 1.0.0 All commands require `X-Tenant-Id`, `X-Workspace-Id`, `X-Actor-Id`, and `Idempotency-Key`.
  Requests and responses use snake_case and project scope is enforced before reads...'
tags:
- api
- contract
- core-data
- phase-1
phase: phase-1
canonical_path: backend/services/core-data-service/docs/phase-1-api-contract.md
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

# Phase 1 API Contract


## Purpose

All commands require `X-Tenant-Id`, `X-Workspace-Id`, `X-Actor-Id`, and `Idempotency-Key`.

Version: 1.0.0

All commands require `X-Tenant-Id`, `X-Workspace-Id`, `X-Actor-Id`, and `Idempotency-Key`. Requests and responses use snake_case and project scope is enforced before reads or writes.

## Resources

- `POST /api/v1/projects/{project_id}/activities`
- `GET /api/v1/projects/{project_id}/activities`
- `POST /api/v1/projects/{project_id}/work-logs`
- `GET /api/v1/projects/{project_id}/work-logs`
- `POST /api/v1/projects/{project_id}/decisions`
- `GET /api/v1/projects/{project_id}/decisions`
- `POST /api/v1/projects/{project_id}/decisions/{decision_id}:supersede`
- `POST /api/v1/projects/{project_id}/issues`
- `GET /api/v1/projects/{project_id}/issues`
- `GET /api/v1/projects/{project_id}/open-issues`
- `POST /api/v1/projects/{project_id}/tasks`
- `GET /api/v1/projects/{project_id}/tasks`
- `POST /api/v1/projects/{project_id}/tasks/{task_id}:transition`
- `POST /api/v1/projects/{project_id}/issues/{issue_id}:transition`
- `POST /api/v1/projects/{project_id}/decisions/{decision_id}:transition`
- `GET /api/v1/projects/{project_id}/task-board`
- `GET /api/v1/projects/{project_id}/decision-history`
- `GET /api/v1/projects/{project_id}/related-work`
- `GET /api/v1/projects/{project_id}/evidence-bundles/{evidence_ref}`
- `GET /api/v1/projects/{project_id}/timeline`

List calls require bounded `page_size` where exposed and return items, page metadata, and correlation data. Expected failures use the API problem envelope. Every mutation emits a versioned outbox event with scope, actor, correlation, causation, idempotency metadata, source, and evidence references.

Critical Issues must include `task_specs` for decomposition or `escalation_reason` for documented human escalation. Decision supersession keeps the old Decision record and moves it to `superseded` rather than deleting it.

PostgreSQL is the only runtime and integration persistence backend and is configured through `ASTLOOM_CORE_DATA_DATABASE_URL`. Deterministic unit tests use the Store port's in-memory fake.

## Related Documents

- `backend/docs/API_NAMING_AND_CONTRACT_STANDARD.md` — HTTP naming and contract conventions
- Sibling service design docs under `docs/` for the owning phase vertical slice

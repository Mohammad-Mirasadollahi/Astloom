---
doc_id: as.doc.docs-sync.phase-3-api-contract
title: Docs Sync Service Phase 3 API Contract
doc_type: contract
status: active
schema_version: '1.0'
owner: docs-sync-service
summary: This contract documents the Phase 3 vertical slice for Docs-as-Code synchronization.
  The service owns scoped CodeSymbol projections used for drift, Documents, DocAnchors, DriftFindings,
  DocumentationDrafts, Bloom filter lookups, CI gate evaluation, and docs-sync outbox events.
tags:
- api
- contract
- docs-sync
- phase-3
phase: phase-3
canonical_path: backend/services/docs-sync-service/docs/phase-3-api-contract.md
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

# Docs Sync Service Phase 3 API Contract

Path: `backend/services/docs-sync-service/docs/phase-3-api-contract.md`

## Purpose

This contract documents the Phase 3 vertical slice for Docs-as-Code synchronization. The service owns scoped CodeSymbol projections used for drift, Documents, DocAnchors, DriftFindings, DocumentationDrafts, Bloom filter lookups, CI gate evaluation, and docs-sync outbox events.

## Scope Headers

Every command and scoped query uses:

- `X-Tenant-Id`
- `X-Workspace-Id`
- `X-Actor-Id` for commands
- `X-Correlation-Id` when a caller needs deterministic trace linkage
- `Idempotency-Key` for retryable commands

All endpoints are scoped under `/api/v1/projects/{project_id}` and return snake_case JSON fields.

## Commands

- `POST /api/v1/projects/{project_id}/symbols`
- `POST /api/v1/projects/{project_id}/documents`
- `POST /api/v1/projects/{project_id}/documents:validate-frontmatter`
- `POST /api/v1/projects/{project_id}/anchors`
- `POST /api/v1/projects/{project_id}/drift-detections`
- `POST /api/v1/projects/{project_id}/drafts`
- `POST /api/v1/projects/{project_id}/drafts/{draft_id}:approve`
- `POST /api/v1/projects/{project_id}/ci-gate`

## Queries

- `GET /api/v1/projects/{project_id}/symbols/{symbol_id}/docs`
- `GET /api/v1/projects/{project_id}/drift-findings`
- `GET /api/v1/projects/{project_id}/coverage`
- `GET /api/v1/projects/{project_id}/missing-docs`
- `GET /api/v1/projects/{project_id}/impact:explain`
- `GET /api/v1/projects/{project_id}/bloom-lookups`

## Event Types

The development outbox emits versioned docs-sync-service events:

- `SymbolIndexed`
- `DocumentIndexed`
- `AnchorRegistered`
- `DocumentationDriftDetected`
- `DocumentationDraftCreated`
- `DocumentationDraftApproved`
- `DocCoverageChanged`

Each event contains `event_id`, `event_type`, `event_version`, `occurred_at`, `producer`, scope fields, `actor_ref`, `correlation_id`, `causation_id`, `idempotency_key`, `payload`, and `evidence_refs`.

## Compatibility

This is an active Phase 3 contract. Breaking changes require a new contract note, matching tests, and a migration or compatibility statement before promotion to shared contracts.

## Related Documents

- `backend/docs/API_NAMING_AND_CONTRACT_STANDARD.md` — HTTP naming and contract conventions
- Sibling service design docs under `docs/` for the owning phase vertical slice

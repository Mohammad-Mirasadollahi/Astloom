---
doc_id: as.doc.reporting.phase-reporting-api-contract
title: Astloom Reporting API Contract
doc_type: contract
status: active
schema_version: '1.0'
owner: reporting-service
summary: '- Scope headers: `X-Tenant-Id`, `X-Workspace-Id`, `X-Actor-Id` - Idempotency: `Idempotency-Key`
  on mutating routes - Persistence target env: `ASTLOOM_REPORTING_DATABASE_URL` - Tests:
  `tests/backend/services/reporting-service/`. Vertical slice for `reporting-service`. - Scope...'
tags:
- api
- contract
- phase-reporting
- reporting
phase: phase-reporting
canonical_path: backend/services/reporting-service/docs/phase-reporting-api-contract.md
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

# Astloom Reporting API Contract


## Purpose

- Scope headers: `X-Tenant-Id`, `X-Workspace-Id`, `X-Actor-Id` - Idempotency: `Idempotency-Key` on mutating routes - Persistence target env: `ASTLOOM_REPORTING_DATABASE_URL` - Tests: `tests/backend/services/reporting-service/`.

Vertical slice for `reporting-service`.

- Scope headers: `X-Tenant-Id`, `X-Workspace-Id`, `X-Actor-Id`
- Idempotency: `Idempotency-Key` on mutating routes
- Persistence target env: `ASTLOOM_REPORTING_DATABASE_URL`
- Tests: `tests/backend/services/reporting-service/`

## Related Documents

- `backend/docs/API_NAMING_AND_CONTRACT_STANDARD.md` — HTTP naming and contract conventions
- Sibling service design docs under `docs/` for the owning phase vertical slice

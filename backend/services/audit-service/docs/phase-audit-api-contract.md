---
doc_id: as.doc.audit.phase-audit-api-contract
title: Astloom Audit API Contract
doc_type: contract
status: active
schema_version: '1.0'
owner: audit-service
summary: '- Scope headers: `X-Tenant-Id`, `X-Workspace-Id`, `X-Actor-Id` - Idempotency: `Idempotency-Key`
  on mutating routes - Persistence target env: `ASTLOOM_AUDIT_DATABASE_URL` - Tests: `tests/backend/services/audit-service/`.
  Vertical slice for `audit-service`. - Scope headers: `X...'
tags:
- api
- audit
- contract
- phase-audit
phase: phase-audit
canonical_path: backend/services/audit-service/docs/phase-audit-api-contract.md
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

# Astloom Audit API Contract


## Purpose

- Scope headers: `X-Tenant-Id`, `X-Workspace-Id`, `X-Actor-Id` - Idempotency: `Idempotency-Key` on mutating routes - Persistence target env: `ASTLOOM_AUDIT_DATABASE_URL` - Tests: `tests/backend/services/audit-service/`.

Vertical slice for `audit-service`.

- Scope headers: `X-Tenant-Id`, `X-Workspace-Id`, `X-Actor-Id`
- Idempotency: `Idempotency-Key` on mutating routes
- Persistence target env: `ASTLOOM_AUDIT_DATABASE_URL`
- Tests: `tests/backend/services/audit-service/`

## Related Documents

- `backend/docs/API_NAMING_AND_CONTRACT_STANDARD.md` — HTTP naming and contract conventions
- Sibling service design docs under `docs/` for the owning phase vertical slice

---
doc_id: as.doc.project-profile.phase-project-profile-api-contract
title: Astloom Project Profile API Contract
doc_type: contract
status: active
schema_version: '1.0'
owner: project-profile-service
summary: 'Vertical slice for `project-profile-service`. Vertical slice for `project-profile-service`.
  - Scope headers: `X-Tenant-Id`, `X-Workspace-Id`, `X-Actor-Id` - Idempotency: `Idempotency-Key`
  on mutating routes - Persistence target env: `ASTLOOM_PROJECT_PROFILE_DATABASE_URL` -
  T...'
tags:
- api
- contract
- phase-project-profile
- project-profile
phase: phase-project-profile
canonical_path: backend/services/project-profile-service/docs/phase-project-profile-api-contract.md
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

# Astloom Project Profile API Contract


## Purpose

Vertical slice for `project-profile-service`.

Vertical slice for `project-profile-service`.

- Scope headers: `X-Tenant-Id`, `X-Workspace-Id`, `X-Actor-Id`
- Idempotency: `Idempotency-Key` on mutating routes
- Persistence target env: `ASTLOOM_PROJECT_PROFILE_DATABASE_URL`
- Tests: `tests/backend/services/project-profile-service/`

## Related Documents

- `backend/docs/API_NAMING_AND_CONTRACT_STANDARD.md` — HTTP naming and contract conventions
- Sibling service design docs under `docs/` for the owning phase vertical slice

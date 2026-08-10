---
doc_id: as.doc.memory.phase-2-api-contract
title: Memory Service Phase 2 API Contract
doc_type: contract
status: active
schema_version: '1.0'
owner: memory-service
summary: This contract documents the Phase 2 vertical slice for Memory and Context. The service
  owns scoped MemoryItems, QuestionMemory, ContextBundles, WorkBatches, and memory-service
  outbox events.
tags:
- api
- contract
- memory
- phase-2
phase: phase-2
canonical_path: backend/services/memory-service/docs/phase-2-api-contract.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
doc_version: 1.1.1
updated_at: 2026-08-10
linked_symbols:
- backend/services/memory-service/src/memory_service/core/items.py::MemoryItemCommands.promote_memory
- backend/services/memory-service/src/memory_service/core/items.py::MemoryItemCommands.deprecate_memory
---

# Memory Service Phase 2 API Contract

Path: `backend/services/memory-service/docs/phase-2-api-contract.md`

## Purpose

This contract documents the Phase 2 vertical slice for Memory and Context. The service owns scoped MemoryItems, QuestionMemory, ContextBundles, WorkBatches, and memory-service outbox events. Human-like remember/forget is supported through promote (long-term), deprecate (soft forget), pin, and working-memory `expires_at`.

## Scope Headers

Every command and scoped query uses:

- `X-Tenant-Id`
- `X-Workspace-Id`
- `X-Actor-Id` for commands and context bundle builds
- `X-Correlation-Id` when a caller needs deterministic trace linkage
- `Idempotency-Key` for retryable commands

All endpoints are scoped under `/api/v1/projects/{project_id}` and return snake_case JSON fields.

## Commands

- `POST /api/v1/projects/{project_id}/memory-items`
- `PATCH /api/v1/projects/{project_id}/memory-items/{memory_item_id}`
- `POST /api/v1/projects/{project_id}/memory-items/{memory_item_id}:promote`
- `POST /api/v1/projects/{project_id}/memory-items/{memory_item_id}:deprecate`
- `POST /api/v1/projects/{project_id}/memory-promotions`
- `POST /api/v1/projects/{project_id}/memory-consolidations`
- `POST /api/v1/projects/{project_id}/memory-decays`
- `POST /api/v1/projects/{project_id}/context-bundles`
- `POST /api/v1/projects/{project_id}/question-memories`
- `POST /api/v1/projects/{project_id}/question-memories/{question_id}:promote-faq`
- `POST /api/v1/projects/{project_id}/question-memories/{question_id}:resolve-documentation`
- `POST /api/v1/projects/{project_id}/work-batches`
- `POST /api/v1/projects/{project_id}/work-batches/{batch_id}:mark-ready`

## Queries

- `GET /api/v1/projects/{project_id}/memory-items` (`state`, `kind`, `pinned`, `q`)
- `GET /api/v1/projects/{project_id}/memory-items/{memory_item_id}`
- `GET /api/v1/projects/{project_id}/context-bundles:explain`
- `GET /api/v1/projects/{project_id}/repeated-questions`
- `GET /api/v1/projects/{project_id}/curious-questions`
- `GET /api/v1/projects/{project_id}/work-batches/{batch_id}`
- `GET /api/v1/projects/{project_id}/stale-memory`

## Remember / forget semantics

| Action | Effect |
|---|---|
| Promote | `kind=semantic`, `state=active`, clears `expires_at` |
| Deprecate | `state=deprecated`; excluded from default ContextBundles; still listable |
| Decay | `state=stale`; temporary sidelining |
| Working `expires_at` | Lazy mark-stale on list/get/retrieve when past |
| Pin | Retrieval score boost; browser filter |

Memory public fields include `pinned` and `expires_at`. Schema revision: migration `0005_memory_retention.sql`.

## Event Types

The development outbox emits versioned memory-service events:

- `MemoryItemCreated`
- `MemoryItemUpdated`
- `MemoryPromotedToLongTerm`
- `MemoryItemDeprecated`
- `MemoryConsolidationCompleted`
- `MemoryDecayCompleted`
- `ContextBundleBuilt`
- `QuestionObserved`
- `FAQPromoted`
- `DocumentationDraftCreated`
- `DocumentationTaskSuggested`
- `KnowledgeGapCreated`
- `BatchReadyForConsolidation`

Each event contains `event_id`, `event_type`, `event_version`, `occurred_at`, `producer`, scope fields, `actor_ref`, `correlation_id`, `causation_id`, `idempotency_key`, `payload`, and `evidence_refs`.

## Compatibility

This is an active Phase 2 contract. Breaking changes require a new contract note, matching tests, and a migration or compatibility statement before promotion to shared contracts.

## Related Documents

- `backend/docs/API_NAMING_AND_CONTRACT_STANDARD.md` — HTTP naming and contract conventions
- Memory Browser UI (not implemented UI): `docs/02-memory-and-context/14-memory-browser-and-long-term-selection-ui.md`
- Sibling service design docs under `docs/` for the owning phase vertical slice

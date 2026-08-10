# Memory Service

Path: `backend/services/memory-service`

## Purpose

Implements Phase 2: scoped working, episodic, semantic, restricted, and deprecated memory; consolidation; retrieval-ready ContextBundles; human remember/forget (promote long-term, deprecate, pin, working TTL); QuestionMemory and FAQ promotion; WorkBatch readiness; and versioned outbox events.

## Modular Boundary

The service owns MemoryItems, QuestionMemory, WorkBatches, ContextBundle construction, memory weighting, and Phase 2 event publication. It must not read core-data-service, code-graph-service, docs-sync-service, or rule-engine-service databases directly; integrations must use APIs, events, SDK contracts, or projections.

## Allowed Contents

- README and design notes for this boundary.
- Source, configuration, fixtures, tests, or generated artifacts that belong to this boundary.
- Subdirectories that follow the backend structure standard.

## Public Interfaces

Documented in `docs/phase-2-api-contract.md`.

- `/api/v1/projects/{project_id}/memory-items` (list filters: `state`, `kind`, `pinned`, `q`)
- `/api/v1/projects/{project_id}/memory-items/{id}` (GET/PATCH)
- `/api/v1/projects/{project_id}/memory-items/{id}:promote` / `:deprecate`
- `/api/v1/projects/{project_id}/memory-promotions`
- `/api/v1/projects/{project_id}/memory-consolidations`
- `/api/v1/projects/{project_id}/memory-decays`
- `/api/v1/projects/{project_id}/context-bundles`
- `/api/v1/projects/{project_id}/context-bundles:explain`
- `/api/v1/projects/{project_id}/question-memories`
- `/api/v1/projects/{project_id}/question-memories/{question_id}:promote-faq`
- `/api/v1/projects/{project_id}/question-memories/{question_id}:resolve-documentation`
- `/api/v1/projects/{project_id}/repeated-questions`
- `/api/v1/projects/{project_id}/curious-questions`
- `/api/v1/projects/{project_id}/work-batches`
- `/api/v1/projects/{project_id}/work-batches/{batch_id}:mark-ready`
- `/api/v1/projects/{project_id}/stale-memory`

## Engineering Standards

The vertical slice follows `backend/docs/ENGINEERING_STANDARDS.md`: dependencies are injected into `MemoryService`, domain entities are framework-free, PostgreSQL implements the Store port, retryable commands require idempotency keys, expected failures use typed errors, events are written through an outbox, scope is enforced before retrieval, and unit tests use deterministic in-memory infrastructure.

## Testing

Executable tests live under `tests/backend/services/memory-service`.

Run:

```bash
PYTHONPATH=backend/services/memory-service/src .venv/bin/python -m pytest tests/backend/services/memory-service
```

## Operational Notes

`config/memory-service.example.env` documents the local development settings. Runtime and integration persistence uses the service-owned `memory` PostgreSQL schema and migrations. The in-memory Store fake is limited to unit and transport-contract tests.

## Rules

- Keep ownership clear and local to this boundary.
- Do not hard-code ports, credentials, tenant IDs, project IDs, model names, provider endpoints, or feature behavior.
- Prefer dependency inversion: domain and application logic should not depend on infrastructure implementation details.
- Use shared packages only for stable contracts or cross-cutting primitives.
- Add or update tests and documentation when this boundary receives implementation code.

## Status

Active Phase 2 vertical slice.

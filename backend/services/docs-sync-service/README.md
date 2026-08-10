# Docs Sync Service

Path: `backend/services/docs-sync-service`

## Purpose

Implements Phase 3: scoped symbol indexing for drift, document indexing with frontmatter validation, AST-hash anchors, drift detection, documentation drafts, Bloom filter lookup, CI gate evaluation, and versioned outbox events.

## Modular Boundary

The service owns Documents, DocAnchors, DriftFindings, DocumentationDrafts, doc coverage projections, and Phase 3 event publication. It must not read core-data-service, memory-service, code-graph-service, or rule-engine-service databases directly; integrations must use APIs, events, SDK contracts, or projections.

## Public Interfaces

Documented in `docs/phase-3-api-contract.md`.

- `/api/v1/projects/{project_id}/symbols`
- `/api/v1/projects/{project_id}/documents`
- `/api/v1/projects/{project_id}/documents:validate-frontmatter`
- `/api/v1/projects/{project_id}/anchors`
- `/api/v1/projects/{project_id}/drift-detections`
- `/api/v1/projects/{project_id}/drift-findings`
- `/api/v1/projects/{project_id}/coverage`
- `/api/v1/projects/{project_id}/missing-docs`
- `/api/v1/projects/{project_id}/impact:explain`
- `/api/v1/projects/{project_id}/bloom-lookups`
- `/api/v1/projects/{project_id}/drafts`
- `/api/v1/projects/{project_id}/drafts/{draft_id}:approve`
- `/api/v1/projects/{project_id}/ci-gate`

## Testing

Executable tests live under `tests/backend/services/docs-sync-service`.

```bash
PYTHONPATH=backend/services/docs-sync-service/src .venv/bin/python -m pytest tests/backend/services/docs-sync-service
```

## Operational Notes

`config/docs-sync-service.example.env` documents local development settings. Runtime persistence uses the service-owned `docs_sync` PostgreSQL schema and migrations. The in-memory Store fake is limited to unit and transport-contract tests.

## Status

Active Phase 3 vertical slice.

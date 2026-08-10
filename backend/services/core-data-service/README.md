# Core Data Service

Path: `backend/services/core-data-service`

## Purpose

Implements Phase 1: scoped Activities, WorkLogs, Decisions, Issues, Tasks, lifecycle changes, idempotent commands, and audit outbox events.

## Boundary

The service owns its records and exposes them only through the Core Data HTTP contract. PostgreSQL is the only runtime and integration persistence backend, configured through `ASTLOOM_CORE_DATA_DATABASE_URL`.

## Public Interfaces

- `/api/v1/projects/{project_id}/activities`
- `/api/v1/projects/{project_id}/work-logs`
- `/api/v1/projects/{project_id}/decisions`
- `/api/v1/projects/{project_id}/decisions/{decision_id}:supersede`
- `/api/v1/projects/{project_id}/issues`
- `/api/v1/projects/{project_id}/open-issues`
- `/api/v1/projects/{project_id}/tasks`
- `/api/v1/projects/{project_id}/tasks/{task_id}:transition`
- `/api/v1/projects/{project_id}/issues/{issue_id}:transition`
- `/api/v1/projects/{project_id}/decisions/{decision_id}:transition`
- `/api/v1/projects/{project_id}/task-board`
- `/api/v1/projects/{project_id}/decision-history`
- `/api/v1/projects/{project_id}/related-work`
- `/api/v1/projects/{project_id}/evidence-bundles/{evidence_ref}`
- `/api/v1/projects/{project_id}/timeline`

## Testing

Run `.venv/bin/python -m pytest tests/backend/services/core-data-service`.

All executable tests live under the root `tests/` tree, with backend tests in `tests/backend` and frontend tests in `tests/frontend`.

## Status

Active Phase 1 vertical slice covering the documented Core Data commands, read queries, scoped records, idempotency, decision supersession, critical issue task decomposition or escalation, timeline reconstruction, redaction, and versioned outbox events.

Runtime persistence uses the service-owned `core_data` PostgreSQL schema and migrations. Unit and transport-contract tests use a deterministic in-memory Store fake; it is not a deployment persistence option.

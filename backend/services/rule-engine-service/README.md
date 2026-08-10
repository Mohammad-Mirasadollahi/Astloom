# Rule Engine Service

Path: `backend/services/rule-engine-service`

## Purpose

Implements Phase 4: policy registry, deterministic pre-checks, local semantic judge adapter, escalation/approval, impact-driven task routing, anomaly signals, rule feedback, and versioned outbox events.

## Modular Boundary

The service owns Rules, RuleEvaluations, ApprovalRequests, ImpactMaps, RoutedTasks, AnomalySignals, and Phase 4 event publication. It must not read sibling service databases directly; integrations must use APIs, events, SDK contracts, or projections.

## Public Interfaces

Documented in `docs/phase-4-api-contract.md`.

- `/api/v1/projects/{project_id}/rules`
- `/api/v1/projects/{project_id}/rules/{rule_id}:update-version`
- `/api/v1/projects/{project_id}/evaluations`
- `/api/v1/projects/{project_id}/evaluations:shadow`
- `/api/v1/projects/{project_id}/approvals`
- `/api/v1/projects/{project_id}/approvals/{approval_id}:resolve`
- `/api/v1/projects/{project_id}/task-routes`
- `/api/v1/projects/{project_id}/rule-feedback`
- `/api/v1/projects/{project_id}/approval-queue`
- `/api/v1/projects/{project_id}/anomalies`
- `/api/v1/projects/{project_id}/rule-health`

## Testing

Executable tests live under `tests/backend/services/rule-engine-service`.

```bash
PYTHONPATH=backend/services/rule-engine-service/src .venv/bin/python -m pytest tests/backend/services/rule-engine-service
```

## Operational Notes

`config/rule-engine-service.example.env` documents local development settings. Runtime persistence uses the service-owned `rule_engine` PostgreSQL schema and migrations. The in-memory Store fake and `HeuristicJudge` are limited to unit/transport tests and local deterministic semantic judgment (no external model calls).

## Status

Active Phase 4 vertical slice.

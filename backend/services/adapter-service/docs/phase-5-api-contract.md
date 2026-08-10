---
doc_id: as.doc.adapter.phase-5-api-contract
title: Adapter Service Phase 5 API Contract
doc_type: contract
status: active
schema_version: '1.0'
owner: adapter-service
summary: This contract documents the Phase 5 interoperability vertical slice. The service
  owns scoped connectors, adapter mappings, Universal Agent JSON validation/normalization,
  in-service broker publish/subscribe/delivery/replay/dead-letter handling, external tickets,
  department work...
tags:
- adapter
- api
- contract
- phase-5
phase: phase-5
canonical_path: backend/services/adapter-service/docs/phase-5-api-contract.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
doc_version: 1.3.1
updated_at: 2026-08-10
linked_symbols:
- backend/services/adapter-service/src/adapter_service/api.py::build_app
- backend/services/adapter-service/src/adapter_service/core/models.py::ExternalTicket
- backend/services/adapter-service/src/adapter_service/core/tickets.py::TicketCommands
- backend/services/adapter-service/src/adapter_service/core/service.py::AdapterService
- backend/services/adapter-service/src/adapter_service/postgres_store.py::PostgresStore
- backend/services/adapter-service/src/adapter_service/trackers.py::build_tracker_registry
- backend/packages/outbox_relay/handlers.py::TicketDispatchHandler
---

# Adapter Service Phase 5 API Contract

Path: `backend/services/adapter-service/docs/phase-5-api-contract.md`

## Purpose

This contract documents the Phase 5 interoperability vertical slice. The service owns scoped connectors, adapter mappings, Universal Agent JSON validation/normalization, in-service broker publish/subscribe/delivery/replay/dead-letter handling, external tickets, department workflow tasks, and adapter-service outbox events.

## Module Layout

Domain logic is packaged under `adapter_service/core/` (replacing the former monolith `core.py`). Public imports remain stable:

```text
from adapter_service.core import AdapterService, ExternalTicket, Scope, Store, …
```

| Module | Responsibility |
|---|---|
| `core/models.py` | Entities (`ExternalTicket`, `Connector`, `AdapterMapping`, …) |
| `core/enums.py` / `core/errors.py` / `core/constants.py` | States, exceptions, protocol constants |
| `core/protocols.py` | `Store`, `TrackerAdapter` ports |
| `core/helpers.py` | Timestamps, sanitize/digest, page tokens, status_map normalize |
| `core/tickets.py` | ExternalTicket commands (`TicketCommands` mixin) |
| `core/connectors.py` | Connector register/validate/health/mapping |
| `core/broker.py` | Subscribe, publish, replay, delivery |
| `core/context.py` | Context injection and department workflow triggers |
| `core/service.py` | `AdapterService` composition + `emit` |
| `core/__init__.py` | Compatibility re-exports |

HTTP composition stays in `api.py`; persistence in `postgres_store.py`; tracker registry in `trackers.py`.

## Scope Headers

Every command and scoped query uses:

- `X-Tenant-Id`
- `X-Workspace-Id`
- `X-Actor-Id` for commands
- `X-Correlation-Id` when a caller needs deterministic trace linkage
- `Idempotency-Key` for retryable commands

All endpoints are scoped under `/api/v1/projects/{project_id}` and return snake_case JSON fields.

## Commands

- `POST /api/v1/projects/{project_id}/connectors`
- `POST /api/v1/projects/{project_id}/connectors/{connector_id}:validate`
- `POST /api/v1/projects/{project_id}/connectors/{connector_id}:rotate-credential`
- `POST /api/v1/projects/{project_id}/subscriptions`
- `POST /api/v1/projects/{project_id}/vendor-events:normalize`
- `POST /api/v1/projects/{project_id}/agent-events`
- `POST /api/v1/projects/{project_id}/broker:replay`
- `POST /api/v1/projects/{project_id}/external-tickets`
- `POST /api/v1/projects/{project_id}/external-tickets/{ticket_id}:sync-status`
- `POST /api/v1/projects/{project_id}/external-tickets/{ticket_id}:retry-dispatch`
- `POST /api/v1/projects/{project_id}/external-tickets/{ticket_id}:record-dispatch-result`
- `POST /api/v1/projects/{project_id}/external-tickets/{ticket_id}:push-status`
- `POST /api/v1/projects/{project_id}/context:inject`

## Queries

- `GET /api/v1/projects/{project_id}/capabilities`
- `GET /api/v1/projects/{project_id}/connectors/{connector_id}/health`
- `GET /api/v1/projects/{project_id}/subscriptions`
- `GET /api/v1/projects/{project_id}/dead-letters`
- `GET /api/v1/projects/{project_id}/connectors/{connector_id}/mappings`
- `GET /api/v1/projects/{project_id}/department-tasks`
- `GET /api/v1/projects/{project_id}/external-tickets`
- `GET /api/v1/projects/{project_id}/external-tickets/{ticket_id}`

## External Ticket Contract

External tickets are scoped by tenant, workspace, and project. List queries support connector, status, external reference, department, update-time, page-size, and stable page-token filters.

Connector registration may include mapping policy fields persisted on the active `AdapterMapping`:

- `status_map` — vendor status string → portable `open|in_progress|done|canceled`;
- `unknown_status_policy` — `reject` or `fallback` with `fallback_status`;
- `reopen_policy` — `allow_remote` or `deny`;
- `mapping_version` — integer recorded on accepted `ExternalStatusSynced` events.

Status synchronization requires:

- `expected_version` for optimistic concurrency;
- timezone-aware `external_updated_at` for stale-update rejection;
- an explicit source (`manual`, `webhook`, `poll`, `adapter`, or `reconciliation`);
- an idempotency key.

Dispatch state is independent from the portable ticket state. Creation records `pending` and emits `ExternalTicketDispatchRequested`. The outbox `TicketDispatchHandler` (flag `ASTLOOM_OUTBOX_TICKET_DISPATCH_HANDLER`) invokes a `TrackerAdapter` (`local` always; `jira` / `linear` / `github-issues` when env credentials are set) and records `succeeded`, `failed`, or `dead_lettered` through the same dispatch-result command used by operators. Retry returns dispatch to `pending` while incrementing its attempt count. Optional `:push-status` calls `TrackerAdapter.update_remote_status` for outbound status updates and emits `ExternalTicketStatusPushed`.

Optional portable fields include description summary, priority, severity, assignee reference, due time, labels, remote URL, synchronization metadata, and a size-bounded sanitized extension object.

Schema revisions: migration `0003_external_ticket_hardening.sql`, mapping policy migration `0004_external_ticket_mapping_policy.sql`.

## Event Types

- `ConnectorRegistered`
- `ConnectorValidated`
- `CapabilityChanged`
- `AdapterNormalizedOutput`
- `AgentEventReceived`
- `BrokerEventPublished`
- `BrokerDeliveryFailed`
- `DeadLetterCreated`
- `IdeNotificationSent`
- `ExternalTicketCreated`
- `ExternalTicketDispatchRequested`
- `ExternalTicketDispatchSucceeded`
- `ExternalTicketDispatchFailed`
- `ExternalTicketStatusPushed`
- `ExternalStatusSynced`
- `ExternalStatusRejected`
- `DepartmentTaskCreated`

## Compatibility

This is an active Phase 5 contract. A future split into standalone `broker-service` should preserve these message and subscription semantics.

## Related Documents

- `backend/docs/API_NAMING_AND_CONTRACT_STANDARD.md` — HTTP naming and contract conventions
- ExternalTicket as-built spec: `docs/05-interoperability-ecosystem/13-external-ticketing-improvement-specification.md`
- Live assessment: `docs/05-interoperability-ecosystem/12-external-ticketing-live-quality-assessment.md`
- Focused ExternalTicket unit tests: `tests/backend/services/adapter-service/test_external_tickets.py`
- Process HTTP quality smoke: `tests/live/adapter-service/smoke_ticketing_quality.py`
- Tracker mapping: `docs/05-interoperability-ecosystem/10-external-vcs-and-tracker-mapping.md`
- AgentTicket (distinct): `backend/services/orchestration-service/docs/phase-orchestration-api-contract.md`
- Integrations: `backend/integrations/tickets/README.md`

---
doc_id: as.doc.interop.external-ticketing-live-quality-assessment
title: 12 - External Ticketing Live Quality Assessment
doc_type: gap
status: active
schema_version: '1.0'
owner: adapter-service
summary: 'As-built quality assessment of the ExternalTicket HTTP, persistence, idempotency,
  status-sync, dispatch, tracker-adapter, and audit path, with remediation status through
  TQ-008 and optional outbound status push.'
tags:
- ticketing
- external-ticket
- live-qa
- quality
phase: 05-interoperability-ecosystem
canonical_path: docs/05-interoperability-ecosystem/12-external-ticketing-live-quality-assessment.md
lifecycle_lane: current
concern_lane: problem
audience_lane:
- platform-engineering
- service-owners
- agents
authority: informative
visibility: internal
linked_symbols:
- backend/services/adapter-service/src/adapter_service/api.py::build_app
- backend/services/adapter-service/src/adapter_service/core/models.py::ExternalTicket
- backend/services/adapter-service/src/adapter_service/core/tickets.py::TicketCommands
- backend/services/adapter-service/src/adapter_service/core/service.py::AdapterService
- backend/services/adapter-service/src/adapter_service/postgres_store.py::PostgresStore
- backend/services/adapter-service/src/adapter_service/trackers.py::build_tracker_registry
- backend/packages/outbox_relay/handlers.py::TicketDispatchHandler
related_docs:
- as.doc.adapter.phase-5-api-contract
- as.doc.interop.external-ticketing-improvement-specification
- as.doc.interop.external-vcs-tracker-mapping
- as.doc.master.agent-control-plane-boundary
language: en
doc_version: 1.4.1
updated_at: 2026-08-10
---

# 12 - External Ticketing Live Quality Assessment

## Purpose

Record the verified quality of the currently implemented `ExternalTicket` slice and identify improvements without presenting the broader documented `AgentTicket` board UI as shipped behavior. AgentTicket HTTP lifecycle quality is verified separately against orchestration-service (see process smoke below).

## Implementation Status

**Hardened ExternalTicket slice is current (2026-08-01).** Adapter Service implements scoped queries, optimistic concurrency, stale-update rejection, mapping-policy reopen/status maps, dispatch create/retry/record, optional `:push-status`, TrackerAdapter registry (local + env-gated Jira/Linear/GitHub Issues), and outbox `TicketDispatchHandler`. Domain logic is modularized under `adapter_service/core/` (see Module Layout below). The separate canonical AgentTicket lifecycle is implemented in orchestration-service and must not be conflated with ExternalTicket.

## Module Layout (2026-08-01)

The former monolith `adapter_service/core.py` was split into package `adapter_service/core/` without changing the public import path `from adapter_service.core import …`.

| Path | Role |
|---|---|
| `core/models.py` | `ExternalTicket` and related entities |
| `core/tickets.py` | Ticket commands mixin (`create` / `sync` / `dispatch` / `push`) |
| `core/connectors.py` / `core/broker.py` / `core/context.py` | Other service command mixins |
| `core/helpers.py` | Page tokens, status_map normalize, sanitize |
| `core/service.py` | `AdapterService` composition |
| `tests/backend/services/adapter-service/test_external_tickets.py` | Focused ExternalTicket unit regression for the modular package |

## Process HTTP Smoke (2026-07-31)

After applying migrations `adapter/0004` and `orchestration/0003`, adapter-service (`:32170`) and orchestration-service (`:32192`) were restarted against main PostgreSQL (`127.0.0.1:32232`). Executable: `tests/live/adapter-service/smoke_ticketing_quality.py`.

Result: **`LIVE_SMOKE_PASS`**.

| Check | Result |
|---|---|
| Connector register + validate (`vendor=local`, mapping policy) | ready |
| ExternalTicket create + idempotent replay | same id, `dispatch_status=pending` |
| `LocalTrackerAdapter.create_remote` (same path as outbox handler) + HTTP durable read | `succeeded`, `external_ref` set, version bump |
| Optimistic concurrency (`expected_version` mismatch) | HTTP `409` / `version_conflict` |
| `status_map` sync (`Done` → portable `done`) | status `done` |
| List filter + get | ticket visible under project filters |
| `:push-status` via live process `LocalTrackerAdapter.update_remote_status` | succeeded |
| Cross-project isolation | HTTP `404` |
| AgentTicket create → `:claim` → `:start` on orchestration-service | `assigned` → `claimed` → `in_progress` |

Example run ids: `project_id=ticket-smoke-48938342f8`, `external_ticket_id=cf75d370-9087-4ea1-a14f-4d84b111e038` (version `4`, status `done`), `agent_ticket_id=atk_ec9541b20d9e` (status `in_progress`).

Quality verdict for this stage: **correctness and quality gates for the local tracker path hold** (idempotency, concurrency, mapping, isolation, durable adapter create/push). Cloud vendor round-trips remain opt-in via the vendor sandbox test.

## Live Verification Snapshot

The short live scenario ran the real FastAPI application from `backend/services/adapter-service/src/adapter_service/api.py::build_app` against the active Astloom PostgreSQL database.

Test scope:

```text
tenant_id=live-audit
workspace_id=astloom
project_id=ticket-live-audit
correlation_id=ticket-live-audit-20260728
external_ref=AUDIT-TICKET-20260728-01
```

| Step | HTTP result | Observed state | Local latency |
|---|---:|---|---:|
| Register connector | `200` | `pending_configuration`, version `1` | `26.465ms` |
| Validate connector | `200` | `ready`, version `2` | `15.038ms` |
| Create external ticket | `200` | `open`, version `1` | `14.557ms` |
| Retry create with the same idempotency key | `200` | Same ID and creation timestamp | `9.721ms` |
| Synchronize status | `200` | `done`, version `2` | `12.529ms` |
| Restart service and retry create | `200` | Same ID, `done`, version `2` | `17.672ms` |

These timings are local smoke-test observations, not service-level objectives.

PostgreSQL outbox evidence contained:

- `ConnectorRegistered`
- `ConnectorValidated`
- `CapabilityChanged`
- `ExternalTicketCreated`
- `ExternalStatusSynced`

The focused existing regression test passed: `1 passed in 0.50s`.

## Baseline Quality Assessment

This table records the pre-remediation state observed on 2026-07-28.

| Quality dimension | Assessment | Evidence |
|---|---|---|
| HTTP correctness | Good | All intended commands returned `200` with stable snake_case payloads |
| Persistence | Strong | Ticket state and timestamps survived a clean process restart |
| Idempotency | Strong | Repeated create returned the same record without a duplicate |
| Traceability | Strong | Actor, scope, correlation, evidence references, version, and outbox events were retained |
| Local performance | Good | Observed command latency remained below `27ms` |
| Data completeness | Limited | The record is adequate for a mirror but not a full work-management ticket |
| State integrity | Limited | Status synchronization assigns any known enum value without an explicit transition or stale-update policy |
| Query ergonomics | Incomplete | No public list or get endpoint exists for external tickets |
| Concurrency safety | Incomplete | Status mutation does not require an expected version |
| Vendor integration proof | Incomplete | The live scenario verified Astloom persistence, not a real Jira, Linear, or equivalent remote API |
| Live regression coverage | Incomplete | The useful path is covered by unit tests but has no canonical live PostgreSQL test under `tests/live/` |

## Remediation Status

| Finding | Status on 2026-07-31 | Implementation evidence |
|---|---|---|
| TQ-001 | Resolved | Scoped list/item routes, filters, and stable page tokens |
| TQ-002 | Resolved | Expected-version checks plus atomic PostgreSQL update predicates |
| TQ-003 | Resolved | Remote timestamps, stale rejection, same-state policy, and per-mapping reopen / status_map / unknown-status policy |
| TQ-004 | Resolved | Migration `0003` and backward-compatible operational fields |
| TQ-005 | Resolved at the Astloom boundary | Independent dispatch state, result callback, failure/dead-letter evidence, retry, and outbox `TicketDispatchHandler`; opt-in vendor sandbox remains external verification |
| TQ-006 | Resolved | Canonical main-infrastructure live pytest and executable wrapper under `tests/live/adapter-service/` |
| TQ-007 | Resolved | Docs distinguish ExternalTicket from AgentTicket (orchestration-service owns AgentTicket HTTP lifecycle) |
| TQ-008 | Resolved (opt-in) | Env-gated Jira/Linear/GitHub adapters under `backend/integrations/tickets/` plus create/status-push sandbox live test |
| TQ-009 | Resolved (optional) | `:push-status` + `TrackerAdapter.update_remote_status` + `ExternalTicketStatusPushed` |

## Baseline Improvement Findings

The findings below preserve the original failure descriptions and rationale. The remediation table above is the current status.

### TQ-001: External Tickets Cannot Be Queried Through the Public API

Severity: High

The current contract exposes create and status-sync commands but no external-ticket list or item query. Operators and agents cannot retrieve the canonical current record without replaying an idempotent command or reading PostgreSQL directly.

Required improvement:

- add scoped list and item queries;
- support status, connector, external reference, and update-time filters;
- use stable pagination;
- preserve the existing project isolation boundary.

### TQ-002: Status Updates Lack Optimistic Concurrency

Severity: High

`backend/services/adapter-service/src/adapter_service/core/tickets.py` (via `AdapterService`) increments `version`, but the caller does not supply `expected_version`. Two status writers can overwrite one another without an explicit conflict.

Required improvement:

- require `expected_version` or an equivalent `If-Match` precondition;
- return a structured conflict containing current version and status;
- keep idempotency and concurrency checks independent.

### TQ-003: Transition and Stale-Update Policy Is Implicit

Severity: Medium

The current status-sync path validates only membership in `open`, `in_progress`, `done`, or `canceled`. It does not define:

- which transitions are permitted;
- whether a remote tracker may reopen a ticket;
- how out-of-order webhooks are detected;
- whether a same-state update increments the version;
- how native authority and external mirror authority interact.

Direct `open → done` may be legitimate for an external mirror, but it must be an explicit policy rather than an accidental consequence of enum assignment.

### TQ-004: Ticket Data Is Too Small for Enterprise Operations

Severity: Medium

The current record provides identity, title, department, external reference, source event, evidence references, status, version, and timestamps. It lacks optional operational fields commonly needed for synchronization and review:

- description summary;
- priority and severity;
- assignee reference;
- due date or service-level target;
- labels or normalized categories;
- remote update timestamp;
- last synchronization outcome and error;
- remote URL;
- connector-specific metadata under a bounded extension field.

These fields should remain optional so the base contract stays portable.

### TQ-005: Local Record Creation Does Not Prove Remote Ticket Creation

Severity: Medium

The verified create command stores a local mirror and emits an outbox event. The test did not prove dispatch to, response normalization from, or retry behavior against a real external tracker.

Required improvement:

- distinguish local mirror creation from remote dispatch success;
- record dispatch state and remote acknowledgement;
- provide a deterministic local adapter process for mandatory live tests;
- keep real Jira or Linear sandbox tests opt-in and secret-safe.

### TQ-006: Canonical Live Coverage Is Missing

Severity: Medium

The current unit regression covers the domain path, but the live PostgreSQL scenario is not encoded under `tests/live/adapter-service/`.

A future live test should cover:

- connector readiness;
- ticket create and idempotent retry;
- status synchronization;
- persistence across application restart;
- outbox event presence;
- cross-project denial;
- expected-version conflict;
- invalid or stale status update.

### TQ-007: ExternalTicket and AgentTicket Readiness Must Stay Distinct

Severity: High

The API catalog documents a complete `AgentTicket` lifecycle, while the active implementation verified here is `ExternalTicket`. Product summaries, demos, and retrieval results must not use the passing ExternalTicket smoke test as evidence that the complete AgentTicket board and lifecycle are shipped.

## Priority

| Priority | Findings | Exit condition |
|---|---|---|
| P0 | TQ-001, TQ-002, TQ-007 | Tickets are queryable, concurrent writers conflict safely, and product truth distinguishes the two ticket types |
| P1 | TQ-003, TQ-005, TQ-006 | Transition policy, dispatch evidence, and canonical live coverage exist |
| P2 | TQ-004 | Optional operational fields are added through a backward-compatible schema revision |

## Verified Implementation Anchors

- API composition and routes: `backend/services/adapter-service/src/adapter_service/api.py::build_app`
- Ticket entity and service behavior: `backend/services/adapter-service/src/adapter_service/core/models.py::ExternalTicket`
- Commands and dispatch: `backend/services/adapter-service/src/adapter_service/core/tickets.py` / `core/service.py::AdapterService`
- Focused unit regression: `tests/backend/services/adapter-service/test_external_tickets.py`
- Tracker registry: `backend/services/adapter-service/src/adapter_service/trackers.py::build_tracker_registry`
- Outbox dispatch handler: `backend/packages/outbox_relay/handlers.py::TicketDispatchHandler`
- Durable store: `backend/services/adapter-service/src/adapter_service/postgres_store.py::PostgresStore`
- Unit regression: `tests/backend/services/adapter-service/test_adapter_service.py`
- Live main infrastructure: `tests/live/adapter-service/test_external_ticketing_main_infrastructure.py`
- Process HTTP quality smoke (adapter + orchestration): `tests/live/adapter-service/smoke_ticketing_quality.py`
- Opt-in vendor sandbox: `tests/live/adapter-service/test_external_ticketing_vendor_sandbox.py`

## Scope Limits

This ExternalTicket assessment does not claim:

- mandatory CI proof of a live third-party tracker round trip (vendor sandbox remains opt-in with credentials);
- AgentTicket board UI quality (AgentTicket HTTP lifecycle lives in orchestration-service);
- authorization correctness beyond the tested project scope;
- load, soak, failover, or multi-region performance.

## Related Documents

- [External Ticketing Improvement Specification](13-external-ticketing-improvement-specification.md)
- [External VCS And Tracker Mapping](10-external-vcs-and-tracker-mapping.md)
- [Agent Control Plane Product Boundary](../00-master-plan/07-agent-control-plane-product-boundary.md)
- [Astloom API Catalog](../14-api-design-and-naming-standards/04-astloom-api-catalog.md)
- `backend/services/adapter-service/docs/phase-5-api-contract.md`

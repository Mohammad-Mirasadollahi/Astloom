# Adapter Service

Path: `backend/services/adapter-service`

## Purpose

Implements Phase 5 interoperability: Universal Agent JSON, connector registry, vendor normalization, in-service pub/sub broker with replay and dead-letter handling, IDE notification delivery, scoped context injection, external tickets, and governed department workflow tasks.

## Modular Boundary

The service owns connectors, adapter mappings, broker events/subscriptions/deliveries/dead letters, external tickets, and department tasks for this vertical slice. It must not read sibling service databases directly.

ExternalTicket is a local mirror of optional tracker projections (Jira/Linear/GitHub Issues). It is not AgentTicket; native agent assignment lifecycle lives in `orchestration-service`.

Domain logic lives in the modular package `adapter_service.core/` (former monolith `core.py`, split 2026-08-01). Public imports remain `from adapter_service.core import …`.

```text
src/adapter_service/core/
  models.py      ExternalTicket, Connector, AdapterMapping, …
  tickets.py     ExternalTicket commands (TicketCommands)
  connectors.py  connector register / validate / mapping
  broker.py      publish / subscribe / deliver / replay
  context.py     context injection + department triggers
  helpers.py     sanitize, page tokens, status_map helpers
  service.py     AdapterService composition
  __init__.py    stable re-exports
```

## Public Interfaces

Documented in `docs/phase-5-api-contract.md` (includes module layout).

ExternalTicket commands include create, list/get, `:sync-status`, `:retry-dispatch`, `:record-dispatch-result`, and `:push-status`.

Tracker adapters:

- Local deterministic adapter always registered as `local`
- Vendor HTTP adapters under `backend/integrations/tickets/{jira,linear,github-issues}/`
- Registry: `adapter_service.trackers.build_tracker_registry`
- Outbox consumer: `outbox_relay.handlers.TicketDispatchHandler` (`ASTLOOM_OUTBOX_TICKET_DISPATCH_HANDLER`)

## Testing

```bash
PYTHONPATH=backend/services/adapter-service/src:backend/packages \
  .venv/bin/python -m pytest tests/backend/services/adapter-service -q
```

Focused ExternalTicket unit tests: `tests/backend/services/adapter-service/test_external_tickets.py`.

The canonical PostgreSQL live test uses the same service composition and main Astloom database:

```bash
tests/live/adapter-service/run-main-infrastructure.sh
```

Opt-in vendor sandbox (skips without credentials):

```bash
PYTHONPATH=backend/services/adapter-service/src \
  .venv/bin/python -m pytest tests/live/adapter-service/test_external_ticketing_vendor_sandbox.py -m live
```

The mandatory live test must not use `InMemoryStore`, a substitute API, or a test-only database.

## Migrations

Apply in order under `migrations/`:

1. `0001_adapter.sql`
2. `0002_outbox_published.sql`
3. `0003_external_ticket_hardening.sql`
4. `0004_external_ticket_mapping_policy.sql`

## Operational Notes

`config/adapter-service.example.env` documents local development settings. Runtime persistence uses the service-owned `adapter` PostgreSQL schema. Broker semantics are co-located for the Phase 5 slice; a later extract to `broker-service` should keep the same contracts.

## Status

Active Phase 5 vertical slice. ExternalTicket hardening TKT-01…TKT-09 is implemented as of 2026-07-31.

LLM calls initiated by Astloom (when adapters leave stub mode) must use the LiteLLM gateway per `docs/13-technology-stack-and-platform-decisions/09-litellm-llm-gateway.md`.

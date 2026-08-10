# Orchestration Service

Path: `backend/services/orchestration-service`

## Purpose

Owns agent routing, workflow coordination, work batches/assignments, and the native **AgentTicket** lifecycle (claim / start / block / submit-review / complete / fail / cancel / reassign).

## Modular Boundary

This service owns WorkBatch, Assignment, and AgentTicket aggregates in the `orchestration` PostgreSQL schema (document store with `kind` discriminator). It must not import private internals from sibling services.

AgentTicket is distinct from ExternalTicket (adapter-service tracker mirrors).

## Public Interfaces

Documented in `docs/phase-orchestration-api-contract.md` and catalogued in `docs/14-api-design-and-naming-standards/04-astloom-api-catalog.md`.

AgentTicket:

```text
GET/POST .../agent-tickets
GET .../agent-tickets/{id}
POST .../:claim|:start|:block|:submit-review|:complete|:fail|:cancel|:reassign
```

Mutations require `expected_version`. Create without `agent_id` → `created`; with `agent_id` → `assigned`.

## Migrations

1. `0001_orchestration.sql`
2. `0002_outbox_published.sql`
3. `0003_agent_ticket.sql` — optional index for `kind='agent_ticket'`

## Testing

```bash
PYTHONPATH=backend/services/orchestration-service/src \
  .venv/bin/python -m pytest tests/backend/services/orchestration-service -q
```

Process HTTP smoke (with restarted adapter + orchestration listeners):

```bash
PYTHONPATH=backend/packages:backend/services/adapter-service/src \
  .venv/bin/python tests/live/adapter-service/smoke_ticketing_quality.py
```

## Status

Vertical slice implemented, including AgentTicket catalog routes (2026-07-31). Canonical tests live under `tests/backend/services/orchestration-service/`. Process HTTP smoke (`LIVE_SMOKE_PASS`) verified create → claim → start against a restarted orchestration-service on 2026-07-31.

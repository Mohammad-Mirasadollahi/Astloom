# Migrations

Path: `backend/services/orchestration-service/migrations`

## Purpose

Service-owned persistence migrations. Parent service: `services/orchestration-service`.

## Migration Order

1. `0001_orchestration.sql` — schema, documents, idempotency, outbox.
2. `0002_outbox_published.sql` — outbox publication tracking.
3. `0003_agent_ticket.sql` — optional partial index for `kind = 'agent_ticket'`.

AgentTicket records are stored as `orchestration.documents` rows with `kind='agent_ticket'` (no separate table required for the MVP).

## Status

Active. Apply numbered files in order before relying on AgentTicket list performance indexes.

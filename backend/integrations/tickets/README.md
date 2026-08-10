# Tickets

Path: `backend/integrations/tickets`

## Purpose

Ticketing integrations for optional ExternalTicket remote projections (Jira, Linear, GitHub Issues).

## Modular Boundary

HTTP create adapters live in this tree. Adapter Service composes them through `adapter_service.trackers.build_tracker_registry` and must remain the system of record for ExternalTicket mirrors. Domain commands that call adapters live in `adapter_service.core.tickets` (`dispatch_external_ticket`, `push_external_ticket_status`).

## Contents

| Path | Adapter |
|------|---------|
| `jira/adapter.py` | Jira REST create |
| `linear/adapter.py` | Linear GraphQL create |
| `github-issues/adapter.py` | GitHub Issues REST create |
| `_http.py` | Shared HTTP JSON helper |

Local deterministic adapter remains in `adapter_service.trackers.LocalTrackerAdapter`.
Outbox consumer: `outbox_relay.handlers.TicketDispatchHandler`.

## Status

Implemented; vendor adapters are env-gated and optional for CI.

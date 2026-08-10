# Migrations

Path: `backend/services/adapter-service/migrations`

## Purpose

Service-owned persistence migrations. Parent service: `services/adapter-service`.

## Modular Boundary

This directory is part of the Astloom backend modular architecture. It must expose behavior through documented contracts, public interfaces, configuration, or events. It must not import private internals from sibling modules.

## Allowed Contents

- README and design notes for this boundary.
- Source, configuration, fixtures, tests, or generated artifacts that belong to this boundary.
- Subdirectories that follow the backend structure standard.

## Rules

- Keep ownership clear and local to this boundary.
- Do not hard-code ports, credentials, tenant IDs, project IDs, model names, provider endpoints, or feature behavior.
- Prefer dependency inversion: domain and application logic should not depend on infrastructure implementation details.
- Use shared packages only for stable contracts or cross-cutting primitives.
- Add or update tests and documentation when this boundary receives implementation code.

## Migration Order

1. `0001_adapter.sql` creates the Adapter Service schema and base tables.
2. `0002_outbox_published.sql` adds outbox publication tracking.
3. `0003_external_ticket_hardening.sql` adds ExternalTicket query indexes, operational fields, dispatch state, and synchronization constraints.
4. `0004_external_ticket_mapping_policy.sql` adds `status_map`, `reopen_policy`, `unknown_status_policy`, `fallback_status`, and `mapping_version` on `adapter.mappings`.

## Status

Active. New Compose volumes apply the files in order. Existing installations must apply the next numbered migration before starting code that requires it.

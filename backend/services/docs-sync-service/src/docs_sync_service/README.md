# docs_sync_service package

## Purpose

In-process docs-sync domain, application service, Store port, and adapters
(Postgres / in-memory) used by Astloom CLI Phase 2 and MCP platform backends.

## Boundaries

- May: expose `DocsSyncService`, `Store` protocol, domain models, and adapters.
- Must not: reach into code-graph Neo4j; invent `DOCUMENTED_BY` edges (graph owns that).
- Concrete Postgres construction belongs in `bootstrap.py` (or tests), not API handlers.

## Start here

1. `service.py` — `DocsSyncService` commands (index, drift, coverage, CI gate)
2. `ports.py` — `Store` protocol
3. `models.py` / `enums.py` / `errors.py` — domain types
4. `postgres_store.py` / `testing.py` — adapters
5. `core.py` — compatibility re-exports for older imports

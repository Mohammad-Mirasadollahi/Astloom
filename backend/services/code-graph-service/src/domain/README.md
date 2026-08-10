# Domain

Path: `backend/services/code-graph-service/src/domain`

## Purpose

Service-level scaffold for pure domain ownership. Implementation for this service lives under the importable package:

- `backend/services/code-graph-service/src/code_graph_service/domain/`

## Modular Boundary

This directory documents the domain layer boundary for `code-graph-service`. Runtime domain modules are packaged as `code_graph_service.domain` so imports stay service-scoped (`from code_graph_service.domain ...`).

## Allowed Contents

- README and design notes for this boundary.
- Cross-links to the packaged domain modules.

## Rules

- Keep ownership clear and local to this boundary.
- Domain must not depend on infrastructure adapters (Postgres, Neo4j, HTTP).
- Prefer dependency inversion through the `Store` port.

## Status

Active via `code_graph_service.domain` (enums, models, languages, parsing,
ports, embeddings, documentation, `impact`, `http_calls`, communities, explore).

Canonical map: `../code_graph_service/domain/README.md`.

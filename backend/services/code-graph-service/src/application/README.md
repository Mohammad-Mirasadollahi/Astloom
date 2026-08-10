# Application

Path: `backend/services/code-graph-service/src/application`

## Purpose

Service-level scaffold for use-case ownership. Implementation lives under:

- `backend/services/code-graph-service/src/code_graph_service/application/`

## Package layout

| Module | Responsibility |
|--------|----------------|
| `support.py` | Shared helpers (`_put_edge`, `_event`, `_symbol_view`) |
| `ingest.py` | File ingest, edge writing, unresolved-call relink |
| `queries.py` | Symbol/structural/semantic queries, polyglot profile |
| `generation.py` | Generation-context packs and generated-code validation |
| `service.py` | `CodeGraphService` facade composing the use-case mixins |

## Status

Active via `code_graph_service.application`.

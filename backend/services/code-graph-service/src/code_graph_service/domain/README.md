# code_graph_service.domain

Path: `backend/services/code-graph-service/src/code_graph_service/domain/`

## Purpose

Pure domain for the Code-Knowledge Graph: symbols, edges, parsers, retrieval
helpers, and Codebase-Memory hybrid structural algorithms. No FastAPI, Neo4j
driver, or Postgres imports here.

## Boundaries

- **Owns:** enums, models, language matrix, parsers, impact/callers, HTTP_CALLS
  extractors, communities, explore packing, risk, freshness helpers.
- **Does not own:** Store adapters (`neo4j/`, `postgres_store.py`), HTTP routes
  (`api/`), MCP dispatch.

## Start here

| File | Role |
| --- | --- |
| `enums.py` | `RelType` / `SymbolKind` / confidence (includes `HTTP_CALLS`, `ASYNC_CALLS`) |
| `impact.py` | Directed impact, caller ranking, `escalate_hint` |
| `http_calls.py` | Client HTTP/async call extraction |
| `languages.py` | Language matrix + guards |
| `parsers/` | Tree-sitter adapters (TS/JS/Go/Rust) |
| `explore.py` | Budget + skeletonization for explore packs |

## Related

- Hybrid design: `docs/07-code-knowledge-graph/44`–`47`
- Package README law: `docs/08-software-engineering-architecture/50-package-folder-readme-standard.md`

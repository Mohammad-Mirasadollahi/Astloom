# Neo4J

Path: `backend/platform/persistence/neo4j`

## Purpose

Graph persistence integration boundary for the Code-Knowledge Graph. Neo4j stores structural code relationships. Semantic embeddings remain in PostgreSQL pgvector.

## Modular Boundary

This directory is part of the Astloom backend modular architecture. It must expose behavior through documented contracts, public interfaces, configuration, or events. It must not import private internals from sibling modules.

## Allowed Contents

- README and design notes for this boundary.
- Cypher schema / constraint scripts under `cypher/`.
- APOC configuration under `conf/`.
- Shared helpers that belong to this persistence boundary.
- Subdirectories that follow the backend structure standard.

## Runtime Plugins

Compose enables:

- **APOC** (`apoc`) — path expansion, batch helpers, merge/meta utilities
- **Graph Data Science** (`graph-data-science`) — degree/path ranking for impact and context prioritization

See `docs/07-code-knowledge-graph/12-neo4j-runtime-plugins.md`.

`Neo4jStore.capabilities()` probes `apoc` / `gds` / fulltext (and reports
`gds_enabled` / `gds_concurrency`). GDS usage is opt-in via
`ASTLOOM_NEO4J_GDS_ENABLED` (default `true`) with concurrency capped at **4**
(Community Edition). Advanced expansion uses APOC when present and falls back
to one-hop Cypher otherwise. See
`docs/07-code-knowledge-graph/32-intentional-fallbacks-and-neo4j-plugin-licensing.md`.

## Runtime Adapter

The Phase 7 service adapter lives in:

- `backend/services/code-graph-service/src/code_graph_service/neo4j_store.py`

Select it with (Neo4j is the service default):

```bash
ASTLOOM_CODE_GRAPH_STORE=neo4j
ASTLOOM_NEO4J_URI=bolt://127.0.0.1:32287
ASTLOOM_NEO4J_USER=neo4j
ASTLOOM_NEO4J_PASSWORD=<local-secret>
ASTLOOM_NEO4J_DATABASE=neo4j
```

Rollback / parity against PostgreSQL:

```bash
ASTLOOM_CODE_GRAPH_STORE=postgres
ASTLOOM_CODE_GRAPH_DATABASE_URL=postgresql://astloom:<secret>@127.0.0.1:32232/astloom
```

Canonical projection: `CodeSymbol` + `CODE_REL` (`docs/07-code-knowledge-graph/13-codesymbol-projection-adr.md`). Structural parity: `code_graph_service.domain.parity`.

When `ASTLOOM_CODE_GRAPH_DATABASE_URL` is set alongside Neo4j:

- Semantic vectors land in `code_graph.symbol_embeddings` (pgvector)
- Outbox events are mirrored to `code_graph.outbox` for the Postgres `outbox-relay` worker
- Pin production images with `ASTLOOM_NEO4J_IMAGE` (see `docs/07-code-knowledge-graph/12-neo4j-runtime-plugins.md`)

Schema constraints in `cypher/0001_code_graph_constraints.cypher` are applied by `Neo4jStore.ensure_schema()` on startup. Do not bind whole directories or conf files under `/var/lib/neo4j/` as read-only mounts; Neo4j chowns that tree on startup. Keep `conf/apoc.conf` as a reference and configure APOC through Compose `NEO4J_apoc_*` variables.

## Language Policy

Python is a **required** (mandatory) code-graph language. The Neo4j cutover must not regress Python ingest, symbol hashing, call/import edges, or generation-context packs.

## Rules

- Keep ownership clear and local to this boundary.
- Do not hard-code ports, credentials, tenant IDs, project IDs, model names, provider endpoints, or feature behavior.
- Prefer dependency inversion: domain and application logic should not depend on infrastructure implementation details.
- Use shared packages only for stable contracts or cross-cutting primitives.
- Add or update tests and documentation when this boundary receives implementation code.

## Status

Active. Cypher constraints + APOC/GDS Compose plugins. Service-owned `Neo4jStore` implements the Code Graph `Store` port with optional multi-hop expansion and degree ranking.

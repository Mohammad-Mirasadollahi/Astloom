# code-graph-service

Phase 7 Code-Knowledge Graph vertical slice for Astloom.

## Package layout

```text
code_graph_service/
  domain/          # enums, models, languages, parsing, parsers/, ports, embeddings, docs
  application/     # ingest / queries / generation use cases + CodeGraphService facade
  api/             # FastAPI build_app + route modules (ingest, query, edit_session, …)
  core.py          # compatibility re-exports (prefer domain/application imports)
  postgres_store.py
  neo4j_store.py
  bootstrap.py
  testing.py
```

## Owns

- Python file ingestion via stdlib `ast` (**required** language)
- TypeScript, JavaScript, Go, and Rust ingestion via tree-sitter adapters (`domain/parsers/`)
- Polyglot project profiling (`language-profile`) that detects related multi-language clusters
- Normalized symbol hashing and change detection
- Local documentation generation for **changed symbols only** (`LlmBackedDocGenerator` via LiteLLM when enabled; heuristic fallback)
- Graph edges: `CONTAINS`, `CALLS`, `IMPORTS`, `INHERITS_FROM`, `DOCUMENTED_BY`, `ROUTES_TO`, `TESTED_BY`, `HTTP_CALLS`, `ASYNC_CALLS`
- ADR 48 parsing authority: durable `CODE_REL` rejects LSP/IDE session writers; `reconcile_after_edit` marks pending and optionally AST re-ingests
- Feature 49 edit session: local LSP `ide_references` / `ide_definition` / `ide_rename` (`reference_kind=ide_semantic`); never dual-writes the graph
- Call resolution confidence: `exact` / `probable` / `ambiguous` / `unresolved` (import-alias aware; `getattr(obj, "name")` call refs)
- Wave 1–3 intelligence: framework routes, `TESTED_BY`, surgical `explore`, risk-scored `detect_changes`, architecture overview, hybrid search, freshness
- Dead-code intelligence (doc `36`): scored `unused_candidates` (`unused_symbol` / `unreachable_file` / `dead_subgraph` / `zombie_package` / `unwired_shared_package` / optional `runtime_dead` / `flag_controlled_dead`) with evidence, CallConfidence policy, `index_coverage`, and `kpi_hints`
- Shared packages (doc `79`): `code-metadata` validators on ingest + generation escalation; `common-context` scoring used by `common-context-service`; package zombies classified `wire` / `keep_public` / `retire` (never `safe_to_delete` for those kinds)
- Future smell/risk categories (doc `80`, not shipped): extend `quality_audit` / `unused_candidates` — no new MCP tool
- Codebase-Memory hybrid (docs `44`–`47`): ranked `callers`, directed `impact`, `community`, structural-first `escalate_hint`
- Production retrieval: BM25 + Neo4j/Postgres FTS + BGE (default) / LiteLLM / stub via RRF (docs `07-code-knowledge-graph/27`–`31`)
- Local BGE / LiteLLM embeddings for semantic ranking (pgvector when `ASTLOOM_CODE_GRAPH_DATABASE_URL` set; default dims 1024)
- Structural neighbor queries (APOC expand when available) and graph-guided generation context packs (`uses_full_repository=false`)
- Generated-code unknown-symbol validation (call-site focused)
- Outbox events `FileIngested`, `SymbolsDocumented`

## Config

Repo-root `.env.example` documents local development settings (LiteLLM, Neo4j, embeddings).

- Default store: Neo4j (`ASTLOOM_CODE_GRAPH_STORE=neo4j` + `ASTLOOM_NEO4J_*`)
- Rollback / parity store: PostgreSQL schema `code_graph` (`ASTLOOM_CODE_GRAPH_STORE=postgres`)
- With `ASTLOOM_CODE_GRAPH_DATABASE_URL`: pgvector `symbol_embeddings` + Postgres outbox mirror (relay-compatible)
- Structural parity helper: `domain/parity.py` (`compare_stores`, `ingest_both_and_compare`)
- Canonical Neo4j projection: `CodeSymbol` + `CODE_REL` (see `docs/07-code-knowledge-graph/13-codesymbol-projection-adr.md`)
- Production embeddings: `ASTLOOM_EMBEDDING_PROVIDER=local_bge` (optional extra `embeddings`); `LocalEmbeddingStub` is test/fallback only
- Optional Leiden: extra `graph-analytics` (`scikit-network`); otherwise in-process Louvain
- Optional Neo4j GDS degree: `ASTLOOM_NEO4J_GDS_ENABLED=true` (default), concurrency ≤ 4 Community cores

## Tests

```bash
PYTHONPATH=backend/services/code-graph-service/src \
  .venv/bin/python -m pytest tests/backend/services/code-graph-service/ -q

# Live MCP HTTP (Compose + MCP up):
.venv/bin/python -m pytest tests/live/code-graph-service/ -m live -v
```

## Contract

See `docs/phase-7-api-contract.md`. Language policy: `docs/07-code-knowledge-graph/10-language-support-policy.md`.

Normative dead-code / package docs: `36`, `79`, `80` under `docs/07-code-knowledge-graph/`.

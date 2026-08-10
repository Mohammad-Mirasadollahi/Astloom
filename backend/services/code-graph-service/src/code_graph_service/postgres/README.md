# postgres package

## Purpose

SQL strings and helpers for code-graph Postgres side adapters (pgvector
embeddings + outbox mirror). Adapters that open connections live in
``postgres_side.py``.

## Boundaries

- May: parameterized SQL / dims-templated DDL used by embedding and outbox adapters.
- Must not: open DB connections; Neo4j Cypher; ingest orchestration.

## Start here

1. `sql.py` — statement constants + `create_symbol_embeddings_table`
2. `../postgres_side.py` — `PostgresEmbeddingIndex` / `PostgresOutboxMirror`

---
doc_id: as.doc.ckg.neo4j-migration-plan
title: Code-Knowledge Graph — Neo4j Migration Plan
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Plan and record the cutover from the Phase 7 PostgreSQL `code_graph` projection to
  Neo4j as the **default** structural graph store, without regressing mandatory Python language
  support.
tags:
- standard
- ckg
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/11-neo4j-migration-plan.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- tests/backend/gates/neo4j-python-ingest/run_gate.py::main
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Code-Knowledge Graph — Neo4j Migration Plan

## Purpose

Plan and record the cutover from the Phase 7 PostgreSQL `code_graph` projection to Neo4j as the **default** structural graph store, without regressing mandatory Python language support.

## Current State

- Phase 7 behavioral slice is implemented in `backend/services/code-graph-service/`.
- **Default persistence is Neo4j** (`ASTLOOM_CODE_GRAPH_STORE=neo4j`).
- PostgreSQL remains available for rollback and structural parity (`ASTLOOM_CODE_GRAPH_STORE=postgres`).
- Neo4j adapter: `neo4j_store.py`; Compose starts Neo4j under profile `core`.
- Canonical projection: `CodeSymbol` + `CODE_REL` (ADR `13-codesymbol-projection-adr.md`).
- Python is **required** (`stdlib_ast`). TypeScript, JavaScript, Go, and Rust are supported via tree-sitter.
- Structural parity helper: `domain/parity.py` (`compare_stores`, `ingest_both_and_compare`).

## Non-Negotiable Gate: Python Support

Before any production cutover (and for any future schema enrichment):

1. Python ingest round-trip must pass on Neo4j (symbols, CONTAINS/CALLS/IMPORTS/INHERITS_FROM/DOCUMENTED_BY).
2. Hash-based change detection must document only changed Python symbols.
3. Generation-context packs and generated-code validation must work for Python repositories.
4. `required_languages()` must include `python` and `assert_required_languages_supported()` must pass at service startup.

A Neo4j cutover that breaks Python support is a release blocker.

## Cutover Steps

1. ~~Run Neo4j locally via Compose (`--profile core`) and point a staging service at `ASTLOOM_CODE_GRAPH_STORE=neo4j`.~~ Done.
2. Replay a representative Python repository through ingest on both stores.
3. Compare symbol counts, edge counts, and sample neighbor queries via `domain/parity.py` / live `test_code_graph_parity.py`.
4. Keep outbox consumers compatible (`FileIngested`, `SymbolsDocumented`).
5. ~~Switch production default store to Neo4j.~~ Done (`Settings.from_environment` default `neo4j`).
6. Retain Postgres for embeddings (pgvector via `code_graph.symbol_embeddings`), outbox mirror for the relay worker, rollback, and any non-graph operational tables.

## Staging acceptance (Python gate)

Before promoting a Neo4j image or plugin change:

1. `backend/deployments/compose/wait-healthy.sh --timeout 90 astloom-postgres-1 astloom-neo4j-1`
2. `.venv/bin/python tests/backend/gates/neo4j-python-ingest/run_gate.py --require-live`

The gate runs live ingest, Postgres↔Neo4j parity, and hybrid (pgvector + outbox mirror) tests.

## Rollback

Set `ASTLOOM_CODE_GRAPH_STORE=postgres` and restart the service. Neo4j data remains intact for later retry; do not drop the Postgres `code_graph` schema until Neo4j has been the default for at least one full release cycle.

## Related Artifacts

- Schema design: `02-neo4j-schema-design.md`
- Projection ADR: `13-codesymbol-projection-adr.md`
- Language policy: `10-language-support-policy.md`
- Gap register: `GAP-011` in `../10-gap-analysis/01-gap-register.md` (**CLOSED**)
- Adapter: `backend/services/code-graph-service/src/code_graph_service/neo4j_store.py`
- Constraints: `backend/platform/persistence/neo4j/cypher/0001_code_graph_constraints.cypher`

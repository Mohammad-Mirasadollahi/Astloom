---
doc_id: as.doc.codegraph.codesymbol-projection-adr
title: 13 - CodeSymbol + CODE_REL Projection ADR
doc_type: adr
status: active
schema_version: '1.0'
owner: code-graph-lead
summary: Accepts the Phase 7 unified CodeSymbol node and CODE_REL relationship projection
  as the canonical Neo4j structural model for code-graph-service, instead of immediately implementing
  per-kind labels from the design catalog.
tags:
- neo4j
- code-graph
- adr
- schema
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/13-codesymbol-projection-adr.md
lifecycle_lane: current
concern_lane: design
audience_lane:
- platform-engineering
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- docs/07-code-knowledge-graph/02-neo4j-schema-design.md
- docs/07-code-knowledge-graph/11-neo4j-migration-plan.md
- docs/10-gap-analysis/01-gap-register.md
doc_version: 1.0.1
audience:
- engineer
- architect
primary_entities:
- CodeSymbol
- CODE_REL
- Neo4jStore
relations_declared:
- type: constrains
  target: backend/services/code-graph-service/src/code_graph_service/neo4j_store.py
- type: complements
  target: docs/07-code-knowledge-graph/02-neo4j-schema-design.md
chunk_hints:
  strategy: heading_h2
  max_tokens: 700
  overlap_tokens: 48
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 13 - CodeSymbol + CODE_REL Projection ADR


## Purpose

Accepts the Phase 7 unified CodeSymbol node and CODE_REL relationship projection as the canonical Neo4j structural model for code-graph-service, instead of immediately implementing per-kind labels from the design catalog.

## Status

Accepted (2026-07-20).

## Context

`02-neo4j-schema-design.md` catalogs typed Neo4j labels (`File`, `Class`, `Function`, `Method`, `Import`, …) and typed relationships. The Phase 7 vertical slice implements a single Store port across PostgreSQL and Neo4j using:

- Node label: `CodeSymbol` (kind carried as a property)
- Relationship type: `CODE_REL` (`rel_type` property: `CONTAINS`, `CALLS`, `IMPORTS`, `INHERITS_FROM`, `DOCUMENTED_BY`)

Both backends must stay interchangeable for ingest, parity checks, and rollback.

## Decision

1. **Canonical runtime projection** for `code-graph-service` is `CodeSymbol` + `CODE_REL` as implemented in `Neo4jStore` and `cypher/0001_code_graph_constraints.cypher`.
2. The typed catalog in `02-neo4j-schema-design.md` remains the **logical product vocabulary** and a future optional enrichment path — not a release blocker for Neo4j as the default structural store.
3. A migration to per-kind labels requires a new ADR and a dual-read period; it must not break Python ingest or Postgres rollback (`ASTLOOM_CODE_GRAPH_STORE=postgres`).

## Consequences

- Indexes and APOC/GDS helpers target `CodeSymbol` / `CODE_REL`.
- Cross-language and polyglot features stay kind/property based.
- Documentation that says “File/Class/Function nodes” should be read as logical kinds unless an enrichment ADR lands.

## Related

- Gap register: `GAP-011` closed when Neo4j became the default store.
- Migration plan: `11-neo4j-migration-plan.md`

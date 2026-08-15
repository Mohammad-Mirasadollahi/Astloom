---
doc_id: as.doc.codegraph.neo4j-runtime-plugins
title: 12 - Neo4j Runtime Plugins
doc_type: standard
status: active
schema_version: '1.0'
owner: code-graph-lead
summary: Default APOC and optional Graph Data Science runtime capabilities for
  Code-Knowledge Graph traversal, path expansion, and ranking algorithms.
tags:
- neo4j
- apoc
- gds
- code-graph
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/12-neo4j-runtime-plugins.md
lifecycle_lane: current
concern_lane: design
audience_lane:
- platform-engineering
- operators
authority: normative
visibility: internal
linked_symbols:
- tests/backend/gates/neo4j-python-ingest/run_gate.py::main
related_docs:
- docs/07-code-knowledge-graph/02-neo4j-schema-design.md
- docs/07-code-knowledge-graph/11-neo4j-migration-plan.md
- docs/07-code-knowledge-graph/32-intentional-fallbacks-and-neo4j-plugin-licensing.md
- docs/07-code-knowledge-graph/81-neo4j-memory-and-content-push-oom-runbook.md
doc_version: 1.2.0
audience:
- engineer
- architect
- operator
primary_entities:
- Neo4jRuntime
- APOC
- GraphDataScience
relations_declared:
- type: depends_on
  target: backend/deployments/compose/compose.yaml
- type: complements
  target: backend/platform/persistence/neo4j/
chunk_hints:
  strategy: heading_h2
  max_tokens: 700
  overlap_tokens: 48
language: en
security_classification: internal
updated_at: 2026-08-15
---

# 12 - Neo4j Runtime Plugins

## Purpose

Defines the Neo4j plugins Astloom can enable so the Code-Knowledge Graph can
use production-grade traversal and ranking capabilities without making normal
service restarts depend on external downloads.

## Required Plugins

| Plugin | Compose id | Runtime policy |
|--------|------------|-------------------------|
| APOC Core | `apoc` | Default. It ships in the Neo4j image, so Compose can install it without network access. |
| Graph Data Science | `graph-data-science` | Optional degree ranking via GDS **Community Edition**. Opt in through `ASTLOOM_NEO4J_PLUGINS`; the app still requires `ASTLOOM_NEO4J_GDS_ENABLED=true`. Free plugin, **≤4 CPU cores**. **Not required** for correctness; Cypher degree fallback always exists. Communities do **not** use GDS. |

Embeddings remain in PostgreSQL pgvector. Plugins do not replace pgvector.

## Compose Configuration

`backend/deployments/compose/compose.yaml` sets:

- `NEO4J_PLUGINS=${ASTLOOM_NEO4J_PLUGINS:-["apoc"]}`
- unrestricted/allow-listed procedures: `apoc.*`, `gds.*`
- APOC file import/export flags for local tooling via Compose environment variables (`NEO4J_apoc_*`)
- Reference `backend/platform/persistence/neo4j/conf/apoc.conf` for operators; do not bind-mount it under `/var/lib/neo4j/conf` (Neo4j chowns conf and read-only mounts fail startup)

Host ports remain non-default from the port profile (`32287` Bolt, `32474` HTTP).

Memory sizing for content-push is documented in
[`81-neo4j-memory-and-content-push-oom-runbook.md`](81-neo4j-memory-and-content-push-oom-runbook.md)
(`ASTLOOM_NEO4J_HEAP_*_SIZE`, `ASTLOOM_NEO4J_PAGECACHE_SIZE`).

## Capability Probe

`Neo4jStore.capabilities()` reports:

| Key | Meaning |
| --- | --- |
| `apoc` | APOC procedures callable |
| `gds` | GDS callable **and** `ASTLOOM_NEO4J_GDS_ENABLED=true` |
| `gds_enabled` | App opt-in flag (default `true`) |
| `gds_concurrency` | Threads for `gds.degree` (default/max **4** Community cores) |
| `fulltext` | Lucene fulltext index present |

Startup and live tests should treat missing plugins or `gds_enabled=false` as a
supported fallback runtime (Store CRUD still works; expansion/degree fall back).

## Env toggles (application)

| Variable | Default | Effect |
| --- | --- | --- |
| `ASTLOOM_NEO4J_PLUGINS` | `["apoc"]` | Compose plugin list. Add `graph-data-science` only when startup can reach its download host. |
| `ASTLOOM_NEO4J_GDS_ENABLED` | `true` | When `false`, skip all GDS calls (Cypher degree only) |
| `ASTLOOM_NEO4J_GDS_CONCURRENCY` | `4` | Passed to `gds.degree.stream`; **clamped to 1–4** (Community Edition core limit) |
| `ASTLOOM_NEO4J_HEAP_INITIAL_SIZE` | `4G` | Compose → `NEO4J_server_memory_heap_initial__size` |
| `ASTLOOM_NEO4J_HEAP_MAX_SIZE` | `4G` | Compose → `NEO4J_server_memory_heap_max__size`. Raise for large multi-hour content-push; see [`81`](81-neo4j-memory-and-content-push-oom-runbook.md). |
| `ASTLOOM_NEO4J_PAGECACHE_SIZE` | `1G` | Compose → `NEO4J_server_memory_pagecache_size` |

Compose installs GDS only when the plugin list opts in; the GDS-enabled env flag
separately controls whether Astloom **uses** an installed copy. Details:
[`32`](32-intentional-fallbacks-and-neo4j-plugin-licensing.md).

## JVM memory (Compose)

Compose **must not** hard-code a 512M heap. Defaults are **4G heap** and **1G
pagecache**, overridable via the env vars above. Under-sized heaps cause
`OutOfMemoryError: Java heap space` during long `ingest-push` runs; clients then
see Bolt handshake failures on `ASTLOOM_NEO4J_BOLT_PORT`. Operator runbook:
[`81-neo4j-memory-and-content-push-oom-runbook.md`](81-neo4j-memory-and-content-push-oom-runbook.md).

## Usage Boundaries

| Capability | Owner | Notes |
|------------|-------|-------|
| CRUD Store port | `neo4j_store.py` | Works without plugins |
| Multi-hop expansion | APOC `apoc.path.*` | Used when `capabilities()['apoc']` is true |
| Symbol ranking / impact hints | Optional `gds.degree` when `ASTLOOM_NEO4J_GDS_ENABLED` and Community plugin load | Free without Enterprise key; **concurrency ≤ 4**; Cypher fallback. See [`32`](32-intentional-fallbacks-and-neo4j-plugin-licensing.md). |
| Fulltext lexical | Neo4j Lucene index `code_symbol_fulltext_v2` | BM25-like; hybrid RRF with in-process BM25 + embeddings. Legacy `code_symbol_fulltext` is query-fallback only (no longer created). |
| Community detection | In-process (scikit-network Leiden or Louvain) | Portability: no GDS dependency. (GDS Community *could* run Leiden without Enterprise key, but Astloom does not call it.) |
| Semantic search | PostgreSQL pgvector | Not a Neo4j plugin concern |

## Licensing note (GDS)

Astloom Compose installs GDS **without** `gds.enterprise.license_file`, i.e.
**GDS Community Edition**: all algorithms available, concurrency capped at
**4 CPU cores**. App default: `ASTLOOM_NEO4J_GDS_ENABLED=true` with
`ASTLOOM_NEO4J_GDS_CONCURRENCY=4` so degree ranking stays within that free
limit. Unlocking unlimited cores / cluster GDS features requires a **paid**
Enterprise key — Astloom does not need that key. Full rationale:
[`32`](32-intentional-fallbacks-and-neo4j-plugin-licensing.md).

## Acceptance Criteria

- Fresh Compose `core` Neo4j boot installs APOC and GDS.
- `RETURN apoc.version()` succeeds.
- `RETURN gds.version()` succeeds when the Community plugin is installed (no Enterprise key required for probe / `gds.degree`).
- With `ASTLOOM_NEO4J_GDS_ENABLED=true` (default), degree may use `gds.degree` at concurrency ≤ 4.
- With `ASTLOOM_NEO4J_GDS_ENABLED=false`, `capabilities().gds` is false and degree uses Cypher only.
- Code-graph Neo4j live ingest continues to pass with plugins enabled.
- Without plugins, Store CRUD remains functional and expansion falls back to one-hop edge listing; degree ranking uses Cypher.
- Degree ranking prefers native `gds.graph.project` Cypher aggregation when GDS works (not deprecated `gds.graph.project.cypher`).

## Operational Notes

- First boot downloads plugins; healthcheck `start_period` is extended accordingly.
- Do not mount read-only trees under `/var/lib/neo4j` except explicit conf files such as `apoc.conf`.
- Production must set `ASTLOOM_NEO4J_IMAGE` to a **patch-pinned** tag (for example `neo4j:5.26.4-community`) rather than relying on the floating `5.26-community` default. Record `apoc.version()` and `gds.version()` after first healthy boot in the release notes.
- Python ingest acceptance gate: `tests/backend/gates/neo4j-python-ingest/run_gate.py` (use `--require-live` in CI with Compose).
- Wait for health with `backend/deployments/compose/wait-healthy.sh --timeout 90` — never chain endless sleep loops with pytest.

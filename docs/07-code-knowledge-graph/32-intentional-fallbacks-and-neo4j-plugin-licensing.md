---
doc_id: as.doc.ckg.intentional-fallbacks-and-plugin-licensing
title: 32 - Intentional Fallbacks And Neo4j Plugin Licensing
doc_type: adr
status: active
schema_version: '1.0'
owner: code-graph-lead
summary: Why Astloom keeps LocalEmbeddingStub, in-process Louvain, Cypher degree ranking,
  and legacy fulltext query fallback — plus Neo4j APOC/GDS Community vs Enterprise licensing
  and offline-safe plugin startup (APOC default, GDS opt-in, concurrency capped
  at 4 Community cores; verified 2026-07-25).
tags:
- licensing
- neo4j
- gds
- apoc
- fallback
- adr
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/32-intentional-fallbacks-and-neo4j-plugin-licensing.md
lifecycle_lane: current
concern_lane: decision
audience_lane:
- platform-engineering
- operators
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- docs/07-code-knowledge-graph/12-neo4j-runtime-plugins.md
- as.doc.ckg.prod-retrieval-feature-spec
- as.doc.ckg.prod-retrieval-risks
external_refs:
- https://neo4j.com/docs/graph-data-science/current/introduction/
- https://neo4j.com/docs/graph-data-science/current/installation/installation-enterprise-edition/
- https://neo4j.com/docs/graph-data-science/current/algorithms/degree-centrality/
doc_version: 1.1.1
audience:
- engineer
- architect
- operator
primary_entities:
- LocalEmbeddingStub
- LouvainFallback
- CypherDegreeFallback
- GdsCommunityEdition
relations_declared:
- type: complements
  target: docs/07-code-knowledge-graph/12-neo4j-runtime-plugins.md
- type: complements
  target: as.doc.ckg.prod-retrieval-risks
chunk_hints:
  strategy: heading_h2
  max_tokens: 700
  overlap_tokens: 48
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 32 - Intentional Fallbacks And Neo4j Plugin Licensing

## Purpose

Record **why** certain pre-production-stack components remain in the tree after
BM25 / BGE / APOC / Leiden work shipped — so they are not deleted as “dead
code” — and state **accurate** Neo4j APOC / GDS licensing for Astloom’s
no-paid-license constraint.

## Decision (intentional keepers)

| Kept component | Why it stays | When it runs | What must not happen |
| --- | --- | --- | --- |
| `LocalEmbeddingStub` | Offline tests, CI without torch/ST, and hard fallback if BGE/LiteLLM fail | `ASTLOOM_EMBEDDING_PROVIDER=stub`, construct failure, or LiteLLM disabled/fail | Must not be documented as production semantic quality |
| In-process Louvain (+ Leiden-style refine) | Communities must work with **zero** GDS/scikit-network install | `scikit-network` missing or Leiden call fails | Must not call Neo4j GDS Leiden as a hard dependency |
| Cypher degree ranking (`method: cypher.degree`) | Importance hints without GDS plugin or when `ASTLOOM_NEO4J_GDS_ENABLED=false` | `capabilities().gds` false or GDS call errors | Must not fail neighbors / generation-context when GDS absent |
| Legacy Neo4j fulltext query fallback (`code_symbol_fulltext`) | Old DBs may still have the pre-v2 index | v2 index missing; query prefers `code_symbol_fulltext_v2` | Must not **create** the legacy index on new `ensure_schema` |
| Optional `rank_bm25` on large corpora only | Package may be present; Lucene-style BM25 is SoT for small N | Corpus size ≥ 32 and package yields positive scores | Must not rely on classic BM25 IDF for tiny test corpora |

These are **deliberate degrade paths**, not obsolete duplicates of the production
stack in docs `27`–`31`.

## Neo4j plugin licensing (verified 2026-07-20)

Sources: [GDS Introduction — Editions](https://neo4j.com/docs/graph-data-science/current/introduction/),
[GDS Enterprise license file](https://neo4j.com/docs/graph-data-science/current/installation/installation-enterprise-edition/),
[Degree Centrality](https://neo4j.com/docs/graph-data-science/current/algorithms/degree-centrality/).

### APOC Core

- Installed via Compose `NEO4J_PLUGINS=['apoc', …]` with Neo4j **Community** images Astloom uses.
- Used for `apoc.path.expandConfig` (and related helpers). **No separate paid GDS-style key** for APOC Core in this deployment model.
- If APOC is missing: one-hop `list_edges` fallback (intentional).

### Graph Data Science (GDS)

| Edition | License / cost | What Astloom cares about |
| --- | --- | --- |
| **GDS Community Edition** (default when plugin is installed **without** `gds.enterprise.license_file`) | **Free / open GDS Community** — no Enterprise key | **Includes all algorithms** (including `gds.degree` and Leiden). Limits: **max 4 CPU cores** concurrency, limited catalog/model ops |
| **GDS Enterprise Edition** | **Paid** — requires valid `gds.enterprise.license_file` | Higher concurrency, cluster write, backup/restore, extended catalog — **Astloom does not require this** |

**Correction vs older wording:** “GDS Leiden requires a commercial license” is
**too strong**. Leiden *procedures* exist in **GDS Community**; what requires a
paid key is **GDS Enterprise** features (cores/cluster/catalog), not the
existence of Leiden itself.

### What Astloom actually calls from GDS

Controlled by **`ASTLOOM_NEO4J_GDS_ENABLED`** (default **`true`**) and
**`ASTLOOM_NEO4J_GDS_CONCURRENCY`** (default/max **`4`** Community cores).

| Call | Purpose | Free without Enterprise key? |
| --- | --- | --- |
| `gds.version()` | Capability probe (only when GDS enabled) | Yes (Community plugin present) |
| `gds.graph.project` (Cypher aggregation) | Temporary in-memory graph | Yes under GDS Community |
| `gds.degree.stream(..., {concurrency: ≤4})` | Optional degree importance hints | **Yes under GDS Community** — Astloom always passes concurrency ≤ 4 |
| `gds.leiden` / similar | **Not used** | Would be Community-capable, but Astloom keeps communities **in-process** |

When `ASTLOOM_NEO4J_GDS_ENABLED=false`, Astloom never probes or calls GDS
(`capabilities().gds` is false); degree ranking uses Cypher only.

Compose defaults to the image-bundled APOC plugin only. Operators may opt in to
`graph-data-science` with
`ASTLOOM_NEO4J_PLUGINS=["apoc","graph-data-science"]` when startup has access
to the plugin host. This avoids making every local Restart wait on the official
runtime downloader. **Production correctness never depends on GDS**: degree
falls back to Cypher; communities never call GDS.

## Env reference

| Variable | Default | Notes |
| --- | --- | --- |
| `ASTLOOM_NEO4J_PLUGINS` | `["apoc"]` | Compose plugin list; GDS is explicit opt-in because its installer fetches at startup |
| `ASTLOOM_NEO4J_GDS_ENABLED` | `true` | App opt-in for optional `gds.degree` |
| `ASTLOOM_NEO4J_GDS_CONCURRENCY` | `4` | Clamped to `1..4` (Community Edition core limit) |

Documented also in repo-root `.env.example` and
`docs/13-technology-stack-and-platform-decisions/12-litellm-environment-configuration.md`.

## Consequences

1. Docs and operators must distinguish **GDS Community (free, 4-core limit)**
   from **GDS Enterprise (paid)**.
2. Default ON uses at most those **4 cores**; never request Enterprise concurrency.
3. Do not remove stub / Louvain / Cypher degree / legacy FTS *query* fallback
   without an ADR that replaces each degrade path.
4. Prefer documenting “we avoid GDS for communities for portability,” not
   “Leiden is paid-only.”
5. Operators can set `ASTLOOM_NEO4J_GDS_ENABLED=false` to force Cypher-only
   degree even when the plugin is installed.

## Acceptance

- [x] This document lists every intentional keeper with a non-deletion reason.
- [x] GDS Community vs Enterprise called out with official edition semantics.
- [x] `ASTLOOM_NEO4J_GDS_ENABLED` default true; concurrency capped at 4.
- [x] `12-neo4j-runtime-plugins.md` and production-retrieval risks aligned to this ADR.
- [x] Code paths: GDS degree optional; Cypher degree always available; communities never require GDS.

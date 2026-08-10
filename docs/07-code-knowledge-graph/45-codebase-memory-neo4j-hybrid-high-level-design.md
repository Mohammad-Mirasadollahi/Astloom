---
doc_id: as.doc.ckg.codebase-memory-neo4j-hybrid-hld
title: 45 - Codebase-Memory Neo4j Hybrid High-Level Design
doc_type: hld
status: active
schema_version: '1.0'
owner: platform-architecture
summary: Runtime topology for Codebase-Memory-style structural MCP tools on Neo4j with hybrid
  escalate into explore and production retrieval inside code-graph-service.
tags:
- code-intelligence
- codebase-memory
- hld
- neo4j
- mcp
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/45-codebase-memory-neo4j-hybrid-high-level-design.md
lifecycle_lane: current
concern_lane: design
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.ckg.codebase-memory-neo4j-hybrid-feature-spec
- as.doc.ckg.codebase-memory-neo4j-hybrid-lld
- as.doc.ckg.codebase-memory-neo4j-hybrid-risks
- as.doc.codegraph.codesymbol-projection-adr
- as.doc.ckg.code-intel-hld
doc_version: 1.0.1
audience:
- engineer
- architect
- agent
primary_entities:
- CodeGraphService
- McpGateway
- Neo4jStore
- StructuralEscalatePolicy
relations_declared:
- type: depends_on
  target: as.doc.ckg.codebase-memory-neo4j-hybrid-feature-spec
- type: depends_on
  target: as.doc.codegraph.codesymbol-projection-adr
- type: complements
  target: as.doc.ckg.code-intel-hld
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 45 - Codebase-Memory Neo4j Hybrid High-Level Design

## Purpose

Defines how Codebase-Memory hybrid capabilities sit in Astloom runtime topology.
Algorithms and contracts live in [`46`](46-codebase-memory-neo4j-hybrid-low-level-design.md);
product requirements in [`44`](44-codebase-memory-neo4j-hybrid-feature-specification.md).

## Document flow

```mermaid
flowchart TD
  Agent[LLM_Agent] --> GW[mcp_gateway_service]
  GW --> CGS[code_graph_service]
  CGS --> Structural[Structural_queries]
  CGS --> Explore[Explore_hybrid_RAG]
  Structural --> Neo4j[(Neo4j_CKG)]
  Explore --> Neo4j
  Explore --> Source[Budgeted_source]
  Ingest[Ingest_Sync] --> Neo4j
  Structural -->|sparse_or_semantic| Explore
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Agent | Invokes structural MCP (`callers` / `impact` / `community`) | Low-token typed graph answer |
| 2 | Agent | If sparse or semantic need, escalates to `explore` / `hybrid_search` | Seeded call-path + compact bodies |
| 3 | Agent | Only then reads raw files under budget | Full nuance without default wide Grep |
| 4 | Operator / CI | Runs `sync` / ingest | Neo4j graph stays explicit-ingest fresh |

## Architectural Decision

**Decision:** Extend `code-graph-service` domain + application + Neo4j store;
expose via MCP gateway and existing HTTP where useful. Keep `CodeSymbol` +
`CODE_REL` projection; add `HTTP_CALLS` (and optionally `ASYNC_CALLS`) as
`rel_type` values.

**Rationale:** Structural and hybrid retrieval already share scope, stores, and
embeddings. A separate SQLite sidecar would split truth and violate ADR [`19`](19-competitive-code-intelligence-roadmap-adr.md).

**Alternatives rejected:**

| Alternative | Why rejected |
| --- | --- |
| Ship DeusData SQLite binary beside Neo4j | Dual SoR; SBOM; contradicts ADR 19 |
| Agent-only prompting without new tools | Non-deterministic; wastes tokens |
| 30+ MCP tools mirroring paper 1:1 | Prefer narrow tools + strong explore primary |

## Module Boundaries

| Area | Owns |
| --- | --- |
| `domain/impact.py` | Directed blast-radius pure functions |
| `domain/http_calls.py` | Client HTTP call extraction |
| `application/queries.py` | Callers / directed impact / community use cases |
| `application/intelligence.py` | Community map reuse; architecture overview |
| `neo4j/retrieval.py` | Optional Cypher fan-in ranking helpers |
| MCP `backends/code_graph/query.py` | Tool handlers + escalate hints in payloads |
| Usage profile + guidance | Tool registration and structural-first order |

## Dependencies

- Neo4j (+ APOC/GDS optional) — structural expand / degree
- Existing Leiden/Louvain in-process communities
- Production retrieval stack (`27`–`31`) for escalate path
- Explicit ingest / pending-sync (`03`, Wave 3 freshness)

## Related Documents

- Feature [`44`](44-codebase-memory-neo4j-hybrid-feature-specification.md)
- LLD [`46`](46-codebase-memory-neo4j-hybrid-low-level-design.md)
- Risks [`47`](47-codebase-memory-neo4j-hybrid-risks-and-acceptance.md)
- Code intel HLD [`23`](23-code-intelligence-enhancements-high-level-design.md)

---
doc_id: as.doc.ckg.prod-retrieval-contracts
title: 30 - Production Retrieval Stack Data Contracts And Events
doc_type: contract
status: active
schema_version: '1.0'
owner: code-graph-lead
summary: HTTP/MCP payload contracts for hybrid BM25+RRF search, path method, architecture
  algorithm, and retrieval transparency fields.
tags:
- contracts
- retrieval
- mcp
- api
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/30-production-retrieval-stack-data-contracts-and-events.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.ckg.prod-retrieval-feature-spec
- backend/services/code-graph-service/docs/phase-7-api-contract.md
doc_version: 1.0.1
audience:
- engineer
- agent
primary_entities:
- HybridSearchResult
- ArchitectureOverview
- SymbolPathResult
relations_declared:
- type: complements
  target: backend/services/code-graph-service/docs/phase-7-api-contract.md
chunk_hints:
  strategy: heading_h2
  max_tokens: 700
  overlap_tokens: 48
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 30 - Production Retrieval Stack Data Contracts And Events


## Purpose

HTTP/MCP payload contracts for hybrid BM25+RRF search, path method, architecture algorithm, and retrieval transparency fields.

## HTTP

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/v1/projects/{project_id}/graph/search:hybrid` | BM25 + semantic + FTS RRF |
| POST | `/api/v1/projects/{project_id}/graph/explore` | Includes `retrieval` mode |
| POST | `/api/v1/projects/{project_id}/graph/path` | Includes `method` |
| POST | `/api/v1/projects/{project_id}/graph/architecture-overview` | Includes `algorithm` |
| GET | `/api/v1/projects/{project_id}/graph/neo4j-capabilities` | `apoc`, `gds`, `fulltext`, `gds_enabled`, `gds_concurrency` |

### HybridSearchResult

```json
{
  "query": "string",
  "mode": "bm25|hybrid_rrf_semantic_bm25|hybrid_rrf_fts_semantic_bm25",
  "hits": [
    {
      "symbol_id": "string",
      "score": 0.0,
      "qualified_name": "string",
      "kind": "function",
      "file_path": "string"
    }
  ],
  "channels": { "bm25": 0, "semantic": 0, "fts": 0 },
  "embedding_backend": "string",
  "fts_method": "neo4j.fulltext|postgres.fts|null"
}
```

### SymbolPathResult (additions)

```json
{
  "method": "neo4j_shortest_path|in_memory_bfs",
  "reachable": true
}
```

### ArchitectureOverview (additions)

```json
{
  "algorithm": "scikit_network_leiden|louvain_leiden_refine|isolated_nodes"
}
```

### Structural neighbors (additions)

```json
{
  "expansion": "apoc_expand|store_expand|one_hop",
  "neo4j_capabilities": { "apoc": true, "gds": false, "fulltext": true }
}
```

## MCP (usage profile)

Unchanged tool names; payloads gain the fields above:

- `astloom_code_graph_hybrid_search`
- `astloom_code_graph_explore`
- `astloom_code_graph_path`
- `astloom_code_graph_architecture_overview`

## Env (operator)

| Variable | Default | Role |
| --- | --- | --- |
| `ASTLOOM_EMBEDDING_PROVIDER` | `local_bge` | `local_bge` \| `stub` \| `litellm` |
| `ASTLOOM_EMBEDDING_MODEL` | `BAAI/bge-large-en-v1.5` | ST model id |
| `ASTLOOM_EMBEDDING_DIMS` | `1024` | pgvector width |
| `ASTLOOM_EMBEDDING_LOCAL_ENABLED` | `true` | Allow local ST |
| `ASTLOOM_CODE_GRAPH_DATABASE_URL` | empty | pgvector + outbox mirror |
| `ASTLOOM_NEO4J_*` | Compose defaults | Structural store + FTS |
| `ASTLOOM_NEO4J_GDS_ENABLED` | `true` | Optional Community `gds.degree` (≤4 cores) |
| `ASTLOOM_NEO4J_GDS_CONCURRENCY` | `4` | Clamped to 1–4 |

Optional extras: `pip install 'astloom[embeddings]'`, `pip install 'astloom[graph-analytics]'`.

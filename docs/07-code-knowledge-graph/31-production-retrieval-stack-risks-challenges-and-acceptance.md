---
doc_id: as.doc.ckg.prod-retrieval-risks
title: 31 - Production Retrieval Stack Risks Challenges And Acceptance
doc_type: standard
status: active
schema_version: '1.0'
owner: code-graph-lead
summary: Risks, license constraints, and acceptance gates for the production retrieval stack
  (BM25, FTS, BGE, APOC, free Leiden).
tags:
- risks
- acceptance
- license
- retrieval
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/31-production-retrieval-stack-risks-challenges-and-acceptance.md
lifecycle_lane: current
concern_lane: problem
audience_lane:
- platform-engineering
- operators
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.ckg.prod-retrieval-feature-spec
- as.doc.ckg.prod-retrieval-lld
- as.doc.ckg.prod-retrieval-live-test-gates
doc_version: 1.0.1
audience:
- engineer
- architect
- operator
primary_entities:
- AcceptanceGate
relations_declared:
- type: depends_on
  target: as.doc.ckg.prod-retrieval-feature-spec
chunk_hints:
  strategy: heading_h2
  max_tokens: 600
  overlap_tokens: 40
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 31 - Production Retrieval Stack Risks Challenges And Acceptance


## Purpose

Risks, license constraints, and acceptance gates for the production retrieval stack (BM25, FTS, BGE, APOC, free Leiden).

## Risks

| ID | Risk | Mitigation |
| --- | --- | --- |
| R-01 | Agents believe stub embeddings are semantic | Report `embedding_backend`; default provider `local_bge` |
| R-02 | Neo4j FTS missing after upgrade | Create v1+v2 indexes in `ensure_schema`; degrade to BM25 |
| R-03 | APOC not installed | One-hop fallback; capabilities probe |
| R-04 | GDS commercial confusion | Doc [`32`](32-intentional-fallbacks-and-neo4j-plugin-licensing.md): Community GDS is free (4-core); Enterprise key not required. Communities stay in-process. |
| R-05 | GPL contamination via leidenalg | Forbidden; scikit-network (BSD) optional only |
| R-06 | BM25 zero scores on tiny corpora | Lucene-style positive IDF in-process |
| R-07 | Model download / disk for BGE | Cache dir `ASTLOOM_EMBEDDING_CACHE_DIR`; stub fallback |
| R-08 | Postgres FTS column absent | Migration `0006`; query falls back to on-the-fly tsvector |
| R-09 | Live suite AuthError looks like ~50 failures | Doc [`33`](33-production-retrieval-live-test-gates.md): skip policy + `pythonpath`; never ERROR-cascade module fixtures |

## License inventory (retrieval extras)

| Component | License | Role |
| --- | --- | --- |
| `rank-bm25` | Apache-2.0 | Optional accelerator for large BM25 corpora |
| `scikit-network` | BSD | Optional Leiden |
| Neo4j APOC Core | Neo4j plugin (Community-compatible install) | Path expand |
| Neo4j GDS | **Community** plugin free (all algos, 4-core limit); **Enterprise** paid | Astloom may call `gds.degree` optionally; never requires Enterprise; communities not on GDS — see [`32`](32-intentional-fallbacks-and-neo4j-plugin-licensing.md) |
| Sentence-Transformers / BGE weights | Model card / Apache-2.0 family (verify per model) | Local embeddings |

## Acceptance gates

- [x] BM25 lexical ranks relevant symbols in unit tests.
- [x] Hybrid response includes `mode`, `channels`, `embedding_backend`.
- [x] Neo4j fulltext v2 schema statement present; Lucene query OR-based.
- [x] Postgres FTS migration `0006_symbol_fts.sql` + `PostgresStore.fulltext_search`.
- [x] Explore uses APOC expand when available.
- [x] Path reports `method`; architecture reports `algorithm`.
- [x] Communities prefer scikit-network Leiden; Louvain fallback without GDS.
- [x] Docs `27`–`31` + index entry; code↔doc field names match.
- [x] Live/fuzzer/challenge gates documented in `33`; AuthError cascades skipped not ERROR-flooded; `pythonpath` in pyproject.
- [x] No GPL leidenalg/igraph dependency.

## Offline retrieval eval (Phase A — durable)

- [x] Offline nDCG harness: `tests/backend/services/code-graph-service/ckg_eval/` + `test_phase_a_honesty_eval.py`.
- [x] Sample-repo nDCG: `test_phase_a_probe_ndcg.py` on `samples/e2e-graph-probe` (≥1 real sample tree).
- [x] Report artifact: `tests/artifacts/code-graph-eval/retrieval-ndcg-latest.json`.
- **Minimum threshold:** mean nDCG@10 **≥ 0.5** on gold queries (callable/type symbols only). Fail the unit gate rather than market retrieval quality without the report.
- Labels are gold queries / human relevance — never graph self-walk (ADR 19).

## Open gaps

| Gap | Notes |
| --- | --- |
| Watcher daemon for freshness | Optional **batched** poll sidecar: `watch_pending_sync.py` + `astloom graph watch` (debounce + max-wait; pending-sync only) |
| Force BGE preload at process start | `ASTLOOM_EMBEDDING_PRELOAD=true` → `maybe_preload_embeddings` in `build_service` |

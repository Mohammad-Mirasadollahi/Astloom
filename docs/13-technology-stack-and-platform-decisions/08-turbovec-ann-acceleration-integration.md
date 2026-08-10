---
doc_id: as.doc.stack.turbovec-ann-acceleration
title: 08 - TurboVec ANN Acceleration Integration
doc_type: adr
status: active
schema_version: '1.0'
owner: platform-architecture
summary: This ADR defines how Astloom may combine with [turbovec](https://github.com/RyanCodrai/turbovec)
  — a Rust TurboQuant vector index with Python bindings — as an **optional in-process ANN
  acceleration layer**.
tags:
- turbovec
- turboquant
- rag
- ann
- pgvector
- memory
- code-graph
- adr
phase: 13-technology-stack-and-platform-decisions
canonical_path: docs/13-technology-stack-and-platform-decisions/08-turbovec-ann-acceleration-integration.md
lifecycle_lane: future
concern_lane: design
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
doc_version: 1.3.1
updated_at: 2026-08-10
linked_symbols:
- backend/packages/vector_index/port.py::VectorIndexPort
- backend/packages/vector_index/turbovec_adapter.py::TurboVecIndexAdapter
- backend/packages/vector_index/factory.py::try_build_accelerator
- backend/packages/vector_index/id_map.py::PostgresEntityIdMap
- backend/packages/vector_index/promotion_gate.py::run_promotion_gate
- backend/services/code-graph-service/src/code_graph_service/application/queries.py::QueryUseCases._maybe_turbovec_rerank
- backend/services/memory-service/src/memory_service/domain/embeddings_store.py::stage1_retrieve
- backend/services/memory-service/src/memory_service/core/retrieval.py::RetrievalCommands.explain_retrieval
- backend/services/memory-service/src/memory_service/postgres_embeddings.py::PostgresMemoryEmbeddingStore
---

# 08 - TurboVec ANN Acceleration Integration

## Purpose

This ADR defines how Astloom may combine with [turbovec](https://github.com/RyanCodrai/turbovec) — a Rust TurboQuant vector index with Python bindings — as an **optional in-process ANN acceleration layer**. It does not replace PostgreSQL + pgvector as the durable RAG system of record.

## Professional Audience

Platform architects, memory-service and code-graph-service engineers, security reviewers, and operators evaluating air-gapped or memory-constrained RAG deployments.

## Problem Statement

Astloom baseline RAG uses PostgreSQL + pgvector so retrieval stays inside the same transactional boundary as tenant, project, access policy, freshness, and lifecycle filters. That baseline is correct for governance. It does not optimize for:

- multi-million embedding corpora under tight RAM budgets;
- SIMD ANN latency on large candidate sets;
- air-gapped stacks that prefer a pure-local quantized index next to open embedding models;
- hybrid pipelines where SQL/FTS/ACL already produced a candidate id set and only dense rerank remains.

turbovec addresses those workloads with online ingest (no train step), 2/3/4-bit TurboQuant compression, and kernel-level allowlist / mask filtering.

## Decision

| Concern | Owner | Notes |
| --- | --- | --- |
| Durable embedding bytes, metadata, lifecycle, audit | PostgreSQL + pgvector | System of record (SoR) |
| Relational / ACL / FTS candidate narrowing | PostgreSQL | Stage-1 filter |
| Graph expansion | Neo4j | Unchanged |
| Optional quantized ANN replica + dense top-k / rerank | turbovec (`IdMapIndex`) | Acceleration replica only |
| Embedding model calls | Existing provider adapters | turbovec does not embed |

**Status:** `accepted` (implementation shipped behind `ASTLOOM_RAG_ANN_ACCELERATOR`; run `python -m vector_index.promotion_gate` before production enablement).

## Goals

- Keep pgvector SoR; turbovec is a rebuildable replica.
- Map Astloom stable ids to turbovec `uint64` external ids via `IdMapIndex`.
- Use turbovec allowlist search for hybrid retrieval after SQL/ACL/FTS.
- Isolate turbovec behind a `VectorIndexPort` so core domain code never imports the vendor package.
- Support air-gapped and low-RAM profiles without a managed vector SaaS.

## Non-Goals

- Replacing pgvector as baseline RAG storage.
- Making turbovec the authority for deletes, ACL, or retention.
- Shipping LangChain/LlamaIndex/Haystack/Agno as Astloom dependencies (optional external worker stacks only).
- Embedding generation inside turbovec.
- Storing secrets or PII plaintext inside `.tv` / `.tvim` artifacts beyond already-governed embedding content.

## Actors And Permissions

| Actor | Permission |
| --- | --- |
| memory-service / code-graph-service | rebuild, search, and snapshot turbovec replicas in their ownership boundary |
| operator | enable profile, set bit width / path, run rebuild jobs |
| agent / MCP client | invoke governed retrieve APIs only; no direct filesystem index access |
| security reviewer | audit that allowlists enforce tenant/project scope before search |

## Product Workflow

1. Operator enables `rag.ann_accelerator = turbovec` for a project or deployment profile.
2. Ingest / refresh jobs write embeddings to pgvector (SoR) and enqueue replica sync.
3. Sync adapter encodes float32 vectors into `IdMapIndex` with Astloom-stable `uint64` ids.
4. At retrieve time, Stage-1 SQL/FTS/ACL yields candidate ids (or a full-corpus path when policy allows).
5. Stage-2 turbovec `search(..., allowlist=candidates)` returns dense scores.
6. Memory / graph scoring packs ContextBundle as today; explainability cites both stages.

## System Behavior

### Ownership Split

```text
PostgreSQL (SoR)                    turbovec replica (optional)
─────────────────                   ──────────────────────────
embedding row + metadata            quantized codes + scales
project / ACL / lifecycle           uint64 id map only
FTS / pg_trgm filters               SIMD ANN / allowlist rerank
audit + retention                   .tvim snapshot on object storage
```

If the replica is missing, corrupt, or disabled, retrieval **falls back to pgvector** (and lexical paths). Fail closed on authorization; fail open on accelerator availability only when the SoR path still works.

### Index Type Choice

| turbovec type | Astloom use |
| --- | --- |
| `IdMapIndex` | **Required** for memory items, symbols, doc anchors — stable external ids + `remove` |
| `TurboQuantIndex` | Forbidden for product SoR mapping (slot ids invalidate on `swap_remove`) |

Constraints from turbovec that Astloom must honor:

- `dim` positive multiple of 8, `≤ 65536`.
- `bit_width ∈ {2, 3, 4}` — default **4** for recall; **2** only when RAM profile demands it and recall gates still pass.
- Vectors contiguous `float32`, finite, `|value| < 1e16`.
- Prefer one replica **per project** (or per project-group shard) to avoid cross-tenant allowlist mistakes.

### Hybrid Retrieval Plan

```text
plan = HybridRetrievalPlan
  stage1_candidates = SQL ∩ FTS ∩ ACL ∩ lifecycle   # PostgreSQL
  if accelerator.enabled and stage1_candidates non-empty:
      scores, ids = turbovec.search(query, k, allowlist=stage1_candidates)
  else:
      scores, ids = pgvector.search(query, k, same filters)
  merge with WeightProfile / graph expansion
  pack ContextBundle
```

Selective allowlists should be the default for multi-tenant queries. Full-corpus turbovec search is allowed only inside a project-scoped replica and when Stage-1 would otherwise scan the same set.

### Id Mapping

Astloom entities use UUID / string ids. The adapter maintains a deterministic `entity_ref → uint64` map:

- durable mapping table in the owning service schema (preferred), or
- stable hash into `uint64` **only** when collision policy is documented and verified.

Deletes in SoR must call `IdMapIndex.remove(id)` (or rebuild). Never leave tombstones only in PostgreSQL while the replica still ranks deleted ids.

### Persistence

| Artifact | Format | Storage |
| --- | --- | --- |
| Live replica | in-process `IdMapIndex` | service memory |
| Snapshot | `.tvim` | S3-compatible object storage under project prefix |
| Rebuild source | pgvector rows | PostgreSQL |

Snapshots are **derivatives**. Disaster recovery restores PostgreSQL first, then rebuilds or reloads `.tvim` after checksum verification.

## Owning Modules

| Module | Responsibility |
| --- | --- |
| `backend/packages/` vector port | `VectorIndexPort` protocol: `add`, `remove`, `search`, `rebuild_from_rows`, `load_snapshot`, `write_snapshot` |
| `backend/integrations/` (or service adapter package) | `TurboVecIndexAdapter` implementing the port |
| memory-service | project memory embeddings sync + retrieve path switch |
| code-graph-service | symbol / doc-anchor semantic search acceleration |
| workers | async rebuild / refresh jobs |
| configs / usage profiles | `rag.ann_accelerator`, `turbovec.bit_width`, snapshot paths |

Core domain and application layers must depend on the port only.

## Public Contracts

Application-facing retrieve contracts stay unchanged (`context-bundles`, `graph/search:semantic`, MCP `memory.retrieve`). Internal port sketch:

```python
class VectorIndexPort(Protocol):
    def upsert(self, ids: Sequence[int], vectors: NDArray[np.float32]) -> None: ...
    def remove(self, ids: Sequence[int]) -> int: ...
    def search(
        self,
        query: NDArray[np.float32],
        k: int,
        *,
        allowlist: Sequence[int] | None = None,
    ) -> tuple[NDArray[np.float32], NDArray[np.uint64]]: ...
    def write_snapshot(self, uri: str) -> None: ...
    def load_snapshot(self, uri: str) -> None: ...
```

Configuration keys (illustrative):

| Key | Meaning |
| --- | --- |
| `ASTLOOM_RAG_ANN_ACCELERATOR` | `off` \| `turbovec` |
| `ASTLOOM_TURBOVEC_BIT_WIDTH` | `2` \| `3` \| `4` (default `4`) |
| `ASTLOOM_TURBOVEC_SNAPSHOT_URI` | object-storage prefix template |
| `ASTLOOM_TURBOVEC_SYNC_MODE` | `sync_on_write` \| `async_job` |

Optional Python extra: `turbovec` (or `astloom[turbovec]`) — never a hard core dependency.

## Security And Privacy Constraints

- Allowlists must be computed from authorized Stage-1 results; never trust client-supplied id lists without re-authorization.
- Replica files inherit project isolation; object keys include `tenant_id` / `workspace_id` / `project_id`.
- Load path validates turbovec magic/version and size caps before allocate (vendor already length-caps; Astloom still checksums snapshots).
- Restricted memory kinds follow existing RESTRICTED handling; accelerator must not widen visibility.
- No cloud exfiltration: turbovec is local; embedding providers remain governed by existing no-exfiltration / VPC rules.

## Failure Modes And Recovery

| Failure | Behavior |
| --- | --- |
| Package missing / import error | Disable accelerator; log; use pgvector |
| Dim / bit_width mismatch on load | Reject snapshot; trigger rebuild from SoR |
| Allowlist empty | Return empty dense stage; do not pad |
| Replica lag behind SoR | Prefer SoR for correctness-critical paths; expose `replica_lag` metric |
| Corrupt `.tvim` | Quarantine object; rebuild |

## Observability And Diagnostics

Emit metrics: `rag.accelerator.search_latency`, `rag.accelerator.recall_proxy`, `rag.accelerator.replica_size_bytes`, `rag.accelerator.fallback_total`, `rag.accelerator.sync_lag_seconds`. Traces must show Stage-1 vs Stage-2 spans and whether allowlist short-circuit applied.

## Testing And Verification

- Unit: fake `VectorIndexPort`; domain retrieval logic without native wheels.
- Contract: adapter tests with turbovec installed in an optional CI job / profile.
- Live: rebuild from fixture embeddings; allowlist search returns only permitted ids; delete removes id from subsequent search.
- Recall gate: on representative corpus, R@k within agreed delta of pgvector baseline at chosen `bit_width`.
- Isolation gate: cross-project allowlist injection attempts return zero foreign hits.

## Rollout And Migration Notes

1. Document-only / flag-off (this ADR).
2. Adapter + optional dependency behind flag in one service (prefer code-graph semantic search or memory retrieve).
3. Measure RAM, latency, recall vs pgvector.
4. Promote to supported profile only after gates pass; keep pgvector SoR forever unless a future ADR changes the product map.

## Engineering Acceptance Criteria

- [x] pgvector remains mandatory SoR for embeddings in baseline profiles.
- [x] Product code depends on `VectorIndexPort`, not `from turbovec import ...` in domain layers.
- [x] Only `IdMapIndex` is used for Astloom entity ids.
- [x] Hybrid allowlist path is the default multi-tenant search shape.
- [x] Accelerator failure never bypasses ACL; it only falls back to SoR retrieval.
- [x] Snapshots are rebuildable derivatives under object storage with project-scoped keys.
- [x] Optional CI profile installs `turbovec` and runs adapter contract tests.
- [x] In-repo promotion gate reports recall@k / latency / RSS proxy (`vector_index.promotion_gate`).
- [x] Durable `PostgresEntityIdMap` is used when service database URL + table are available.
- [x] Memory and code-graph SoR index/delete keep the ANN replica consistent (`sync_on_write`).
- [x] Process-local accelerator metrics (`vector_index.metrics`) record search/sync/fallback/snapshot.
- [x] Boot loads `ASTLOOM_TURBOVEC_SNAPSHOT_URI` when set; mutations persist local/`file://` snapshots.
- [x] Isolation unit tests assert Stage-2 allowlists cannot return foreign project candidates.

## Product Acceptance Criteria

- [x] Operators can enable/disable the accelerator per deployment profile without code changes.
- [x] ContextBundle explain output can attribute hits to `pgvector` vs `turbovec` stage.
- [x] Air-gapped profile can run retrieve with local embeddings + turbovec and no managed vector SaaS.

## Open Gaps

- Operators still run `python -m vector_index.promotion_gate` (or the pytest promotion suite) on representative host hardware before flipping production profiles to `ASTLOOM_RAG_ANN_ACCELERATOR=turbovec`.
- `ASTLOOM_TURBOVEC_SYNC_MODE=async_job` remains parsed for forward compatibility; quality path uses `sync_on_write` (default). In-process async drain is not required for retrieval correctness.
- Cloud object-storage `.tvim` backends beyond local/`file://` URIs remain future work.

## Related Documents

- `04-data-rag-analytics-and-storage-stack.md` — baseline store map
- `07-service-product-standard.md` — one-product-per-role; this ADR is the exception record for ANN acceleration
- `../02-memory-and-context/` — retrieval product behavior
- `../07-code-knowledge-graph/` — semantic search design
- `../11-logical-implementation-examples/08-turbovec-hybrid-retrieval-example.md` — worked hybrid flow
- `11-turbovec-for-rag.md` — engineer/agent RAG usage guide
- Upstream: [turbovec README](https://github.com/RyanCodrai/turbovec), [API reference](https://github.com/RyanCodrai/turbovec/blob/main/docs/api.md), [TurboQuant paper](https://arxiv.org/abs/2504.19874)

---
doc_id: as.doc.stack.turbovec-for-rag
title: 11 - TurboVec For RAG
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-architecture
summary: This guide tells engineers and agents **how to use [turbovec](https://github.com/RyanCodrai/turbovec)
  in an Astloom RAG pipeline**. It is the operational companion to the normative ADR `08-turbovec-ann-acceleration-integration.md`.
tags:
- turbovec
- turboquant
- rag
- ann
- hybrid-retrieval
- pgvector
- embeddings
phase: 13-technology-stack-and-platform-decisions
canonical_path: docs/13-technology-stack-and-platform-decisions/11-turbovec-for-rag.md
lifecycle_lane: future
concern_lane: design
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
doc_version: 1.1.2
updated_at: 2026-08-10
linked_symbols:
- backend/packages/vector_index/promotion_gate.py::run_promotion_gate
- backend/packages/vector_index/id_map.py::PostgresEntityIdMap
- backend/services/memory-service/src/memory_service/postgres_embeddings.py::PostgresMemoryEmbeddingStore
related_docs:
- as.doc.stack.turbovec-ann-acceleration
- as.doc.stack.data-rag-analytics-storage
- as.doc.examples.turbovec-hybrid-retrieval
- as.doc.stack.litellm-llm-gateway
audience:
- engineer
- architect
- agent
primary_entities:
- IdMapIndex
- HybridRetrievalPlan
- VectorIndexPort
- TurboVecReplica
- PromotionGateResult
relations_declared:
- type: depends_on
  target: docs/13-technology-stack-and-platform-decisions/08-turbovec-ann-acceleration-integration.md
- type: depends_on
  target: docs/13-technology-stack-and-platform-decisions/04-data-rag-analytics-and-storage-stack.md
- type: complements
  target: docs/11-logical-implementation-examples/08-turbovec-hybrid-retrieval-example.md
- type: complements
  target: docs/02-memory-and-context/
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
external_refs:
- https://github.com/RyanCodrai/turbovec
- https://github.com/RyanCodrai/turbovec/blob/main/docs/api.md
- https://arxiv.org/abs/2504.19874
- https://pypi.org/project/turbovec/
---

# 11 - TurboVec For RAG

## Purpose

This guide tells engineers and agents **how to use [turbovec](https://github.com/RyanCodrai/turbovec) in an Astloom RAG pipeline**. It is the operational companion to the normative ADR `08-turbovec-ann-acceleration-integration.md`.

turbovec is a Rust TurboQuant vector index with Python bindings: online ingest, 2/3/4-bit compression, SIMD search, and kernel-level allowlist filtering. It does **not** embed text and does **not** replace PostgreSQL + pgvector as the durable system of record (SoR).

## When To Use It In RAG

| Use turbovec when | Prefer pgvector-only when |
| --- | --- |
| Large float32 corpora strain RAM | Corpus is small and already filtered in SQL |
| Stage-1 SQL/FTS/ACL already produced candidate ids | You need transactional dense search without a replica |
| Air-gapped / no managed vector SaaS | Accelerator package unavailable on the host |
| Latency-sensitive dense rerank inside a project replica | Correctness-critical path and replica lag is high |

Default Astloom shape: **pgvector SoR + optional turbovec replica** for Stage-2 dense allowlist search.

## Install

```bash
pip install turbovec
## optional framework extras (not Astloom product deps):
## pip install "turbovec[langchain]" "turbovec[llama-index]" "turbovec[haystack]" "turbovec[agno]"
```

Optional profile only. Product domain code must depend on `VectorIndexPort`, not `from turbovec import …` (see ADR `08`).

## Index Choice For RAG

| Type | Stable ids | Deletes | Astloom RAG |
| --- | --- | --- | --- |
| `IdMapIndex` | `uint64` external ids | `remove(id)` O(1) | **Required** |
| `TurboQuantIndex` | positional slots | `swap_remove` invalidates slots | Forbidden for entity-backed RAG |

Always map Astloom UUID/string entity refs to durable `uint64` ids (mapping table preferred; see ADR).

## Hard Constraints (Vendor)

Honor these before create/add/search or the vendor raises:

| Constraint | Rule |
| --- | --- |
| `dim` | Positive multiple of **8**, `≤ 65536` (or omit and infer on first add) |
| `bit_width` | `{2, 3, 4}` — Astloom default **4** |
| Vectors / queries | Contiguous `float32`, finite, `|value| < 1e16` |
| `add_with_ids` | `len(ids) == n`, ids unique `uint64` |
| Allowlist search | Non-empty allowlist; unknown ids → `KeyError` |
| Output shape | `(nq, min(k, n_allowed))` — **no padding** |

Align embedding model output dim with LiteLLM / provider config (`09-litellm-llm-gateway.md`). Pad or reject dims that are not multiples of 8 at the embedding adapter boundary.

## Minimal RAG Lifecycle

```python
import numpy as np
from turbovec import IdMapIndex

## 1. Create project-scoped replica (dim must match embedding model)
idx = IdMapIndex(dim=1536, bit_width=4)

## 2. Ingest after SoR write (ids from embedding_id_map)
vectors = np.asarray(batch_vectors, dtype=np.float32)  # (n, 1536)
ids = np.asarray(batch_uint64_ids, dtype=np.uint64)
idx.add_with_ids(vectors, ids)

## 3. Optional: warm kernels before first query
idx.prepare()

## 4. Retrieve (hybrid — prefer allowlist)
query = np.asarray(query_vector, dtype=np.float32).reshape(1, -1)
allowed = np.asarray(stage1_candidate_ids, dtype=np.uint64)
scores, hit_ids = idx.search(query, k=10, allowlist=allowed)

## 5. Persist derivative snapshot
idx.write("project_xxx.tvim")
## later: idx = IdMapIndex.load("project_xxx.tvim")
## 6. Delete must mirror SoR
idx.remove(deleted_uint64_id)
```

## Hybrid RAG Pattern (Canonical)

Astloom multi-tenant RAG must not run unfiltered corpus ANN across tenants.

```text
query text
  → embed via LiteLLM / approved embedding port  → q (float32)
  → Stage-1 PostgreSQL: tenant ∩ project ∩ ACL ∩ lifecycle ∩ (optional FTS)
  → allowed: uint64[]
  → Stage-2: IdMapIndex.search(q, k, allowlist=allowed)   # turbovec
       OR pgvector.search(q, k, same predicates)           # fallback
  → join hits to SoR rows → WeightProfile / graph expand → ContextBundle
```

Why allowlist matters:

- Filtering is inside the SIMD kernel (block short-circuit), not post-filter.
- You always get up to `k` results **from the allowed set**.
- Selective allowlists skip most scoring work.

Worked scenario: `../11-logical-implementation-examples/08-turbovec-hybrid-retrieval-example.md`.

## Bit Width Guidance

| `bit_width` | Compression (approx vs FP32) | When |
| --- | --- | --- |
| `4` | ~8× | **Default** — best recall / speed tradeoff for OpenAI-scale dims |
| `3` | intermediate | Only with measured recall gates |
| `2` | ~16× | Low-RAM profiles; validate R@k vs pgvector before enable |

Vendor recall notes (100K vectors): at d=1536/3072, TurboQuant tracks or slightly beats FAISS IndexPQ at R@1 for 2/4-bit and reaches ~1.0 by k≈8. Low-dim embeddings (e.g. GloVe d=200) are harder; prefer `4` and measure.

## Persistence And Rebuild

| Artifact | Magic | Role |
| --- | --- | --- |
| `.tvim` | `TVIM` | `IdMapIndex` snapshot (codes + scales + TQ+ + `slot_to_id`) |
| `.tv` | `TVPI` | Positional index only — not used for Astloom entity RAG |

Rules:

- Snapshots are **derivatives**. Restore PostgreSQL first; rebuild or reload `.tvim` after checksum verification.
- Store under project-scoped object keys (`tenant` / `workspace` / `project`).
- Dim / bit_width mismatch on load → reject snapshot → rebuild from pgvector rows.
- TQ+ calibration freezes after the **first** add; later adds reuse it (no separate train phase).

## What turbovec Does Not Do

- Generate embeddings (use LiteLLM / local stub ports).
- Own ACL, retention, or deletes (PostgreSQL SoR).
- Store document text or metadata (join back to SoR by `uint64`).
- Replace Neo4j graph expansion.
- Act as a managed remote vector database.

## Framework Integrations (External Only)

Upstream drop-ins exist for LangChain, LlamaIndex, Haystack, and Agno. Astloom **does not** take those as product dependencies. Use them only in experimental workers outside the core services; in-tree path stays `VectorIndexPort` → `TurboVecIndexAdapter`.

## Configuration Keys

| Key | Values | Meaning |
| --- | --- | --- |
| `ASTLOOM_RAG_ANN_ACCELERATOR` | `off` \| `turbovec` | Enable replica path |
| `ASTLOOM_TURBOVEC_BIT_WIDTH` | `2` \| `3` \| `4` | Default `4` |
| `ASTLOOM_TURBOVEC_SNAPSHOT_URI` | URI template | Object-storage prefix |
| `ASTLOOM_TURBOVEC_SYNC_MODE` | `sync_on_write` \| `async_job` | Replica freshness policy |
| `ASTLOOM_TURBOVEC_ID_MAP_TABLE` | `schema.table` | Durable id map (factory override) |
| `ASTLOOM_TURBOVEC_ID_MAP_DATABASE_URL` | PostgreSQL URL | Optional id-map DB when not passed by composition root |

## Failure And Fallback

| Condition | Behavior |
| --- | --- |
| `import turbovec` fails | Log; disable accelerator; pgvector only |
| Empty Stage-1 allowlist | Empty dense hits; do not call search with empty allowlist |
| Corrupt / bad magic `.tvim` | Quarantine; rebuild from SoR |
| Replica lag above policy | Prefer pgvector for that request; emit `replica_lag` metric |

Authorization never falls open: missing accelerator must not widen ACL.

## Checklist For Implementers

## Mark remaining implementer checklist items that are already enforced in code/tests.
- [x] Embeddings written to pgvector before or atomically with replica upsert.
- [x] Only `IdMapIndex` + durable `uint64` map.
- [x] Stage-1 filters always precede Stage-2 allowlist search.
- [x] Deletes call `remove` (or full rebuild).
- [x] Dim multiple of 8 validated at embedding boundary.
- [x] Fallback path tested without the wheel installed.
- [x] ContextBundle explain can attribute `turbovec` vs `pgvector`.
- [x] Run `python -m vector_index.promotion_gate` (recall@k / latency / RSS proxy) before production enablement.
- [x] Prefer durable `PostgresEntityIdMap` when service database URL is available.

## Related Documents

- Normative ADR: `08-turbovec-ann-acceleration-integration.md`
- Baseline store map: `04-data-rag-analytics-and-storage-stack.md`
- Hybrid example: `../11-logical-implementation-examples/08-turbovec-hybrid-retrieval-example.md`
- Embeddings gateway: `09-litellm-llm-gateway.md`
- Memory / RAG product behavior: `../02-memory-and-context/`
- Upstream: [README](https://github.com/RyanCodrai/turbovec), [API](https://github.com/RyanCodrai/turbovec/blob/main/docs/api.md), [TurboQuant paper](https://arxiv.org/abs/2504.19874)

---
doc_id: as.doc.examples.turbovec-hybrid-retrieval
title: 08 - TurboVec Hybrid Retrieval Example
doc_type: example
status: draft
schema_version: '1.0'
owner: platform-architecture
summary: Worked example of Astloom Stage-1 SQL/ACL candidate narrowing followed by turbovec
  IdMapIndex allowlist dense rerank, with fallback to pgvector.
tags:
- turbovec
- rag
- hybrid-retrieval
- example
- memory
phase: 11-logical-implementation-examples
canonical_path: docs/11-logical-implementation-examples/08-turbovec-hybrid-retrieval-example.md
lifecycle_lane: future
concern_lane: example
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.stack.turbovec-ann-acceleration
- as.doc.stack.turbovec-for-rag
- as.doc.examples.memory-and-context
doc_version: 1.0.1
audience:
- engineer
- agent
primary_entities:
- HybridRetrievalPlan
- TurboVecReplica
- ContextBundle
relations_declared:
- type: depends_on
  target: docs/13-technology-stack-and-platform-decisions/08-turbovec-ann-acceleration-integration.md
- type: complements
  target: docs/11-logical-implementation-examples/02-memory-and-context-example.md
chunk_hints:
  strategy: heading_h2
  max_tokens: 800
  overlap_tokens: 64
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 08 - TurboVec Hybrid Retrieval Example

## Purpose

Show engineers how Astloom combines PostgreSQL filtering with an optional [turbovec](https://github.com/RyanCodrai/turbovec) `IdMapIndex` allowlist search when building a ContextBundle.

## Scenario

Project `proj_payments` stores semantic memory embeddings for architecture facts. An agent asks: "Where do we enforce idempotency on payment webhooks?" The deployment profile has `rag.ann_accelerator = turbovec`.

## Inputs

- Tenant / workspace / project scope headers.
- Query text → embedding vector `q` (`float32`, dim `1536`, multiple of 8).
- Actor permissions: may read non-RESTRICTED semantic memory in this project.
- `k = 8`, token budget from WeightProfile.

## Processing Steps

### 1. Stage-1 candidate narrowing (PostgreSQL)

```sql
SELECT id_map.uint64_id
FROM memory.memory_items m
JOIN memory.embedding_id_map id_map ON id_map.memory_item_id = m.id
WHERE m.project_id = :project_id
  AND m.kind = 'SEMANTIC'
  AND m.lifecycle_state = 'active'
  AND m.access_class <> 'RESTRICTED'
  AND m.updated_at > now() - interval '180 days';
```

Result: `allowed = uint64[1204, 1882, 2201, ...]` (e.g. 40 ids). FTS/`pg_trgm` may further intersect this set when exact symbols appear in the query.

### 2. Stage-2 dense allowlist search (turbovec)

```python
import numpy as np
from turbovec import IdMapIndex

## Loaded earlier by TurboVecIndexAdapter for this project replica
idx: IdMapIndex  # dim=1536, bit_width=4

allowed = np.asarray(stage1_ids, dtype=np.uint64)
query = q.reshape(1, -1).astype(np.float32)

scores, ids = idx.search(query, k=8, allowlist=allowed)
## shapes: (1, min(8, len(allowed)))
```

Kernel behavior (vendor): blocks with no allowed slots are skipped; output length is `min(k, len(allowed))` with no padding.

### 3. Join scores back to SoR rows

```text
for each id in ids[0]:
    memory_item = load_by_uint64(id)          # PostgreSQL
    attach score, evidence refs, freshness
rank with WeightProfile (semantic boost, decay, confidence)
pack ContextBundle under token budget
```

### 4. Explainability fragment

```json
{
  "retrieval_stages": [
    {"stage": "sql_acl", "candidate_count": 40},
    {"stage": "turbovec_allowlist", "k": 8, "bit_width": 4, "hit_ids": ["…"]}
  ],
  "accelerator": "turbovec",
  "fallback_used": false
}
```

## Outputs

- ContextBundle with up to 8 memory items, all within Stage-1 authorization.
- Outbox / audit unchanged from normal retrieve (no new public event required for accelerator use).
- Metrics: Stage-1 count, Stage-2 latency, accelerator = turbovec.

## Fallback Path

If turbovec is disabled, missing, or replica lag exceeds policy:

```text
scores, rows = pgvector_search(q, k=8, same SQL predicates)
explain.accelerator = null
explain.fallback_used = true
```

Authorization predicates stay identical; only the dense ranker changes.

## Sync Path (write side)

When a SemanticFact embedding is upserted:

1. Write float32 embedding + metadata to pgvector (SoR).
2. Resolve `uint64` via `embedding_id_map`.
3. `idx.add_with_ids(vectors, ids)` or remove+re-add on update.
4. Optionally enqueue `.tvim` snapshot after N writes or on a schedule.

On delete / deprecate: SoR lifecycle update **and** `idx.remove(uint64_id)`.

## Edge Cases

| Case | Expected behavior |
| --- | --- |
| Allowlist empty | Empty dense hits; bundle may still include non-vector context |
| `k > len(allowlist)` | Return `len(allowlist)` hits, no pad |
| Unknown id in allowlist | Adapter must not pass unknown ids; vendor raises `KeyError` |
| Dim not multiple of 8 | Reject at embedding-provider / config validation before index create |
| RESTRICTED item in SoR | Never appears in Stage-1; cannot surface via accelerator |

## Minimal Adapter Sketch

```python
class TurboVecIndexAdapter:
    """Infrastructure adapter; application code sees VectorIndexPort only."""

    def __init__(self, dim: int, bit_width: int = 4) -> None:
        from turbovec import IdMapIndex  # optional dependency boundary
        self._idx = IdMapIndex(dim=dim, bit_width=bit_width)

    def search(self, query, k, *, allowlist=None):
        import numpy as np
        q = np.asarray(query, dtype=np.float32).reshape(1, -1)
        al = None if allowlist is None else np.asarray(allowlist, dtype=np.uint64)
        return self._idx.search(q, k, allowlist=al)
```

## What To Test Before Coding Further

- Allowlist cannot return an id absent from Stage-1.
- Delete in SoR removes subsequent turbovec hits.
- Fallback activates when `import turbovec` fails.
- Snapshot reload yields the same top-k on a frozen fixture corpus.

## Related Documents

- Normative ADR: `../13-technology-stack-and-platform-decisions/08-turbovec-ann-acceleration-integration.md`
- RAG guide: `../13-technology-stack-and-platform-decisions/11-turbovec-for-rag.md`
- Memory example without accelerator: `02-memory-and-context-example.md`
- Upstream API: https://github.com/RyanCodrai/turbovec/blob/main/docs/api.md

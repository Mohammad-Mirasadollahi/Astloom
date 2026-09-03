---
doc_id: as.doc.ckg.sync-cpu-budget-and-store-concurrency-lld
title: 50 - Sync CPU Budget And Store Concurrency Low-Level Design
doc_type: lld
status: active
schema_version: '1.0'
owner: code-graph-lead
summary: Operator CPU percent derives sync workers, embed slots, Torch/OMP pins, and
  store concurrency; LockedStore bounds Neo4j/store mutations; Postgres adapters use
  checkout/checkin pools (see doc 79) rather than permanent per-worker clients.
tags:
- sync
- cpu
- neo4j
- locked-store
- parallelism
- lld
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/50-sync-cpu-budget-and-store-concurrency-lld.md
lifecycle_lane: current
concern_lane: design
audience_lane:
- platform-engineering
- operators
- agents
authority: normative
visibility: internal
linked_symbols:
- backend/services/code-graph-service/src/code_graph_service/locked_store.py::LockedStore
- backend/services/code-graph-service/src/code_graph_service/locked_store.py::resolve_sync_cpu_plan
- backend/services/code-graph-service/src/code_graph_service/locked_store.py::apply_sync_compute_limits
- backend/services/code-graph-service/src/code_graph_service/pg_thread_local.py::ThreadLocalPsycopg
- backend/services/code-graph-service/src/code_graph_service/neo4j/cypher.py::LIST_SYMBOLS
- tests/backend/services/code-graph-service/test_locked_store.py::test_sync_max_file_workers_auto_from_cpu_and_rpm
- tests/backend/services/code-graph-service/test_pg_thread_local.py::test_bounded_pool_never_exceeds_max_size_under_parallel_workers
related_docs:
- as.doc.ckg.rpm-session-parallel-sync-feature-spec
- as.doc.ckg.rpm-session-parallel-sync-hld
- as.doc.ckg.rpm-session-parallel-sync-lld
- as.doc.ckg.rpm-session-parallel-sync-risks
- as.doc.ckg.ingestion-and-living-documentation-workflow
- as.doc.ckg.postgres-connection-pool-and-capacity-lld
- docs/13-technology-stack-and-platform-decisions/12-litellm-environment-configuration.md
doc_version: 1.3.0
audience:
- engineer
- operator
- agent
primary_entities:
- SyncCpuPlan
- LockedStore
- ListSymbolsLite
relations_declared:
- type: complements
  target: as.doc.ckg.rpm-session-parallel-sync-lld
- type: complements
  target: as.doc.ckg.postgres-connection-pool-and-capacity-lld
- type: complements
  target: as.doc.ckg.sync-finalizing-and-provider-cost-runbook
- type: constrains
  target: backend/services/code-graph-service/src/code_graph_service/locked_store.py
chunk_hints:
  strategy: heading_h2
  max_tokens: 700
  overlap_tokens: 48
language: en
security_classification: internal
updated_at: '2026-09-03'
---
# 50 - Sync CPU Budget And Store Concurrency Low-Level Design

## Purpose

Define how `astloom sync` turns an operator **CPU percent** into workers and
thread caps, how `LockedStore` bounds Neo4j traffic without a global write lock,
and why Neo4j `list_symbols` must not pull embedding vectors on the Bolt wire.
Postgres client lifecycle and capacity errors are specified in
[`79`](79-postgres-connection-pool-and-capacity-lld.md).

## Implementation status

**Implemented** in `code_graph_service.locked_store` (`SyncCpuPlan`,
`LockedStore`, `apply_sync_compute_limits`), bootstrap wiring of
`store_concurrency`, and Neo4j `LIST_SYMBOLS` projection with `embedding: []`.
Bulk parallel ingest also defers the cross-file pass and prefers heuristic docs
during the worker pool (see Related Documents pack `37`–`40`).

## Design flow

```mermaid
flowchart TD
  env[Env_or_CLI_cpu_percent] --> plan[resolve_sync_cpu_plan]
  plan --> workers[file_workers]
  plan --> embeds[local_embed_slots]
  plan --> torch[Torch_OMP_1]
  plan --> storeConc[store_concurrency_2_to_8]
  workers --> pool[ThreadPool_ingest_files]
  embeds --> bge[Local_BGE_encode]
  storeConc --> locked[LockedStore_slots]
  pool --> parse[Parse_hash_heuristic_docs]
  parse --> bge
  bge --> locked
  locked --> neo4j[(Neo4j_Bolt)]
  pool --> finalize[finalize_cross_file_once]
  finalize --> listLite[list_symbols_no_embeddings]
  listLite --> neo4j
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | CLI / bootstrap | Resolve `ASTLOOM_SYNC_CPU_PERCENT` or workers override | `SyncCpuPlan` |
| 2 | `apply_sync_compute_limits` | Pin OMP/MKL/Torch=1; set embed semaphore | No thread-stack explosion |
| 3 | File pool | Parallel parse / heuristic docs / embed | CPU work without LiteLLM RPM wait |
| 4 | `LockedStore` | Up to `store_concurrency` concurrent store ops | Writes not single-flight |
| 5 | Postgres path | Checkout/checkin ``psycopg`` pool (doc 79); store slots still apply | No exclusive ``lock_reads`` in production; no idle client per worker forever |
| 6 | Finalize | One `list_symbols` without embeddings + relink | Indexes without multi-MB vectors |

## CPU plan resolution

Precedence (see `resolve_sync_cpu_plan`):

1. Explicit positive int `ASTLOOM_SYNC_MAX_FILE_WORKERS`
2. `ASTLOOM_SYNC_CPU_PERCENT` in `1..100` (CLI `--cpu-percent` overrides env)
3. Auto / percent result, then LLM-aware RPM cap:
   - **LLM-cold** (docs off and embeds not on LiteLLM/OpenRouter): `min(cpu, RPM)`
   - **LLM-hot** (living docs and/or cloud embeds): `min(cpu, RPM // 2)`

`_LLM_HOT_CALLS_PER_FILE` is **2** after batched living docs (≈1 docs
`complete` + 1 embed batch per file). It was **6** when docs called the
Provider once per symbol. See
[`82`](82-sync-finalizing-and-provider-cost-runbook.md).

When percent mode is active (before the LLM-hot floor):

| Field | Formula |
| --- | --- |
| `workers` | `max(1, round(cpu_count * percent / 100))`, then LLM-aware RPM cap |
| `embed_concurrency` | same as `workers` (local embed path still capped at 4 in auto) |
| `torch_threads` | always `1` |
| `store_concurrency` | `max(2, min(8, workers))` |

Example: 48 CPUs at 60% with docs+cloud embeds and `RPM=30` → CPU share 29,
LLM-hot cap `30 // 2 = 15` → `workers=15`.

## LockedStore semantics

| Backend | Reads | Mutations |
| --- | --- | --- |
| Postgres / Neo4j (`max_concurrent=N`) | Re-entrant semaphore depth `N` | Same semaphore (not a process-wide write RLock) |
| Unsafe adapter (`lock_reads=True`) | Exclusive RLock | Exclusive RLock |
| Without `max_concurrent` | Unlocked reads | Exclusive RLock fallback for mutations |

**Why not a global write lock:** with dozens of file workers, every
`put_symbol` / `put_edge` queued behind one RLock left threads on futex while
progress showed `parallel N active`, so host CPU stayed near one core.

**Why still cap at 8:** Neo4j Community on a small heap (and Postgres connection
count) cannot absorb 29 concurrent sessions; the slot budget protects overload
without serializing all workers.

Nested store calls on the same thread re-enter the semaphore via thread-local
depth (avoids BoundedSemaphore deadlock).

## list_symbols without embeddings

Neo4j `LIST_SYMBOLS` returns a map projection with `embedding: []`. Embeddings
live in the vector index (Qdrant / remote); resolution indexes only need id,
names, kind, and paths.

Pulling ~11k symbols × 1024 floats over Bolt cost ~14–16s per call and ran
multiple times before the file pool. Omitting vectors drops that to ~1.5–5s on
the same host.

`list_symbols_for_file` and single-symbol get paths may still return stored
properties as needed for prune / lookup.

## Parallel ingest notes (companion to pack 37–40)

During the worker pool (`defer_cross_file_pass=True`):

- Shared resolution indexes are built once up front.
- Per-file full-graph relink / test_links / dynamic_dispatch are deferred.
- When living LLM docs are **enabled**, each changed file uses
  `generate_many` (one Provider `complete` per file, chunked) — not one call
  per symbol. When docs are **disabled**, the heuristic generator is used.
- Cross-file finalize runs once after the pool (local sync) or once on the
  **last** content-push HTTP batch (`finalize_cross_file`). Relink mutations
  are Neo4j-batched (`delete_edges` / `put_edges`).

File-level upsert prepares docs and embeddings first, then writes, so workers
spend wall time on CPU/network before contending for store slots.

## Operator knobs

| Knob | Effect |
| --- | --- |
| `ASTLOOM_SYNC_CPU_PERCENT` | Preferred budget; derives workers + embeds + store cap |
| `astloom sync --cpu-percent N` | One-run override |
| `ASTLOOM_SYNC_MAX_FILE_WORKERS` | Exact worker count (wins over percent) |
| `ASTLOOM_LITELLM_RPM` | Caps auto workers and LLM inflight |

Env field reference:
[`12-litellm-environment-configuration.md`](../13-technology-stack-and-platform-decisions/12-litellm-environment-configuration.md).

## Failure modes

| Failure | Behavior |
| --- | --- |
| Invalid percent | Fall back to auto plan |
| Neo4j overload / network aborts | Reduce effective concurrency via smaller percent or heap ops; do not remove the slot cap |
| Finalize exception | Logged/swallowed at ingest boundary so the walk still finishes; edges may be incomplete until next sync |
| Postgres | Checkout/checkin pool + optional auto capacity cap (doc 79); keep ``lock_reads`` only for non-thread-safe fakes |
| Postgres capacity exhausted | Typed ``DatabaseCapacityError`` after retries — not an unhandled traceback |

## Verification

| Check | Expectation |
| --- | --- |
| Unit | `tests/backend/services/code-graph-service/test_locked_store.py` |
| Live | Progress shows `CPU budget P% → W workers`; `parallel` active advances `code k/n` |
| Host | Under heavy new files, sync process uses multiple cores (not ~1) without multi‑GB native thread stacks |
| Neo4j | No sustained bolt abort storm at default `store_concurrency` |

## Related Documents

- [`37` RPM session parallel sync feature spec](37-rpm-session-parallel-sync-feature-specification.md)
- [`38` HLD](38-rpm-session-parallel-sync-high-level-design.md)
- [`39` LLD](39-rpm-session-parallel-sync-low-level-design.md)
- [`40` risks and acceptance](40-rpm-session-parallel-sync-risks-challenges-and-acceptance.md)
- [`03` ingestion workflow](03-ingestion-and-living-documentation-workflow.md)
- [`79` Postgres connection pool and capacity LLD](79-postgres-connection-pool-and-capacity-lld.md)
- [`82` sync finalizing and Provider cost runbook](82-sync-finalizing-and-provider-cost-runbook.md)
- LiteLLM env configuration (sync CPU knobs)

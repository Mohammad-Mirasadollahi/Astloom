---
doc_id: as.doc.ckg.rpm-session-parallel-sync-hld
title: 38 - RPM Session Parallel Sync High Level Design
doc_type: hld
status: active
schema_version: '1.0'
owner: code-graph-lead
summary: 'Runtime topology for bounded parallel sync: file worker pools, gateway-owned
  RPM sessions for network calls, bounded stores, and CLI/HTTP observation.'
tags:
- sync
- rpm
- hld
- llm-gateway
- code-graph
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/38-rpm-session-parallel-sync-high-level-design.md
lifecycle_lane: current
concern_lane: design
audience_lane:
- platform-engineering
authority: informative
visibility: internal
linked_symbols:
- backend/packages/llm_gateway/gateway.py::LlmGateway
- backend/packages/llm_gateway/rate_limit.py::RpmSessionGate
- backend/services/code-graph-service/src/code_graph_service/application/ingest/parallel_files.py::run_parallel_file_jobs
- backend/services/code-graph-service/src/code_graph_service/application/ingest/repo_ingest.py::RepoIngestMixin
- backend/services/code-graph-service/src/code_graph_service/application/ingest/file_relink.py::FileRelinkMixin
- backend/services/code-graph-service/src/code_graph_service/domain/dispatch_synth.py::synthesize_interface_dispatch
- backend/services/code-graph-service/src/code_graph_service/locked_store.py::LockedStore
- backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs
related_docs:
- as.doc.ckg.rpm-session-parallel-sync-feature-spec
- as.doc.ckg.rpm-session-parallel-sync-lld
- as.doc.ckg.rpm-session-parallel-sync-risks
- as.doc.ckg.sync-cpu-budget-and-store-concurrency-lld
- as.doc.stack.litellm-llm-gateway
doc_version: 1.1.3
audience:
- engineer
- architect
primary_entities:
- RpmSessionGate
- SessionRegistry
- FileWorkerPool
- LockedStore
relations_declared:
- type: depends_on
  target: as.doc.ckg.rpm-session-parallel-sync-feature-spec
- type: complements
  target: as.doc.stack.litellm-llm-gateway
- type: complements
  target: as.doc.ckg.sync-cpu-budget-and-store-concurrency-lld
chunk_hints:
  strategy: heading_h2
  max_tokens: 700
  overlap_tokens: 48
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 38 - RPM Session Parallel Sync High Level Design

## Implementation status

**Implemented.** Runtime matches this topology via `RpmSessionGate`,
`LockedStore` / bounded local embeddings, parallel `ingest_repo`, and session observe
surfaces (`GET /api/v1/llm/sessions`, `astloom llm sessions`). Live tests on
2026-07-25 verified exact file/Docs/HTTP peaks at worker levels 1, 2, and 4.
Bulk ingest intentionally generates living docs heuristically; it does not have
the previously proposed round-robin `LlmWorkQueue`.

## Purpose

Show how `astloom sync` parallelism, LiteLLM RPM sessions, and store writes
compose without exceeding RPM or corrupting persistence.

## Architecture overview

```mermaid
flowchart LR
  discover[DiscoverFiles] --> fileQueue[FileWorkerPool]
  fileQueue --> parseHash[ParseAndHash]
  parseHash --> heuristic[BulkHeuristicLivingDocs]
  parseHash --> networkWork[ConfiguredNetworkEmbed_or_nonBulkDocCall]
  networkWork --> rpmGate[RpmSessionGate]
  rpmGate --> complete[gateway.complete_or_embed]
  heuristic --> writeQ[LockedStore_bounded]
  complete --> writeQ
  writeQ --> graph[(Postgres_or_Neo4j)]
  discover --> docsQueue[HumanDocsFileWorkerPool]
  docsQueue --> docsStore[(DocsSyncPostgres)]
  docsQueue --> writeQ
  rpmGate --> registry[SessionRegistry_inMemory]
  registry --> observe[CLI_and_HTTP_status]
```

### Agent-readable primary flow

| Step | Component | Action | Output |
| --- | --- | --- | --- |
| 1 | CLI `cmd_sync` | Resolve roots + filters | Sync job params |
| 2 | `sync_repo` / discover | List eligible files | File list (capped) |
| 3 | FileWorkerPool | Parse + hash per file (bounded workers) | Changed symbols + pending writes |
| 4 | Bulk living-doc policy | Use heuristic docs in repository ingest; network embeddings still go through the gateway when configured | Documentation + vectors |
| 5 | RpmSessionGate | For each actual network call, wait for RPM window + in-flight slot; start session | Session id |
| 6 | LiteLlmGateway | `complete` / `embed` | Text / vector or error |
| 7 | RpmSessionGate | End session on success, error, or timeout | Updated registry |
| 8 | LockedStore / per-thread stores | Apply bounded symbol, edge, and human-doc upserts | Graph and docs SoR update |
| 9 | Progress + observe | Emit progress; expose registry snapshot | CLI/HTTP status |

## Component ownership

| Component | Owns | Path (target) |
| --- | --- | --- |
| SessionRegistry + RpmSessionGate | Start/end, window, in-flight, snapshot | `backend/packages/llm_gateway/` (`rate_limit.py` evolution) |
| LiteLlmGateway | Call gate around every network complete/embed | `backend/packages/llm_gateway/gateway.py` |
| Parallel ingest scheduler | Bounded file workers and cross-file finalization | `code_graph_service/application/ingest/` |
| Human-doc scheduler | Bounded Phase-2 file workers | `astloom_cli/docs_link_sync.py` |
| LockedStore | Bounded store-operation slots | `code_graph_service/locked_store.py` |
| Postgres adapters | One tracked connection per worker thread | `code_graph_service/postgres_store.py`, `docs_sync_service/postgres_store.py` |
| Progress tracker | Thread-safe progress events | `astloom_cli/sync_progress/` |
| HTTP observe | Snapshot endpoint | `code_graph_service/api.py` (`/api/v1/llm/...`) |
| CLI observe | Status command / sync enrichment | `astloom_cli` |

## Boundaries

```text
astloom CLI
    │  sync / session status
    ▼
code-graph-service (in-process or HTTP)
    ├── Parallel ingest scheduler
    ├── LlmBackedDocGenerator / HybridEmbeddings  ──► llm_gateway
    │                                                      │
    │                                                      ├── RpmSessionGate
    │                                                      └── SessionRegistry
    └── LockedStore ──► Neo4jStore | PostgresStore
```

- **Domain ports** stay provider-agnostic; only the gateway opens RPM sessions.
- **Application ingest** may parallelize CPU work; it **must not** bypass the
  gateway for LiteLLM calls.
- **Registry** is process-local; two CLI processes have independent RPM truth.

## Parallelism policy (summary)

| Stage | Parallel? | Cap |
| --- | --- | --- |
| File parse + hash | Yes | auto `min(cpu, RPM)` or explicit `ASTLOOM_SYNC_MAX_FILE_WORKERS` |
| Local BGE embedding | Yes | four concurrent calls process-wide across cached models |
| LiteLLM calls | Yes | `ASTLOOM_LITELLM_RPM` + in-flight sessions |
| Code-graph store writes | Yes, bounded | `LockedStore` slot budget; thread-local Postgres connections |
| Human-doc Phase 2 | Yes, bounded | Same file-worker cap; thread-local docs-sync Postgres connections |
| Cross-file finalization | Serial, bounded reads | One symbol snapshot, relation-filtered edge reads, indexed dispatch lookup |
| Package README mapping | Serial, bounded reads | One symbol snapshot grouped by parent directory |

Embeddings via local BGE or stub skip the RPM gate. LiteLLM embeddings take a
session like completions. Repository bulk living-document generation is
heuristic by design, so that path reports zero completion sessions.

The serial finalization stage is intentionally outside the file worker pool
because it resolves relationships after all peers land. It must not repeat
whole-scope reads per relationship or README. On 2026-07-25, a live graph with
about 14.7k symbols showed `dynamic_dispatch` falling from 12.143s to 0.117s
after pre-indexing classes, and the observed post-worker interval fell from
about 192s to about 18s after snapshot reuse and README parent indexing.

Per-file idempotency keys include the root request key, relative path, and
language-aware content hash. A retry of the same content remains idempotent,
while a later sync of changed content cannot be suppressed by an earlier run.
Inventory and ingest both use the same `content_hash` contract.

## Observability surfaces

| Surface | Reads | Notes |
| --- | --- | --- |
| `GET /api/v1/llm/sessions` (exact path in LLD) | SessionRegistry snapshot | Loopback clients only; no secrets / prompts |
| CLI session status | Same snapshot | Reads an active CLI sync through its private (`0600`) transient progress snapshot; otherwise reads the running service via `ASTLOOM_CODE_GRAPH_URL` |
| Sync progress | File/symbol counters | Independent of session history ring |

The in-process CLI reads the secret-bearing code-graph service environment only
when its file is owned by the current user and has mode `0600`. A non-private LLM
route requires explicit per-run consent before ingest starts: interactive TTY
prompt (shows tenant, workspace, project, paths) or `--allow-cloud-llm`.

## Dependencies

- Existing ingest workflow: [`03`](03-ingestion-and-living-documentation-workflow.md)
- LiteLLM gateway ADR: [`09`](../13-technology-stack-and-platform-decisions/09-litellm-llm-gateway.md)
- Env reference: [`12`](../13-technology-stack-and-platform-decisions/12-litellm-environment-configuration.md)
- Feature requirements: [`37`](37-rpm-session-parallel-sync-feature-specification.md)

## Related Documents

- Feature spec: [`37`](37-rpm-session-parallel-sync-feature-specification.md)
- LLD: [`39`](39-rpm-session-parallel-sync-low-level-design.md)
- Risks: [`40`](40-rpm-session-parallel-sync-risks-challenges-and-acceptance.md)

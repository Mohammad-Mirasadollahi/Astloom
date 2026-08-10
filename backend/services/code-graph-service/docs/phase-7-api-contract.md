---
doc_id: as.doc.code-graph.phase-7-api-contract
title: Code Graph Service Phase 7 API Contract
doc_type: contract
status: active
schema_version: '1.0'
owner: code-graph-service
summary: This contract documents the Phase 7 vertical slice for the Code-Knowledge Graph.
  The service owns scoped graph symbol projections, relationship edges (CONTAINS, CALLS, IMPORTS,
  INHERITS_FROM, DOCUMENTED_BY, ROUTES_TO, TESTED_BY, HTTP_CALLS, ASYNC_CALLS), hash-based
  change dete...
tags:
- api
- code-graph
- contract
- phase-7
phase: phase-7
canonical_path: backend/services/code-graph-service/docs/phase-7-api-contract.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
doc_version: 1.3.2
updated_at: 2026-08-10
linked_symbols:
- backend/services/code-graph-service/src/code_graph_service/api/ingest.py
- backend/services/code-graph-service/src/code_graph_service/api/auth.py::require_content_push_http_auth
---

# Code Graph Service Phase 7 API Contract

Path: `backend/services/code-graph-service/docs/phase-7-api-contract.md`

## Purpose

This contract documents the Phase 7 vertical slice for the Code-Knowledge Graph. The service owns scoped graph symbol projections, relationship edges (CONTAINS, CALLS, IMPORTS, INHERITS_FROM, DOCUMENTED_BY, ROUTES_TO, TESTED_BY, HTTP_CALLS, ASYNC_CALLS), hash-based change detection, documentation generation for changed symbols, **production retrieval** (BM25 + store FTS + BGE/LiteLLM embeddings via RRF — docs `27`–`31`), generation-context packs, explore / detect-changes / architecture intelligence, Codebase-Memory hybrid structural tools (callers / directed impact / community), generated-code symbol validation, and code-graph outbox events.

Neo4j is the **default** structural store (`ASTLOOM_CODE_GRAPH_STORE=neo4j`, `Neo4jStore`). PostgreSQL (`code_graph` schema) remains available for rollback and parity via `ASTLOOM_CODE_GRAPH_STORE=postgres`. When `ASTLOOM_CODE_GRAPH_DATABASE_URL` is set, semantic vectors use pgvector (`code_graph.symbol_embeddings`) and Neo4j outbox events are mirrored to `code_graph.outbox` for the relay worker. The canonical Neo4j projection is `CodeSymbol` + `CODE_REL` (see `docs/07-code-knowledge-graph/13-codesymbol-projection-adr.md`). Unit tests use an in-memory Store fake and may use `LocalEmbeddingStub`; production defaults to local BGE when the `embeddings` extra is installed. **Python is a required language** (`stdlib_ast`). TypeScript, JavaScript, Go, and Rust are supported via tree-sitter adapters. See `docs/07-code-knowledge-graph/10-language-support-policy.md`.

## Scope Headers

Every command and scoped query uses:

- `X-Tenant-Id`
- `X-Workspace-Id`
- `X-Actor-Id` for commands
- `X-Correlation-Id` when a caller needs deterministic trace linkage
- `Idempotency-Key` for retryable ingest commands

All endpoints are scoped under `/api/v1/projects/{project_id}` and return snake_case JSON fields.

## Commands

- `POST /api/v1/projects/{project_id}/graph/ingest-file`
- `POST /api/v1/projects/{project_id}/graph/ingest-repo` — walk a local `root_path` and ingest supported sources (soft-fail per file)
- `POST /api/v1/projects/{project_id}/graph/ingest-push` — client content-push bodies (no on-server tree); optional `docs[]`; requires Bearer when `ASTLOOM_CODE_GRAPH_HTTP_TOKEN` / `ASTLOOM_CONNECT_TOKEN` is set (else loopback only); header `X-Sync-Job-Id` registers a cancelable job; returns **499** when that job is cancelled or the client disconnects
- `POST /api/v1/projects/{project_id}/graph/ingest-push/cancel` — explicit cancel for one in-flight push (`{"job_id"}`); same Bearer + scope headers; cancels only the exact `(tenant, workspace, project, job_id)` handle (wrong scope / unknown id is a no-op)
- `GET /api/v1/projects/{project_id}/graph/file-hashes` — FILE path → content hash map for client skip; same Bearer gate as ingest-push
- `POST /api/v1/projects/{project_id}/graph/search:semantic` — Stage-1 hybrid RAG: kind-filtered pgvector (when `ASTLOOM_CODE_GRAPH_DATABASE_URL` set) or in-store cosine, then Neo4j/store neighborhood expand on top seeds
- `POST /api/v1/projects/{project_id}/graph/explore` — hybrid seeds + call path + APOC expand when available; budgeted bodies / sibling skeletonization; `retrieval` mode
- `POST /api/v1/projects/{project_id}/graph/detect-changes` — Wave 1 risk-scored review report for changed files (flows, test gaps, priorities)
- `POST /api/v1/projects/{project_id}/graph/architecture-overview` — communities (scikit-network Leiden or Louvain), hubs/bridges/gaps; `algorithm` field
- `POST /api/v1/projects/{project_id}/graph/path` — shortest path (`method`: neo4j_shortest_path | in_memory_bfs)
- `POST /api/v1/projects/{project_id}/graph/search:hybrid` — BM25 + semantic + store FTS via RRF (`mode`, `channels`, `embedding_backend`, `fts_method`)
- `POST /api/v1/projects/{project_id}/graph/pending-sync` — Wave 3 mark file pending
- `POST /api/v1/projects/{project_id}/graph/reconcile-after-edit` — ADR 48 mark edited paths pending; optional AST `sync_repo` re-ingest (`reference_kind=structural`; never LSP dual-write)
- `POST /api/v1/projects/{project_id}/graph/edit-session/references` — Feature 49 IDE-semantic find-references (local LSP)
- `POST /api/v1/projects/{project_id}/graph/edit-session/definition` — Feature 49 IDE-semantic go-to-definition
- `POST /api/v1/projects/{project_id}/graph/edit-session/rename` — Feature 49 IDE-semantic rename + reconcile
- `GET /api/v1/projects/{project_id}/graph/freshness` — Wave 3 stale banner state
- `POST /api/v1/projects/{project_id}/graph/generation-context`
- `POST /api/v1/projects/{project_id}/graph/generated-code:validate`

## Queries

- `GET /api/v1/projects/{project_id}/graph/symbols/{symbol_id}`
- `GET /api/v1/projects/{project_id}/graph/symbols/{symbol_id}/neighbors` (supports `max_depth` for APOC multi-hop when Neo4j plugins are enabled)
- `POST /api/v1/projects/{project_id}/graph/symbols/{symbol_id}/callers` — ranked inbound callers (fan-in); body: `top_k`, `max_depth`, `min_confidence`, `rel_types`
- `POST /api/v1/projects/{project_id}/graph/symbols/{symbol_id}/impact` — directed blast radius; body: `direction` (`upstream`|`downstream`|`both`), `max_depth`, `min_confidence`, `rel_types`, `top_k`
- `POST /api/v1/projects/{project_id}/graph/symbols/{symbol_id}/community` — Leiden/Louvain membership; body: `member_limit`
- `POST /api/v1/projects/{project_id}/graph/symbols/{symbol_id}/call-path` — compact outbound call-path pack; body: `max_depth`, `max_nodes`
- `GET /api/v1/projects/{project_id}/graph/language-profile`
- `GET /api/v1/projects/{project_id}/graph/neo4j-capabilities`

Structural responses include `escalate_hint` and, when available, a `freshness` banner (Codebase-Memory hybrid — docs `44`–`47`).

## LiteLLM Gateway

Service-wide (not project-scoped) endpoints from `backend/packages/llm_gateway`:

- `GET /api/v1/llm/providers` — list providers; `configured` reflects env API keys
- `GET /api/v1/llm/config` — public settings (auto Base URL, timeout default 180s, retries default 3; no secrets)
- `GET /api/v1/llm/sessions` — process-local RPM session snapshot (in-flight + short history; no secrets)
- `POST /api/v1/llm/complete` — chat completion via LiteLLM (`prompt`, optional `model` / `system` / `reasoning_enabled` / `reasoning_effort`)

Environment: `ASTLOOM_LITELLM_*` in repo-root `.env` (template: `.env.example`). Base URL auto-resolves to `http://{HOST}:{PORT}` unless `ASTLOOM_LITELLM_API_BASE` overrides it. Defaults: timeout `180`s, retries `3`, RPM `30`.

## Event Types

The development outbox emits versioned code-graph-service events:

- `FileIngested` (payload includes a compact `polyglot` summary when available)
- `SymbolsDocumented`
- `ProjectLanguageProfileUpdated` (emitted when the project is polyglot after ingest)

Each event contains `event_id`, `event_type`, `event_version`, `occurred_at`, `producer`, scope fields, `actor_ref`, `correlation_id`, `causation_id`, `idempotency_key`, `payload`, and `evidence_refs`.

## Compatibility

This is an active Phase 7 contract. Breaking changes require a new contract note, matching tests, and a migration or compatibility statement before promotion to shared contracts.

## Related Documents

- `backend/docs/API_NAMING_AND_CONTRACT_STANDARD.md` — HTTP naming and contract conventions
- Sibling service design docs under `docs/` for the owning phase vertical slice

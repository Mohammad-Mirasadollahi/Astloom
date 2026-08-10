---
doc_id: as.doc.ckg.live-audit-remediation-record
title: 73 - Live Audit Defect Remediation Record
doc_type: example
status: active
schema_version: '1.0'
owner: code-graph-service
summary: 'Root-cause and remediation record for seven defects reproduced during the live ingest and remaining-feature audits.'
tags:
- defects
- root-cause
- remediation
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/73-live-audit-defect-remediation-record.md
lifecycle_lane: current
concern_lane: problem
audience_lane:
- platform-engineering
- reviewers
- agents
authority: informative
visibility: internal
linked_symbols:
- backend/services/mcp-gateway-service/src/mcp_gateway_service/http_app.py::create_http_app
- backend/services/code-graph-service/src/code_graph_service/application/service.py::CodeGraphService
- backend/services/code-graph-service/src/code_graph_service/domain/parsing.py::resolve_call_target
- backend/services/code-graph-service/src/code_graph_service/application/intelligence.py::IntelligenceUseCases
- backend/services/code-graph-service/src/code_graph_service/application/ingest/repo_ingest.py::RepoIngestMixin
- backend/services/code-graph-service/src/code_graph_service/application/embedding_refresh.py::EmbeddingRefreshMixin
- backend/services/code-graph-service/src/code_graph_service/neo4j/crud.py::Neo4jCrudMixin
- backend/packages/astloom_cli/util.py::ensure_service_import_paths
related_docs:
- as.doc.ckg.live-ingest-remediation-index
- as.doc.ckg.verification-test-matrix
- as.doc.ckg.sync-semantic-integrity-evidence
language: en
doc_version: 1.0.3
updated_at: 2026-08-10
---

# 73 - Live Audit Defect Remediation Record

## Purpose

This record connects every reproduced defect to its root cause, implementation seam, regression coverage, and real-system verification.

## Defect Summary

| ID | Severity | Defect | Final state |
|---|---|---|---|
| FIX-001 | High | MCP HTTP event loop starved by blocking tool execution | Closed |
| FIX-002 | High | Built-in or ambiguous calls produced false internal `CALLS` edges | Closed |
| FIX-003 | High | Freshness and semantic refresh could report or preserve incomplete state | Closed |
| FIX-004 | Medium | Live tests could mutate the active checkout state | Closed |
| FIX-005 | High | Multi-phase sync exhausted PostgreSQL client connections | Closed |
| FIX-006 | High | Legacy Neo4j nodes with `version=null` broke incremental ingest | Closed |
| FIX-007 | Medium | Isolated CLI state roots broke service module imports | Closed |

## FIX-001: MCP HTTP Starvation

| Field | Record |
|---|---|
| Symptom | `/health` could not respond while an MCP tool executed blocking work on the async request thread |
| Root cause | Async HTTP handlers invoked the synchronous `handle_message` path directly |
| Remediation | `create_http_app` dispatches blocking message handling through `asyncio.to_thread` |
| Primary file | `backend/services/mcp-gateway-service/src/mcp_gateway_service/http_app.py` |
| Regression | `test_mcp_http_gateway.py::test_http_health_remains_responsive_during_blocking_tool` |
| Live proof | Health returned `200` in `0.084502s` during a tool call active for more than `10.417s`; cold repetition returned in `0.096281s` during more than `12.217s` |

The fix keeps the HTTP event loop available without changing the synchronous tool contract.

## FIX-002: False Internal Call Edges

| Field | Record |
|---|---|
| Symptom | A documented drift path incorrectly included `DocsSyncService.detect_drift -> FakeClock.set` |
| Root cause | Python built-ins and ambiguous short names could resolve to unrelated internal symbols; low-confidence edges were then consumed as definite architecture facts |
| Remediation | Classify Python built-ins as external before global short-name resolution; preserve confidence through polyglot resolution; admit only exact or probable edges to blast-radius calculations; filter low-confidence calls from impact, flow, explore, path, community, and architecture views |
| Primary files | `domain/parsing.py`, `domain/cross_language.py`, `domain/external_calls.py`, `application/intelligence.py` |
| Regression | `test_cross_language_resolution.py`, `test_codebase_memory_hybrid.py`, `test_external_calls.py`, `test_wave2_wave3_intelligence.py` |
| Live proof | Final Neo4j query returned `false_edges=0` for any `CALLS` target named `FakeClock.set` |

The correction distinguishes observed syntax from a trustworthy internal relationship. Low-confidence evidence remains available where appropriate but cannot silently become a definite dependency.

## FIX-003: Freshness, Invalidation, and Semantic Completeness

| Field | Record |
|---|---|
| Symptom | A new process could imply clean state without verification; policy changes could retain stale ingest state; refresh work performed unnecessary per-symbol and per-edge operations |
| Root cause | Freshness did not encode whether it had been verified, hash policy was not part of all idempotency decisions, and semantic/edge persistence lacked adequate batching and reuse |
| Remediation | Add `FreshnessState.verified`; expose `pending`, `ok`, and `unknown`; advance `HASH_VERSION` to `4`; include content, hash, and parser policy in idempotency; batch embeddings and edge writes; reuse valid embeddings during policy re-ingest; prune stale file-owned graph data; parallelize refresh with a bounded worker count |
| Primary files | `application/service.py`, `application/repo_ingest.py`, `application/file_symbols.py`, `application/embedding_refresh.py`, Neo4j store mixins |
| Regression | Code Graph focused and aggregate suites, including refresh, ingest, freshness, persistence, and intelligence tests |
| Live proof | Final intersection contained `8,979` eligible nodes, `8,979` eligible indexed nodes, `0` missing, and `0` orphan embeddings |

Additional verified behavior:

- `ASTLOOM_EMBEDDING_REFRESH_WORKERS` is configurable and capped at `16`; the observed run used `12`.
- Language-only backfill avoids unnecessary edge churn.
- Pruning removed stale file-owned symbols and generated documents while preserving human documents and shared external nodes.
- Final stored vector metadata was `BAAI/bge-large-en-v1.5`, declared dimension `1024`, actual dimension `1024`.

## FIX-004: Live-Test Isolation

| Field | Record |
|---|---|
| Symptom | Approval and docs-drift tests could share mutable state with the active checkout or depend on a live runtime method |
| Root cause | Tests reused the repository state root and did not consistently isolate runtime status behavior |
| Remediation | Patch service-runtime `mcp_status`, execute live approval with a temporary `ASTLOOM_ROOT`, and use an isolated project for the unknown-symbol docs-drift scenario |
| Primary files | Live CLI and Code Graph test modules |
| Regression | Complete `live` test selection |
| Live proof | Final live suite completed with `24 passed`, `767 deselected` |

## FIX-005: PostgreSQL Connection Exhaustion

| Field | Record |
|---|---|
| Symptom | Real sync failed in the document phase with `FATAL: sorry, too many clients already` |
| Root cause | A `29`-worker sync accumulated thread-local PostgreSQL connections across phases while the server allowed `100` clients; document synchronization was not bounded to store concurrency |
| Remediation | Reset database connections between phases and after document sync; cap document parallelism to the store concurrency limit of `8`; expose connection reset through the application and store layers |
| Primary files | `application/docs_link_sync.py`, `commands/sync/one_root.py`, `application/service.py`, `outbox_mirror_store.py`, `postgres_side.py`, `postgres_store.py` |
| Regression | `test_sync_human_docs_runs_with_parallel_workers`, `test_sync_human_docs_caps_workers_to_database_slots`, and related focused tests |
| Live proof | Recovery sync completed without connection exhaustion; final PostgreSQL clients were `22`, and the maximum observed during backfill was `63 / 100` |

The focused connection-regression selection completed with `13 passed`.

## FIX-006: Legacy Null Neo4j Version

| Field | Record |
|---|---|
| Symptom | Incremental recovery failed for `38` files with `int() argument ... NoneType` |
| Root cause | Legacy Neo4j symbol nodes could contain `version=null`, while deserialization assumed a valid integer |
| Remediation | `Neo4jCrudMixin` normalizes a legacy null version to version `1` |
| Primary file | `adapters/neo4j/crud.py` |
| Regression | `test_symbol_from_node_defaults_legacy_null_version` |
| Live proof | The next recovery processed `39 / 39` files with `files_failed=0` |

The legacy/docs focused selection completed with `7 passed`.

## FIX-007: Isolated CLI Import Resolution

| Field | Record |
|---|---|
| Symptom | A live approval test failed with `ModuleNotFoundError: code_graph_service` when `ASTLOOM_ROOT` pointed to a temporary directory |
| Root cause | Service import paths incorrectly treated the mutable state root as the only installed-code root |
| Remediation | `ensure_service_import_paths` now resolves both the state root and the installed checkout/package root |
| Primary file | `backend/services/astloom-cli/src/astloom_cli/util.py` |
| Regression | `test_service_import_paths_use_install_checkout_when_state_root_is_isolated` |
| Live proof | The previously failing live test passed, followed by the complete `24`-test live selection |

## Implementation Boundaries

The remediation intentionally did not:

- Convert synchronous MCP tool implementations to async APIs.
- Treat every syntactic call as a definite internal graph dependency.
- Delete shared external nodes during file-owned graph pruning.
- Increase PostgreSQL `max_connections` as a substitute for connection lifecycle control.
- Rewrite legacy graph data in bulk solely to repair null versions.
- Couple mutable state placement to Python package discovery.

## Code Evidence Anchors

- `backend/services/mcp-gateway-service/src/mcp_gateway_service/http_app.py::create_http_app`
- `backend/services/code-graph-service/src/code_graph_service/application/service.py::CodeGraphService`
- `backend/services/code-graph-service/src/code_graph_service/domain/parsing.py::resolve_call_target`
- `backend/services/code-graph-service/src/code_graph_service/application/intelligence.py::IntelligenceUseCases`
- `backend/services/code-graph-service/src/code_graph_service/application/ingest/repo_ingest.py::RepoIngestMixin`
- `backend/services/code-graph-service/src/code_graph_service/application/embedding_refresh.py::EmbeddingRefreshMixin`
- `backend/services/code-graph-service/src/code_graph_service/neo4j/crud.py::Neo4jCrudMixin`
- `backend/packages/astloom_cli/util.py::ensure_service_import_paths`

## Closure Criteria

Every defect in this record met all closure gates:

1. The failure was reproduced or directly observed.
2. A root cause was identified at a shared implementation seam.
3. A regression test covered the failure mode.
4. The relevant focused suite passed.
5. A real ingest, graph, live-test, or HTTP check confirmed the corrected behavior.
6. The final post-restart quality audit contained no remaining finding.

## Related Documents

- [Live Ingest Remediation and Verification Index](72-live-ingest-remediation-verification-index.md)
- [Verification Test Matrix and Results](74-verification-test-matrix-and-results.md)
- [Sync Semantic Integrity and Recovery Evidence](75-sync-semantic-integrity-and-recovery-evidence.md)
- [Post-Restart Operations Verification Runbook](76-post-restart-operations-verification-runbook.md)

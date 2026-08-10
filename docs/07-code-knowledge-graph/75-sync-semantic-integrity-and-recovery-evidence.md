---
doc_id: as.doc.ckg.sync-semantic-integrity-evidence
title: 75 - Sync Semantic Integrity and Recovery Evidence
doc_type: example
status: active
schema_version: '1.0'
owner: code-graph-service
summary: 'Quantitative graph, semantic-index, incremental-sync, and interruption-recovery evidence from the final live verification.'
tags:
- sync
- embeddings
- recovery
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/75-sync-semantic-integrity-and-recovery-evidence.md
lifecycle_lane: current
concern_lane: ops
audience_lane:
- platform-engineering
- operators
- agents
authority: informative
visibility: internal
linked_symbols:
- backend/services/code-graph-service/src/code_graph_service/application/ingest/repo_ingest.py::RepoIngestMixin
- backend/services/code-graph-service/src/code_graph_service/application/embedding_refresh.py::EmbeddingRefreshMixin
- backend/services/code-graph-service/src/code_graph_service/application/ingest/file_symbols.py::FileSymbolsMixin
- backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs
- backend/services/code-graph-service/src/code_graph_service/neo4j/crud.py::Neo4jCrudMixin
related_docs:
- as.doc.ckg.live-ingest-remediation-index
- as.doc.ckg.live-audit-remediation-record
- as.doc.ckg.post-restart-verification-runbook
- as.doc.ckg.sync-embedding-heal-runbook
language: en
doc_version: 1.0.5
updated_at: 2026-08-10
---

# 75 - Sync Semantic Integrity and Recovery Evidence

## Purpose

This document records the quantitative evidence behind the final ingest result. It covers the initial gap, graph pruning, failure and recovery runs, semantic set equality, and recovery after a power interruption.

## Baseline and Final State

| Measure | Baseline observation | Final observation |
|---|---:|---:|
| Eligible semantic nodes in the initial code-only sample | `2,754` | Superseded by full eligibility calculation |
| Indexed nodes in the initial code-only sample | `130` | Superseded by full refresh |
| Missing in the initial code-only sample | `2,624` | `0` |
| Initial sample coverage | `4.7%` | `100%` |
| Final total Neo4j nodes | Not applicable | `15,132` |
| Final eligible semantic nodes | Not applicable | `8,979` |
| Final eligible indexed nodes | Not applicable | `8,979` |
| Final stored embeddings | Not applicable | `8,979` |
| Final missing eligible nodes | Not applicable | `0` |
| Final orphan embeddings | Not applicable | `0` |

The remediation acceptance comparison used exact identity-set intersection, not only equal aggregate counts.

After this five-document evidence pack was ingested, semantic refresh scanned and validated `8,984 / 8,984` eligible records. The `8,979` values above remain the pre-documentation remediation acceptance snapshot.

## Semantic Metadata

The final raw metadata result was:

```text
8979|BAAI/bge-large-en-v1.5|1024|1024
```

This means:

- `8,979` stored semantic records.
- Model identifier `BAAI/bge-large-en-v1.5`.
- Declared vector dimension `1024`.
- Actual stored vector dimension `1024`.

## Graph Pruning Evidence

During the rebuilding path:

| Measure | Before prune | After prune |
|---|---:|---:|
| `FILE` nodes | `488` | `411` |
| Total nodes | `15,811` | `14,976` |

The prune boundary was ownership-aware:

- Stale symbols owned by removed or replaced files were deleted.
- Generated document graph objects tied to stale files were removed.
- Human-authored documentation nodes were preserved.
- Shared external symbols were preserved when they were not exclusively file-owned.

Subsequent document ingest and current repository content produced the final `15,132` total-node state.

## Sync Run Timeline

| Durable usage record | Outcome | Important result |
|---|---|---|
| `.astloom/sync-usage/2026-07-28_21-41-25.json` | Failed | Document phase no longer showed connection exhaustion, but `38` files failed on legacy `version=null` |
| `.astloom/sync-usage/2026-07-28_21-57-28.json` | Succeeded | Recovery queue processed `39 / 39`; `files_failed=0`; document errors empty |
| `.astloom/sync-usage/2026-07-28_22-19-02.json` | Succeeded | Final changed-file queue processed `1 / 1`; semantic refresh scanned `8,979`, skipped `8,979`, refreshed `0`; freshness `ok` |

The first long rebuild before these durable recovery records failed in document synchronization with PostgreSQL reporting too many clients. That failure caused the connection-lifecycle remediation documented in the defect record.

## Recovery Sequence

### PostgreSQL Exhaustion

The initial real sync used `29` workers while PostgreSQL allowed `100` clients. Thread-local connections accumulated across phases, and document synchronization opened additional work.

The recovery changed behavior at the application/store seam:

- Reset database connections at phase boundaries.
- Reset again after document synchronization.
- Bound document workers to the store concurrency value of `8`.

Observed after the change:

- No repeat of `too many clients`.
- `22` clients at final observation.
- Maximum observed during the final backfill: `63 / 100`.

### Legacy Null Versions

The next real retry progressed past document connection management but exposed `38` legacy Neo4j nodes with `version=null`.

Deserialization now treats a legacy null as version `1`. The next queue contained one changed file plus the failed backfill and completed `39 / 39`.

### Power Interruption

An electrical interruption stopped the in-flight work. After power returned:

- PostgreSQL and Neo4j recovered to healthy states.
- The stopped sync process was not assumed to have completed.
- `8,946` previously persisted embeddings remained available.
- MCP Gateway was started again.
- Sync resumed from durable repository and graph state rather than restarting blindly.
- Idempotent refresh skipped already-valid semantic records.
- The final exact set reached `8,979 / 8,979`.

This demonstrates interruption tolerance for already committed records. It does not imply that an interrupted phase is transactionally complete; the operator must always rerun verification.

## Freshness and Idempotency Invariants

The final implementation enforces these invariants:

1. A process that has not verified repository state reports freshness as `unknown`, not clean.
2. Content identity includes file content, hash version, and parser policy.
3. `HASH_VERSION="4"` invalidates state created under older identity policy.
4. Valid embeddings may be reused during a policy-only re-ingest.
5. Symbol embeddings are produced in batches.
6. Edge persistence uses bulk writes.
7. Semantic refresh worker count is configurable through `ASTLOOM_EMBEDDING_REFRESH_WORKERS` and capped at `16`.
8. Language-only semantic backfill does not rewrite unrelated graph edges.
9. A successful final state requires zero failed files and exact semantic set equality.
10. Everyday `astloom sync` heals embeddings only for touched files (noop: capped backlog). Full-project missing/mismatch + orphan cleanup uses `astloom sync heal` (or `embedding_refresh_mode=full` / `ASTLOOM_EMBEDDING_REFRESH_FULL=1`) without force-reparsing healthy hash-stable sources. Operator contract: [77 - Sync Embedding Heal Operator Runbook](./77-sync-embedding-heal-operator-runbook.md).

## Integrity Queries

The verification procedure must answer all of the following:

- How many graph nodes are eligible for semantic indexing?
- How many of those exact identities have stored embeddings?
- Which eligible identities are missing?
- Which stored identities no longer exist or are no longer eligible?
- Does each stored vector match the configured dimension?
- Do known false target patterns occur in definite `CALLS` relationships?
- Does the latest sync usage record report `ok=true` and `files_failed=0`?

Aggregate count equality alone is insufficient because different missing and orphan identities can cancel numerically.

## Final Acceptance

The final state passed all ingest-specific gates:

- Latest sync succeeded.
- No file failed.
- Document synchronization returned no error.
- Freshness was verified and reported `ok`.
- Semantic refresh completed with no missing or orphan record.
- Stored vector dimensions matched the model contract.
- Known false `FakeClock.set` call edges were absent.
- Post-restart quality audit returned zero findings.

## Code Evidence Anchors

- `backend/services/code-graph-service/src/code_graph_service/application/ingest/repo_ingest.py::RepoIngestMixin`
- `backend/services/code-graph-service/src/code_graph_service/application/embedding_refresh.py::EmbeddingRefreshMixin`
- `backend/services/code-graph-service/src/code_graph_service/application/ingest/file_symbols.py::FileSymbolsMixin`
- `backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs`
- `backend/services/code-graph-service/src/code_graph_service/neo4j/crud.py::Neo4jCrudMixin`

## Related Documents

- [Live Audit Defect Remediation Record](73-live-audit-defect-remediation-record.md)
- [Verification Test Matrix and Results](74-verification-test-matrix-and-results.md)
- [Post-Restart Operations Verification Runbook](76-post-restart-operations-verification-runbook.md)

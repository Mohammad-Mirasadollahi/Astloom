---
doc_id: as.doc.ckg.post-restart-verification-runbook
title: 76 - Post-Restart Operations Verification Runbook
doc_type: runbook
status: active
schema_version: '1.0'
owner: code-graph-service
summary: 'Repeatable diagnosis, restart, ingest, concurrency, semantic-integrity, and audit checks for the remediated local Code Knowledge Graph stack.'
tags:
- restart
- operations
- verification
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/76-post-restart-operations-verification-runbook.md
lifecycle_lane: current
concern_lane: ops
audience_lane:
- operators
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- backend/services/mcp-gateway-service/src/mcp_gateway_service/http_app.py::create_http_app
- backend/services/code-graph-service/src/code_graph_service/application/service.py::CodeGraphService
- backend/services/code-graph-service/src/code_graph_service/application/ingest/repo_ingest.py::RepoIngestMixin
related_docs:
- as.doc.ckg.live-ingest-remediation-index
- as.doc.ckg.verification-test-matrix
- as.doc.ckg.sync-semantic-integrity-evidence
- as.doc.ckg.sync-embedding-heal-runbook
- as.doc.ckg.postgres-connection-pool-and-capacity-lld
language: en
doc_version: 1.0.5
updated_at: 2026-08-10
---

# 76 - Post-Restart Operations Verification Runbook

## Purpose

Use this runbook after Code Knowledge Graph or MCP Gateway changes, dependency restarts, an interrupted sync, or an unexpected host shutdown. Completion requires both service health and product-level verification.

## Triggers

Run the procedure when any of these conditions occurs:

- Code affecting MCP dispatch, ingest, graph persistence, semantic refresh, document sync, or CLI import resolution changes.
- PostgreSQL, Neo4j, or MCP Gateway restarts.
- A sync exits non-zero or is interrupted.
- The host loses power or the container runtime restarts.
- Freshness reports `unknown`, `pending`, or stale state.
- Quality audit reports missing embeddings, stale edited files, or document findings.

## Safety and Preconditions

- Run from the repository checkout that owns the target state.
- Confirm the intended `ASTLOOM_ROOT` before any live test.
- Use a temporary state root for approval and mutation-oriented test scenarios.
- Never place bearer tokens, database passwords, or complete authenticated commands in captured logs.
- Do not delete graph or database volumes as a first recovery step.
- Preserve failed sync usage records for diagnosis.

## Step 1: Inspect Before Restart

Record:

- Running PostgreSQL, Neo4j, MCP Gateway, sync, and test processes.
- Dependency health state.
- Latest `.astloom/sync-usage/*.json` result.
- Current freshness status.
- Current PostgreSQL client count and configured maximum.
- Current eligible, indexed, missing, and orphan semantic counts.

If a sync is still running and making progress, do not start a second sync.

## Step 2: Diagnose the Failure Class

| Symptom | Likely class | Required inspection |
|---|---|---|
| Health blocks during a long MCP tool | Event-loop starvation | Compare concurrent tool duration with health latency |
| `too many clients already` / sync “database at capacity” | Database connection lifecycle/concurrency | Observe clients by phase; prefer restart of long-lived graph/MCP; see [79](79-postgres-connection-pool-and-capacity-lld.md) |
| `int()` receives `NoneType` during graph read | Legacy null node version | Inspect affected Neo4j node `version` values |
| `ModuleNotFoundError` under a temporary root | State-root/import-root coupling | Compare state root with installed service checkout paths |
| Many missing embeddings | Incomplete refresh or stale eligibility | Compute exact eligible/indexed identity sets; run `astloom sync heal` (see [77](77-sync-embedding-heal-operator-runbook.md)) |
| Freshness appears clean immediately after process start | Unverified state | Inspect `verified`, status, and stale fields |
| Suspicious internal call target | Ambiguous or low-confidence resolution | Inspect edge confidence, language, target identity, and consumer filter |

## Step 3: Run Focused Regression Tests

Choose the smallest selection covering the observed class, then run the owning full service suite if the focused selection passes.

Minimum expectations:

- MCP HTTP changes: health-during-blocking-tool regression plus MCP non-live suite.
- Call-resolution changes: cross-language, external-call, hybrid-memory, and intelligence selections.
- Ingest/semantic changes: freshness, repo ingest, embedding refresh, store, and full Code Graph suites.
- Document/connection changes: document parallelism and connection-reset selections.
- Neo4j compatibility changes: null-version regression plus graph-store selection.
- CLI import changes: isolated-root unit test, the affected live scenario, then the full CLI and live selections.

Stop and investigate any new unexplained failure. Do not convert a failing assertion to a skip merely to complete the runbook.

## Step 4: Restart the Stack

Restart in dependency order:

1. Stop MCP Gateway cleanly.
2. Stop PostgreSQL and Neo4j through the repository's service orchestration.
3. Start PostgreSQL and Neo4j.
4. Wait until both dependencies report healthy.
5. Start MCP Gateway with the intended repository root, store, and model-provider configuration.
6. Confirm only the expected gateway instance is listening.

If a clean stop is impossible, capture process and log evidence before escalating to termination.

## Step 5: Verify Basic Health

Require all of the following:

- PostgreSQL reports healthy and accepts the configured application connection.
- Neo4j reports healthy and accepts a read query.
- MCP Gateway process remains running.
- MCP `/health` returns HTTP `200`.
- Recent MCP logs contain no `Traceback`, `ERROR`, `too many clients`, or `Connection refused`.
- No abandoned sync or test process remains.

The 2026-07-28 reference restart produced HTTP `200` in `0.003188s`.

## Step 6: Verify Concurrent HTTP Responsiveness

Start a known long-running, read-only MCP tool with a locally minted credential. While it is still active, request `/health` independently.

Pass conditions:

- The tool remains active long enough to overlap the health request.
- Health returns `200`.
- Health latency remains consistent with a responsive local service rather than waiting for the tool.
- No authentication material appears in saved output.

Reference evidence:

- Tool active for more than `10.417s`; health `200` in `0.084502s`.
- Cold repetition active for more than `12.217s`; health `200` in `0.096281s`.

## Step 7: Resume or Run Incremental Sync

After an interrupted or failed sync:

1. Read the latest usage record and classify its failure.
2. Confirm dependency health and available PostgreSQL client capacity.
3. Rerun sync idempotently against the same intended repository state.
4. Observe phase progress and client count.
5. Require a durable usage record with `ok=true`.
6. Require `files_failed=0`.
7. Require document synchronization to return no error.
8. Require freshness to finish as verified `ok`.

Do not infer success from a stopped process or from partial progress output.

## Step 8: Verify Graph and Semantic Integrity

Compute exact identity sets and require:

- Eligible graph identities equal eligible indexed identities.
- Missing identities equal `0`.
- Orphan stored identities equal `0`.
- Declared and actual vector dimensions match.
- Stored model identifier matches the configured semantic model.
- Known false call patterns return no definite `CALLS` edge.

The reference final state was:

```text
total_nodes=15132
eligible=8979
eligible_indexed=8979
missing=0
orphan=0
stored=8979
model=BAAI/bge-large-en-v1.5
declared_dimension=1024
actual_dimension=1024
false_FakeClock_set_edges=0
```

## Step 9: Run Final Quality Checks

Run:

- Repository documentation standards validation.
- `git diff --check`.
- Astloom quality audit.

Pass conditions:

- No documentation standard violation in changed documents.
- No whitespace/patch integrity error.
- No high, medium, or low code or documentation finding attributable to the change.

The 2026-07-28 post-restart reference result was `0` total findings.

## Rollback and Recovery

If the restarted service is unhealthy:

1. Preserve the failing logs and latest sync usage record.
2. Restore the last known-good application revision without deleting persistent data.
3. Restart dependencies only if their own health is failing.
4. Start the known-good MCP Gateway.
5. Repeat health, semantic-integrity, and quality checks.

If graph and semantic sets disagree, prefer an idempotent refresh (`astloom sync heal` for missing/mismatch embeddings) or targeted re-ingest. Destructive volume recreation requires separate authorization and a verified backup.

## Escalation

Escalate with:

- Exact failed step.
- Service health and process status.
- Sanitized error excerpt.
- Latest durable sync usage record path.
- PostgreSQL client count and maximum.
- Eligible/indexed/missing/orphan counts.
- Focused test name and result.
- Whether the failure reproduces after a clean restart.

Never include credentials or access tokens.

## Completion Record

The runbook is complete only when:

- Dependencies and MCP Gateway are healthy.
- Health remains responsive during overlapping tool work.
- Latest sync succeeds with no failed file.
- Semantic identity sets match exactly.
- Focused, broad, and live tests required by the change pass.
- Recent logs are clean.
- Documentation standards, patch integrity, and quality audit pass.

## Code Evidence Anchors

- `backend/services/mcp-gateway-service/src/mcp_gateway_service/http_app.py::create_http_app`
- `backend/services/code-graph-service/src/code_graph_service/application/service.py::CodeGraphService`
- `backend/services/code-graph-service/src/code_graph_service/application/ingest/repo_ingest.py::RepoIngestMixin`

## Related Documents

- [Live Ingest Remediation and Verification Index](72-live-ingest-remediation-verification-index.md)
- [Verification Test Matrix and Results](74-verification-test-matrix-and-results.md)
- [Sync Semantic Integrity and Recovery Evidence](75-sync-semantic-integrity-and-recovery-evidence.md)
- [Sync Embedding Heal Operator Runbook](77-sync-embedding-heal-operator-runbook.md)

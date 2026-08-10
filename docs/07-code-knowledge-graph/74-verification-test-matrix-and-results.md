---
doc_id: as.doc.ckg.verification-test-matrix
title: 74 - Verification Test Matrix and Results
doc_type: example
status: active
schema_version: '1.0'
owner: code-graph-service
summary: 'Exact focused, aggregate, live, and operational verification results for the 2026-07-28 remediation cycle.'
tags:
- test-matrix
- regression
- live-qa
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/74-verification-test-matrix-and-results.md
lifecycle_lane: current
concern_lane: example
audience_lane:
- platform-engineering
- reviewers
- operators
authority: informative
visibility: internal
linked_symbols:
- backend/services/mcp-gateway-service/src/mcp_gateway_service/http_app.py::create_http_app
- backend/services/code-graph-service/src/code_graph_service/application/service.py::CodeGraphService
- backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs
- backend/packages/astloom_cli/util.py::ensure_service_import_paths
related_docs:
- as.doc.ckg.live-ingest-remediation-index
- as.doc.ckg.live-audit-remediation-record
- as.doc.ckg.sync-semantic-integrity-evidence
language: en
doc_version: 1.0.3
updated_at: 2026-08-10
---

# 74 - Verification Test Matrix and Results

## Purpose

This matrix records what was tested, which product behavior each selection covers, and the exact observed result. It separates focused regressions from broad suites and real-system checks so that a passing count is not mistaken for complete behavioral evidence.

## Automated Test Matrix

| Selection | Coverage intent | Result | Duration |
|---|---|---:|---:|
| MCP Gateway non-live suite | HTTP routing, authentication boundaries, tool dispatch, health responsiveness | `33 passed` | Not separately retained |
| Code Graph full suite after primary fixes | Parsing, call resolution, ingest, graph stores, semantics, freshness, intelligence | `402 passed` | `136.61s` |
| CLI non-live suite before isolated-import correction | CLI commands, approvals, sync orchestration, output contracts | `347 passed` | Not separately retained |
| Combined Code Graph + MCP + CLI non-live aggregate | Cross-service regression coverage after the main remediation | `766 passed`, `24 deselected` | `95.05s` |
| PostgreSQL/document concurrency focused selection | Connection reset, document worker bounding, parallel document sync | `13 passed` | Not separately retained |
| Legacy Neo4j/document focused selection | Null-version compatibility and document sync recovery | `7 passed` | Not separately retained |
| Isolated import unit regression | Package discovery when state root is temporary | `1 passed` | Not separately retained |
| Previously failing isolated live scenario | Exact live approval/import failure path | `1 passed` | Not separately retained |
| Final CLI non-live suite | CLI regression after import-path correction | `348 passed`, `2 deselected` | `11.87s` |
| First complete live selection | All marked live scenarios; exposed isolated import defect | `23 passed`, `1 failed` | Intermediate run |
| Final complete live selection | All marked live scenarios after correction | `24 passed`, `767 deselected` | `153.56s` |

## Behavior-to-Test Traceability

| Product behavior | Automated evidence | Real-path evidence | Status |
|---|---|---|---|
| Health remains responsive during blocking MCP work | `test_http_health_remains_responsive_during_blocking_tool` | Two concurrent health/tool probes | Passed |
| Python built-ins do not resolve to unrelated internal symbols | Cross-language resolution and external-call tests | Neo4j false-edge query | Passed |
| Low-confidence calls do not pollute definite intelligence views | Hybrid memory and Wave 2/3 intelligence tests | Final affected-path inspection | Passed |
| New-process freshness is not falsely reported as clean | Freshness/service tests | Final sync freshness status `ok` after verification | Passed |
| Parser/hash policy changes invalidate correctly | Ingest/idempotency tests | Policy re-ingest with embedding reuse | Passed |
| Semantic refresh is complete and bounded | Refresh/store tests | Exact `8,979 / 8,979` eligibility intersection | Passed |
| Stale file-owned graph data is pruned safely | Ingest/store tests | Node-count and survivor checks | Passed |
| Document parallelism respects database capacity | Two explicit docs-link concurrency regressions | Successful recovery under `max_connections=100` | Passed |
| Legacy null graph versions deserialize safely | `test_symbol_from_node_defaults_legacy_null_version` | `39 / 39` recovery ingest | Passed |
| Live tests isolate mutable state | Live-test isolation changes plus full selection | Temporary state-root scenario | Passed |
| CLI imports installed services with isolated state | `test_service_import_paths_use_install_checkout_when_state_root_is_isolated` | Previously failing live test and full live rerun | Passed |
| Restarted stack preserves expected operation | Existing health and service tests | Final service, log, and health checks | Passed |

## Failure-to-Fix Chronology

| Order | Observation | Action | Verification |
|---:|---|---|---|
| 1 | Blocking MCP work starved HTTP | Offload synchronous dispatch from event loop | Regression plus two live concurrent probes |
| 2 | False `FakeClock.set` relationship | Correct built-in/name resolution and confidence filtering | Unit/integration tests plus `false_edges=0` |
| 3 | Semantic baseline was incomplete | Correct freshness, invalidation, batching, pruning, and refresh | Exact final set equality |
| 4 | Real sync exhausted PostgreSQL connections | Reset phase connections and cap docs workers | `13` focused passes and successful real rerun |
| 5 | Rerun exposed legacy null versions | Default legacy null to version `1` | `7` focused passes and `39 / 39` ingest |
| 6 | First full live suite exposed isolated import coupling | Separate state root from installed code root | Focused unit/live passes and final `24 / 24` live result |
| 7 | Power interruption stopped in-flight work | Recover dependencies and resume idempotently | Persisted semantic count retained; final sync and restart passed |

## Real-System Checks

The following checks were performed against running services rather than only mocks:

- Concurrent MCP tool execution and HTTP health polling.
- PostgreSQL client-count observation during multi-worker ingest.
- Neo4j queries for node counts, false call edges, and eligible semantic nodes.
- Stored embedding count, model, and vector-dimension comparison.
- Incremental sync after two separate failure modes.
- Recovery after an electrical power interruption.
- Full service stop/start followed by process, health, log, and stuck-process checks.
- Quality audit before and after the final restart.

No secret token or database credential was retained in the evidence.

## Acceptance Gates

| Gate | Required condition | Final observation |
|---|---|---|
| Focused regressions | Every new regression passes | Passed |
| Broad non-live coverage | No failure in Code Graph, MCP, or CLI selections | Passed |
| Complete live coverage | Every collected live test passes | `24 / 24` passed |
| Real ingest | No failed file in the recovery/final successful run | `files_failed=0` |
| Semantic integrity | Eligible graph set equals indexed set | Exact equality at `8,979` |
| Operational restart | Dependencies and gateway healthy after restart | Passed |
| Static patch integrity | No whitespace or patch-format error | `git diff --check` clean |
| Quality audit | No unresolved documentation or code finding | `0` total |

## Interpretation and Limits

The results demonstrate conformance for the tested repository state and configured local PostgreSQL, Neo4j, fake-model, and MCP paths. They do not establish:

- Infinite-load or long-duration soak capacity.
- Correctness of external model providers that were not selected.
- Production network, proxy, or identity-provider behavior outside the local stack.
- Future semantic completeness after later source changes without another sync.

These limits are deliberate. The operational runbook defines the checks required to re-establish the same evidence after a later change.

## Code Evidence Anchors

- `backend/services/mcp-gateway-service/src/mcp_gateway_service/http_app.py::create_http_app`
- `backend/services/code-graph-service/src/code_graph_service/application/service.py::CodeGraphService`
- `backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs`
- `backend/packages/astloom_cli/util.py::ensure_service_import_paths`

## Related Documents

- [Live Audit Defect Remediation Record](73-live-audit-defect-remediation-record.md)
- [Sync Semantic Integrity and Recovery Evidence](75-sync-semantic-integrity-and-recovery-evidence.md)
- [Post-Restart Operations Verification Runbook](76-post-restart-operations-verification-runbook.md)

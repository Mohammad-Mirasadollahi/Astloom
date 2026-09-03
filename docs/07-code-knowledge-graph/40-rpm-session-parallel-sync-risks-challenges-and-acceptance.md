---
doc_id: as.doc.ckg.rpm-session-parallel-sync-risks
title: 40 - RPM Session Parallel Sync Risks Challenges And Acceptance
doc_type: standard
status: draft
schema_version: '1.0'
owner: code-graph-lead
summary: Risks, challenges, known limits, and acceptance gates for RPM-session-tracked parallel
  sync.
tags:
- risks
- acceptance
- sync
- rpm
- concurrency
phase: 07-code-knowledge-graph
canonical_path: docs/07-code-knowledge-graph/40-rpm-session-parallel-sync-risks-challenges-and-acceptance.md
lifecycle_lane: current
concern_lane: problem
audience_lane:
- platform-engineering
- operators
authority: normative
visibility: internal
linked_symbols:
- backend/packages/llm_gateway/rate_limit.py::RpmSessionGate
- backend/services/code-graph-service/src/code_graph_service/application/ingest/parallel_files.py::run_parallel_file_jobs
- backend/services/code-graph-service/src/code_graph_service/application/ingest/repo_ingest.py::RepoIngestMixin
- backend/services/code-graph-service/src/code_graph_service/domain/dispatch_synth.py::synthesize_interface_dispatch
- backend/services/docs-sync-service/src/docs_sync_service/postgres_store.py::PostgresStore
- backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs
related_docs:
- as.doc.ckg.rpm-session-parallel-sync-feature-spec
- as.doc.ckg.rpm-session-parallel-sync-lld
- as.doc.stack.litellm-llm-gateway
doc_version: 1.2.0
audience:
- engineer
- architect
- operator
primary_entities:
- AcceptanceGate
- RpmSession
relations_declared:
- type: depends_on
  target: as.doc.ckg.rpm-session-parallel-sync-feature-spec
- type: complements
  target: as.doc.ckg.sync-finalizing-and-provider-cost-runbook
chunk_hints:
  strategy: heading_h2
  max_tokens: 600
  overlap_tokens: 40
language: en
security_classification: internal
updated_at: '2026-09-03'
---

# 40 - RPM Session Parallel Sync Risks Challenges And Acceptance


## Purpose

Risks, challenges, known limits, and acceptance gates for RPM-session-tracked parallel sync. Designed ahead of implementation; gates unchecked until code.

## Implementation status

**Implemented.** Re-check acceptance gates below against the current tree when
claiming production readiness; keep multi-process RPM sharing as a known v1 limit.

Last verified: 2026-07-25

## Challenges (must be designed for)

| ID | Challenge | Why it bites | Design response |
| --- | --- | --- | --- |
| C-01 | Postgres connection sharing | Sharing one ``psycopg`` connection across threads corrupts cursors | Code-graph and docs-sync Postgres adapters use **per-thread** connections; ``LockedStore`` applies the same slot budget as Neo4j |
| C-02 | RPM starts ≠ in-flight | Long completions keep provider busy after “start” counted | Dual gate: sliding starts **and** in-flight cap |
| C-03 | Session leaks | Exception / timeout without `finally` leaves ghost in-flight | Mandatory `release` in `finally`; unit leak tests |
| C-04 | Idempotency races | Parallel `ingest_file` sharing keys or overlapping completes | Unique per-file keys; begin/complete under writer lock |
| C-05 | Cross-file edges | Waiting for peer files deadlocks; ignoring peers drops edges | No cross-file wait; unresolved calls/imports/inheritance relink as peer symbols land |
| C-06 | Retry accounting | SDK `num_retries` multiplies provider load | One outer session per gateway invocation (LLD); document load effect |
| C-07 | Heuristic / stub false RPM | Runtime fallback must not acquire or leave sessions | No `acquire` on runtime heuristic/local-stub paths; `FakeLlmGateway` explicitly emulates network-session semantics in tests |
| C-08 | Local BGE vs LiteLLM embed | BGE must not consume RPM slots or serialize all files | Only `gateway.embed` acquires; model construction is process-serialized and inference is bounded to four concurrent calls process-wide across cached models |
| C-09 | Hung sessions | Provider hang beyond operator patience | Timeout = `ASTLOOM_LITELLM_TIMEOUT_SECONDS`; forced end |
| C-10 | Multi-process CLI | Two `astloom sync` processes do not share registry | Document known limit; no Redis in v1 |
| C-11 | File monopoly | One huge file’s network-backed symbol work can starve others | Living docs are one `complete` per file (`generate_many`); RPM gate still serializes Provider starts; an explicit round-robin DocWork scheduler is not implemented |
| C-12 | Progress races | Unsynchronized counters mislead ETA | Lock/queue in `SyncProgressTracker` |
| C-13 | Observability secrets | Status API could leak prompts/keys | Snapshot fields allowlist only |
| C-14 | Test flakiness | Real 60s sleeps | Fake clock / injected time; never sleep a full minute in unit CI |
| C-15 | Serial finalization masks worker gains | Whole-scope reads or per-edge Neo4j RTT after progress reaches 100% | Shared symbol snapshot, batched `delete_edges`/`put_edges`, indexed dispatch, explicit `finalizing` status + progress steps; content-push finalizes only on last HTTP batch — [`82`](82-sync-finalizing-and-provider-cost-runbook.md) |
| C-16 | Restart depends on plugin network | Official GDS installer fetches on every container start | APOC-only offline-safe default; GDS is explicit `ASTLOOM_NEO4J_PLUGINS` opt-in |
| C-17 | Stable root idempotency suppresses later edits | A prior file key short-circuits before hash comparison | Derive the file key from root key + path + content hash |
| C-18 | CLI/service config drift | In-process sync silently falls back when model env is absent | Graph CLI loads repo-root `.env` (single source of truth); process env retains precedence |
| C-19 | Silent cloud code egress | A configured provider may receive symbol bodies without per-run consent | Non-private/uncertain routes fail closed before ingest; interactive TTY consent (tenant/workspace/project/paths shown) or `--allow-cloud-llm` |

## Risks

| ID | Risk | Mitigation |
| --- | --- | --- |
| R-01 | Operators believe RPM is cluster-wide | Docs + CLI banner: process-local; warn if multiple syncs |
| R-02 | Raising file workers without RPM headroom | Queue grows; wall time flat; document worker ≤ inflight guidance |
| R-03 | Store concurrency overwhelms persistence | `LockedStore` bounds operations; Postgres adapters use tracked per-thread connections |
| R-04 | Provider 429 despite client RPM | Lower RPM; retries amplify load — tune `NUM_RETRIES` |
| R-05 | Partial graph on soft-fail | Same as today; outcomes list failed files |
| R-06 | Docs claim shipped while code serial | `lifecycle_lane: current` until gates pass; honesty in status section |

## Known limits (v1)

- Session registry and RPM truth are **per process**.
- History is **short** (100) and **volatile** (lost on exit).
- Human-docs Phase 2 uses the same `sync_max_file_workers` pool as code ingest;
  docs-sync and code-graph Postgres adapters use **per-thread** connections so
  Phase-1/2 writers share the ``LockedStore`` slot budget (not exclusive
  ``lock_reads`` serialization).
- Bulk repository ingest has no round-robin network DocWork queue. When living
  LLM docs are enabled, each changed file uses one batched Provider `complete`
  (`generate_many`); when disabled, the heuristic generator is used. Explicit
  network calls are bounded by `RpmSessionGate`, but cross-file fairness is not
  claimed.
- No distributed limiter across hosts.

## Acceptance gates

Uncheck → check only when proven in code + tests.

### Session gate

- [x] Every LiteLLM `complete`/`embed` has matching start and end (no leak tests).
- [x] Concurrent threads never observe `starts_in_window > rpm` or `inflight > cap`.
- [x] Timeout path ends the session; registry count drops.
- [x] Heuristic / local BGE / stub paths create **zero** sessions.

### Parallel sync gate

- [x] File parse/hash runs with bounded workers (`ASTLOOM_SYNC_MAX_FILE_WORKERS`).
- [x] Store ops use bounded slots for Neo4j **and** Postgres (per-thread
  connections); paths pass `test_rpm_session_parallel_sync_live.py` with
  concurrent local HTTP LLM calls.
- [x] Production bulk composition with real cached BGE and real Neo4j completes
  five changed files with heuristic living docs and zero false HTTP/RPM sessions
  (`test_production_build_uses_heuristic_docs_without_rpm_sessions`).
- [x] Explicit network-backed per-file ingest against real Neo4j reaches exact
  HTTP/RPM peaks 1, 2, and 4 with no leaked sessions
  (`test_live_llm_rpm_sessions_follow_parallel_worker_level`).
- [x] Multiple service instances and cached models observe the same four-call
  process-wide bound
  (`test_local_embedding_limit_is_shared_across_service_instances`).
- [x] Concurrent cache misses cannot construct multiple large local models at once
  (`test_local_model_loads_are_process_serialized`).
- [x] Per-file soft-fail preserved; one failure does not abort the job.
- [ ] Fairness for a future network DocWork queue: multi-file fixture shows
  interleaved symbol work under a low in-flight cap. This does not block the
  current heuristic bulk path.
- [x] Idempotency keys are unique per file and content version under
  concurrency. Same-content retries no-op; later edits ingest
  (`test_repo_idempotency_allows_new_file_content`).
- [x] Cross-file finalization reuses one symbol snapshot and never performs an
  unfiltered edge read
  (`test_cross_file_finalizer_reuses_symbols_and_filters_edge_reads`).
- [x] Package README mapping uses one symbol snapshot and skips folders without
  indexed code (`test_package_readme_maps_reuse_one_symbol_snapshot`).
- [x] Dynamic-dispatch ownership and call lookup are indexed. The 2026-07-25
  live graph measurement was 0.117s for 14,732 symbols and 27,049 CALL edges,
  down from 12.143s.

### Observability gate

- [x] `GET /api/v1/llm/sessions` (or final path) returns inflight + history + RPM stats.
- [x] CLI exposes the same snapshot fields from an active CLI sync or the running
  HTTP service (`test_llm_sessions_prefers_active_sync_process`,
  `test_llm_sessions_reads_running_service_snapshot`; live HTTP/CLI verified 2026-07-22).
- [x] CLI progress reports zero sessions on heuristic bulk work without inventing
  activity (`test_cli_progress_reports_heuristic_docs_without_rpm_sessions`);
  the network-backed Live matrix separately proves non-zero 1/2/4 session peaks.
- [x] CLI loads LiteLLM / model configuration from repo-root `.env`
  (`test_load_dotenv_files_reads_root_litellm_config`,
  `test_graph_cli_builds_gateway_from_root_env`).
- [x] Cloud/uncertain LLM routes require explicit per-run consent before sync,
  graph explore, or hybrid search — interactive TTY (tenant/workspace/project/paths)
  or `--allow-cloud-llm` (`test_sync_cloud_llm_requires_explicit_per_run_consent`,
  `test_cloud_llm_consent_prompt_shows_scope_and_path`,
  `test_graph_query_commands_apply_cloud_consent_guard`).
- [x] Payloads contain no API keys, prompts, completion bodies, or raw provider
  error text (`test_litellm_gateway_releases_sessions_on_failures`).
- [x] Detailed HTTP sessions are loopback-only, and the transient CLI snapshot
  is explicitly `0600` (`test_llm_sessions_route_is_loopback_only`,
  `test_tracker_snapshot_is_private_before_json_is_written`).
- [x] Human-docs Phase 2 (`docs_link_sync`) uses ``sync_max_file_workers`` with
  concurrent docs-sync writes. The Live matrix verifies exact 1/2/4 peaks
  against PostgreSQL and Neo4j
  (`test_live_code_and_docs_file_parallelism_matrix`).
- [x] Unchanged session polls do not rewrite/fsync transient progress
  (`test_tracker_skips_unchanged_session_snapshot`).
- [x] Default Compose restart is offline-safe and does not fetch GDS. A real
  restart completed healthy in 38.71s after the prior network-backed attempt
  timed out at 300s.

### Documentation / honesty gate

- [x] Pack `37`–`40` field names match implementation.
- [x] `lifecycle_lane` moved from `future` to `current` only after gates above.
- [x] LiteLLM env doc (`12`) updated for session/in-flight semantics and new knobs.
- [x] Ingest workflow (`03`) notes parallel pipeline + serial writer.

## Open gaps (post-v1)

| Gap | Notes |
| --- | --- |
| Shared ``psycopg_pool`` | Optional; per-thread connections already allow parallel Phase-2 writers |
| Round-robin network DocWork fairness | Living docs are already file-batched; fairness across files still RPM-FIFO only |
| Shared limiter across processes | Redis/file lock — only if multi-sync becomes common |
| Attempt-level session nesting | If ops need per-retry visibility |

## Related Documents

- Feature: [`37`](37-rpm-session-parallel-sync-feature-specification.md)
- HLD: [`38`](38-rpm-session-parallel-sync-high-level-design.md)
- LLD: [`39`](39-rpm-session-parallel-sync-low-level-design.md)
- CPU budget: [`50`](50-sync-cpu-budget-and-store-concurrency-lld.md)
- Finalizing / Provider cost: [`82`](82-sync-finalizing-and-provider-cost-runbook.md)
- LiteLLM ADR: [`09`](../13-technology-stack-and-platform-decisions/09-litellm-llm-gateway.md)

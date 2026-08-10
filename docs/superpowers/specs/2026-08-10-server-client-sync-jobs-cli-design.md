---
doc_id: as.doc.sea.server-client-sync-jobs-cli
title: Server CLI tracking for live client content-push sync jobs
doc_type: feature_spec
status: active
schema_version: '1.0'
owner: platform-engineering
summary: 'Server-only CLI (astloom sync jobs) lists live client ingest-push job IDs
  and shows heavy progress (done/total, rate, ETA, in-flight paths, graph process
  CPU/RSS) from disk snapshots under the data root — no new public HTTP surface.'
tags:
- design
- sync
- ingest
- client
- ops
- cli
phase: 08-software-engineering-architecture
canonical_path: docs/superpowers/specs/2026-08-10-server-client-sync-jobs-cli-design.md
lifecycle_lane: current
concern_lane: ops
audience_lane:
- platform-engineering
- operators
- agents
authority: normative
visibility: internal
doc_version: 1.2.2
updated_at: 2026-08-10
linked_symbols:
- backend/services/code-graph-service/src/code_graph_service/api/client_sync_job_snapshots.py::write_job_snapshot
- backend/services/code-graph-service/src/code_graph_service/api/client_sync_job_snapshots.py::clear_job_snapshot
- backend/services/code-graph-service/src/code_graph_service/api/client_sync_job_snapshots.py::list_live_job_snapshots
- backend/services/code-graph-service/src/code_graph_service/api/ingest.py::ingest_push
- backend/packages/astloom_cli/commands/sync/jobs.py::cmd_sync_jobs
- backend/packages/astloom_cli/parser/_core.py::peel_sync_words
- backend/services/code-graph-service/src/code_graph_service/api/job_cancel_registry.py::register_job
- backend/services/code-graph-service/src/code_graph_service/application/ingest/pushed.py::ingest_pushed_sources
- backend/packages/astloom_cli/connect_flow/client_push.py::_run_ingest_push_http
- backend/packages/astloom_cli/sync_progress/store.py::read_live_progress
- backend/packages/astloom_cli/data_root.py::ensure_data_root
related_docs:
- docs/superpowers/specs/2026-08-05-client-push-progress-stream-design.md
- docs/superpowers/specs/2026-08-10-client-sync-auto-discovery-inventory-design.md
- docs/08-software-engineering-architecture/42-astloom-cli-command-reference.md
- docs/08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding-continued.md
---

# Server CLI tracking for live client content-push sync jobs

## Purpose

Operators on the **Astloom server** need a **CLI-only** way to see live
`astloom-client sync` (HTTPS `ingest-push`) work: pick a `job_id` from a list,
then inspect heavy progress (files planned vs done, rate, ETA, in-flight paths)
and approximate graph-process resource use (CPU%, RSS). Client-side progress
already streams to the client; this design adds a **server-local snapshot** the
server CLI can read without a new public HTTP API or UI.

## Approaches considered

| Option | Idea | Trade-off |
| --- | --- | --- |
| A — Disk snapshots under data-root (selected) | Each in-flight push writes/updates `{data_root}/run/client-sync-jobs/<job_id>.json`; CLI reads them | Smallest ops surface; matches cancel `job_id`; no DB |
| B — Postgres job table | Persist every progress event | History + multi-node ready; overkill for live CLI watch |
| C — Log scrape only | Operator `rg` uvicorn logs | Cannot reliably expose ETA / in-flight / CPU |

## End-to-end flow

```mermaid
flowchart TD
  client[astloom-client sync] -->|POST ingest-push + job_id| graph[code-graph ingest-push]
  graph --> reg[job_cancel_registry register]
  graph --> snap[Write/update job snapshot JSON]
  graph -->|NDJSON progress| client
  op[Operator on server] --> cli[astloom sync jobs]
  cli --> list[List live job_id rows]
  op --> detail[astloom sync jobs JOB_ID]
  detail --> snap
  detail --> proc["/proc sample CPU RSS for graph PID"]
  graph -->|job end or cancel| clear[Mark inactive / delete snapshot]
```

| Step | Actor | Action | Success signal |
| --- | --- | --- | --- |
| 1 | Client | Starts content-push with `X-Job-Id` (existing) | Server registers cancel handle |
| 2 | Graph | On each progress emit, upsert snapshot under data-root | File mtime fresh; `active=true` |
| 3 | Operator | Runs `astloom sync jobs` | Table of live `JOB_ID` + scope + done/total |
| 4 | Operator | Runs `astloom sync jobs <job_id>` | Heavy detail + CPU/RSS best-effort |
| 5 | Graph | Job finishes or cancel | Snapshot removed or `active=false` (stale list filter) |

## CLI contract (server role only)

| Invocation | Behavior |
| --- | --- |
| `astloom sync jobs` | List live jobs: full `job_id`, scope, `done/total`, `%`, age. Exit 0 if empty with `No live client sync jobs.` |
| `astloom sync jobs <job_id>` | Heavy detail for one id (see fields below). Unknown/stale → non-zero + clear error |
| `--json` | Same payloads as JSON |

**Client-only installs:** command is absent or fails closed (server/both only), consistent with other server admin surfaces.

**Non-goals:** public HTTP list/detail API, web UI, long-term history, interactive TUI picker (list output is the ID menu; operator copies `job_id`).

## Snapshot schema (SoT on disk)

Path: `{ASTLOOM_DATA_ROOT}/run/client-sync-jobs/<job_id>.json`  
(Fallback if data-root unset: install `.astloom/run/client-sync-jobs/` — same layout as other run artifacts.)

| Field | Source |
| --- | --- |
| `job_id`, `tenant_id`, `workspace_id`, `project_id` | Request headers / cancel registry |
| `active`, `started_at`, `updated_at` | Writer timestamps |
| `phase`, `status`, `done`, `total`, `file` | Existing ingest progress events |
| `files_in_flight`, `files_in_flight_paths`, `file_workers` | Progress events (workers required for UI parity) |
| `symbols_indexed`, `edges_written`, `approx_tokens` | Progress events |
| `rate` / ETA | Derived by CLI from `done` + age (or stored if already computed server-side) |

Never store bearer tokens, file bodies, or bootstrap secrets in the snapshot.

## Detail view (heavy)

When detailing one `job_id`, print at least:

- Identity: job id, scope, started, age  
- Progress: done/total, percent, phase, status, current file  
- Throughput: files/sec (from EWMA or simple done/elapsed), ETA  
- Parallel: workers, in-flight count, up to N in-flight paths  
- Resources (best-effort): graph process CPU% and RSS via `/proc/<pid>/…` for the code-graph uvicorn PID known to the host; if unavailable → `n/a`

## Failure policy

| Case | Policy |
| --- | --- |
| No live jobs | Empty list message, exit 0 |
| Stale snapshot (e.g. `updated_at` older than threshold, default ~60s) | Omit from list; detail may say stale/gone |
| Graph process PID unknown | Progress still shown; resources `n/a` |
| Snapshot I/O error during ingest | Progress to client must not fail (best-effort write) |
| Cancel / client disconnect | `clear_job_snapshot` closes the id; late worker progress must not recreate the JSON (misleading `status=ok`) |

## Verification

| Check | Evidence |
| --- | --- |
| Unit | Snapshot write/read; list filters inactive/stale; late write after clear does not recreate; detail field presence |
| Live | Start `astloom-client sync` on lab client; on server `astloom sync jobs` shows id; detail shows advancing `done` and non-`?` workers |

## Related Documents

- [Client content-push sync progress stream](./2026-08-05-client-push-progress-stream-design.md)
- [Client sync auto discovery and inventory-complete prune](./2026-08-10-client-sync-auto-discovery-inventory-design.md)
- [Astloom CLI command reference](../../08-software-engineering-architecture/42-astloom-cli-command-reference.md)
- [Onboarding continued — content-push](../../08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding-continued.md)

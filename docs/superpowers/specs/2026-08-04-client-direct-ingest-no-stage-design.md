---
doc_id: as.doc.sea.client-direct-ingest-no-stage
title: Client direct ingest without durable source stage
doc_type: feature_spec
status: active
schema_version: '1.0'
owner: platform-engineering
summary: Client sync pushes only file contents needed for graph ingest into Astloom;
  no durable rsync mirror of the client checkout is created on the Astloom host.
tags:
- design
- sync
- ingest
- client
phase: 08-software-engineering-architecture
canonical_path: docs/superpowers/specs/2026-08-04-client-direct-ingest-no-stage-design.md
lifecycle_lane: current
concern_lane: design
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
doc_version: 1.5.1
updated_at: 2026-08-10
linked_symbols:
- backend/packages/astloom_cli/commands/sync/client_remote.py::cmd_sync_client_remote
- backend/packages/astloom_cli/connect_flow/client_push.py::client_push_sync
- backend/packages/astloom_cli/connect_flow/client_push.py::build_push_docs
- backend/packages/astloom_cli/connect_flow/client_push.py::build_push_files
- backend/packages/astloom_cli/connect_flow/ingest.py::remote_ingest
- backend/packages/astloom_cli/commands/ingest_push.py::cmd_ingest_push
- backend/packages/astloom_cli/parser/_core.py::resolve_discovery_max_files
- backend/services/code-graph-service/src/code_graph_service/application/ingest/pushed.py::ingest_pushed_sources
- backend/services/code-graph-service/src/code_graph_service/domain/path_safety.py::safe_repo_rel_path
- backend/services/code-graph-service/src/code_graph_service/api/ingest.py::register
- backend/services/code-graph-service/src/code_graph_service/api/auth.py::require_content_push_http_auth
- backend/services/code-graph-service/src/code_graph_service/api/schemas.py::IngestPushRequest
related_docs:
- docs/superpowers/specs/2026-08-10-client-sync-auto-discovery-inventory-design.md
- docs/superpowers/specs/2026-08-05-client-push-progress-stream-design.md
- docs/superpowers/specs/2026-08-10-server-client-sync-jobs-cli-design.md
---

# Client direct ingest without durable source stage

## Purpose

Client remote sync must not require a software checkout on the Astloom host.
The client discovers local sources and sends **ingest payloads** (path + body)
to the server graph pipeline. Bytes may cross the wire for changed files; a
durable code tree on the server is out of scope.

## Approaches considered

| Option | Idea | Trade-off |
| --- | --- | --- |
| A — Rsync stage + remote `astloom sync --path` | Copy tree then walk on server | Durable mirror; rejected |
| B — Ephemeral unpack on server, ingest, delete | Tar to temp then wipe | Still writes a tree; rejected |
| C — Content-push ingest (selected) | Client walks locally; server `ingest_file` on bodies | No durable tree |

**Recommendation:** C.

## Goal / non-goals

**Goals**

- `astloom-client sync` (no CLI `--path`) content-pushes only.
- Transport: private-LAN HTTPS when `server.graph_url` + bearer token are set.
- Default discovery is **auto** (full tree up to 20 000); explicit `max-file N` caps.
- Unchanged bodies may be skipped via FILE content-hash comparison.
- Human Markdown docs may be pushed on the last batch (`docs[]` →
  `upsert_human_documentation`) when sync docs filters are enabled.
- Connect ingest uses the same content-push path (no on-server tree required).
- Deleted local files are pruned only when the client sends both `present_paths`
  and `inventory_complete=true` (authoritative full inventory). `present_paths`
  alone never deletes — partial/scoped syncs must not wipe other graph files.
- Explicit CLI `--path` remains for operators who already have a tree on the host
  (NFS/clone/dogfood).

**Non-goals**

- Opening Postgres/Neo4j ports to developer laptops.
- Changing MCP query tools or embedding model routing.
- Replacing same-host / dogfood `astloom sync --path`.
- Durable rsync mirrors or `source.mirror` escape hatches.
- Restoring SSH as a product transport.

## Architecture

```mermaid
flowchart TD
  client[Client checkout cwd]
  disc[Discover + sync filters]
  hash{Server FILE hashes?}
  pack[Build changed HTTP batches]
  http[HTTPS ingest-push]
  svc[CodeGraphService.ingest_pushed_sources]
  graph[(Neo4j / Postgres graph)]

  client --> disc --> hash
  hash -->|skip stable| pack
  hash -->|first sync / miss| pack
  pack --> http --> svc
  svc --> graph
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | CLI client | Resolve connect.yaml scope + cwd | No `source.server_path` required |
| 2 | CLI client | Discover sources (+ docs); default auto up to 20 000 | Candidate relative paths |
| 3 | CLI client | Optional: fetch FILE hash map (HTTP) | Skip unchanged bodies |
| 4 | CLI client | POST size-capped batches of `{file_path, source}` | Wire payload |
| 5 | CLI client | Last batch: optional `docs[]`; `present_paths` + `inventory_complete=true` only when discovery is full | Docs upsert; prune only when inventory is authoritative |
| 6 | Server | `ingest_pushed_sources` (+ docs); prune iff `inventory_complete` | Graph updated without partial-inventory deletes |

## Service / CLI

- `CodeGraphService.ingest_pushed_sources`
- `POST /api/v1/projects/{id}/graph/ingest-push` (optional `docs`)
- `GET /api/v1/projects/{id}/graph/file-hashes`
- `GET /api/v1/llm/config` (HTTP cloud-LLM consent probe)
- `astloom ingest-push` (stdin JSON) and `astloom file-hashes`
- Connect: `server.graph_url` / `ASTLOOM_CONNECT_GRAPH_URL` + token

## Client remote sync

1. Load connect settings (`graph_url` + token).
2. Cloud-LLM consent on the local TTY (HTTP uses `/api/v1/llm/config`, fail-closed
   to assume-cloud when probe fails).
3. Run content-push against cwd (sources + optional docs); auto discovery unless
   `max-file` is set.
4. CLI `--path` → local/on-host `astloom sync --path` only (not content-push).

## Optional capabilities (shipped)

| Capability | Behavior |
| --- | --- |
| HTTP content-push | When `server.graph_url` + bearer token set, prefer HTTP for hashes + push (SSH removed from product path) |
| Docs push | `build_push_docs` → last-batch `docs[]` → server `upsert_human_documentation` |
| Connect content-push | `remote_ingest` / `should_ingest` use content-push when HTTPS is ready |
| Auto discovery | Default `max_files=0` discovers up to `HARD_SYNC_MAX_FILES` (20 000); see auto-discovery design |
| HTTP batching | Split push by ~4 MiB / 1500 files per request; batch size ≠ discovery cap |
| Inventory prune | `present_paths` + `inventory_complete=true` only when `prune_ok` |

## Security / sovereignty

- **Trust boundary:** bearer-auth HTTPS on a private LAN. Do not expose graph
  `ingest-push` to the public internet.
- **HTTP auth:** `ingest-push` / `file-hashes` require `Authorization: Bearer` matching
  `ASTLOOM_CODE_GRAPH_HTTP_TOKEN` (or `ASTLOOM_CONNECT_TOKEN`). When unset, only
  loopback is accepted.
- **Path safety:** server rejects absolute paths, ``..``, and NUL; keys are
  repo-relative only (`safe_repo_rel_path`).
- **Bounds:** discovery and server `max_files` hard-cap at 20 000; `max_file_bytes`
  enforced server-side; HTTP schema caps list/body sizes (including typed `docs[]`).
- **Secrets floor:** client never pushes `.env*`, key/pem material, or common
  credential filenames into the graph.
- **No body logging:** CLI/HTTP must not print full file sources.
- **Cloud LLM:** local TTY consent before non-private embed/docs routes (existing gate).
- Payload stays on the private LAN / existing HTTPS trust boundary.

## Verification

- Unit: path traversal / absolute paths rejected; oversize soft-fails; secrets skipped client-side.
- Unit: pushed ingest without a disk tree; prune only with `inventory_complete`; hash skip.
- Unit: HTTP bearer auth; typed docs push; auto discovery + multi-batch.
- Live: client without a server checkout updates the graph over HTTPS content-push.

## Related Documents

- [Client sync auto discovery and inventory-complete prune](./2026-08-10-client-sync-auto-discovery-inventory-design.md)
- [Client content-push sync progress stream](./2026-08-05-client-push-progress-stream-design.md)
- [Server CLI tracking for live client sync jobs](./2026-08-10-server-client-sync-jobs-cli-design.md)

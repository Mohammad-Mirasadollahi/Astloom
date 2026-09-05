# MCP Gateway Service

Path: `backend/services/mcp-gateway-service`

## Purpose

Exposes Astloom capabilities to IDE clients (Cursor) over the Model Context Protocol (MCP). Tool surfaces are defined by the active **Usage Profile**. Tool calls are dispatched to **in-process** core-data, memory, code-graph, docs-sync, and common-context (Agent Workspace Guidance) service slices.

## Cursor tools (`programming-cursor-mcp`)

| Tool | Mode | Purpose |
|------|------|---------|
| `astloom_ping` | read | Connectivity + profile metadata |
| `astloom_get_effective_profile` | read | Effective Usage Profile |
| `astloom_memory_retrieve` | read | Retrieve memory for a query |
| `astloom_context_compress` | write | Native compress bulky JSON/text; store original under TTL handle |
| `astloom_context_retrieve` | read | Retrieve original payload by compress handle (same scope) |
| `astloom_context_stats` | read | Process-local compression counters (chars saved / pct) |
| `astloom_code_graph_search` | read | Semantic search over the code-knowledge graph |
| `astloom_code_graph_get_symbol` | read | Fetch one symbol by id or qualified_name |
| `astloom_code_graph_neighbors` | read | **Structural** neighbors (CALLS/IMPORTS/…); `reference_kind=structural` |
| `astloom_code_graph_ide_references` | read | **IDE-semantic** find-references via local LSP (`reference_kind=ide_semantic`) |
| `astloom_code_graph_ide_definition` | read | **IDE-semantic** go-to-definition via local LSP |
| `astloom_code_graph_ide_rename` | write | **IDE-semantic** rename + AST `reconcile_after_edit` (never dual-writes CODE_REL) |
| `astloom_code_graph_reconcile_after_edit` | write | Mark edited paths pending; optional AST re-ingest |
| `astloom_code_graph_impact` | read | Directed multi-hop impact / blast radius |
| `astloom_code_graph_callers` | read | Ranked inbound callers (fan-in) |
| `astloom_code_graph_community` | read | Community membership for one symbol |
| `astloom_code_graph_call_path` | read | Compact outbound call-path pack |
| `astloom_code_graph_unused_candidates` | read | Scored dead-code candidates (`score`/`evidence`/`finding_kind`; includes `unwired_shared_package` with `recommendation` wire\|keep_public\|retire; default `task_neighborhood`; optional `path_prefix` + `repo_root`; anchors required except `project_scan`; never deletes) |
| `astloom_code_graph_explore` | read | **Primary** surgical context: seeds + call path + budgeted source |
| `astloom_code_graph_detect_changes` | read | Risk-scored review context for changed files |
| `astloom_code_graph_architecture_overview` | read | Communities, hubs, bridges, gaps, surprises |
| `astloom_code_graph_path` | read | Shortest path between two symbols |
| `astloom_code_graph_hybrid_search` | read | RRF hybrid lexical + semantic search |
| `astloom_code_graph_freshness` | read | Pending-sync / stale banners |
| `astloom_code_graph_sync` | write | **Preferred:** auto full vs incremental repo sync; under MCP use small `max_files` (see tool-budget runbook) |
| `astloom_code_graph_purge` | write | Wipe project graph (`confirm=true`); then sync |
| `astloom_code_graph_generation_context` | read | Generation context pack for coding agents (includes `hybrid_documentation`) |
| `astloom_code_graph_ingest_file` | write | Index one source file (power users) |
| `astloom_code_graph_ingest_repo` | write | Walk a repo root (prefer `sync`) |
| `astloom_code_graph_language_profile` | read | Polyglot language stats for the project graph |
| `astloom_create_task` | write | Create a Task |
| `astloom_write` | write | Unified write: `memory` / `task` / `activity` / `decision` |
| `astloom_docs_drift_check` | read | Docs drift for a symbol |
| `astloom_docs_stale_candidates` | read | Scored stale-documentation candidates (`orphan_doc`/`ghost_link`/`stale_anchor`/`superseded_retrieval_risk`/`wiki_orphan`/`duplicate_authority`; optional `coverage_gap`; never deletes Markdown) |
| `astloom_docs_write` | write | Docs workflow: `validate` / `note` / `draft` / `index` |
| `astloom_docs_status` | read | Coverage + missing docs |
| `astloom_docs_catalog` | read | Cached frontmatter catalog (tags/lanes) for retrieval narrowing |
| `astloom_docs_authoring_standards` | read | Full-tier documentation authoring law |
| `astloom_quality_audit` | read | Docs+code quality findings (`must_remediate`; MCP soft budget + project scope; optional Task create/reconcile) |
| `astloom_guidance_resolve` | read | Resolve AGENTS entry, always-on rules, skill catalog (seeds MCP-first pack) |
| `astloom_guidance_list_skills` | read | List skill catalog descriptors |
| `astloom_guidance_get_skill` | read | Fetch one skill body by id or name |

## Layout

| Module | Role |
|--------|------|
| `store_factory.py` | memory vs postgres store selection |
| `backends/platform.py` | `PlatformBackends` facade + seeds |
| `backends/dispatch.py` | capability router (`maps_to`) |
| `backends/writes.py` | `platform.write` (memory/task/activity/decision) |
| `backends/docs.py` | docs-sync write/status/drift helpers |
| `backends/context.py` | native context compress/retrieve/stats (doc 54) |
| `backends/guidance.py` | Agent Workspace Guidance resolve/list/get-skill |
| `backends/_paths.py` | PYTHONPATH bootstrap for in-process services |
| `server.py` | MCP JSON-RPC stdio surface |

| Mode | When | Behavior |
|------|------|----------|
| `memory` | Default, or `ASTLOOM_MCP_STORE_MODE=memory` | In-memory stores (tests / ephemeral IDE sessions) |
| `postgres` | `ASTLOOM_DATABASE_URL` set, or `ASTLOOM_MCP_STORE_MODE=postgres` | Shared PostgreSQL schemas with the platform services |

**Code-graph backend** is selected separately via `ASTLOOM_MCP_GRAPH_MODE` (or auto):

| Graph mode | When | Behavior |
|------------|------|----------|
| `neo4j` | `ASTLOOM_MCP_GRAPH_MODE=neo4j`, or auto when `ASTLOOM_NEO4J_PASSWORD` is set and store is neo4j | Same composition root as `code-graph-service` (`bootstrap.build_service`) — **no toy seed** |
| `postgres` | Explicit or `ASTLOOM_CODE_GRAPH_STORE=postgres` | Postgres structural store |
| `memory` | Tests / default without Neo4j password; **also used as fallback** if Neo4j/Postgres are configured but unreachable at gateway start (ERROR logged; MCP stays up) | In-memory graph + optional demo seed |

Responses include `store_mode` and `graph_mode`.

## HTTP tool budgets (Cursor / concurrent agents)

| Env | Default | Meaning |
| --- | --- | --- |
| `ASTLOOM_MCP_TOOL_TIMEOUT_SECONDS` | `25` | Hard JSON-RPC timeout; `-32001` names the tool when known |
| `ASTLOOM_MCP_QUALITY_AUDIT_BUDGET_SECONDS` | `18` (capped to tool timeout − 6s) | Soft collect deadline for `astloom_quality_audit` |

**`astloom_code_graph_sync`:** Prefer small `max_files` under MCP. When `max_files` is below the ingest default, the gateway sets `embedding_refresh_mode=off` if unset (`max_files < 50`), and code-graph uses FILE-only lookups + empty shared resolution indexes so Neo4j full-graph dumps cannot burn the hard timeout. Re-run while `truncated=true`.

**`astloom_quality_audit`:** Uses the MCP project graph scope (not CLI defaults), runs code inventory before docs under the soft deadline, caps discovery under deadline, and returns `degraded` / `truncated_phases` only when the soft budget is exhausted.

Normative runbook: `docs/07-code-knowledge-graph/83-mcp-tool-budget-and-small-batch-sync.md`.

Per-service URL overrides (optional):

- `ASTLOOM_CORE_DATA_DATABASE_URL`
- `ASTLOOM_MEMORY_DATABASE_URL`
- `ASTLOOM_CODE_GRAPH_DATABASE_URL`
- `ASTLOOM_DOCS_SYNC_DATABASE_URL`

Neo4j (when graph_mode=neo4j):

- `ASTLOOM_NEO4J_URI` / `USER` / `PASSWORD` / `DATABASE`
- `ASTLOOM_CODE_GRAPH_STORE=neo4j`
- `ASTLOOM_MCP_GRAPH_SEED=false` is implied for Neo4j (toy seed never written)

## Prerequisites

```bash
bash scripts/ensure-venv.sh
```

Apply service migrations (Compose profile `core` / `all` mounts them). For Cursor + Postgres:

```bash
export ASTLOOM_DATABASE_URL=postgresql://astloom:secret@127.0.0.1:32232/astloom
export ASTLOOM_MCP_STORE_MODE=postgres
# Real Neo4j code graph (same env as code-graph-service):
export ASTLOOM_NEO4J_PASSWORD=secret
export ASTLOOM_NEO4J_URI=bolt://127.0.0.1:32287
# optional force:
# export ASTLOOM_MCP_GRAPH_MODE=neo4j
```

## Run (stdio for Cursor)

```bash
export ASTLOOM_USAGE_PROFILE=programming-cursor-mcp
export ASTLOOM_TENANT_ID=t
export ASTLOOM_WORKSPACE_ID=w
export ASTLOOM_PROJECT_ID=p
PYTHONPATH=backend/services/mcp-gateway-service/src:backend/packages:backend/services/core-data-service/src:backend/services/memory-service/src:backend/services/code-graph-service/src:backend/services/docs-sync-service/src \
  .venv/bin/python -m mcp_gateway_service
```

`astloom cursor export` forwards `ASTLOOM_DATABASE_URL` / `ASTLOOM_MCP_STORE_MODE` into the generated MCP env when present.

## Run (HTTP — Phase B, concurrent agents)

```bash
export ASTLOOM_MCP_TOKEN_SECRET='long-random-secret'
# Prefer operator path: astloom service start (TLS when certs are present).
export ASTLOOM_MCP_HTTP_PUBLIC_URL='https://127.0.0.1:32500'
export ASTLOOM_MCP_STORE_MODE=memory   # or postgres when Compose is up
astloom mcp serve-http --host 0.0.0.0 --port 32500
# POST /mcp with Authorization: Bearer <scoped-or-shared-token>
# Local self-signed: live tests default ASTLOOM_MCP_HTTP_TLS_VERIFY off
```

Or: `python -m mcp_gateway_service --http --port 32500`

## Tests

```bash
PYTHONPATH=backend/services/mcp-gateway-service/src:backend/packages \
  .venv/bin/python -m pytest tests/backend/services/mcp-gateway-service -q

# Live HTTP matrix (gateway up on :32500):
.venv/bin/python -m pytest tests/live/mcp-gateway-service/ -m live -v
```

Design: `docs/08-software-engineering-architecture/35-usage-profile-and-cursor-mcp-onboarding.md`  
Tool budgets / small-batch sync: `docs/07-code-knowledge-graph/83-mcp-tool-budget-and-small-batch-sync.md`  
One-command connect: `docs/08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding.md`

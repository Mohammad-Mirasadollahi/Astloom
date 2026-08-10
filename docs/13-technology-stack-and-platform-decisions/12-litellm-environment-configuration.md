---
doc_id: as.doc.stack.litellm-environment-configuration
title: 12 - LiteLLM Environment Configuration
doc_type: standard
status: active
schema_version: '1.0'
owner: ai-platform-lead
summary: 'Operator and engineer reference for every Astloom LiteLLM and related code-graph
  store environment variable: purpose, defaults, change impact, and worked examples.'
tags:
- litellm
- configuration
- environment
- llm
- code-graph
- operators
phase: 13-technology-stack-and-platform-decisions
canonical_path: docs/13-technology-stack-and-platform-decisions/12-litellm-environment-configuration.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
related_docs:
- as.doc.stack.litellm-llm-gateway
- as.doc.ckg.rpm-session-parallel-sync-feature-spec
- as.doc.ckg.sync-cpu-budget-and-store-concurrency-lld
- as.doc.ckg.postgres-connection-pool-and-capacity-lld
- as.doc.stack.turbovec-ann-acceleration
- as.doc.stack.turbovec-for-rag
doc_version: 1.3.1
updated_at: 2026-08-10
---

# 12 - LiteLLM Environment Configuration

## Purpose

This document is the normative **configuration contract** for Astloom LiteLLM settings and the related code-graph store variables that operators copy from the repository-root `.env.example` into `.env`.

It explains, for each variable:

- what it controls,
- the default when unset,
- what happens when you change it,
- a concrete example.

## Professional Audience

Platform operators, backend engineers wiring `code-graph-service` or other consumers of `backend/packages/llm_gateway`, and security reviewers validating secret handling.

## Goals

- Make every env knob discoverable without reading source.
- Prevent silent misconfiguration (wrong Base URL, empty password, embedding dims surprises).
- Align with the LiteLLM gateway ADR and ModelRoutingProfile specification.

## Non-Goals

- Choosing which commercial vendor is “best.”
- Documenting IDE-side model settings (Cursor, etc.).
- Replacing Compose / port-profile ownership of infrastructure ports.

## Configuration Source Of Truth

| Artifact | Role |
| --- | --- |
| `.env.example` → `.env` (repo root) | **Single** operator template: scope, Neo4j, LiteLLM, embeddings, optional ANN |
| This document | Behavioral contract + examples |
| `09-litellm-llm-gateway.md` | Why LiteLLM is mandatory |
| `10-model-routing-profiles-with-litellm.md` | Task/risk → model alias rules |
| `08-turbovec-ann-acceleration-integration.md` / `11-turbovec-for-rag.md` | Optional Stage-2 Turbovec ANN |
| `backend/packages/llm_gateway/` | Runtime implementation |

`install.sh` / `astloom init` create root `.env` from `.env.example` when missing. CLI `load_dotenv_files()` loads root `.env` automatically.

Inspect live public settings (no secrets):

```bash
astloom llm test
PYTHONPATH=backend/packages .venv/bin/python -m llm_gateway config
## or GET /api/v1/llm/config on code-graph-service
```

List providers and `configured` flags:

```bash
PYTHONPATH=backend/packages .venv/bin/python -m llm_gateway providers
## or GET /api/v1/llm/providers
```

---

## Service And Structural Store Variables

These are not LiteLLM knobs, but they appear in the same root `.env.example` and affect whether the HTTP service, embeddings/outbox, and Neo4j work together.

### `ASTLOOM_CODE_GRAPH_PORT`

| | |
| --- | --- |
| **Purpose** | HTTP listen port for `code-graph-service`. |
| **Default** | `32140` (port profile) |
| **If you change it** | Clients, Compose health checks, and local scripts must target the new port. Binding fails if the port is already in use. |

**Example:**

```bash
ASTLOOM_CODE_GRAPH_PORT=32140
## curl http://127.0.0.1:32140/api/v1/llm/config
```

### `ASTLOOM_CODE_GRAPH_STORE`

| | |
| --- | --- |
| **Purpose** | Selects structural graph persistence. |
| **Allowed** | `neo4j`, `postgres` |
| **Default** | `neo4j` |
| **If you change it** | `postgres` → rollback/parity path; Neo4j unused for symbols/edges. `neo4j` → requires Neo4j credentials. Invalid value → startup error. |

**Example:** keep Neo4j in staging, roll back one environment:

```bash
ASTLOOM_CODE_GRAPH_STORE=postgres
ASTLOOM_CODE_GRAPH_DATABASE_URL=postgresql://astloom:secret@127.0.0.1:32232/astloom
```

### `ASTLOOM_CODE_GRAPH_DATABASE_URL`

| | |
| --- | --- |
| **Purpose** | PostgreSQL URL for structural postgres store and/or pgvector + outbox mirror beside Neo4j. |
| **Default** | empty (must be set for `postgres` store; recommended for `neo4j`) |
| **Fallback** | When empty, Settings uses `ASTLOOM_DATABASE_URL` (shared MCP/CLI/platform URL). Compose and `local_mcp` also copy the shared URL into this variable when unset. |
| **If you change it** | Wrong URL → connection errors on ingest index/outbox. Empty **both** this and `ASTLOOM_DATABASE_URL` with Neo4j → no `embedding_index`, no `symbol_embeddings` upsert, no mirror into `code_graph.outbox` (heal/sync report `embedding_index_unavailable`; hybrid may return BM25-only with `semantic_error`). |

**Example:** Neo4j graph + Postgres side tables:

```bash
ASTLOOM_CODE_GRAPH_STORE=neo4j
ASTLOOM_CODE_GRAPH_DATABASE_URL=postgresql://astloom:secret@127.0.0.1:32232/astloom
```

**Example:** Cursor MCP with only the shared URL (Settings fallback):

```bash
ASTLOOM_DATABASE_URL=postgresql://astloom:secret@127.0.0.1:32232/astloom
# ASTLOOM_CODE_GRAPH_DATABASE_URL may be omitted; pgvector still attaches
```

### `ASTLOOM_NEO4J_URI` / `USER` / `PASSWORD` / `DATABASE`

| Variable | Purpose | Default | If you change it |
| --- | --- | --- | --- |
| `ASTLOOM_NEO4J_URI` | Bolt endpoint | `bolt://127.0.0.1:32287` | Wrong port → live Neo4j tests/ingest fail |
| `ASTLOOM_NEO4J_USER` | Auth user | `neo4j` | Must match Compose auth |
| `ASTLOOM_NEO4J_PASSWORD` | Auth secret | _(required)_ | Empty with store=neo4j → startup `RuntimeError` |
| `ASTLOOM_NEO4J_DATABASE` | DB name | `neo4j` | Multi-DB installs must match |

**Example:**

```bash
ASTLOOM_NEO4J_URI=bolt://127.0.0.1:32287
ASTLOOM_NEO4J_USER=neo4j
ASTLOOM_NEO4J_PASSWORD=astloom-local-dev-secret
ASTLOOM_NEO4J_DATABASE=neo4j
```

### `ASTLOOM_NEO4J_GDS_ENABLED`

| | |
| --- | --- |
| **Purpose** | Opt-in to Neo4j Graph Data Science **Community** procedures for optional `gds.degree` ranking. |
| **Default** | `true` (on) |
| **If you set `false`** | Code-graph never calls GDS; degree ranking always uses Cypher. Communities (Leiden/Louvain) are unaffected (never used GDS). |
| **License note** | GDS Community is free without an Enterprise key; concurrency is limited to **4 CPU cores**. See `docs/07-code-knowledge-graph/32-intentional-fallbacks-and-neo4j-plugin-licensing.md`. |

**Example:**

```bash
ASTLOOM_NEO4J_GDS_ENABLED=true
```

### `ASTLOOM_NEO4J_GDS_CONCURRENCY`

| | |
| --- | --- |
| **Purpose** | Thread count passed to `gds.degree.stream` when GDS is enabled. |
| **Default** | `4` |
| **Hard max** | `4` (Neo4j GDS Community Edition limit — values above 4 are clamped) |
| **If you change it** | `1`–`4` only. Does not unlock Enterprise features. |

**Example:**

```bash
ASTLOOM_NEO4J_GDS_CONCURRENCY=4
```

### `ASTLOOM_NEO4J_IMAGE`

| | |
| --- | --- |
| **Purpose** | Compose image tag for the Neo4j container (`compose.yaml`). Not read by the Python service. |
| **Default** | `neo4j:5.26-community` (Compose default) |
| **If you change it** | Recreate the Neo4j container to pick up the new image. Patch-pin in production (e.g. `neo4j:5.26.4-community`). Invalid tag → Compose pull/start fails; Bolt URI becomes unreachable. |

**Example:**

```bash
ASTLOOM_NEO4J_IMAGE=neo4j:5.26.4-community
## docker compose up -d neo4j  # after setting the env for Compose
```

---

## LiteLLM Gateway Core

### `ASTLOOM_LITELLM_ENABLED`

| | |
| --- | --- |
| **Purpose** | Master switch for the LiteLLM adapter. |
| **Default** | `true` |
| **If you set `false`** | `complete` / `embed` raise; doc generation and embeddings use heuristic / local stub only. Providers API still lists catalog. |

**Example — offline CI without models:**

```bash
ASTLOOM_LITELLM_ENABLED=false
```

### Auto Base URL: `ASTLOOM_LITELLM_HOST` + `ASTLOOM_LITELLM_PORT`

| | |
| --- | --- |
| **Purpose** | Build auto Base URL `http://{HOST}:{PORT}` when no override is set. |
| **Defaults** | Host `127.0.0.1`, Port `32400` (port profile; not upstream LiteLLM `4000`) |
| **If you change them** | All LiteLLM SDK calls that rely on auto Base URL target the new host/port. Mismatch with the real proxy → connection refused / wrong service. |

**Example:**

```bash
ASTLOOM_LITELLM_HOST=127.0.0.1
ASTLOOM_LITELLM_PORT=32400
## → api_base auto = http://127.0.0.1:32400
```

### `ASTLOOM_LITELLM_API_BASE` (override)

| | |
| --- | --- |
| **Purpose** | Explicit Base URL; wins over auto host/port. |
| **Default** | empty (auto) |
| **Alias** | `LITELLM_API_BASE` used only if `ASTLOOM_LITELLM_API_BASE` is empty |
| **If you set it** | `api_base_is_auto=false`; host/port ignored for Base URL. Trailing `/` is stripped. |
| **If you clear it** | Returns to auto Base URL. |

**Example — point at a remote proxy:**

```bash
ASTLOOM_LITELLM_API_BASE=http://llm-proxy.internal:4100
## Changing only HOST/PORT has no effect while this is set.
```

### `ASTLOOM_LITELLM_API_KEY`

| | |
| --- | --- |
| **Purpose** | Credential for proxy or OpenAI-compatible endpoint. |
| **Default** | empty |
| **Fallback order** | `ASTLOOM_LITELLM_API_KEY` → `LITELLM_API_KEY` → `OPENAI_API_KEY` |
| **If empty** | Local Ollama may still work; cloud providers typically return 401. |
| **If set** | Sent on every LiteLLM completion/embedding call. Never exposed in `/api/v1/llm/config`. |

### `ASTLOOM_LITELLM_DEFAULT_MODEL`

| | |
| --- | --- |
| **Purpose** | Default LiteLLM model alias when task-specific `MODEL_*` is empty. |
| **Default** | empty in settings code; `.env.example` suggests `ollama/qwen2.5-coder` |
| **If empty** | Routes for docs/embed have no primary model → stub/heuristic (`allow_stub`). |
| **If set** | Used for docs (when docs enabled), complete CLI, and embed (when embeddings enabled) unless overridden. |

**Example:**

```bash
ASTLOOM_LITELLM_DEFAULT_MODEL=gpt-4o-mini
## All tasks without MODEL_* override now call gpt-4o-mini via LiteLLM.
```

### `ASTLOOM_LITELLM_TIMEOUT_SECONDS`

| | |
| --- | --- |
| **Purpose** | Per-call timeout (seconds) passed to LiteLLM. |
| **Default** | `180` |
| **If lowered (e.g. 30)** | Hung providers fail faster; long doc generations may abort. |
| **If raised (e.g. 600)** | Slow models finish more often; workers can block longer under load. |
| **If ≤ 0** | Startup validation error. |

### `ASTLOOM_LITELLM_NUM_RETRIES`

| | |
| --- | --- |
| **Purpose** | LiteLLM `num_retries` on transient failures. |
| **Default** | `3` |
| **If `0`** | No SDK retries; first failure surfaces immediately (RPM limiter still applies). |
| **If higher (e.g. 8)** | More resilience on flaky networks; multiplies provider load and latency. |
| **If &lt; 0** | Startup validation error. |

### `ASTLOOM_LITELLM_RPM`

| | |
| --- | --- |
| **Purpose** | Client-side requests-per-minute limit (sliding 60s window) before each `complete`/`embed`. |
| **Default** | `30` |
| **If lowered (e.g. 5)** | Throughput drops; calls wait until a slot frees. Protects quotas. |
| **If raised (e.g. 120)** | Higher burst rate; may trigger provider 429s despite retries. |
| **If &lt; 1** | Startup validation error. |

**Current runtime:** `RpmSessionGate` records **start** timestamps in a sliding
60s window **and** tracks in-flight sessions until `release` (end). Launching a
call waits until both `starts_in_window < rpm` and `inflight < inflight_cap`
(v1: inflight_cap = rpm). See
[`37`–`40` RPM-session parallel sync](../07-code-knowledge-graph/37-rpm-session-parallel-sync-feature-specification.md).
Companion knob: `ASTLOOM_SYNC_CPU_PERCENT` (preferred) or
`ASTLOOM_SYNC_MAX_FILE_WORKERS` for parse/hash/embed parallelism.
Neo4j store traffic is **bounded** (not single-flight) via `LockedStore`
`store_concurrency` (typically `max(2, min(8, workers))`). Postgres adapters use
**checkout/checkin** pools (auto-sized from server capacity; see
[`79` Postgres pool LLD](../07-code-knowledge-graph/79-postgres-connection-pool-and-capacity-lld.md))
— they do not keep one idle client per file worker forever. Torch/OMP threads are
pinned to 1 when limits are applied so workers do not multiply into host RAM
exhaustion. Details: [`50` sync CPU budget LLD](../07-code-knowledge-graph/50-sync-cpu-budget-and-store-concurrency-lld.md).

**Example — strict local quota:**

```bash
ASTLOOM_LITELLM_RPM=10
## After 10 starts in ~60s, the next acquire blocks until the oldest start ages out
## or an in-flight session ends (whichever frees capacity first).
## Sync file workers auto-cap at min(cpu_count, 10) unless CPU percent / workers override.
```

### `ASTLOOM_SYNC_CPU_PERCENT`

| | |
| --- | --- |
| **Purpose** | Operator CPU budget for `astloom sync` / `ingest_repo`. |
| **Default** | **auto** |
| **If `auto` / unset** | Workers = `min(cpu_count, ASTLOOM_LITELLM_RPM)`; local-embed concurrency capped at 4. |
| **If `1`–`100`** | Workers and local-embed concurrency ≈ that percent of `cpu_count`; Torch/OMP = 1; Neo4j `store_concurrency` = `max(2, min(8, workers))`. |
| **CLI** | `astloom sync --cpu-percent 25` overrides env for one run. |
| **Design** | [`50` sync CPU budget LLD](../07-code-knowledge-graph/50-sync-cpu-budget-and-store-concurrency-lld.md). |

### `ASTLOOM_SYNC_MAX_FILE_WORKERS`

| | |
| --- | --- |
| **Purpose** | Advanced override: exact parallel file worker count. |
| **Default** | **auto** — see `ASTLOOM_SYNC_CPU_PERCENT` |
| **If unset / `auto`** | Falls through to CPU percent, then `min(cpu_count, ASTLOOM_LITELLM_RPM)`. |
| **If set to a positive int** | Wins over `ASTLOOM_SYNC_CPU_PERCENT` (still ≥ 1). |
| **If invalid / `0`** | Falls back to auto / CPU percent. |

Postgres pool knobs (`ASTLOOM_PG_POOL_MAX`, `ASTLOOM_PG_POOL_SHARE`,
`ASTLOOM_PG_CAPACITY_RETRIES`) live with the pool LLD — see
[`79` Postgres connection pool and capacity](../07-code-knowledge-graph/79-postgres-connection-pool-and-capacity-lld.md).

### `ASTLOOM_LITELLM_DROP_PARAMS`

| | |
| --- | --- |
| **Purpose** | Sets `litellm.drop_params`. |
| **Default** | `true` |
| **If `true`** | Unsupported kwargs dropped; fewer cross-provider errors. |
| **If `false`** | Stricter; e.g. `response_format` on a model that rejects it can fail the call. |

### `ASTLOOM_LITELLM_DEBUG`

| | |
| --- | --- |
| **Purpose** | Turns on LiteLLM SDK debug logging (`litellm._turn_on_debug()`). |
| **Default** | `false` |
| **If `true`** | First `complete`/`embed` call enables verbose LiteLLM traces so provider errors show root cause (request path, HTTP status, response body excerpts). Noisy — use while diagnosing sync or gateway failures. |
| **If `false`** | Quiet LiteLLM logging (production default). |

```bash
ASTLOOM_LITELLM_DEBUG=true
## then re-run: astloom sync
```

### `ASTLOOM_LITELLM_REASONING_ENABLED`

| | |
| --- | --- |
| **Purpose** | When `true`, completions send OpenRouter-style `extra_body.reasoning` = `{"enabled": true}` (and optional effort). |
| **Default** | `false` |
| **If `true`** | Required for some models (e.g. `openai/gpt-oss-20b:free` on OpenRouter). Payload is passed via LiteLLM `extra_body` so `drop_params` does not strip it. |
| **If `false`** | No `reasoning` object — safer for models that reject unknown fields. |
| **Per-call override** | `CompletionRequest.reasoning_enabled`, CLI `--reasoning` / `--no-reasoning`, API `reasoning_enabled`. |

**Example — OpenRouter gpt-oss:**

```bash
ASTLOOM_LITELLM_API_BASE=https://openrouter.ai/api/v1
ASTLOOM_LITELLM_DEFAULT_MODEL=openai/gpt-oss-20b:free
ASTLOOM_LITELLM_REASONING_ENABLED=true
## Equivalent HTTP body fragment:
## "reasoning": { "enabled": true }
```

### `ASTLOOM_LITELLM_REASONING_EFFORT`

| | |
| --- | --- |
| **Purpose** | Optional provider-specific effort when reasoning is enabled (`low` / `medium` / `high` / …). |
| **Default** | empty (only `{"enabled": true}`) |
| **If set** | Becomes `"reasoning": {"enabled": true, "effort": "<value>"}`. |
| **If empty** | Effort omitted. Leave empty unless the model docs require it. |

---

## Related Documents

- Continued in `docs/13-technology-stack-and-platform-decisions/12-litellm-environment-configuration-continued.md`

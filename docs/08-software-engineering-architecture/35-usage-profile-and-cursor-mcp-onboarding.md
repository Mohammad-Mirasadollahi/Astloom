---
doc_id: as.doc.sea.usage-profile-and-cursor-mcp-onboarding
title: Usage Profile and Cursor MCP Onboarding
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: A **Usage Profile** lets a person or organization shape Astloom for a concrete
  job (for example software engineering with Cursor) without forking the platform.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/35-usage-profile-and-cursor-mcp-onboarding.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.2.1
updated_at: 2026-08-10
---

# Usage Profile and Cursor MCP Onboarding

## Purpose

A **Usage Profile** lets a person or organization shape Astloom for a concrete job (for example software engineering with Cursor) without forking the platform. It composes existing knobs—domain pack, feature profile, connectors, and exposed MCP tools—into one named, versioned configuration that can be activated on a project and materialized into a Cursor MCP connection.

This document is the design home for Usage Profiles. It complements:

- `26-domain-customization-and-feature-control.md` (domain packs and feature profiles)
- `20-agent-and-resource-connectivity-automation.md` (connectors and connection profiles)
- `05-interoperability-ecosystem/08-agent-communication-language-and-runtime-sdk.md` (MCP as a translator bridge)

## Vocabulary

| Term | Meaning |
|------|---------|
| Usage Profile | Named composition of packs, features, connectors, and MCP tool surface for a use case |
| Feature profile | Which capabilities are enabled/hidden/approval-gated (existing concept) |
| Domain pack | Domain-oriented defaults (existing concept) |
| Connection profile | Generated client config for one connector (for example Cursor MCP) |
| MCP gateway | Astloom process that speaks MCP to IDE clients and maps tools to platform APIs |

Usage Profiles are **not** Cursor workspace rule packs under `.cursor/rules/`. Those configure the Astloom development IDE only.

**Agent Workspace Guidance** (product AGENTS entry, always-on rules, and skills for customer projects) is specified in [`../15-agent-workspace-guidance/00-index.md`](../15-agent-workspace-guidance/00-index.md). Connect-time delivery is MCP-primary via tools such as `astloom_guidance_resolve`, `astloom_guidance_list_skills`, and `astloom_guidance_get_skill` when a Usage Profile allow-lists them. The MCP-first seed rule and capability skills that tell Cursor (and other coding agents) to call Astloom tools for memory, graph, docs-sync, writes, and tasks are normative in [`../15-agent-workspace-guidance/06-mcp-first-agent-skills-and-rules.md`](../15-agent-workspace-guidance/06-mcp-first-agent-skills-and-rules.md). This document owns Usage Profile composition and MCP onboarding; phase 15 owns guidance artifact contracts, resolve semantics, and that seed pack. Implementation of guidance tools and seed materialization is follow-on work after the phase 15 design docs.

## Goals

- Organizations can pick a profile such as `programming-cursor-mcp` and attach it to a project.
- Cursor can connect through MCP using a generated `mcp.json` fragment.
- Only tools allowed by the active Usage Profile are advertised on `tools/list`.
- Activation is scoped (tenant / workspace / project) and auditable.

## Non-goals

- Replacing Universal Agent JSON or the Phase 5 broker.
- Shipping a full Neo4j/MCP marketplace.
- Embedding Cursor-specific product logic inside every backend service.

## Schema (machine-readable)

Catalog path: `backend/configs/usage-profiles/<profile_id>.json`

Required fields:

| Field | Type | Description |
|-------|------|-------------|
| `profile_id` | string | Stable id (filename stem) |
| `version` | string | Semver-like version |
| `title` | string | Human title |
| `audience` | string | e.g. `software-engineering` |
| `domain_pack` | string | Default domain pack id |
| `feature_profile` | string | Default feature profile id |
| `connectors` | array | Connector specs (`type`, `id`, `transport`, …) |
| `mcp` | object | MCP surface (`server_name`, `tools[]`) |
| `defaults` | object | Optional scope defaults |

Each MCP tool entry:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | MCP tool name |
| `description` | string | Shown to the IDE |
| `maps_to` | string | Astloom capability key (e.g. `memory.retrieve`) |
| `input_schema` | object | JSON Schema for tool arguments |

## Runtime ownership

| Concern | Owner |
|---------|--------|
| Catalog load/validate | `backend/packages/usage_profile/` |
| Activate on project, resolve effective profile, export Cursor config | `project-profile-service` |
| MCP stdio/JSON-RPC server and tool dispatch | `mcp-gateway-service` |
| Generic IDE/broker connectors | `adapter-service` (unchanged contract; Usage Profile may reference it) |

## Activation flow

```text
1. Operator selects usage_profile_id (e.g. programming-cursor-mcp)
2. project-profile-service stores usage_profile on the project
3. Effective profile = catalog entry + project overrides
4. Export Cursor MCP connection profile (command + env)
5. Cursor starts mcp-gateway stdio server with scope env
6. tools/list returns only profile.mcp.tools
7. tools/call maps to Astloom capability handlers
```

## Cursor onboarding (operator steps)

1. Activate Usage Profile on the project via API (`PATCH` / activate endpoint).
2. Download or copy the generated MCP connection fragment.
3. Merge into Cursor MCP settings (user or project `mcp.json`).
4. Restart MCP / reload window.
5. Verify tools appear and a smoke `tools/call` succeeds.

### ≤30 minute checklist (`programming-cursor-mcp`, backlog 34 C2)

Stable env (export or Cursor `mcpServers.env`):

| Variable | Purpose |
| --- | --- |
| `ASTLOOM_ROOT` | Repo root |
| `ASTLOOM_USAGE_PROFILE` | `programming-cursor-mcp` |
| `ASTLOOM_TENANT_ID` / `ASTLOOM_WORKSPACE_ID` / `ASTLOOM_PROJECT_ID` | Scope |
| `PYTHONPATH` | Absolute paths as written by `astloom cursor export` |

Timed path (new machine):

| Minute | Step |
| --- | --- |
| 0–10 | `bash scripts/ensure-venv.sh` · `astloom doctor` · `astloom path install` |
| 10–15 | `astloom project register/activate` with `programming-cursor-mcp` |
| 15–20 | `astloom cursor export --out …` · merge into Cursor MCP · reload |
| 20–25 | Ingest sample (`astloom graph smoke` or probe) |
| 25–30 | Call **PRIMARY** tool `astloom_code_graph_explore` (prefer before wide Read/Grep); confirm pack sections |

**Exit:** explore returns sections for a known query (e.g. login) within 30 minutes of a clean checkout.

### Reload After Host Or Heuristic Changes

Restarting Astloom services (`astloom service restart`) updates the **host** stack (Neo4j, MCP HTTP, workers). Cursor’s **in-process** MCP session may still serve cached tool implementations or stale overview heuristics until you reload MCP in the IDE (MCP settings → Reload, or reload the window).

Required after:

- Deploying code-graph analytics / `architecture_overview` heuristic changes
- Changing Usage Profile tool allow-lists that are already loaded in an open session
- Materializing or rotating MCP connection env that Cursor already spawned

See also `docs/07-code-knowledge-graph/55-structural-isolation-and-architecture-overview-residuals.md`.

Example generated fragment (shape):

```json
{
  "mcpServers": {
    "Astloom-Programming": {
      "command": "python",
      "args": ["-m", "mcp_gateway_service"],
      "env": {
        "ASTLOOM_USAGE_PROFILE": "programming-cursor-mcp",
        "ASTLOOM_TENANT_ID": "<tenant>",
        "ASTLOOM_WORKSPACE_ID": "<workspace>",
        "ASTLOOM_PROJECT_ID": "<project>"
      }
    }
  }
}
```

## Security

- Scope headers / env must identify tenant, workspace, and project.
- Tools inherit feature-profile gates; disabled features are omitted from `tools/list`.
- Do not put secrets in Usage Profile JSON; inject via environment or secret managers.
- MCP gateway must refuse tools not listed in the active profile.

## MCP env for semantic / embeddings

Project `.cursor/mcp.json` is often gitignored. For Neo4j + pgvector in the MCP process:

| Env | Required for |
| --- | --- |
| Neo4j URI / user / password | Graph store when `ASTLOOM_CODE_GRAPH_STORE=neo4j` |
| `ASTLOOM_CODE_GRAPH_DATABASE_URL` **or** `ASTLOOM_DATABASE_URL` | pgvector SoR (`symbol_embeddings`), outbox mirror, heal/sync embedding refresh |

Code-graph Settings prefer `ASTLOOM_CODE_GRAPH_DATABASE_URL` and fall back to `ASTLOOM_DATABASE_URL`. If both are missing, hybrid search can look “empty” on the semantic channel (`semantic_error` / `embedding_index_unavailable`) even when Neo4j has symbols. Heal/sync contract: [77 - Sync Embedding Heal Operator Runbook](../07-code-knowledge-graph/77-sync-embedding-heal-operator-runbook.md).

## Acceptance criteria

- Catalog validates required fields for every shipped profile.
- A project can activate `programming-cursor-mcp`.
- Effective profile resolution returns domain pack, feature profile, connectors, and MCP tools.
- Cursor connection materialization produces a valid `mcpServers` fragment.
- MCP gateway `tools/list` matches the profile tool set.
- Unknown tool names on `tools/call` fail closed.
- MCP tool handlers call in-process Astloom services (memory, code-graph, core-data, docs-sync), not stub-only responses.
- MCP gateway supports `ASTLOOM_MCP_STORE_MODE=memory|postgres` (auto-postgres when `ASTLOOM_DATABASE_URL` is set) so Cursor sessions share durable store schemas with the platform.
- With `ASTLOOM_DATABASE_URL` (or `ASTLOOM_CODE_GRAPH_DATABASE_URL`) set, MCP sync/heal can refresh pgvector embeddings beside Neo4j; without either, operators see `embedding_index_unavailable` rather than a silent empty semantic channel.
- Write path: Usage Profile tool `astloom_write` creates memory, task, activity, or decision records for the scoped project (in addition to `astloom_create_task`).
- Docs path: `astloom_docs_write` (`validate` / `note` / `draft` / `index`) and `astloom_docs_status` wire Cursor documentation work into docs-sync.
- Tests cover catalog validation, activation, materialization, MCP protocol handlers, and wired backend calls.
- Project `.venv` is created via `scripts/ensure-venv.sh` / `requirements-dev.txt`.
- Connect-cost and MCP usage attribution: [44-mcp-token-accounting.md](./44-mcp-token-accounting.md) (`astloom mcp tokens`).

## Implementation home

- Design: this file
- Catalog: `backend/configs/usage-profiles/`
- Loader: `backend/packages/usage_profile/`
- Activation API: `backend/services/project-profile-service/`
- MCP server: `backend/services/mcp-gateway-service/`
- Tests: `tests/backend/tools/usage-profile/`, `tests/backend/services/mcp-gateway-service/`, extended project-profile tests

## Related Documents

- [44-mcp-token-accounting.md](./44-mcp-token-accounting.md) — MCP connect estimate and usage history
- [36-astloom-cli.md](./36-astloom-cli.md) — CLI overview
- [40-remote-dev-client-mcp-wiring.md](./40-remote-dev-client-mcp-wiring.md) — client wiring
- [41-one-command-cross-platform-agent-onboarding.md](./41-one-command-cross-platform-agent-onboarding.md) — connect UX
- [26-domain-customization-and-feature-control.md](./26-domain-customization-and-feature-control.md) — domain packs and feature profiles

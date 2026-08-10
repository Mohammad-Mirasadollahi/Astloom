---
doc_id: as.doc.sea.astloom-cli-command-reference
title: 42 - Astloom CLI Command Reference
doc_type: runbook
status: active
schema_version: '1.0'
owner: platform-product
summary: 'Operator reference for every astloom subcommand: why it exists, required vs optional
  flags, examples, what files or stores change, and mandatory sync filter config (wildcards
  + built-in language excludes).'
tags:
- cli
- astloom
- operator
- runbook
- mcp
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/42-astloom-cli-command-reference.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- backend/packages/astloom_cli/main.py::main
- backend/packages/astloom_client/main.py::main
- backend/packages/astloom_cli/client_allowlist.py::CLIENT_TOP_LEVEL_COMMANDS
- backend/packages/astloom_cli/sync_config.py::SyncConfigError
- backend/packages/astloom_cli/software_paths.py::format_paths_env
- backend/packages/astloom_cli/docs_link_sync.py::DocsLinkSyncResult
- backend/services/code-graph-service/src/code_graph_service/domain/repo_discovery.py::DiscoveredFile
- backend/services/code-graph-service/src/code_graph_service/domain/doc_discovery.py::DiscoveredDocFile
- backend/services/code-graph-service/src/code_graph_service/application/ingest/human_docs.py::human_doc_symbol_id
- backend/packages/astloom_cli/cli_defaults.py::load_dotenv_files
- backend/packages/astloom_cli/identity.py::identity_path
- tests/backend/services/code-graph-service/test_human_docs_ingest.py::login
- backend/packages/astloom_cli/commands/sync/cmd.py::cmd_sync
- backend/packages/astloom_cli/commands/docs_standards/cmd.py::cmd_docs_standards
- backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs
- backend/packages/astloom_cli/commands/docs_standards/remediate.py::remediate_markdown_doc
doc_version: 1.3.1
updated_at: 2026-08-10
---

# 42 - Astloom CLI Command Reference

## Purpose

This document is the **canonical operator reference** for the `astloom` CLI: every shipped subcommand, why it exists, which flags are required, a copy-paste example, and what changes on disk or in stores when you run it.

**Two entries:**

| Install role | Binary on PATH | Catalog in this doc |
| --- | --- | --- |
| `server` / `both` | `astloom` only (full `astloom_cli`) | All sections below |
| `client` | `astloom-client` only (thin; **no** bare `astloom`) | Only: `version`, `doctor`, `status`, `connect`, `sync`, `purge`, `profile`, `project`, `client`, `path`, `upgrade client` |

On client-only hosts, `purge` / `sync` / `status` are remote operations scoped to `connect.yaml` (CLI `--tenant` / `--workspace` / `--project` must match or the command fails closed). Server and `both` do **not** need a separate thin-client install to run `connect`.

For install / PATH / package layout, see [36-astloom-cli.md](./36-astloom-cli.md). For remote MCP onboarding flows, see [41](./41-one-command-cross-platform-agent-onboarding.md). For **server/client upgrade** (`astloom upgrade *`, `install.sh --upgrade`), see [51-software-upgrade-server-and-client.md](./51-software-upgrade-server-and-client.md). Design: [thin-client CLI](../superpowers/specs/2026-07-25-thin-client-cli-design.md).

## How to read each command

| Field | Meaning |
| --- | --- |
| **Why** | Problem this command solves (reason it exists) |
| **Required** | Flags / preconditions that must be present or the command exits |
| **Optional** | Common optional flags |
| **Example** | Typical invocation |
| **What changes** | Files, env, graph data, or processes affected |
| **If you change X** | What happens when you re-run with different IDs or flags |

## Scope IDs (tenant / workspace / project)

Astloom isolates graph and project state by three string IDs:

| ID | Role |
| --- | --- |
| `tenant` | Org / customer boundary |
| `workspace` | Team or environment inside a tenant |
| `project` | One application / repo under a workspace |

**You choose these IDs.** Nothing mints a tenant id from your username. Use lowercase letters, digits, and hyphens (slug style), e.g. `acme`, `eng`, `payments`.

### Where IDs are set

| Step | Command / file | Sets |
| --- | --- | --- |
| First time (recommended) | `astloom init --tenant … --workspace … --path …` | `~/.astloom/identity.yaml`, repo `.env`, software `paths`, optional merge into `connect.yaml`, local project state |
| Connect config | `~/.astloom/connect.yaml` → `scope:` | Used when identity/env do not already pin scope |
| Per-command override | `--tenant` / `--workspace` / `--project` | Highest priority for that run only |
| Env | `ASTLOOM_TENANT_ID`, `ASTLOOM_WORKSPACE_ID`, `ASTLOOM_PROJECT_ID` | After CLI flags; often written by `init` into `.env` |

### Resolution order (everyday commands)

For `status`, `sync`, `purge` (and other commands that call operator defaults):

1. CLI flags (`--tenant` / `--workspace` / `--project`)
2. Env (`ASTLOOM_*` from shell or loaded `.env` / `.env.local`)
3. `~/.astloom/identity.yaml`
4. `~/.astloom/connect.yaml` → `scope`
5. Dogfood defaults (`tenant=astloom`, `workspace=dev`, `project=<cwd name>`)

**If you change IDs** (new `--tenant` / re-run `init --force` with different values): later `sync` / MCP tools read and write a **different scope**. Old graph data under the previous IDs remains until you `purge` that old scope (or wipe stores). IDE MCP configs keep the env baked in at `connect` time until you re-run `connect`.

### Required vs optional scope flags

| Command family | Scope flags |
| --- | --- |
| `init` | **`--tenant`, `--workspace`, and at least one `--path` required.** `--project` optional (default: current directory name) |
| `paths` | Uses active identity; `add` / `remove` take path arguments |
| `status` / `sync` / `purge` | Optional scope flags if identity/env/connect already set; `sync` uses pinned software paths |
| `inventory` | **No dashed mode flags.** Word modes only (`detail`, `save <path>`). Scope from identity/env/connect; uses pinned software paths |
| `docs-standards` | **No dashed mode flags.** Word modes only (`detail`, `save <path>`). Scans product Markdown under `docs/`, `backend/docs/`, `frontend/docs/`, and `deploy-toolkit/` (Full-tier gate + revision debt) |
| `docs-suggest-links` | Evidence-only `linked_symbols` suggestions from path citations. Flags: `--path`, `--docs-root`, `--include-all`, `--apply`, `--json`. Does **not** invent graph edges |
| `docs-catalog` | Cached frontmatter catalog from **observed** tags/lanes (not a global hardcoded enum). Flags: `--refresh`, `--roots`, `--tag`, `--concern`, … `--json` |
| `quality-audit` | **No dashed mode flags.** Word modes only (`detail`, `save [<path>]`). Categorized docs+code quality findings (incl. revision stamps); `save` defaults under `.astloom/quality-audit/` |
| `followup-tasks` | Automated follow-up Task lifecycle ops: `list`, `status`, `adopt-legacy`, `reconcile`, `purge` (scope optional; destructive steps need `--yes` or `--dry-run`) |
| `stats` | **No dashed mode flags.** Word modes only (`detail`, `save <path>`). Scope from identity/env/connect; pinned software paths + sync filters |
| `project register|activate|show|effective` | **Required** (`--tenant` `--workspace` `--project`) |
| `cursor export`, `mcp serve`, `graph *` | **Required** unless noted |

## First-time dogfood flow (same host)

```bash
cd /opt/Astloom
bash install.sh                    # once
astloom init --tenant acme --workspace eng --path /opt/Astloom
astloom connect --local
astloom status
## Required before first sync:
## cp astloom.sync.yaml.example astloom.sync.yaml   # then edit (file is gitignored)
astloom sync
```

| Step | Why |
| --- | --- |
| `init` | You pick durable IDs **and software path(s)** once so later commands stay short |
| `connect --local` | Write IDE MCP configs pointing at this checkout’s stdio gateway |
| `status` | Confirm Postgres/Neo4j/graph/MCP/paths before syncing |
| Sync filter file | `astloom.sync.yaml` (or `.astloom/sync.yaml`) must exist at each sync root — see [Sync filters](#sync-filters) |
| `sync` | Load each pinned software path into the code graph for that scope |

---

## Related Documents

- Continued in `docs/08-software-engineering-architecture/42-astloom-cli-command-reference-continued.md`
- Upgrade CLI catalog: [51-software-upgrade-server-and-client.md](./51-software-upgrade-server-and-client.md#cli-catalog-astloom-upgrade)
- Overview: [36-astloom-cli.md](./36-astloom-cli.md)

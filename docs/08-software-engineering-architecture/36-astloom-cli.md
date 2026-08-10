---
doc_id: as.doc.sea.astloom-cli
title: 36 - Astloom CLI
doc_type: runbook
status: active
schema_version: '1.0'
owner: platform-product
summary: '`astloom` is the operator/developer CLI. Server/both installs get the full surface;
  client-only installs use the thin `astloom-client` entry (PATH still named `astloom`) for
  connect, profile, and process control against a remote Astloom server.'
tags:
- cli
- astloom
- operator
- install
- client
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/36-astloom-cli.md
lifecycle_lane: current
concern_lane: ops
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- backend/packages/astloom_cli/main.py::main
- backend/packages/astloom_client/main.py::main
- backend/packages/astloom_cli/client_allowlist.py::CLIENT_TOP_LEVEL_COMMANDS
- backend/packages/astloom_cli/commands/sync/cmd.py::cmd_sync
- backend/packages/astloom_cli/docs_link_sync.py::sync_human_docs
related_docs:
- docs/08-software-engineering-architecture/42-astloom-cli-command-reference.md
- docs/08-software-engineering-architecture/39-local-install-runbook.md
- docs/08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding.md
- docs/08-software-engineering-architecture/40-remote-dev-client-mcp-wiring.md
- docs/08-software-engineering-architecture/35-usage-profile-and-cursor-mcp-onboarding.md
- docs/08-software-engineering-architecture/51-software-upgrade-server-and-client.md
- docs/superpowers/specs/2026-07-25-thin-client-cli-design.md
- docs/07-code-knowledge-graph/77-sync-embedding-heal-operator-runbook.md
doc_version: 1.3.1
audience:
- engineer
- operator
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 36 - Astloom CLI

## Purpose

`astloom` is the operator/developer CLI for Usage Profiles, local project state, coding-agent MCP connection, graph sync/status, and (on server installs) the MCP gateway and stack. It is installed into the project virtualenv and linked onto the user PATH.

**Install roles and CLI surface:**

| Role | PATH CLI name | Surface |
| --- | --- | --- |
| `server` / `both` | `astloom` only (full `astloom_cli`) | Full catalog; includes client workflows — no `astloom-client` on PATH |
| `client` | `astloom-client` only (thin `astloom_client`) | Allowlist only; bare `astloom` is **not** installed on PATH |

Client-only `purge` / `sync` / `status` run against the Astloom **server** over HTTPS using `connect.yaml` scope (fail-closed if CLI scope flags disagree). Design SoT: [thin-client CLI design](../superpowers/specs/2026-07-25-thin-client-cli-design.md).

**Full command catalog** (why each command exists, required vs optional flags, examples, and what changes when you run it):

→ **[42 - Astloom CLI Command Reference](./42-astloom-cli-command-reference.md)**

## Install (PATH)

Preferred (full local bootstrap including OS deps and Compose when needed):

```bash
bash install.sh
## or client-only (venv/PATH; thin CLI):
bash install.sh --role client
## alias:
bash install.sh --skip-infra
```

See [39-local-install-runbook.md](./39-local-install-runbook.md).

Venv-only helper (also used by install stage `02_venv`):

```bash
bash scripts/ensure-venv.sh
```

This will:

1. Create/refresh `.venv`
2. Install `requirements-dev.txt`
3. `pip install -e .` so `.venv/bin/astloom` and `.venv/bin/astloom-client` exist
4. Symlink `~/.local/bin/astloom` (server/both) or `~/.local/bin/astloom-client` (client-only); remove the opposite name if present
5. Append a PATH export to `~/.bashrc` or `~/.zshrc` when `~/.local/bin` is not already on PATH

Manual PATH install:

```bash
astloom path install --shell-rc .bashrc
```

## Where you choose IDs

Tenant and workspace IDs are **chosen by you** (not auto-minted):

```bash
astloom init --tenant acme --workspace eng --path .
## optional: --project payments   (default: current directory name)
```

That writes `~/.astloom/identity.yaml`, repo `.env`, and pins software path(s) for `sync`. Details: [doc 42 § Scope IDs](./42-astloom-cli-command-reference.md#scope-ids-tenant--workspace--project).

## First-time operator flow

```bash
astloom init --tenant acme --workspace eng --path /opt/Astloom
astloom connect --local
astloom status
cp astloom.sync.yaml.example astloom.sync.yaml   # required; local/gitignored
astloom sync
```

`astloom init` requires at least one `--path` (software root). Edit later: `astloom paths list|add|remove` (remove warns that old graph data remains). Sync uses pinned paths unless you pass `--path` to override.

Everyday:

```bash
astloom sync              # incremental files; embeddings for touched paths only
astloom sync heal         # same file pass + full-project embedding heal (missing/mismatch)
astloom purge --yes       # graph only
## astloom destroy-profile --tenant acme --workspace eng --project astloom
## (interactive: type two different confirmation phrases; does not delete source code)
```

`sync` never force-reparses healthy hash-stable files. Use `sync heal` when semantic search is missing rows project-wide; it does not re-ingest unchanged sources. `astloom stats`, `inventory`, and the plain-`sync` preflight show a **Need embedding heal** section with the missing count and the `astloom sync heal` command when a backlog exists. pgvector needs `ASTLOOM_CODE_GRAPH_DATABASE_URL` or fallback `ASTLOOM_DATABASE_URL`. Full contract: [77 - Sync Embedding Heal Operator Runbook](../07-code-knowledge-graph/77-sync-embedding-heal-operator-runbook.md).

## Command index (quick)

Full CLI (`server` / `both`). On **client-only**, only the rows marked **client** appear in `--help`.

| Command | One-line purpose | Client-only |
| --- | --- | --- |
| `astloom init` | You choose tenant + workspace IDs and software `--path`(s); save identity + `.env` | no |
| `astloom paths` | List / add / remove pinned software roots (sync targets) | no |
| `astloom status` | Scope, paths, infra, graph counts, MCP configs, hints (proxies to server on client) | **yes** |
| `astloom inventory` | Code/docs done vs remaining for pinned software roots | no |
| `astloom docs-standards` | Which `docs/` files fail documentation standards + percent | no |
| `astloom stats` | Code/docs counts, language mix %, processed vs remaining | no |
| `astloom connect` / `init` / `--local` | Onboard coding agents from connect.yaml or same-host dogfood | **yes** |
| `astloom sync` [`heal`] / `purge` | Load or wipe project graph data; `heal` adds full-project embedding refresh (client: remote HTTPS, scope locked to connect.yaml) | **yes** |
| `astloom destroy-profile` | Delete this scope’s profile data (not source code); two typed confirmations | no |
| `astloom backup *` | Export/validate/dry-run/restore project `.asbak` bundles | no |
| `astloom list-profiles` | List local tenant/workspace/project profiles + active scope | no |
| `astloom doctor` / `version` | Health / version | **yes** |
| `astloom profile *` | Usage Profile catalog | **yes** |
| `astloom project *` | Local project register / activate / show | **yes** |
| `astloom cursor export` | Export Cursor `mcpServers` fragment | no |
| `astloom mcp tools` / `tokens` / `serve` / `serve-http` | List tools; estimate connect/usage tokens; run stdio or HTTP gateway | no |
| `astloom client *` | List supported coding-agent MCP config targets | **yes** |
| `astloom path install` | Symlink CLI onto `~/.local/bin` (thin vs full by role) | **yes** |
| `astloom ports show` / `check` | Port profile preflight | no |
| `astloom graph *` | Ingest, freshness, explore, hybrid, smoke, watch | no |
| `astloom upgrade *` | Server/client upgrade, contract check, control-plane jobs | `upgrade client` only |

Every row above is expanded in [doc 42](./42-astloom-cli-command-reference.md). Upgrade details: [51 - Software Upgrade Server And Client](./51-software-upgrade-server-and-client.md).

## Port preflight

Uses `backend/packages/port_profile` and the default profile at `backend/configs/port-profiles/astloom-dev.json`.

```bash
astloom ports show
astloom ports check
```

`ports check` exits `0` when all ports are free, `1` on conflict. Env vars named like profile keys (e.g. `ASTLOOM_API_PORT`) override defaults.

## Implementation home

- Package: `backend/packages/astloom_cli/`
- Entry point: `pyproject.toml` → `astloom = astloom_cli.main:main`
- Layout: `main.py` · `parser/` · `cli_defaults.py` · `identity.py` · `commands/`
- Local state: `.astloom/projects/<tenant>/<workspace>/<project>.json`
- Identity: `~/.astloom/identity.yaml`
- Sync filters: local `astloom.sync.yaml` (**gitignored**); template `astloom.sync.yaml.example` (tracked)
- Tests: `tests/backend/tools/astloom-cli/`

## Related Documents

- [42-astloom-cli-command-reference.md](./42-astloom-cli-command-reference.md) — **full command reference**
- [Project-scoped backup and restore](../09-platform-governance-operations/13-project-scoped-backup-and-restore.md) — `.asbak` operator runbook
- [51-software-upgrade-server-and-client.md](./51-software-upgrade-server-and-client.md) — server/client upgrade + `astloom upgrade` catalog
- [44-mcp-token-accounting.md](./44-mcp-token-accounting.md) — MCP connect cost and usage history
- [39-local-install-runbook.md](./39-local-install-runbook.md)
- [41-one-command-cross-platform-agent-onboarding.md](./41-one-command-cross-platform-agent-onboarding.md)
- [40-remote-dev-client-mcp-wiring.md](./40-remote-dev-client-mcp-wiring.md)
- [35-usage-profile-and-cursor-mcp-onboarding.md](./35-usage-profile-and-cursor-mcp-onboarding.md)
- [../07-code-knowledge-graph/35-wedge-operator-connect-runbook.md](../07-code-knowledge-graph/35-wedge-operator-connect-runbook.md)

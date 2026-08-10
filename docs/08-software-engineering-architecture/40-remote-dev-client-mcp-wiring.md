---
doc_id: as.doc.sea.remote-dev-client-mcp-wiring
title: 40 - Remote Dev Client MCP Wiring (Historical — SSH Removed)
doc_type: runbook
status: deprecated
schema_version: '1.0'
owner: platform-engineering
summary: HISTORICAL. Describes the removed Phase A SSH stdio path for wiring a dev
  machine to Astloom MCP. SSH has been removed from the Astloom product; use
  the HTTPS wizard in doc 41 instead.
tags:
- mcp
- cursor
- ssh
- client
- runbook
- cross-platform
- historical
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/40-remote-dev-client-mcp-wiring.md
lifecycle_lane: current
concern_lane: ops
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- scripts/client/wire-remote-mcp.py::main
related_docs:
- docs/08-software-engineering-architecture/35-usage-profile-and-cursor-mcp-onboarding.md
- docs/08-software-engineering-architecture/36-astloom-cli.md
- docs/08-software-engineering-architecture/39-local-install-runbook.md
- docs/08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding.md
- docs/08-software-engineering-architecture/44-mcp-token-accounting.md
doc_version: 2.0.3
audience:
- engineer
- operator
language: en
security_classification: internal
updated_at: 2026-08-10
---

# 40 - Remote Dev Client MCP Wiring (Historical — SSH Removed)

## Purpose

**HISTORICAL — this runbook describes a removed feature.** SSH has been removed from the Astloom product (API-only HTTPS migration; see
[docs/superpowers/specs/2026-08-04-api-only-https-no-ssh-design.md](../superpowers/specs/2026-08-04-api-only-https-no-ssh-design.md)).
The `astloom client wire-remote` / `doctor-remote` commands, `remote_client.wire_remote_dev_host`,
`remote_mcp_serve.py`, and `connect_wizard.run_ssh_connect_wizard` described below no longer exist.

**Use instead:** [41-one-command-cross-platform-agent-onboarding.md](./41-one-command-cross-platform-agent-onboarding.md) —
`astloom connect` now wires MCP over **Streamable HTTP** (long-lived scoped access token with SHA-256 digest at rest, auto-TLS), with local stdio for same-host dogfood. This document is retained for historical reference only (why the SSH path existed, what it did); do not follow its steps.

The remainder of this document is preserved as-written for historical context.

## Supported coding-agent clients

All targets use the same **MCP stdio** shape (`command` + `args` + optional `env`): `mcpServers.<name>`.

| `client_id` | Product | Config path (under `--project-dir` unless user scope) |
| --- | --- | --- |
| `cursor` | Cursor | `.cursor/mcp.json` |
| `windsurf` | Windsurf / Codeium | `.windsurf/mcp.json` |
| `vscode` | VS Code (workspace MCP file) | `.vscode/mcp.json` |
| `claude-code` | Claude Code | `.mcp.json` |
| `continue` | Continue | `.continue/mcp.json` |
| `fragment` | Portable copy (commit or hand-merge) | `.astloom/mcp-servers.json` |
| `cursor-user` | Cursor user global | `~/.cursor/mcp.json` (requires `--include-user-clients`) |
| `claude-desktop` | Claude Desktop | OS-specific user config (requires `--include-user-clients`) |

List ids: `astloom client list-mcp-clients`.

**Default:** `wire-remote` writes **all project-scoped** targets (`--clients all`). Narrow with e.g. `--clients cursor,vscode`.

Products that use a different schema (some JetBrains or Zed layouts) can copy from `.astloom/mcp-servers.json` manually.

## Architecture

```text
[Cursor on Windows/macOS/Linux]
        │
        ▼ spawns MCP (stdio)
[Dev host: ssh → Astloom server]
        │
        ▼ python -m astloom_cli.remote_mcp_serve TENANT WORKSPACE PROJECT
[Astloom server: MCP gateway + Postgres/Neo4j on localhost]
```

- The **IDE brand does not matter**; any MCP client that supports `command` + `args` stdio works.
- MCP gateway runs on the **Astloom server** (where Compose and `.venv` live).
- The dev host only needs **OpenSSH client**, **Python 3.12+**, and the **`astloom` CLI** (or the repo launcher script).

## Prerequisites

| Location | Requirement |
| --- | --- |
| Astloom server | Completed [39-local-install-runbook.md](./39-local-install-runbook.md); `astloom doctor` OK |
| Dev host | OpenSSH client; first-time `astloom connect` wizard installs BatchMode key login (or use an existing key) |
| Dev host Python | 3.12+; install CLI via `pip install -e .` from an Astloom checkout **or** use `scripts/client/wire-remote-mcp.py` from a copied repo tree |

Preferred onboarding UX: [41-one-command-cross-platform-agent-onboarding.md](./41-one-command-cross-platform-agent-onboarding.md) (`astloom connect` / `edit`). This runbook remains the low-level SSH wiring detail.

## Server-side (once)

On the Astloom host after deploy:

```bash
cd /opt/Astloom
bash install.sh --check   # or full install
astloom doctor
```

No separate shell wrapper is required; SSH invokes:

```text
/opt/Astloom/.venv/bin/python -m astloom_cli.remote_mcp_serve TENANT WORKSPACE PROJECT
```

That module loads `backend/deployments/compose/.env.local`, sets MCP store URLs, and runs `astloom mcp serve`.

## Dev host — install CLI

**Option A — editable install (recommended on dev laptop):**

```bash
git clone <repo> Astloom && cd Astloom
bash install.sh --skip-infra
astloom path install
```

**Option B — launcher only (minimal copy):**

```bash
python3 /path/to/Astloom/scripts/client/wire-remote-mcp.py doctor-remote \
  --ssh user@astloom-host --remote-root /opt/Astloom
```

## Wire MCP from your application repo

Run from the **application repository** root (the tree Cursor opens over Remote SSH):

```bash
astloom client doctor-remote \
  --ssh user@astloom-host \
  --remote-root /opt/Astloom

astloom client wire-remote \
  --ssh user@astloom-host \
  --remote-root /opt/Astloom \
  --tenant acme --workspace eng --project myapp \
  --register --project-name "My App" \
  --project-dir .
```

This merges `Astloom-Programming` into **every selected client config** under `--project-dir` (default `--clients all`). Reload MCP in your agent / IDE.

### Flags reference

| Flag | Meaning |
| --- | --- |
| `--ssh` | SSH target `user@host` for the Astloom server |
| `--remote-root` | Astloom install path on that server |
| `--project-dir` | Application repo root |
| `--clients` | Comma-separated `client_id` values or `all` (default) |
| `--include-user-clients` | Also update user-global Cursor / Claude Desktop configs |
| `--out` | Single explicit JSON path (skips `--clients`; manual merge) |
| `--register` | Run `project register` + `activate` on the server |
| `--remote-os` | `unix` (default) or `windows` for venv layout on the server |
| `--remote-python` | Override path to remote venv Python |
| `--dry-run` | Print `mcpServers` JSON only |

## Windows notes

- Use **Windows OpenSSH Client** (`ssh` in PowerShell or Git Bash).
- Run `astloom client …` from PowerShell after `install.sh --skip-infra` in a Windows clone, or run the wire command from the **Remote SSH Linux workspace** (simplest for Cursor Remote SSH).
- Cursor MCP spawn uses the **remote Linux** environment when the workspace is Remote SSH; wire **on that Linux host** from your app repo path.

## Code graph ingest

Ingest runs against paths visible on the **Astloom server** (or shared storage):

```bash
ssh user@astloom-host "cd /opt/Astloom && ./.venv/bin/astloom graph ingest \
  --tenant acme --workspace eng --project myapp --path /path/on/server/to/repo"
```

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| MCP stuck connecting | SSH password prompt | Use key-based auth; test `ssh -o BatchMode=yes user@host true` |
| `remote python missing` | No venv on server | Run `install.sh` on Astloom host |
| `compose env missing` | No `.env.local` | Run install stage 03 or copy from example |
| Tools empty / errors | Project not registered | Re-run with `--register` |
| Wrong store | Env not loaded on server | Ensure Compose env exists; check `remote_mcp_serve` logs on stderr |

## Related documents

- [35-usage-profile-and-cursor-mcp-onboarding.md](./35-usage-profile-and-cursor-mcp-onboarding.md)
- [36-astloom-cli.md](./36-astloom-cli.md)
- [39-local-install-runbook.md](./39-local-install-runbook.md)

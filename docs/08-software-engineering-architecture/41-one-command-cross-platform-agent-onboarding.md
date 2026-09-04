---
doc_id: as.doc.sea.one-command-agent-onboarding
title: 41 - One-Command Cross-Platform Agent Onboarding
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-product
summary: Operator guide and specification for connecting any MCP-capable coding agent to a
  remote Astloom server with one command over HTTPS (long-lived scoped access token with
  SHA-256 digest at rest, Argon2id bootstrap secret, auto-TLS). Covers the HTTPS connect
  wizard, Streamable HTTP MCP transport, same-host local stdio dogfood, shared config
  (client content-push sync; optional source.server_path for existing on-server trees),
  authentication, concurrency, and security. SSH has been removed from the Astloom
  product (see doc 40, historical).
tags:
- mcp
- onboarding
- cross-platform
- api
- coding-agent
- specification
- runbook
- https
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
related_docs:
- docs/08-software-engineering-architecture/36-astloom-cli.md
- docs/08-software-engineering-architecture/39-local-install-runbook.md
- docs/08-software-engineering-architecture/40-remote-dev-client-mcp-wiring.md
- docs/08-software-engineering-architecture/52-client-tls-trust-and-verify.md
- docs/superpowers/specs/2026-07-25-thin-client-cli-design.md
- docs/superpowers/specs/2026-08-04-api-only-https-no-ssh-design.md
doc_version: 2.4.2
updated_at: 2026-09-04
linked_symbols:
- backend/packages/astloom_cli/connect_wizard.py::run_https_connect_wizard
- backend/packages/astloom_cli/connect_wizard.py::prompt_usage_profile
- backend/packages/astloom_cli/connect_wizard.py::prompt_api_key
- backend/packages/astloom_cli/connect_flow/run.py::run_connect
- backend/packages/astloom_cli/commands/connect.py::_ensure_api_key
- backend/packages/astloom_cli/connect_config.py::write_or_merge_connect_yaml
- backend/packages/astloom_cli/connect_http.py::persist_access_token
- backend/packages/astloom_cli/connect_http.py::read_access_token_file
- backend/packages/astloom_client/main.py::main
- backend/packages/astloom_cli/connect_flow/source_path.py::source_path_for_connect
- backend/packages/astloom_cli/commands/sync/client_remote.py::cmd_sync_client_remote
---

# 41 - One-Command Cross-Platform Agent Onboarding

## Purpose

Connect any **MCP-capable coding agent** (Cursor, Windsurf, VS Code, Claude Code, Continue, Claude Desktop, …) to **Astloom on a remote server** with one command:

```bash
astloom connect
```

This document is the **operator guide** (examples included) and the **normative specification** for what is shipped. HTTPS is the **only** remote transport — SSH has been removed from the Astloom product (API-only HTTPS migration).

Historical SSH wiring (removed): [40-remote-dev-client-mcp-wiring.md](./40-remote-dev-client-mcp-wiring.md).  
CLI reference: [36-astloom-cli.md](./36-astloom-cli.md).  
Server install: [39-local-install-runbook.md](./39-local-install-runbook.md).  
Client TLS verify / CA trust (including **Cursor MCP `fetch failed` on private auto-TLS**):
[52-client-tls-trust-and-verify.md](./52-client-tls-trust-and-verify.md) — after connect,
expect `.cursor/mcp.json` to use `npx mcp-remote` + `NODE_EXTRA_CA_CERTS` when `ca.pem` exists;
then Reload Cursor / reconnect Remote SSH.

## Two hosts (topology)

```text
┌──────────────────────────────┐         network          ┌──────────────────────────────┐
│ Dev host                     │ ◄──────── HTTPS ────────► │ Astloom server             │
│ - Application repository     │                           │ - bash install.sh            │
│ - Coding agent / IDE         │                           │ - Postgres + Neo4j (Compose) │
│ - astloom on PATH          │                           │ - MCP HTTP (Streamable)      │
│ - .astloom/connect.yaml    │                           │ - profile / graph API        │
└──────────────────────────────┘                           └──────────────────────────────┘
```

| Role | What lives there | Example names in this doc |
| --- | --- | --- |
| **Dev host** | Your app code + IDE MCP config files | hostname `devbox.example.internal`, app path `/opt/MyApp` |
| **Astloom server** | Platform install + stores + MCP gateway | hostname `astloom.example.internal`, install `/opt/Astloom` |

Replace example hostnames and paths with your own. Do not commit real secrets.

### Same host (dogfood / develop Astloom)

When the coding agent opens the **Astloom checkout itself** and Postgres/Neo4j are already local from `install.sh`:

```bash
cd /opt/Astloom
astloom init --tenant acme --workspace eng --path /opt/Astloom   # you choose the IDs + roots
astloom connect --local
astloom status
## Requires astloom.sync.yaml at each sync root (see doc 42 § Sync filters)
astloom sync
```

This registers a local project, writes workspace MCP configs (stdio gateway on this checkout), and skips HTTPS entirely. Check state with `astloom status`. Graph sync is off by default for `--local`; run `astloom sync` when you want the code graph filled (requires a sync filter file; auto full vs incremental; scope/path defaults apply). Use `astloom purge --yes` only to wipe corrupt graph data.

Command details (required flags, sync filters, what each run changes) → [42 - Astloom CLI Command Reference](./42-astloom-cli-command-reference.md) ([§ Sync filters](./42-astloom-cli-command-reference.md#sync-filters)).

Equivalent YAML: `server.local: true` and `connect.prefer_http: false` in `<checkout>/.astloom/connect.yaml`.

## Two modes (both shipped)

Both modes speak the **same MCP tools** and the **same project scope**. Only **how the IDE reaches the gateway** changes.

| | **Local stdio (same-host dogfood)** | **Streamable HTTP (remote, HTTPS)** |
| --- | --- | --- |
| IDE config shape | `command` + `args` (stdio, this checkout) | `url` + `headers` |
| Auth | None (same-host process) | Bearer access token (long-lived scoped; re-bootstrap on expiry) |
| Encryption | N/A (local process) | HTTPS (TLS; auto-generated CA for private deployments) |
| Server process | Spawned per IDE session on this checkout | Long-running `astloom mcp serve-http` |
| Best when | Developing/dogfooding the Astloom checkout itself | Any remote Astloom server |
| Fail closed | N/A | Needs `serve-http` up + valid `server.mcp_http_url` + token |

Shared for both modes:

- `scope.tenant` / `scope.workspace` / `scope.project`
- `usage_profile` (default `programming-cursor-mcp`)
- `clients` (which IDE config files to write)
- optional `source` + ingest
- one command: `astloom connect`

Selection rule inside `astloom connect`:

1. If `--local` (or `server.local: true`) → local stdio MCP on this checkout; no network transport.
2. Else if HTTP URL + auth headers/token are available → write **Streamable HTTP** MCP configs.
3. Else fail closed with a message to run `astloom connect edit` (or fix `connect.yaml`).

## One-time setup checklist

### A) Astloom server (once)

```bash
cd /opt/Astloom
bash install.sh
astloom doctor
```

Open a new shell so `astloom` is on `PATH` ([36](./36-astloom-cli.md)).

### B) Dev host (once)

```bash
## Install CLI only (no Docker infra on the laptop) — PATH name: astloom-client only
bash install.sh --role client
## alias: bash install.sh --skip-infra
astloom-client path install   # if needed; links ~/.local/bin/astloom-client (removes bare astloom)
cd /opt/MyApp
astloom-client connect
```

On **client-only** hosts, use **`astloom-client`** (there is no bare `astloom` on PATH). Help lists only connect / profile / process commands. Use `astloom-client sync`, `astloom-client status`, and `astloom-client purge --yes` for **your** connected scope on the server (scope locked to `connect.yaml`). Server-admin commands stay on the Astloom server (or a `both` install under bare `astloom`).

On a TTY with no `<checkout>/.astloom/connect.yaml`, `astloom connect` runs the **interactive HTTPS wizard**: server URL, tenant / workspace, **Usage Profile**, and a one-time bootstrap secret. It writes `connect.yaml` (mode `600`), mints a long-lived scoped access token via the bootstrap call (server stores only the SHA-256 digest), and wires MCP. The bootstrap secret is never stored on the client. Legacy `~/.astloom/connect.yaml` is still read if present.

**Missing scope on first connect:** if tenant, workspace, Usage Profile (and related connect fields) are not already present, the wizard **must** collect them before wiring MCP — see [First connect when scope is missing](./41-one-command-cross-platform-agent-onboarding-continued.md#first-connect-when-scope-is-missing) in the continued document. Usage Profile is **selected** from the installed catalog (not authored during client install). Project id defaults to the current directory name.

Advanced template only: `astloom connect init` then hand-edit YAML.

Reload MCP / the IDE window after connect succeeds.

Re-run the wizard (new server URL, rotate the bootstrap secret, or scope changed):

```bash
astloom connect edit
```

### Quick Setup — where the access token goes (client)

Do **not** put the raw bearer token in `connect.yaml`. `astloom-client connect` (and `connect edit`) **always prompts for an API key** on a TTY:

- If `.astloom/access_token` (or `ASTLOOM_TOKEN`) already has a key → **Enter keeps it**; paste a new `as1.*` value to replace.
- If none exists → paste is **required** (connect fails closed without it).
- The chosen key is written to `<checkout>/.astloom/access_token` (mode `600`).

| Prefer | What you do | Path / name |
| --- | --- | --- |
| 1 (connect wizard) | Answer the API key prompt (keep or paste) | Writes `<checkout>/.astloom/access_token` |
| 2 (install-minted key) | Paste the once-shown `as1.*` key at that prompt | Same file — one line, no quotes |
| 3 (env / non-interactive) | Export the env named by `auth.token_env` | Default `ASTLOOM_TOKEN` (override with `ASTLOOM_CONNECT_TOKEN`) |
| Recover | Re-run connect / edit | Paste a new key, or set `ASTLOOM_CONNECT_BOOTSTRAP_SECRET` for register/CA |

Token lookup when loading `connect.yaml` (before the interactive prompt):

1. Env named by `auth.token_env` (default `ASTLOOM_TOKEN`), or `ASTLOOM_CONNECT_TOKEN`
2. Else `<checkout>/.astloom/access_token` (sibling of `connect.yaml`)

A user-supplied API key is **not** overwritten if bootstrap also mints a token. `connect.yaml` only names the env (`auth.token_env`); it must not store the secret. Gitignore `.astloom/access_token`. TLS trust/verify: [52](./52-client-tls-trust-and-verify.md). Server mint during install: [39](./39-local-install-runbook.md#server-auth-secrets-jwt--bootstrap--optional-api-key).

Minimal client checklist:

```bash
# On the app checkout (client host)
cd /opt/MyApp
bash /opt/Astloom/install.sh --role client   # once
astloom-client connect                      # prompts API key (required); optional bootstrap
astloom-client doctor
# Reload MCP / IDE window
```

---

## Example 1 — HTTPS mode (remote Astloom server)

Use this whenever the coding agent connects to an Astloom server over the network.

### Server: start HTTP MCP

```bash
export ASTLOOM_MCP_TOKEN_SECRET='replace-with-a-long-random-secret'
export ASTLOOM_MCP_HTTP_PUBLIC_URL='https://astloom.example.internal:32500'
## When Compose Postgres is up:
## export ASTLOOM_MCP_STORE_MODE=postgres
## export ASTLOOM_DATABASE_URL=...
astloom mcp serve-http --host 0.0.0.0 --port 32500
```

Keep this process running (systemd/supervisor in real deployments). Put a TLS-terminating reverse proxy (or the auto-generated CA) in front — plain `http://` is rejected unless `ASTLOOM_ALLOW_INSECURE_HTTP=1` is set for an explicit lab/loopback override.

Optional: run project-profile HTTP API for bootstrap (`server.url` in connect.yaml). Port profile default for project-profile is `ASTLOOM_PROJECT_PROFILE_PORT` (`32194`).

### Dev host: `<checkout>/.astloom/connect.yaml`

```yaml
server:
  url: https://astloom.example.internal:32194
  mcp_http_url: https://astloom.example.internal:32500

auth:
  # Optional API token for bootstrap if your profile API requires it:
  token_env: ASTLOOM_TOKEN

scope:
  tenant: acme
  workspace: eng

usage_profile: programming-cursor-mcp
clients: all

source:
  server_path: /srv/repos/MyApp

connect:
  register: true
  smoke_test: true
  prefer_http: true
  ingest: optional
```

Credentials: see [Quick Setup — where the access token goes](#quick-setup--where-the-access-token-goes-client). Prefer `.astloom/access_token` or:

```bash
export ASTLOOM_TOKEN='...'
```

The MCP bearer token is **minted by bootstrap** (single long-lived scoped access token; no refresh token) when the profile API is set, and written into IDE `headers` — not as a database password. On the server, only the token's SHA-256 digest is persisted (`project_profile.access_tokens`). When the token expires or is revoked, re-run `astloom connect` / `astloom connect edit`.

### Dev host: run connect

```bash
cd /opt/MyApp
astloom connect
```

Expected: prints `transport: streamable_http (https://astloom.example.internal:32500/mcp)`
and, when the client has `ca.pem`, notes that Cursor MCP uses **stdio `mcp-remote`**
(see [52](./52-client-tls-trust-and-verify.md)).

What lands in MCP config (shape) — **with private CA** (normal auto-TLS lab):

```json
{
  "mcpServers": {
    "Astloom-Programming": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://astloom.example.internal:32500/mcp",
        "--header", "Authorization: Bearer as1....",
        "--header", "X-Tenant-Id: acme",
        "--header", "X-Workspace-Id: eng",
        "--header", "X-Project-Id: MyApp",
        "--header", "X-Usage-Profile: programming-cursor-mcp"
      ],
      "env": {
        "NODE_EXTRA_CA_CERTS": "/opt/MyApp/.astloom/certs/ca.pem"
      }
    }
  }
}
```

Bare HTTPS `url` + `headers` (legacy / public CA only):

```json
{
  "mcpServers": {
    "Astloom-Programming": {
      "url": "https://astloom.example.internal:32500/mcp",
      "headers": {
        "Authorization": "Bearer as1....",
        "X-Tenant-Id": "acme",
        "X-Workspace-Id": "eng",
        "X-Project-Id": "MyApp",
        "X-Usage-Profile": "programming-cursor-mcp"
      }
    }
  }
}
```

Do **not** commit files that contain live bearer tokens. Prefer gitignoring generated MCP JSON or redacting before commit.

After connect: **Reload Window** (or reconnect Cursor Remote). If MCP shows
`fetch failed`, follow the repair steps in [52](./52-client-tls-trust-and-verify.md).

---

## Shared config reference (`<checkout>/.astloom/connect.yaml`)

| Key | Required | Meaning |
| --- | --- | --- |
| `server.remote_root` | Optional | Astloom install path (informational; default `/opt/Astloom`) |
| `server.url` | Optional | project-profile API base for bootstrap / ingest |
| `server.mcp_http_url` | For remote mode | Public base of MCP HTTP (port `32500` by default); must be `https://` |
| `auth.token_env` | Optional | Env var name for the bearer (default `ASTLOOM_TOKEN`); prefer `.astloom/access_token` over inline secrets |
| `scope.tenant` / `workspace` | Yes | Platform scope |
| `scope.project` | Optional | Defaults to **cwd directory name** |
| `usage_profile` | Optional | Default `programming-cursor-mcp` |
| `clients` | Optional | `all` or comma list (`cursor,vscode,…`) |
| `source.server_path` | Optional (NFS/clone / explicit `--path`) | On-server tree when set. Default `astloom-client sync` uses **content-push** (`ingest-push`) and does not require this. Details: [41-continued](./41-one-command-cross-platform-agent-onboarding-continued.md) |
| `source.git` | Optional | `{ remote, branch }` registration |
| `connect.prefer_http` | Optional | Default `true` |
| `connect.register` | Optional | Default `true` |
| `connect.smoke_test` | Optional | Default `true` |
| `connect.ingest` | Optional | `off` \| `optional` \| `always` |

Environment overrides (examples): `ASTLOOM_CONNECT_URL`, `ASTLOOM_CONNECT_MCP_HTTP_URL`, `ASTLOOM_CONNECT_TENANT`, `ASTLOOM_CONNECT_PROJECT`, `ASTLOOM_CONNECT_LOCAL`.

CLI:

```bash
astloom connect init
astloom connect
astloom connect --project myapp --clients cursor,vscode
astloom connect --dry-run
astloom client list-mcp-clients
```

## Related Documents

- Continued: [41-one-command-cross-platform-agent-onboarding-continued.md](./41-one-command-cross-platform-agent-onboarding-continued.md)
- Normative HTTPS/auth: [2026-08-04-api-only-https-no-ssh-design.md](../superpowers/specs/2026-08-04-api-only-https-no-ssh-design.md)
- Historical SSH wiring: [40-remote-dev-client-mcp-wiring.md](./40-remote-dev-client-mcp-wiring.md)
- CLI: [36-astloom-cli.md](./36-astloom-cli.md)
- Install: [39-local-install-runbook.md](./39-local-install-runbook.md)

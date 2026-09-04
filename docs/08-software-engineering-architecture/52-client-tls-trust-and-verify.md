---
doc_id: as.doc.sea.client-tls-trust-and-verify
title: 52 - Client TLS Trust And Certificate Verify
doc_type: runbook
status: active
schema_version: '1.0'
owner: platform-product
summary: >-
  Operator guide for Astloom client HTTPS trust — default tls_verify off (encrypt
  without validating the server cert), how to enable verification with the server
  private CA PEM, where certs live on server and client, and clear errors when
  verify is on without trust material.
tags:
- tls
- https
- connect
- client
- ca
- verify
- runbook
- security
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/52-client-tls-trust-and-verify.md
lifecycle_lane: current
concern_lane: ops
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
doc_version: 1.0.1
updated_at: 2026-08-10
linked_symbols:
- backend/packages/astloom_cli/connect_http.py::httpx_verify
- backend/packages/astloom_cli/connect_http.py::parse_tls_verify
- backend/packages/astloom_cli/connect_config.py::ConnectSettings
- backend/packages/astloom_cli/tls_certs.py::ensure_tls_material
- backend/packages/astloom_cli/service_runtime/mcp.py::prepare_mcp_env
related_docs:
- docs/08-software-engineering-architecture/39-local-install-runbook.md
- docs/08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding.md
- docs/superpowers/specs/2026-08-04-api-only-https-no-ssh-design.md
audience:
- engineer
- operator
- agent
language: en
security_classification: internal
---

# 52 - Client TLS Trust And Certificate Verify

## Purpose

Explain how a coding-agent host (client) trusts an Astloom server over HTTPS:
what is automatic, what `auth.tls_verify` means, where CA files live, and how to
turn verification on safely.

## Quick answer

| Mode | Config | Behavior |
| --- | --- | --- |
| **Default (lab)** | `auth.tls_verify: false` (or omit) | HTTPS URLs still encrypt traffic; **certificate is not validated** |
| **Verify on** | `auth.tls_verify: true` + `auth.ca_file` | Client validates the server cert against the Astloom **private CA PEM** |
| **Verify on, no CA** | `tls_verify: true` without a readable CA file | **Fails closed** with an explicit error (not a cryptic SSL stacktrace) |

You do **not** paste a raw public key into `connect.yaml`. Trust material is the
server **CA certificate** (`ca.pem`), not the leaf private key.

## Topology

```text
Client app repo                         Astloom server
.astloom/connect.yaml                 {data-root}/certs/
  auth.tls_verify: false|true             ca.pem      ← trust anchor (copy to client)
  auth.ca_file: …/ca.pem                  ca.key      ← server only (never copy)
                                          server.pem  ← leaf (served by profile/graph/MCP)
                                          server.key  ← server only
```

Fresh server install / `astloom service start` auto-creates those certs under the
durable data root (sibling `<install>-data` by default) when missing. Upgrade
**preserves** existing certs.

## Client config (`connect.yaml`)

Path: `<your-app>/.astloom/connect.yaml` (gitignored).

### Default — encrypt, do not verify (easiest)

```yaml
server:
  url: https://192.168.1.150:32194
  graph_url: https://192.168.1.150:32140
  mcp_http_url: https://192.168.1.150:32500
auth:
  token_env: ASTLOOM_TOKEN
  tls_verify: false          # default if omitted
scope:
  tenant: mir
  workspace: dev
  project: ThinkingSOC
usage_profile: programming-cursor-mcp
```

Use this for private LAN / auto-TLS labs. Traffic is still HTTPS; MITM protection
from cert validation is off.

### Recommended for shared / production-like — verify with CA

1. On the **server**, copy the CA (not the private key):

```bash
# On Astloom server
sudo cat /opt/Astloom-data/certs/ca.pem
# or: scp root@astloom-host:/opt/Astloom-data/certs/ca.pem ./
```

2. On the **client** app repo:

```bash
mkdir -p .astloom/certs
# place ca.pem there (mode 0644 is fine — it is a public certificate)
cp /path/from/server/ca.pem .astloom/certs/ca.pem
```

3. Enable verify in `connect.yaml`:

```yaml
auth:
  token_env: ASTLOOM_TOKEN
  tls_verify: true
  ca_file: .astloom/certs/ca.pem
```

Absolute paths and env also work:

```bash
export ASTLOOM_CONNECT_CA_FILE=/secure/path/ca.pem
export ASTLOOM_CONNECT_TLS_VERIFY=true
```

Env overrides the YAML when set.

### Automatic CA from connect bootstrap

```bash
cd /path/to/YourApp
astloom-client connect
```

When bootstrap succeeds, the server may return `ca_pem`. The client writes
`.astloom/certs/ca.pem` and can point `auth.ca_file` at it. **Verification stays
off until you set `tls_verify: true`.**

## Server side (what starts with HTTPS)

| Service | Port (default) | TLS |
| --- | --- | --- |
| Project profile API | 32194 | HTTPS (leaf under data-root certs) |
| Code graph API | 32140 | HTTPS |
| MCP Streamable HTTP | 32500 | HTTPS by default (`ASTLOOM_MCP_TLS=0` disables) |

Set advertise host for clients:

```bash
# Server .env (example)
ASTLOOM_PUBLIC_HOSTNAME=192.168.1.150
ASTLOOM_MCP_HTTP_PUBLIC_URL=https://192.168.1.150:32500
```

Then restart MCP: `astloom service restart`.

## Cursor / IDE Streamable HTTP vs CLI ``tls_verify``

`auth.tls_verify: false` only affects the **Astloom CLI** (httpx). Cursor's
native Streamable HTTP `url` entry **always verifies** TLS and cannot take a
custom CA path — private Astloom CA then surfaces as:

```text
MCP HTTP exchange failed
Transient error connecting to streamableHttp server: fetch failed
```

Node often reports `UNABLE_TO_VERIFY_LEAF_SIGNATURE` (and may require
`NODE_EXTRA_CA_CERTS` even after `update-ca-certificates`).

**Fix (automatic on connect):** when `.astloom/certs/ca.pem` exists, connect
writes Cursor MCP as **stdio `npx mcp-remote`** with
`NODE_EXTRA_CA_CERTS=<ca>` (plus OS trust + `/etc/environment` on Linux). That
spawns a child Node that trusts the private CA; bare `url` transport does not.

**Manual lab repair (already connected host):**

```bash
# 1) OS trust + Node env (root)
sudo cp /path/to/YourApp/.astloom/certs/ca.pem \
  /usr/local/share/ca-certificates/astloom-private-ca.crt
sudo update-ca-certificates
echo 'NODE_EXTRA_CA_CERTS="/usr/local/share/ca-certificates/astloom-private-ca.crt"' \
  | sudo tee -a /etc/environment

# 2) Re-run connect so .cursor/mcp.json becomes mcp-remote + NODE_EXTRA_CA_CERTS
cd /path/to/YourApp
astloom-client connect

# 3) Fully reconnect Cursor Remote / Reload Window (kill stale cursor-server if needed)
```

Confirm Node trusts the gateway:

```bash
export NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/astloom-private-ca.crt
node -e "require('https').get('https://<astloom-host>:32500/health',r=>console.log(r.statusCode)).on('error',e=>console.error(e))"
```

Expect `200`.

## Commands that honor `tls_verify`

All client HTTPS calls that go through `httpx_verify` (connect, status, sync
content-push, profile/graph helpers) use the same rule.

```bash
# Lab default — no CA required
astloom-client sync --allow-cloud-llm

# After enabling tls_verify + ca_file
astloom-client connect
astloom-client sync --allow-cloud-llm
```

Plain `http://` URLs are still rejected unless `ASTLOOM_ALLOW_INSECURE_HTTP=1`
(separate from certificate verify — that flag only allows non-TLS URLs).

## Error when verify is on without trust

If you set `tls_verify: true` but forget the CA:

```text
error: auth.tls_verify is true but no CA trust file was found.
  TLS verification needs the Astloom private CA PEM on the client.
  Fix one of:
  • auth.ca_file: /path/to/ca.pem
  • env ASTLOOM_CONNECT_CA_FILE=/path/to/ca.pem
  • re-run `astloom-client connect` so bootstrap can write .astloom/certs/ca.pem
  • copy server file {data-root}/certs/ca.pem (often /opt/Astloom-data/certs/ca.pem)
  Or set auth.tls_verify: false (default) to connect without verifying the certificate.
```

## Checklist

**Server fresh install**

1. `bash install.sh --role server` (or `get-astloom.sh`)
2. Confirm `{data-root}/certs/ca.pem` and `server.pem` exist after bring-up
3. Confirm `curl -sk https://127.0.0.1:32500/health` → 200

**Client**

1. `bash install.sh --role client` on the coding host
2. From the app repo: `astloom-client connect` (HTTPS URLs + optional CA save)
3. Leave `tls_verify: false` until you deliberately pin the CA
4. For verify: copy `ca.pem`, set `tls_verify: true` + `ca_file`, then sync

## Security notes

- Never copy `ca.key` or `server.key` to clients.
- `tls_verify: false` is intentional for private auto-TLS labs; turn verify **on**
  when clients leave a trusted LAN or when policy requires cert validation.
- Rotating the server CA requires distributing the new `ca.pem` to every client
  that uses `tls_verify: true`.

## Related Documents

- [39 - Local Install Runbook](./39-local-install-runbook.md) — server install, MCP HTTPS, auth secrets
- [41 - One-Command Cross-Platform Agent Onboarding](./41-one-command-cross-platform-agent-onboarding.md) — connect wizard and MCP wiring
- [API-only HTTPS design](../superpowers/specs/2026-08-04-api-only-https-no-ssh-design.md) — transport law

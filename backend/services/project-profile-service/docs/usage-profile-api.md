---
doc_id: as.doc.project-profile.usage-profile-api
title: Usage Profile API (project-profile-service)
doc_type: contract
status: active
schema_version: '1.0'
owner: project-profile-service
summary: HTTP contract for project-profile health, Usage Profile catalog/activation,
  connect bootstrap/status/sources/ingest, and scoped access-token (API key) mint/revoke.
  Bootstrap and POST access-tokens mint as1.* Bearers; ttl_seconds=0 is non-expiring;
  DELETE revokes by token_id (jti). Server stores only SHA-256 digests.
tags:
- api
- contract
- project-profile
- usage-profile
- auth
- access-token
phase: usage-profile
canonical_path: backend/services/project-profile-service/docs/usage-profile-api.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
doc_version: 1.2.1
updated_at: 2026-08-10
linked_symbols:
- backend/services/project-profile-service/src/project_profile_service/api.py
- backend/packages/astloom_auth/tokens.py::mint_and_register_access_token
- backend/packages/astloom_auth/tokens.py::revoke_access_token_in_scope
- backend/packages/astloom_auth/token_registry.py::hash_access_token
related_docs:
- docs/superpowers/specs/2026-08-04-api-only-https-no-ssh-design.md
- docs/08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding.md
---

# Usage Profile API (project-profile-service)

## Purpose

Document the project-profile-service HTTP surface used by `astloom connect`: Usage
Profile catalog and activation, connect bootstrap/status/sources/ingest, scoped
access-token mint and revoke, and how tokens are stored without plaintext at rest.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Service health (used by `astloom connect`) |
| GET | `/api/v1/usage-profiles` | List catalog profile ids |
| POST | `/api/v1/projects/{project_id}/connect/bootstrap` | Idempotent register + activate + MCP fragment; mint access token |
| POST | `/api/v1/projects/{project_id}/connect/sources` | Register server path or git source |
| POST | `/api/v1/projects/{project_id}/connect/ingest` | Request graph ingest for registered source |
| GET | `/api/v1/projects/{project_id}/connect/status` | Profile, code source, ingest status (Bearer when enforcement on) |
| POST | `/api/v1/projects/{project_id}/access-tokens` | Mint scoped access token (API key); Bearer required when secret configured |
| DELETE | `/api/v1/projects/{project_id}/access-tokens/{token_id}` | Revoke by `token_id` (`jti`); scoped to tenant/workspace/project |
| POST | `/api/v1/projects/{project_id}/usage-profile:activate` | Activate a Usage Profile on the project |
| GET | `/api/v1/projects/{project_id}/usage-profile/effective` | Resolve effective profile for scope |
| GET | `/api/v1/projects/{project_id}/usage-profile/cursor-mcp` | Materialize Cursor `mcpServers` fragment |

### Connect bootstrap auth

When `ASTLOOM_CONNECT_BOOTSTRAP_SECRET` is set, the bootstrap body must include a matching
`bootstrap_secret` (verified with Argon2id against the server hash). On success the response
includes:

| Field | Meaning |
| --- | --- |
| `access_token` | Plaintext `as1.*` Bearer returned **once** to the client |
| `expires_in` | TTL seconds (default 30 days) |
| `ca_pem` | Trust material when auto-TLS CA exists under the data root |

The server **does not** persist the raw access token. It registers a SHA-256 digest plus
`jti` / scope / expiry in `project_profile.access_tokens` via
`mint_and_register_access_token`. Subsequent connect Bearer checks use
`verify_registered_access_token` (HMAC + registry liveness). There is no refresh token;
clients re-run bootstrap/connect after expiry or revoke.

### Access tokens (API keys)

Additional scoped tokens (same `as1.*` format as bootstrap) can be minted and revoked
without re-running connect. When `ASTLOOM_MCP_TOKEN_SECRET` (or
`ASTLOOM_MCP_HTTP_TOKEN`) is set, both routes require a live Bearer for the same
`X-Tenant-Id` / `X-Workspace-Id` / `{project_id}` scope.

#### Create

`POST /api/v1/projects/{project_id}/access-tokens`

Request body:

```json
{
  "ttl_seconds": 3600
}
```

| Field | Meaning |
| --- | --- |
| `ttl_seconds` | Lifetime in seconds. Omit → default 30 days. **`0` = non-expiring** (claim `exp=0`; registry `expires_at` null). Negative values → `400`. |

Response (plaintext token returned **once**):

```json
{
  "access_token": "as1.…",
  "token_id": "jti-hex",
  "expires_in": 3600,
  "scope": {
    "tenant_id": "mir",
    "workspace_id": "dev",
    "project_id": "demo-app"
  }
}
```

For non-expiring tokens, `expires_in` is `0`. Rate-limited per client IP (default 20/min).

#### Revoke by id

`DELETE /api/v1/projects/{project_id}/access-tokens/{token_id}`

`token_id` is the `jti` from create (or from decoding the Bearer). Revoke is
scope-checked: a token registered under another project returns `404` (same as
unknown id). Response:

```json
{
  "revoked": true,
  "token_id": "jti-hex"
}
```

After revoke, Bearer checks fail closed with `401`.

### MCP HTTP gateway (Phase B)

On the Astloom host:

```bash
export ASTLOOM_MCP_TOKEN_SECRET='long-random-secret'
export ASTLOOM_MCP_HTTP_PUBLIC_URL='https://astloom.example.internal:32500'
export ASTLOOM_MCP_STORE_MODE=postgres   # when Compose is up
astloom mcp serve-http --host 0.0.0.0 --port 32500
```

Clients receive `url` + `Authorization` from bootstrap / `astloom connect` (no SSH in mcp.json).

Register/patch project profile may also set `usage_profile`.

## Activate body

```json
{
  "usage_profile": "programming-cursor-mcp",
  "apply_catalog_defaults": true
}
```

When `apply_catalog_defaults` is true (default), domain pack and feature profile are taken from the catalog entry.

## Cursor onboarding

1. Register project (or use existing).
2. Activate `programming-cursor-mcp`.
3. GET `.../usage-profile/cursor-mcp` and merge into Cursor MCP settings.
4. Set `PYTHONPATH` so `python -m mcp_gateway_service` resolves.
5. Reload Cursor.

See `docs/08-software-engineering-architecture/35-usage-profile-and-cursor-mcp-onboarding.md`.

## Related Documents

- Normative HTTPS/auth design: `docs/superpowers/specs/2026-08-04-api-only-https-no-ssh-design.md`
- Operator onboarding: `docs/08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding.md`
- `backend/docs/API_NAMING_AND_CONTRACT_STANDARD.md` — HTTP naming and contract conventions

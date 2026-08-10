---
doc_id: as.doc.sea.api-only-https-migration-plan
title: API-only HTTPS migration implementation plan
doc_type: runbook
status: active
schema_version: '1.0'
owner: platform-engineering
summary: Bite-sized implementation plan for absolute SSH removal, HTTPS edge with auto
  TLS certificates, a single long-lived scoped access token (SHA-256 digest at rest),
  and Argon2id for the bootstrap secret.
tags:
- plan
- https
- auth
- connect
- migration
phase: 08-software-engineering-architecture
canonical_path: docs/superpowers/plans/2026-08-04-api-only-https-migration.md
lifecycle_lane: current
concern_lane: ops
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
doc_version: 1.3.1
updated_at: 2026-08-10
related_docs:
- docs/superpowers/specs/2026-08-04-api-only-https-no-ssh-design.md
- docs/08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding-continued.md
linked_symbols:
- backend/packages/usage_profile/mcp_tokens.py::mint_connect_token
- backend/packages/astloom_auth/token_registry.py::hash_access_token
- backend/packages/astloom_auth/tokens.py::mint_and_register_access_token
- backend/packages/astloom_auth/tokens.py::mint_access_token
- backend/packages/astloom_cli/connect_config.py::load_connect_settings
- backend/packages/astloom_cli/connect_config.py::write_or_merge_connect_yaml
- backend/packages/astloom_cli/connect_config.py::ConnectSettings
- backend/packages/astloom_cli/tls_certs.py::ensure_tls_material
- backend/packages/astloom_cli/tls_certs.py::TlsMaterial
- backend/packages/astloom_cli/connect_flow/client_push.py::client_push_sync
- backend/packages/astloom_cli/connect_flow/client_push.py::build_push_files
- backend/packages/astloom_cli/connect_wizard.py::mask_api_key
- backend/packages/astloom_cli/connect_flow/run.py::reachability_check
- backend/services/code-graph-service/src/code_graph_service/api/auth.py::require_content_push_http_auth
- backend/services/code-graph-service/src/code_graph_service/api/auth.py::configured_graph_http_token
---

# API-only HTTPS migration Implementation Plan

## Purpose

Executable implementation plan for absolute SSH removal: HTTPS edge with auto
TLS certificates, a single long-lived scoped access token (SHA-256 digest at
rest), and Argon2id for the bootstrap secret.
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove SSH from the Astloom product path and run all client traffic over HTTPS with auto TLS certificates, a single long-lived scoped access token (SHA-256 digest at rest; never plaintext in DB), and Argon2id hashes for the bootstrap secret at rest.

**Architecture:** One HTTPS edge terminates TLS (auto-CA under `ASTLOOM_DATA_ROOT/certs` when missing). Clients authenticate with a long-lived access Bearer token minted at bootstrap/connect; there is no refresh flow — clients re-bootstrap once the token expires. MCP, connect, and content-push use HTTPS only.

> **Update (2026-08-04):** the refresh-token flow originally shipped in Tasks 2–4/8
> below was removed as YAGNI. `astloom_auth` now only mints/verifies a single
> access token (default TTL 30 days); `POST /api/v1/auth/refresh`, the refresh
> store, and the client's 401→refresh→retry helper are deleted. On 401, clients
> fail closed with a message to re-run `astloom connect`. Historical task
> steps below are kept for context but no longer reflect the shipped auth model.
>
> **Update (2026-08-04, hash-at-rest):** minted `as1.*` tokens carry `jti`;
> `astloom_auth.token_registry` stores only the SHA-256 digest in
> `project_profile.access_tokens`. Bootstrap uses `mint_and_register_access_token`;
> connect Bearer uses `verify_registered_access_token`. See Task 9.

**Tech Stack:** FastAPI, httpx, `argon2-cffi`, `cryptography` (X.509), existing `as1.*` HMAC mint in `usage_profile.mcp_tokens`, Caddy or nginx edge sample under `scripts/install/`.

## Global Constraints

- Absolute zero SSH in product code/docs/client schema after Phase 3.
- HTTPS only (lab/loopback override must be explicit env, not default).
- Argon2id minimums: `time_cost=3`, `memory_cost=65536`, `parallelism=4`.
- Access TTL default 30 days; no refresh token (removed as YAGNI — see update note above).
- Access token at rest: SHA-256 digest + metadata only (never raw Bearer in DB).
- Auto-certs under `<ASTLOOM_DATA_ROOT>/certs/`; never log private keys.
- English-only committed docs; tests under repository `tests/`.
- Normative design: `docs/superpowers/specs/2026-08-04-api-only-https-no-ssh-design.md`.

---

### Task 1: TLS auto-certificate module

**Files:**
- Create: `backend/packages/astloom_cli/tls_certs.py`
- Create: `tests/backend/tools/astloom-cli/test_tls_certs.py`
- Modify: dependency declaration where Astloom CLI / install declares Python deps (add `cryptography` if missing)

**Interfaces:**
- Produces: `ensure_tls_material(*, data_root: Path, hostname: str, cert_env: str = "", key_env: str = "") -> TlsMaterial` with fields `ca_pem_path`, `cert_path`, `key_path`, `generated: bool`

- [ ] **Step 1: Write the failing test**

```python
def test_ensure_tls_material_creates_once(tmp_path):
    from astloom_cli.tls_certs import ensure_tls_material

    first = ensure_tls_material(data_root=tmp_path, hostname="astloom.test")
    assert first.cert_path.is_file()
    assert first.key_path.is_file()
    assert first.ca_pem_path.is_file()
    assert first.generated is True
    second = ensure_tls_material(data_root=tmp_path, hostname="astloom.test")
    assert second.generated is False
    assert second.cert_path == first.cert_path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/backend/tools/astloom-cli/test_tls_certs.py::test_ensure_tls_material_creates_once -v`  
Expected: FAIL import / missing module

- [ ] **Step 3: Implement `ensure_tls_material`**

Use `cryptography` to create a private CA + leaf for `hostname` under `{data_root}/certs/`. If `ASTLOOM_TLS_CERT`/`ASTLOOM_TLS_KEY` env paths exist, return those and `generated=False`. chmod keys to `0o600`.

- [ ] **Step 4: Run test to verify it passes**

Run: same pytest command — Expected: PASS

- [ ] **Step 5: Commit** (only when user asks to commit)

---

### Task 2: Argon2id + refresh token store

**Files:**
- Create: `backend/packages/astloom_auth/` (minimal package: `hashing.py`, `refresh.py`, `tokens.py`) **or** extend `backend/packages/usage_profile/` if packaging cost is lower — prefer new `astloom_auth` when it avoids circular imports
- Create: `tests/backend/packages/astloom_auth/test_refresh_argon2.py`
- Add dependency: `argon2-cffi`

**Interfaces:**
- Produces:
  - `hash_secret(raw: str) -> str` (Argon2id with design floors)
  - `verify_secret(raw: str, encoded: str) -> bool`
  - `RefreshRecord` store protocol: `put`, `get`, `revoke_family`
  - `mint_access_token(...)` wrapping/shortening TTL of `mint_connect_token` (default 900s)
  - `issue_token_pair(...) -> TokenPair(access, refresh, refresh_expires_at)`
  - `rotate_refresh(raw_refresh: str) -> TokenPair`

- [ ] **Step 1: Failing tests for hash + rotate**

```python
def test_argon2id_roundtrip():
    from astloom_auth.hashing import hash_secret, verify_secret
    encoded = hash_secret("refresh-raw-value")
    assert verify_secret("refresh-raw-value", encoded)
    assert not verify_secret("wrong", encoded)

def test_refresh_rotate_invalidates_old(store):
    from astloom_auth.refresh import issue_token_pair, rotate_refresh
    pair1 = issue_token_pair(store, tenant="t", workspace="w", project="p")
    pair2 = rotate_refresh(store, pair1.refresh)
    # old refresh must fail
    import pytest
    with pytest.raises(ValueError):
        rotate_refresh(store, pair1.refresh)
    assert pair2.access != pair1.access
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement hashing + in-memory store for unit tests; Postgres table follow-up in same task if profile service already has DB access, else memory + interface for Phase 1 wiring**

In-memory is enough to green unit tests; durable store must land before bootstrap goes live (Task 3).

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit when asked**

---

### Task 3: Auth HTTP routes + Bearer on connect APIs

**Files:**
- Modify: project-profile connect routers (bootstrap/status/ingest/sources)
- Create: `POST /api/v1/auth/refresh` (prefer project-profile or mcp-gateway — **choose project-profile** as SoT for connect identity)
- Modify: [`code_graph_service/api/auth.py`](backend/services/code-graph-service/src/code_graph_service/api/auth.py) to accept access tokens from the unified verifier (not only static env equality), keeping env static as lab fallback
- Test: `tests/backend/services/project-profile-service/test_auth_refresh.py` (or nearest existing test package path)

**Interfaces:**
- Consumes: Task 2 `issue_token_pair`, `rotate_refresh`, `verify` access
- Produces: bootstrap response fields `access_token`, `refresh_token`, `ca_pem`, `expires_in`

- [ ] **Step 1: Write failing TestClient tests** — bootstrap without secret → 401; with secret → pair; refresh rotates; connect route without Bearer → 401 when enforcement on

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Wire Depends() Bearer verification; mint pair on successful bootstrap; refresh route**

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit when asked**

---

### Task 4: Client HTTPS enforce + auto-refresh

**Files:**
- Modify: [`connect_config.py`](backend/packages/astloom_cli/connect_config.py) — reject `http://` for `url` / `mcp_http_url` / `graph_url` unless `ASTLOOM_ALLOW_INSECURE_HTTP=1`
- Modify: remove/ignore `server.ssh` load for product path (warn then Phase 3 delete)
- Modify: [`client_push.py`](backend/packages/astloom_cli/connect_flow/client_push.py) + connect HTTP helpers — on 401, refresh once and retry
- Store refresh via `auth.refresh_token_env` / local secure file under `.astloom/` mode `0600`
- Test: `tests/backend/tools/astloom-cli/test_connect_https_and_refresh.py`

- [ ] **Step 1–4:** TDD as above for scheme reject + single refresh retry
- [ ] **Step 5:** Commit when asked

---

### Task 5: Edge recipe + install hook for auto-certs

**Files:**
- Create: `scripts/install/tls_edge/Caddyfile.example` (or nginx conf)
- Modify: install stage that starts MCP HTTP / compose to call `ensure_tls_material` and export cert paths
- Doc snippet in design already; update [39-local-install-runbook](../../08-software-engineering-architecture/39-local-install-runbook.md) lightly

- [ ] Write example Caddyfile binding `{$ASTLOOM_PUBLIC_HOSTNAME}` with `tls {$CERT} {$KEY}`
- [ ] Install script ensures certs before starting edge
- [ ] Test: unit already covers cert module; add install dry-run test if pattern exists under `tests/backend/tools/install/`

---

### Task 6: HTTPS purge + status; HTTPS-only wizard

**Files:**
- Add control endpoints for purge/status (project-profile)
- Rewrite [`connect_wizard.py`](backend/packages/astloom_cli/connect_wizard.py) for HTTPS URL + bootstrap secret (no SSH)
- Delete SSH MCP fragment usage from [`run_connect`](backend/packages/astloom_cli/connect_flow/run.py)
- Content-push: delete `_run_ingest_push_ssh` / SSH hash path

- [x] TDD for wizard writing yaml without `ssh:`
- [x] TDD for purge/status HTTP client paths
- [x] Remove SSH branches from client sync entry

Note: `materialize_ssh_mcp_fragment` usage in `run_connect` was intentionally kept
(SSH stdio MCP fallback for existing SSH-only installs) — full removal is Task 7,
per explicit instruction not to delete all SSH code in Task 6.

---

### Task 7: Delete SSH from product

**Files:**
- Delete or gut: `ssh_bootstrap.py`, `connect_flow/ssh.py`, SSH remote register/purge/sync helpers
- Update docs 36/40/41/41-continued; retire SSH-normative doc 40 or mark historical
- Update `.cursor/rules/astloom-source-server-path.mdc` (already content-push; ensure no SSH stage)
- CI/unit: `test_connect_schema_rejects_ssh_key`

- [ ] `rg` gate in test: product packages must not call `ssh_bootstrap` / `materialize_ssh_mcp_fragment`
- [ ] Docs pass Full-tier bump

---

### Task 8: Hardening

**Files:**
- Refresh reuse → revoke family *(historical — refresh removed; use access-token `revoke(jti)` instead)*
- Rate limit bootstrap/refresh (simple in-process or edge)
- Cert renew-before-expiry in `tls_certs.py`
- Security regression tests listed in design Verification section

---

### Task 9: Access-token hash-at-rest registry (shipped)

**Files:**
- Create: `backend/packages/astloom_auth/token_registry.py`
- Modify: `backend/packages/astloom_auth/tokens.py` (`mint_and_register_access_token`, `verify_registered_access_token`)
- Modify: `usage_profile.mcp_tokens` — always embed `jti` on mint; return in verify claims
- Modify: project-profile `build_app` / bootstrap / `http_auth` — Postgres or in-memory registry
- Tests: `tests/backend/packages/astloom_auth/test_token_registry.py`, update `test_auth_refresh.py`

**Interfaces:**
- `hash_access_token(raw) -> sha256_hex` (never log raw)
- `AccessTokenRegistry.register` / `assert_active` / `revoke`
- Table `project_profile.access_tokens` — **no raw-token column**

- [x] Unit: register + assert; wrong hash fails; revoke fails; plaintext absent from store
- [x] Wire bootstrap mint through registry; Bearer verify through registry
- [x] Design doc normative section + security bar

---

## Execution notes

- Prefer Task 1 → 2 → 3 → 4 before deleting SSH (Task 7), so HTTP path is safer than today’s dual stack.
- Do not commit unless the user explicitly asks.
- After this plan file is reviewed, execute with subagent-driven-development or inline executing-plans.

## Spec coverage checklist

| Design requirement | Task |
| --- | --- |
| Auto TLS certs | 1, 5, 8 |
| Access token (no refresh; re-bootstrap) | 2→9 (refresh removed), 3, 4 |
| Access token SHA-256 at rest + revoke | 9 |
| Argon2id floors (bootstrap secret) | 2 |
| Bearer on connect APIs | 3, 9 |
| HTTPS client enforce | 4 |
| Edge recipe | 5 |
| Purge/status/wizard HTTPS | 6 |
| Delete SSH | 7 |
| Rate limit / cert renew / regressions | 8 |

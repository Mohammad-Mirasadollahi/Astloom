# astloom_sdk

Path: `backend/packages/astloom_sdk`

## Purpose

Installable Python SDK (`astloom-sdk` / import `astloom_sdk`) with HTTP GET/POST,
correlation id, and idempotency key helpers.

## Boundaries

- May: join public `/api/v1` paths, set transport headers, use injectable `httpx` clients.
- Must not: import service internals, embed credentials/secret values, hard-code ports or tenant ids.

## Start here

1. `client.py` — `AstloomClient`, `SdkError`
2. `__init__.py` — public exports
3. `docs/05-interoperability-ecosystem/11-sdk-release-and-adapter-harness.md`

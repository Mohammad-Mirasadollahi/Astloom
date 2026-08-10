# Typescript

Path: `backend/packages/sdk/typescript`

## Purpose

TypeScript SDK package `@astloom/sdk` with GET/POST, correlation, and idempotency parity
to Python `astloom_sdk`.

## Boundaries

- May: public HTTP helpers for Astloom APIs.
- Must not: embed secret values, import backend service internals.

## Start here

1. `src/client.ts` — `AstloomClient`
2. `package.json` — name `@astloom/sdk`
3. `docs/05-interoperability-ecosystem/11-sdk-release-and-adapter-harness.md`

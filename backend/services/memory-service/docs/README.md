# Memory Service Docs

Path: `backend/services/memory-service/docs`

## Purpose

Service-local contract and implementation notes for the Phase 2 Memory and Context vertical slice.

## Contents

- `phase-2-api-contract.md` — HTTP commands, queries, scope headers, and outbox event types.

## Status

Active. Matches `src/memory_service/` (InMemoryStore for tests; PostgreSQL via `ASTLOOM_MEMORY_SERVICE_DATABASE_URL` at runtime).

# Core Data Service Docs

Path: `backend/services/core-data-service/docs`

## Purpose

Service-local contract and implementation notes for the Phase 1 Core Data vertical slice.

## Contents

- `phase-1-api-contract.md` — HTTP commands, queries, scope headers, and outbox expectations.

## Status

Active. Matches `src/core_data_service/` (InMemoryStore for tests; PostgreSQL via `ASTLOOM_CORE_DATA_DATABASE_URL` at runtime).

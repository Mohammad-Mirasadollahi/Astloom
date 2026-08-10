# Resilience Primitives

Path: `backend/packages/shared-kernel/resilience`

## Purpose

Bounded retry and timeout defaults for Astloom operations.

## Implementation (GAP-A02)

Machine catalog: `backend/configs/governance/sync-async-boundaries.json`.

Load via `architecture_governance`:

- `retry_policy(operation_id=None)` — default retry (max_attempts, backoff_seconds)
- `timeout_seconds(operation_id)` — per-operation timeout
- `operation_mode(operation_id)` — `sync` | `async`

Retries must be bounded, observable, and idempotency-aware. Infrastructure resilience must not hide business failures.

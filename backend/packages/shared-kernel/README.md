# Shared Kernel

Path: `backend/packages/shared-kernel`

## Purpose

Stable cross-cutting primitives allowed across modules.

## Modular Boundary

This directory is part of the Astloom backend modular architecture. It must expose behavior through documented contracts, public interfaces, configuration, or events. It must not import private internals from sibling modules.

## Allowed Contents

- README and design notes for this boundary.
- Source, configuration, fixtures, tests, or generated artifacts that belong to this boundary.
- Subdirectories that follow the backend structure standard.

## Rules

- Keep ownership clear and local to this boundary.
- Do not hard-code ports, credentials, tenant IDs, project IDs, model names, provider endpoints, or feature behavior.
- Prefer dependency inversion: domain and application logic should not depend on infrastructure implementation details.
- Use shared packages only for stable contracts or cross-cutting primitives.
- Add or update tests and documentation when this boundary receives implementation code.

## Status

Minimal implementation under `shared_kernel/` (results, errors, time, validation, config loaders for technology and environment profiles).


## Standard Primitive Areas

- `dependency-injection/` for DI and composition-root primitives.
- `validation/` for deterministic validation helpers.
- `results/` for Result, typed error, and problem-detail primitives.
- `time/` for clock and deterministic time primitives.
- `resilience/` for retry, timeout, circuit breaker, and idempotency helpers.
- `testing/` for fake clocks, deterministic ids, builders, and contract-test helpers.

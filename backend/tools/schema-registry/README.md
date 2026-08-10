# Schema Registry

Path: `backend/tools/schema-registry`

## Purpose

Repository-directory schema catalog for Astloom contracts (GAP-008). Normative
decision:
[`docs/09-platform-governance-operations/12-schema-registry-architecture.md`](../../../docs/09-platform-governance-operations/12-schema-registry-architecture.md).

## Shape (v1)

- **Not** a runtime microservice.
- **Not** database-backed.
- Authoritative schemas: `backend/configs/**/*.schema.json` (and peers).
- Discovery index: `catalog.json` in this directory.

## Files

| File | Role |
|------|------|
| `catalog.json` | Machine-readable index (id, path, owner, status, compatibility) |
| `README.md` | Operator / agent entry |

## Rules

- Add a catalog entry whenever a new first-party JSON Schema ships.
- Keep ownership clear; do not hard-code credentials or tenant IDs.
- Validate examples in unit tests (see `tests/backend/tools/schema-registry/` and
  `tests/backend/configs/`).

## Status

Active for v1 discovery. Compatibility automation remains pytest-based; a
networked registry requires a new ADR.

# Config

Path: `backend/services/core-data-service/config`

## Purpose

Service-specific configuration schema and templates. Parent service: `services/core-data-service`.

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

Active. `core-data-service.example.env` documents the required PostgreSQL connection URL.

## Runtime Configuration

- `ASTLOOM_CORE_DATA_DATABASE_URL` is required at service composition time.
- The URL must use `postgresql://` or `postgresql+psycopg://`; other database schemes fail startup.
- Containers should use the Compose hostname `postgres` and internal port `5432`.
- Host-run services should use the configured `ASTLOOM_POSTGRES_PORT`, documented as `32232` by default.
- Credentials must come from local secret configuration and must not be committed.

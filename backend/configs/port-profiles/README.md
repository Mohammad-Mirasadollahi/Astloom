# Port Profiles

Path: `backend/configs/port-profiles`

## Purpose

Development and deployment port profile templates.

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

Phase 8 profile implemented: `astloom-dev.json` loaded by `backend/packages/port_profile/`.


## Required Local Port Keys

New local services must use Astloom-specific non-default host ports. Suggested local keys:

```text
ASTLOOM_ADMIN_PORT=32101
ASTLOOM_API_PORT=32100
ASTLOOM_POSTGRES_PORT=32232
ASTLOOM_NEO4J_BOLT_PORT=32287
ASTLOOM_NEO4J_HTTP_PORT=32474
ASTLOOM_REDIS_PORT=32379
ASTLOOM_OBJECT_STORE_API_PORT=32390
ASTLOOM_OBJECT_STORE_CONSOLE_PORT=32391
ASTLOOM_BROKER_PORT=32160
ASTLOOM_OTEL_COLLECTOR_PORT=32418
ASTLOOM_GRAFANA_PORT=32300
```

These are documentation defaults, not hard-coded constants. They must be overrideable per developer and validated before startup.

Do not change existing port keys or values when adding new services unless the task explicitly requests a migration.


## Database Baseline

PostgreSQL is the only required local database service. Use:

```text
ASTLOOM_POSTGRES_PORT=32232
ASTLOOM_NEO4J_BOLT_PORT=32287
ASTLOOM_NEO4J_HTTP_PORT=32474
ASTLOOM_REDIS_PORT=32379
```

Do not add another product for an already assigned role without a formal ADR. PostgreSQL, Neo4j, and Redis ports must remain configurable and non-default.

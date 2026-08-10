# Compose

Path: `backend/deployments/compose`

## Purpose

Docker Compose or local orchestration boundaries.

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

Active PostgreSQL + Neo4j foundation. `compose.yaml` provisions PostgreSQL 18 with pgvector and Neo4j 5 community on configurable non-default host ports. Database files bind-mount under `ASTLOOM_DATA_ROOT` (default sibling `<install>-data`, e.g. `/opt/Astloom-data/postgres` and `…/neo4j`). PostgreSQL initializes service-owned schemas; Neo4j constraints are applied by `code-graph-service` when `ASTLOOM_CODE_GRAPH_STORE=neo4j`.


## Astloom Local Compose Policy

Local infrastructure services must be started through Docker Compose profiles or an equivalent local container orchestration profile. Do not require developers to install PostgreSQL, Neo4j, Redis, object storage, brokers, or observability tools directly on the host for normal development. Infrastructure services must use Compose profiles when enabled.

Compose profiles should be additive:

- `core` for PostgreSQL with pgvector, Neo4j, and object storage.
- `app` for the MCP HTTP gateway application container (built from `/opt/astloom-wheelhouse`).
- `observability` for OpenTelemetry, metrics, logs, and dashboards when enabled.
- `all` for all approved local infrastructure services.

Additional database profiles require a formal ADR before they can become part of the baseline.

New services must use non-default host ports from `backend/configs/port-profiles/`. Do not change existing service ports unless an explicit migration is requested.

Copy `postgres.example.env` (and optionally `neo4j.example.env`) to an untracked environment file, set local passwords, and run:

```bash
docker compose --env-file <environment-file> -f backend/deployments/compose/compose.yaml --profile core up -d postgres neo4j
```

Wait for health with a **hard timeout** (default 300s / 5 minutes; do not spin forever).
Progress lines name Compose services (for example `postgres: starting`), not raw container IDs:

```bash
backend/deployments/compose/wait-healthy.sh --timeout 300 astloom-postgres-1 astloom-neo4j-1
# Example progress:
#   Checking health for: postgres, neo4j
#   Waiting for databases (285s left): postgres: starting, neo4j: ready
#   OK: all healthy (postgres, neo4j)
```

Exit codes: `0` healthy, `1` timeout, `2` missing/exited/restart loop. Agents must stop on non-zero instead of chaining another sleep loop after pytest.

Code-graph-service defaults to the **Neo4j** structural store. To roll back to the PostgreSQL projection:

```bash
ASTLOOM_CODE_GRAPH_STORE=postgres
ASTLOOM_CODE_GRAPH_DATABASE_URL=postgresql://astloom:<local-secret>@127.0.0.1:32232/astloom
```

Neo4j defaults (when unset, URI defaults to the port profile Bolt address):

```bash
ASTLOOM_CODE_GRAPH_STORE=neo4j
ASTLOOM_NEO4J_URI=bolt://127.0.0.1:32287
ASTLOOM_NEO4J_USER=neo4j
ASTLOOM_NEO4J_PASSWORD=<local-secret>
```

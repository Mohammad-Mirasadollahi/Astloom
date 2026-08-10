---
doc_id: as.doc.stack.local-venv-docker-and-port-policy
title: 06 - Local Venv, Docker, And Port Policy
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the local development runtime policy for Astloom. Python
  dependencies must be installed inside a project virtual environment, infrastructure services
  must run through Docker Compose or an equivalent container orchestration profile, and every
  newly exposed .
tags:
- standard
- stack
phase: 13-technology-stack-and-platform-decisions
canonical_path: docs/13-technology-stack-and-platform-decisions/06-local-venv-docker-and-port-policy.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 06 - Local Venv, Docker, And Port Policy

## Purpose

This document defines the local development runtime policy for Astloom. Python dependencies must be installed inside a project virtual environment, infrastructure services must run through Docker Compose or an equivalent container orchestration profile, and every newly exposed development port must avoid default vendor ports.

## Python Virtual Environment Rule

All Python package installation for Astloom development must happen inside the project virtual environment.

Required local path:

```text
/root/Astloom/.venv
```

Rules:

- Do not install backend dependencies into the global Python interpreter.
- Do not use system Python site-packages for Astloom service dependencies.
- Backend services, tools, generators, tests, workers, and scripts must use `/root/Astloom/.venv` unless a specific CI container profile provides an isolated environment.
- The virtual environment must be reproducible from locked dependency manifests when implementation begins.
- Bootstrap automation must create the virtual environment if it does not exist.
- Bootstrap automation must validate that commands are running inside the virtual environment before installing packages.

Expected activation pattern:

```text
python -m venv /root/Astloom/.venv
. /root/Astloom/.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

The exact dependency files may change during implementation, but installation must remain isolated.

## Docker Service Rule

Local infrastructure services must run through Docker Compose profiles or an equivalent local container orchestration profile.

This includes:

- PostgreSQL with pgvector enabled.
- Neo4j for the code graph.
- Redis when cache, coordination, locks, rate limits, or ephemeral job state are enabled.
- S3-compatible object storage when artifact storage is needed.
- durable broker or queue infrastructure when enabled.
- observability services when enabled.

Do not require developers to install PostgreSQL, Neo4j, Redis, object storage, brokers, or observability tools manually on the host machine for normal Astloom development.

PostgreSQL is also required for persistence integration tests. Do not substitute a different embedded SQL engine for local convenience. Unit tests should use injected in-memory fakes when real persistence behavior is outside the test scope.

## Application Service Rule

During early development, Python/FastAPI application services may run from `/root/Astloom/.venv` for fast iteration, while infrastructure dependencies run in Docker. When service containers are introduced, they must use Docker images and Compose profiles with non-default ports.

The intended progression is:

1. infrastructure services in Docker Compose.
2. backend services running from `.venv` during rapid development.
3. backend services containerized through Docker profiles for integration testing.
4. production deployment through Kubernetes or another production orchestration profile.

## Non-Default Port Rule

New local services must not use vendor defaults as Astloom development host ports. Host ports must come from `backend/configs/port-profiles/` and must be overrideable.

Examples of vendor defaults that must not be used directly as Astloom development host ports:

- PostgreSQL `5432`
- Neo4j Bolt `7687`
- Neo4j HTTP `7474`
- Redis `6379`
- MinIO API `9000`
- MinIO console `9001`
- FastAPI/Uvicorn `8000`
- Next.js `3000`

Recommended Astloom local host ports:

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

These values are documentation defaults only. They must remain configurable and validated before startup.

## Compose Profile Rule

Docker Compose must be profile-driven. Example profiles:

- `core`: PostgreSQL with pgvector, Neo4j, and object storage required for normal backend integration.
- `app`: MCP HTTP gateway application container (built from `/opt/astloom-wheelhouse`; see [43-app-docker-and-wheelhouse-runbook.md](../08-software-engineering-architecture/43-app-docker-and-wheelhouse-runbook.md)).
- `cache`: Redis for cache, coordination, rate limits, locks, and ephemeral job state.
- `broker`: durable message broker when asynchronous workflow execution requires one beyond Redis coordination.
- `observability`: OpenTelemetry collector, metrics, logs, dashboards.
- `all`: all local infrastructure services.

Implementation must not bring up every heavy service by default unless the selected profile requires it. Neo4j remains the approved graph product even when a profile temporarily disables graph features for a narrow unit test.

The implemented PostgreSQL profile is defined in `backend/deployments/compose/compose.yaml`. It uses the configurable host port `ASTLOOM_POSTGRES_PORT`, requires `ASTLOOM_POSTGRES_PASSWORD`, enables pgvector and pg_trgm, and applies service-owned initialization migrations on a new volume. PostgreSQL 18 data volumes must be mounted at `/var/lib/postgresql`.

## Preflight Rule

Bootstrap must run preflight checks before starting services:

- verify Docker is available.
- verify Compose is available.
- verify `/root/Astloom/.venv` exists or create it.
- verify Python commands use `.venv`.
- verify required host ports are available.
- verify PostgreSQL can enable pgvector.
- verify Neo4j Bolt and HTTP ports are reachable when the graph profile is enabled.
- verify Redis health when the cache profile is enabled.
- write a startup evidence report with resolved ports and enabled profiles.

## Do Not Touch Existing Services Rule

When adding a new local service, do not change old service ports, old profiles, or old assumptions unless the task explicitly asks for migration. Add new configuration keys and document them. Existing values should remain stable to avoid breaking developers.

## Acceptance Criteria

Local runtime setup is acceptable when Python dependencies are isolated in `/root/Astloom/.venv`, infrastructure services start through Docker Compose profiles, new host ports are non-default and configurable, preflight catches conflicts before startup, and the resolved runtime configuration is visible to developers.

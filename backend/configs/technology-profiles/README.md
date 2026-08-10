# Technology Profiles

Path: `backend/configs/technology-profiles`

## Purpose

Stores future environment-specific technology profile templates for Astloom. Profiles define which data stores, brokers, cache layers, vector backends, analytics stores, observability endpoints, and deployment modes are enabled.

## Expected Profile Fields

- frontend framework profile: Next.js settings, API base URLs, generated client settings.
- backend API profile: FastAPI runtime settings, worker settings, OpenAPI generation settings.
- PostgreSQL profile: DSN reference, pool settings, migration settings, required extensions.
- RAG profile: pgvector settings, embedding dimensions, index strategy, retrieval thresholds.
- Neo4j profile: graph schema version, Bolt URI, database name, auth reference, traversal limits, and graph index settings.
- Redis profile: enabled flag, TTL defaults, cache namespaces, lock TTLs, rate-limit windows, and connection settings.
- PostgreSQL profile: pgvector, pg_trgm, full-text search, reporting partitions, and materialized view settings.
- messaging profile: broker type, topics, retry policy, dead-letter settings.
- observability profile: OpenTelemetry, metrics, logs, traces, dashboard endpoints.

## Rule

Technology profiles must be data-driven. Do not hard-code technology endpoints, credentials, ports, model names, scoring weights, queue names, or analytics thresholds in application code.


## Local Runtime Fields

Technology profiles should include local runtime fields such as:

```text
venv_path=/root/Astloom/.venv
compose_profiles=core
port_profile=local-non-default
install_python_dependencies=true
start_infrastructure_with_docker=true
```

Default profile: `default.json`, loaded by `backend/packages/shared-kernel/shared_kernel/config.py`.

Approved service products are PostgreSQL for operational data, pgvector for RAG vectors, Neo4j for code graph, and Redis for optional ephemeral cache/coordination. Additional products for the same role require a formal ADR.

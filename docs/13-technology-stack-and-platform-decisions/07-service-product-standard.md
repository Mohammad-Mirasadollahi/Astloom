---
doc_id: as.doc.stack.service-product-standard
title: 07 - Service Product Standard
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the Astloom product-per-role standard. The architecture should
  use one approved product for each infrastructure responsibility so implementers do not mix
  multiple competing technologies for the same concern.
tags:
- standard
- stack
phase: 13-technology-stack-and-platform-decisions
canonical_path: docs/13-technology-stack-and-platform-decisions/07-service-product-standard.md
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

# 07 - Service Product Standard

## Purpose

This document defines the Astloom product-per-role standard. The architecture should use one approved product for each infrastructure responsibility so implementers do not mix multiple competing technologies for the same concern.

This does not mean every workload belongs in PostgreSQL. It means every role has a clear owner.

## Approved Product Map

| Responsibility | Approved Product | Mandatory Role Boundary |
| --- | --- | --- |
| Operational database | PostgreSQL | durable relational data, transactional records, project isolation, rules, memory records, metadata records, audit references, report source data |
| RAG vector retrieval | PostgreSQL with pgvector | vector embeddings and semantic retrieval with relational filters, project isolation, and access-policy filtering |
| Code graph | Neo4j | graph-native code relationships, dependency traversal, impact analysis, call/import/inheritance traversal, graph-guided code context |
| Cache and ephemeral coordination | Redis, when required | TTL cache, rate limits, locks, deduplication windows, transient job state, lightweight coordination |
| Large artifact storage | S3-compatible object storage | evidence bundles, exports, diagnostics, logs, generated documents, large snapshots |
| Observability | OpenTelemetry-compatible stack | traces, metrics, logs, correlation ids, service health, evidence reports |
| LLM gateway | LiteLLM | unified chat/completions, structured outputs, and provider-backed embeddings initiated by Astloom; see `09-litellm-llm-gateway.md` |

## PostgreSQL Standard

PostgreSQL is the primary durable database. It owns business records and relationally governed state:

- users, projects, workspaces, project groups, and isolation boundaries.
- tasks, tickets, agent activity, decisions, approvals, and audit references.
- memory records, rules, common context, profiles, configuration, and preferences.
- document metadata, source metadata summaries, drift findings, and evidence references.
- RAG embedding tables through pgvector.
- report source data, aggregate tables, partitions, and materialized views.

PostgreSQL must not be used as a replacement for Neo4j graph traversal when graph-native relationships are the core query shape.

PostgreSQL is the only approved relational database for runtime, development persistence, integration tests, live tests, staging, and production. SQLite is explicitly excluded from service adapters and test persistence because it does not validate PostgreSQL migrations, concurrency, JSONB, constraints, or transaction behavior. Unit tests should use injected in-memory fakes instead of another SQL product.

Services may share a PostgreSQL cluster but must retain service-owned schemas, migrations, access boundaries, and credentials. Core Data currently owns `core_data`; Memory currently owns `memory`. Cross-service access to private tables is forbidden.

## pgvector Standard

pgvector is the approved RAG vector technology. It should store embeddings that need to be filtered by:

- project id.
- project group id.
- access policy.
- source type.
- freshness.
- confidence.
- lifecycle state.
- common context scope.

A separate vector database is not part of the baseline. It requires an ADR with measured evidence that pgvector cannot meet the target workload.

An optional **in-process ANN acceleration replica** (not a second SoR) is governed by `08-turbovec-ann-acceleration-integration.md`. That ADR allows [turbovec](https://github.com/RyanCodrai/turbovec) behind a `VectorIndexPort` while PostgreSQL+pgvector remains the durable embedding store. Enabling it still requires the measured gates in that ADR.

## Neo4j Standard

Neo4j is the approved code graph product. It owns graph-native records and traversal behavior:

- repositories, files, modules, packages, classes, methods, functions, API endpoints, document anchors, owners, and rules.
- relationships such as CONTAINS, IMPORTS, CALLS, EXTENDS, IMPLEMENTS, OWNS, DOCUMENTED_BY, AFFECTS, DEPENDS_ON, USES_RULE, and VIOLATES_RULE.
- impact analysis for changed files, changed functions, API contract changes, rule changes, and documentation drift.
- graph-guided retrieval before source reads.
- graph-guided code generation context.

Neo4j must not be used as the operational database or as the durable source of truth for business state.

## LiteLLM Standard

LiteLLM is the approved **LLM gateway** for Astloom-initiated model calls. It owns:

- unified chat / completion requests across cloud and local providers,
- provider-backed embedding generation when a routing profile selects a real embedding model,
- model alias resolution for `ModelRoutingProfile` entries,
- optional shared LiteLLM proxy deployment when operators need a network gateway.

Application and domain layers must depend on an LLM port, not on vendor SDKs. Direct use of OpenAI, Anthropic, or other provider SDKs for model calls from Astloom services is forbidden without an ADR that replaces this product-per-role decision.

Normative detail: `09-litellm-llm-gateway.md`.

## Redis Standard

Redis is approved only when the system needs fast ephemeral behavior. Valid use cases include:

- cache entries with TTL.
- rate-limit windows.
- distributed locks with expiration.
- temporary idempotency and deduplication windows.
- short-lived job progress.
- transient coordination between agents or workers.

Redis must not contain durable business data, long-term memory, project source of truth, audit records, permanent rules, or graph truth.

## Docker Infrastructure Standard

All infrastructure services other than the Astloom source tree must run through Docker Compose or an equivalent orchestration profile for local development and integration testing.

This includes:

- PostgreSQL with pgvector.
- Neo4j.
- Redis when enabled.
- S3-compatible object storage.
- broker infrastructure when enabled.
- OpenTelemetry collector, metrics, logs, and dashboard tools when enabled.

The source project remains editable on the host filesystem. Application services may run from `/root/Astloom/.venv` during early development, but infrastructure dependencies should not require manual host installation.

## Approved Local Development Ports

All ports must be configurable and must avoid vendor defaults.

```text
ASTLOOM_API_PORT=32100
ASTLOOM_ADMIN_PORT=32101
ASTLOOM_POSTGRES_PORT=32232
ASTLOOM_NEO4J_BOLT_PORT=32287
ASTLOOM_NEO4J_HTTP_PORT=32474
ASTLOOM_REDIS_PORT=32379
ASTLOOM_OBJECT_STORE_API_PORT=32390
ASTLOOM_OBJECT_STORE_CONSOLE_PORT=32391
ASTLOOM_BROKER_PORT=32160
ASTLOOM_WORKER_METRICS_PORT=32180
ASTLOOM_OTEL_COLLECTOR_PORT=32418
ASTLOOM_GRAFANA_PORT=32300
ASTLOOM_LITELLM_PORT=32400
```

Vendor defaults such as PostgreSQL `5432`, Neo4j `7687` and `7474`, Redis `6379`, FastAPI `8000`, Next.js `3000`, and MinIO `9000` or `9001` must not be used as Astloom development host ports.

## Unsupported Technology Rule

Do not choose technologies that are unmaintained, end-of-life, deprecated, or unsupported by their active ecosystem. Every selected technology must have:

- active maintenance.
- security update path.
- production adoption.
- supported client libraries for Python and TypeScript where relevant.
- documented upgrade path.

## Exception Rule

Changing an approved product or adding a second product for the same role requires a formal architecture decision record. The ADR must include:

- the role being changed.
- current approved product.
- measured limitation or requirement.
- why configuration, schema design, indexing, batching, scaling, or operational tuning cannot solve the problem.
- data ownership model.
- integration and migration plan.
- rollback plan.
- security and backup plan.
- test strategy.
- operational cost.
- approval from the architecture owner.

## Acceptance Criteria

The stack is acceptable when PostgreSQL owns durable operational data, pgvector owns RAG vector retrieval, Neo4j owns code graph traversal, Redis is used only for justified ephemeral workloads, infrastructure services run through Docker profiles, ports are non-default and documented, and unsupported technologies are excluded.

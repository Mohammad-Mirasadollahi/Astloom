---
doc_id: as.doc.sea.data-and-persistence-engineering
title: 09 - Data And Persistence Engineering
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how Astloom should engineer persistence, storage ownership,
  migrations, indexes, graph data, retention, and data access. The goal is to keep data reliable,
  auditable, and owned by the correct module.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/09-data-and-persistence-engineering.md
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

# 09 - Data And Persistence Engineering

## Purpose

This document defines how Astloom should engineer persistence, storage ownership, migrations, indexes, graph data, retention, and data access. The goal is to keep data reliable, auditable, and owned by the correct module.

Astloom stores operational records, memory, code graph data, documentation anchors, rules, events, audit evidence, and configuration. These data types have different consistency, retention, query, and performance requirements.

## Data Ownership Rules

Every persistent record must have one owning service.

Ownership means:

- the service defines the schema.
- the service controls writes.
- the service owns migrations.
- the service defines retention behavior.
- the service exposes public APIs, events, or projections for consumers.
- other services do not read or write the owning service database directly.

## Store Types

Astloom may need multiple store types.

| Store Type | Primary Use | Owning Areas |
| --- | --- | --- |
| relational database (PostgreSQL) | work records, tasks, decisions, config, audit indexes | core-data, config, audit, memory metadata |
| Neo4j code graph | symbols, typed relationships, impact traversal | code-graph (Postgres projection = rollback only) |
| object storage | large evidence bundles, logs, exports, snapshots | audit, code-graph |
| PostgreSQL pgvector | durable embeddings for memory and code retrieval | memory, code-graph |
| Redis (optional) | TTL cache, locks, rate limits, ephemeral coordination | platform packages |
| message broker storage | event delivery, retry, dead-letter | broker |

The exact technology can change, but ownership and access rules should remain stable. The authoritative entity→store matrix is `../13-technology-stack-and-platform-decisions/13-storage-ownership-matrix.md`.

## Persistence Boundaries

Services should access persistence through repositories or data access interfaces owned by the service.

Allowed:

- core-data-service writes Task through TaskRepository.
- memory-service reads MemoryItem through MemoryRepository.
- code-graph-service writes Symbol and CodeEdge through graph repositories.
- docs-sync-service asks code-graph-service for symbol impact through public API or event projection.

Forbidden:

- rule-engine-service reading core-data tables directly.
- admin-console querying service databases directly.
- docs-sync-service writing code graph nodes without a graph contract.
- adapter-service modifying Task status without core-data-service command handling.

## Transaction Strategy

Local transactions should protect invariants inside one service boundary.

Cross-service workflows should use events, idempotency, and compensating actions instead of distributed transactions.

Recommended approach:

1. validate command.
2. load aggregate.
3. apply domain operation.
4. persist state and pending event in the same local transaction when possible.
5. publish event through outbox relay.
6. consumers process event idempotently.
7. failures go to retry or dead-letter with correlation metadata.

## Outbox Pattern

Services that produce events after state changes should use an outbox pattern.

The outbox should store:

- event_id
- event_type
- event_version
- aggregate_id
- aggregate_type
- workspace_id
- payload
- correlation_id
- causation_id
- created_at
- publish_attempts
- publish_status
- last_error

This prevents state from being saved while the corresponding event is lost.

## Inbox Pattern

Services that consume events should use an inbox or processed-event registry.

The inbox should store:

- event_id
- consumer_name
- event_type
- event_version
- processed_at
- result
- failure_reason
- retry_count

This prevents duplicate event processing from creating duplicate tasks, memories, graph edges, or audit records.

## Migration Engineering

Every schema change should be treated as an engineering artifact.

A migration should include:

- owner service.
- reason.
- expected before state.
- expected after state.
- forward migration.
- rollback strategy or explicit no-rollback statement.
- data validation query.
- compatibility notes.
- deployment order.
- estimated runtime and lock risk.

Migration rules:

- never assume production data is small.
- avoid long locks during normal release windows.
- make destructive migrations two-step when possible.
- deploy code that can read old and new shapes before removing old fields.
- validate migrated data before enabling dependent features.

## Graph Persistence

The code graph should preserve semantic relationships between repositories, files, symbols, documentation, decisions, tasks, and owners.

Graph engineering rules:

- graph schema versions must be explicit.
- node identities must be stable across repeated ingestion.
- edges must include source evidence and parser version where relevant.
- stale edges should be marked or removed through a documented policy.
- large graph updates should be chunked.
- graph queries should have performance budgets.
- impact analysis should explain why each related node was returned.

Important graph node types:

- Repository
- SourceFile
- Symbol
- CodeEdge
- Document
- DocumentAnchor
- Decision
- Task
- Owner
- GraphSnapshot

Important edge types:

- CONTAINS
- DEFINES
- CALLS
- IMPORTS
- REFERENCES
- DOCUMENTS
- AFFECTS
- OWNED_BY
- SUPERSEDES

## Memory Persistence

Memory persistence should support retrieval quality, explainability, and retention.

Memory records should include:

- memory_id
- source_type
- source_ref
- workspace_id
- project_ref
- content_summary
- embedding_ref when used
- weight_factors
- final_score
- confidence
- feedback_state
- retention_class
- created_at
- updated_at
- expires_at when applicable

Weight factors must be configurable and stored with enough metadata to explain retrieval decisions later.

## Indexing Strategy

Indexes should be designed from query patterns.

Expected query patterns:

- find current open tasks by workspace and owner.
- find decisions related to a module or symbol.
- find memory items relevant to a task and project.
- find documentation anchors affected by a symbol change.
- find events by correlation ID.
- find audit records by actor and time range.
- find graph paths from changed symbol to affected files.

Index changes should include performance expectations and test queries.

## Retention And Deletion

Retention policy should be explicit by data class.

Data classes:

- operational work records.
- audit evidence.
- memory items.
- raw external payloads.
- prompt context snapshots.
- graph snapshots.
- logs and traces.
- documentation metadata.

Deletion should respect audit requirements and tenant boundaries. If a record cannot be deleted because of compliance requirements, the system should document why and support redaction or access restriction when appropriate.

## Backup And Restore

Each store should define backup and restore expectations.

Backup docs should include:

- store owner.
- backup frequency.
- retention duration.
- encryption requirements.
- restore procedure.
- restore validation.
- recovery point objective.
- recovery time objective.

Restore must be tested before production reliance.

## Acceptance Criteria

Data engineering is acceptable when:

- every persistent data type has one owner.
- migrations are documented and validated.
- cross-service workflows avoid direct database sharing.
- event outbox and inbox behavior is defined where needed.
- graph and memory persistence include explainability metadata.
- retention and deletion behavior is explicit.
- backup and restore expectations are documented and tested.


## Selected Data Technologies

Astloom should use PostgreSQL as the primary transactional system of record. PostgreSQL should also support default RAG/vector storage through pgvector when relational filtering, project isolation, access policy filtering, and lifecycle filtering are important.

Neo4j should own code graph nodes, dependency graph edges, document-code relationships, ownership relationships, and impact analysis traversal. PostgreSQL should own durable relational data, report aggregates, token usage analytics, and audit/event projections. Redis should be used only for justified ephemeral cache and coordination workloads.

S3-compatible object storage should hold evidence bundles, snapshots, exports, diagnostics bundles, large generated artifacts, and retained logs.

See `../13-technology-stack-and-platform-decisions/04-data-rag-analytics-and-storage-stack.md` for the full technology decision.


## PostgreSQL-Only Baseline

Astloom uses one approved product per role: PostgreSQL for durable operational data, pgvector for RAG vectors, Neo4j for code graph traversal, Redis for justified ephemeral cache/coordination, and object storage for large artifacts.

Adding another product for an existing role requires a formal ADR that proves the approved product cannot satisfy the measured workload after reasonable tuning and design improvements.

### Relational Runtime And Test Policy

- PostgreSQL is the only relational database allowed for runtime, local development persistence, integration tests, live tests, staging, and production.
- SQLite must not be introduced as a development adapter, test database, fallback store, CLI store, or service default. Database-specific behavior, concurrency, JSONB, migrations, constraints, and transaction semantics must be validated against PostgreSQL.
- Fast unit and transport-contract tests should inject deterministic in-memory fakes through public persistence ports. A fake must not expose SQL behavior or become a deployment option.
- Services may share one PostgreSQL deployment, but each service owns a separate schema, migrations, tables, credentials, and transaction boundary. Direct cross-service table access remains forbidden.
- The current Core Data and Memory schemas are `core_data` and `memory`. Their migrations live under the owning service directories.
- A second relational product requires a formal ADR, measured evidence, migration and rollback plans, security review, and architecture-owner approval.

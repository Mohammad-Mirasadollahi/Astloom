---
doc_id: as.doc.stack.data-rag-analytics-and-storage-stack
title: 04 - Data, RAG, Analytics, And Storage Stack
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the data and infrastructure stack for Astloom.
tags:
- standard
- stack
phase: 13-technology-stack-and-platform-decisions
canonical_path: docs/13-technology-stack-and-platform-decisions/04-data-rag-analytics-and-storage-stack.md
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

# 04 - Data, RAG, Analytics, And Storage Stack

## Purpose

This document defines the data and infrastructure stack for Astloom. The architecture uses one approved product per responsibility instead of forcing every workload into one store or allowing multiple competing products for the same role.

## Required Store Map

| Workload | Approved Baseline | Notes |
| --- | --- | --- |
| Transactional system of record | PostgreSQL | projects, tasks, decisions, rules, common context, configuration, audit indexes, metadata records, tenant/project isolation records |
| RAG vectors | PostgreSQL with pgvector | memory embeddings, document embeddings, metadata embeddings, project-scoped retrieval, access-policy-aware retrieval |
| Full-text and fuzzy search | PostgreSQL full-text search and pg_trgm | exact terms, symbols, doc anchors, names, paths, tags, glossary terms |
| Code graph | Neo4j | repositories, files, symbols, typed relationships, ownership, dependencies, call graph, import graph, documentation links, impact traversal |
| Cache and ephemeral coordination | Redis, when required | TTL cache, rate limits, locks, deduplication windows, short-lived job state, optional lightweight queue coordination |
| Analytics and reporting baseline | PostgreSQL partitions, indexes, materialized views, aggregate tables | token usage, agent activity, audit/event reporting, workflow metrics, architecture quality reports |
| Large artifacts | S3-compatible object storage | evidence bundles, logs, exports, graph snapshots, generated docs, diagnostics bundles |

## PostgreSQL Responsibilities

PostgreSQL owns durable relational Astloom data:

- tenant, workspace, project, and project-group records.
- tasks, issues, work logs, decisions, approvals, and audit references.
- memory, context bundle, common context, rule, and profile records.
- source metadata summaries that need relational filtering and governance.
- document anchors, documentation drift findings, and docs sync state.
- report source data, aggregates, and materialized views.
- idempotency keys and durable command state where required.

PostgreSQL must not become the graph traversal engine when the question is relationship-heavy and belongs to Neo4j.

## PostgreSQL-Only Relational Policy

PostgreSQL is the sole relational persistence product across runtime environments and persistence-oriented tests. SQLite and other embedded relational databases are not approved as service adapters, local-development stores, integration-test substitutes, fallbacks, or CLI persistence. Using a different SQL engine would allow migration, locking, concurrency, constraint, JSONB, and transaction differences to escape verification.

Unit tests remain infrastructure-independent by injecting deterministic in-memory fakes through application-owned ports. These fakes model service contracts, not SQL compatibility, and cannot be selected by runtime configuration.

Multiple services may use the same PostgreSQL cluster while preserving ownership through service-specific schemas and migrations. Sharing a cluster does not permit one service to read or write another service's private tables.

## Required PostgreSQL Capabilities

Use supported PostgreSQL capabilities for operational and retrieval-adjacent data:

- pgvector for vector embeddings.
- pg_trgm for fuzzy matching.
- full-text search for documents, symbols, names, and glossary terms.
- JSONB for governed flexible metadata.
- GIN/GiST indexes where appropriate.
- partitioning for high-volume records.
- materialized views and aggregate tables for reports.

## RAG With pgvector

RAG should use PostgreSQL plus pgvector by default. Retrieval must apply project isolation and access filters before semantic ranking.

RAG retrieval should combine:

1. project and access filtering from PostgreSQL.
2. full-text search from PostgreSQL.
3. pgvector similarity.
4. metadata freshness and confidence.
5. common context filtering.
6. Neo4j relationship expansion when a query depends on ownership, calls, imports, inheritance, or impact.
7. source-read escalation rules when metadata and retrieval context are insufficient.

Optional Stage-2 dense acceleration with [turbovec](https://github.com/RyanCodrai/turbovec) (`IdMapIndex` allowlist search) is defined in `08-turbovec-ann-acceleration-integration.md` and `11-turbovec-for-rag.md`. pgvector remains the durable embedding SoR; turbovec is a rebuildable replica only.

## Code Graph With Neo4j

The code graph must use Neo4j as the approved graph product. Neo4j stores graph-native structures that should not be flattened into PostgreSQL merely to avoid another service.

Recommended graph concepts:

- Repository.
- File.
- Module.
- Package.
- Class.
- Method.
- Function.
- APIEndpoint.
- DocumentAnchor.
- Rule.
- Owner.
- relationship types such as CONTAINS, IMPORTS, CALLS, EXTENDS, IMPLEMENTS, OWNS, DOCUMENTED_BY, AFFECTS, DEPENDS_ON, and VIOLATES_RULE.

Each graph node and relationship should include project id, repository id, revision id, confidence score, parser version, source span, evidence reference, created timestamp, and updated timestamp where relevant.

## Redis Responsibilities

Redis may be used when the implementation needs fast ephemeral state. Approved Redis uses include:

- cache entries with explicit TTL.
- rate-limit counters.
- short-lived locks.
- idempotency deduplication windows.
- temporary job progress.
- transient agent coordination signals.

Redis must not contain durable business records, memory source of truth, project state, audit state, rule definitions, or code graph truth.

## Analytics With PostgreSQL

Reporting should begin with PostgreSQL:

- partition high-volume event tables.
- create aggregate tables for dashboards.
- use materialized views for expensive report projections.
- schedule refresh jobs.
- index report filters.

A separate analytics database is not part of the baseline unless a future ADR proves PostgreSQL reporting cannot meet measured production requirements.

## Docker Infrastructure Rule

Infrastructure services must run through Docker Compose or an equivalent orchestration profile during local development and integration testing. This includes PostgreSQL, Neo4j, Redis when enabled, object storage, brokers, and observability services. The Astloom source tree remains on the host filesystem; infrastructure dependencies should not require manual host installation.

## Unsupported Technology Rule

Do not use unmaintained, deprecated, end-of-life, or unsupported technologies. Every selected technology must have an active security update path, supported Python and TypeScript client libraries where relevant, production maturity, and a documented upgrade path.

## Scaling Rule

Scale the approved product for its role before adding another product for the same responsibility. PostgreSQL should be tuned for relational/reporting workloads, Neo4j for graph workloads, pgvector for RAG vectors, and Redis for ephemeral cache/coordination. Introducing a second product for an existing role requires an ADR with measured evidence.

## Optional ANN Acceleration

When RAM, SIMD latency, or air-gapped local ANN matters and pgvector remains the SoR, consult `08-turbovec-ann-acceleration-integration.md` for the approved optional turbovec replica pattern (hybrid SQL/ACL allowlist → dense rerank).

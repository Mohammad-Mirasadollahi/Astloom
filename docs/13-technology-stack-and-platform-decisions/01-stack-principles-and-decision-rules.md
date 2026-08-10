---
doc_id: as.doc.stack.stack-principles-and-decision-rules
title: 01 - Stack Principles And Decision Rules
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines technology selection principles for Astloom. The stack must
  support a strong modular architecture, high-quality developer experience, reliable automation,
  RAG, code graph intelligence, project isolation, reporting, and long-term maintainability.
tags:
- standard
- stack
phase: 13-technology-stack-and-platform-decisions
canonical_path: docs/13-technology-stack-and-platform-decisions/01-stack-principles-and-decision-rules.md
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

# 01 - Stack Principles And Decision Rules

## Purpose

This document defines technology selection principles for Astloom. The stack must support a strong modular architecture, high-quality developer experience, reliable automation, RAG, code graph intelligence, project isolation, reporting, and long-term maintainability.

## Selection Principles

Technology choices must optimize for:

- strong ecosystem and long-term maintainability.
- type safety and contract-first development.
- reliable async processing and background jobs.
- excellent API and SDK generation support.
- strong observability and debugging.
- mature security patterns.
- strong test tooling.
- local development ergonomics.
- production scalability.
- clear separation between OLTP, graph, vector, cache, object storage, messaging, and analytics workloads.
- one approved product per responsibility unless an ADR proves a different need.

## Mandatory Technology Baseline

Astloom baseline technologies are:

| Area | Preferred Technology | Reason |
| --- | --- | --- |
| Web interface | Next.js | mature React framework for admin console, routing, server components, API integration, and deployment flexibility |
| Web language | TypeScript | type safety, generated clients, maintainable frontend architecture |
| Backend API | FastAPI | high-performance Python API framework, OpenAPI generation, async support, strong Pydantic integration |
| Backend language | Python | AI, automation, parsing, data pipelines, RAG, and agent ecosystem alignment |
| Operational database | PostgreSQL | durable system of record, transactions, relational integrity, JSONB, indexing, full-text search, extensions, operational maturity |
| RAG vector retrieval | PostgreSQL with pgvector | embeddings stay close to project, tenant, access-policy, lifecycle, and metadata filters |
| Code graph store | Neo4j | native graph traversal for symbols, calls, imports, inheritance, ownership, documentation links, impact analysis, and graph-guided generation |
| Cache and ephemeral coordination | Redis, when required | fast TTL data, rate limits, locks, deduplication windows, short-lived job state, and lightweight queue coordination |
| Analytics baseline | PostgreSQL partitions and materialized views | reporting starts from the system of record; a separate analytics engine requires a formal ADR |
| Object storage | S3-compatible storage | evidence bundles, exports, large artifacts, snapshots, logs, generated documents |
| Observability | OpenTelemetry-based stack | portable traces, metrics, logs, correlation ids, and vendor-neutral instrumentation |

## One Product Per Responsibility Rule

Astloom must avoid parallel technologies that solve the same responsibility. PostgreSQL must not be used as the graph database when Neo4j is the approved graph product. Neo4j must not be used as the operational database. Redis must not become durable business storage. pgvector must be used for RAG vectors unless a future ADR proves a different vector technology is necessary.

## RAG Decision Rule

Default RAG storage must use PostgreSQL plus pgvector. Retrieval must apply project isolation, access-policy filters, lifecycle filters, and metadata filters before semantic ranking.

Astloom retrieval should be hybrid:

- metadata-first retrieval for code context.
- Neo4j graph retrieval for dependencies, ownership, impact, and relationship expansion.
- pgvector retrieval for semantic similarity.
- full-text retrieval for exact terms, symbols, and documentation anchors.
- rule/common-context filtering for scope, access, and project isolation.

## Graph Decision Rule

The code graph must use Neo4j as the baseline graph store. Code graph write paths should be owned by the code-graph service. Other services may read graph-derived context through service APIs or governed query adapters, but they must not bypass ownership boundaries with unmanaged graph writes.

## Redis Decision Rule

Redis is approved only for ephemeral workloads where it creates clear value:

- cache entries with TTL.
- rate limits and quota windows.
- distributed locks with expiration.
- idempotency deduplication windows.
- short-lived job state.
- queue coordination when a dedicated broker is not required.

Redis must not store durable project state, memory records, audit records, source metadata, rule definitions, or business records.

## Versioning And Upgrade Governance

The docs should define technology families and architectural commitments, not freeze every package version. Exact versions must be pinned in implementation manifests, lockfiles, and deployment manifests. Upgrades require compatibility checks, migration notes, test evidence, and rollback instructions.

## Unsupported Technology Rule

Technologies that are unmaintained, deprecated, end-of-life, or unsupported by their active ecosystem must not be selected. Every selected technology must have active maintenance, security updates, supported client libraries, production maturity, and a documented upgrade path.

---
doc_id: as.doc.stack.index
title: 13 - Technology Stack And Platform Decisions Index
doc_type: index
status: active
schema_version: '1.0'
owner: platform-docs
summary: 'This section defines the preferred technology stack for Astloom. The goal is to
  make implementation decisions explicit before code is written and to ensure that the selected
  technologies match the documented architecture: modular backend services, admin web interface,
  metadata-.'
tags:
- index
- stack
phase: 13-technology-stack-and-platform-decisions
canonical_path: docs/13-technology-stack-and-platform-decisions/00-index.md
lifecycle_lane: current
concern_lane: onboarding
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.2
updated_at: 2026-08-10
---

# 13 - Technology Stack And Platform Decisions Index

## Purpose

This section defines the preferred technology stack for Astloom. The goal is to make implementation decisions explicit before code is written and to ensure that the selected technologies match the documented architecture: modular backend services, admin web interface, metadata-first code understanding, RAG, Neo4j-backed code graph intelligence, project isolation, automation, reporting, SDKs, and strong software engineering standards. Includes the GAP-T03 embedding lifecycle ADR (`14-embedding-lifecycle-and-refresh.md`).

## Files

- `01-stack-principles-and-decision-rules.md` defines stack selection principles, decision rules, mandatory technologies, and upgrade governance.
- `02-frontend-and-admin-console-stack.md` defines the Next.js, TypeScript, UI, API client, testing, and admin-console stack.
- `03-backend-api-and-service-stack.md` defines the Python, FastAPI, service, worker, SDK, validation, DI, and testing stack.
- `04-data-rag-analytics-and-storage-stack.md` defines the product-per-role data baseline: PostgreSQL for operational data, pgvector for RAG embeddings, Neo4j for the code graph, Redis for optional cache/coordination, object storage, reporting, and exception rules.
- `05-runtime-messaging-observability-and-deployment-stack.md` defines messaging, cache, jobs, observability, deployment, infrastructure, and operational stack choices.
- `06-local-venv-docker-and-port-policy.md` defines the local `.venv` policy, Docker Compose service policy, non-default port rules, profile strategy, and preflight requirements.
- `07-service-product-standard.md` defines the one-product-per-role standard, approved ports, Docker infrastructure rule, unsupported technology rule, and exception governance.
- `08-turbovec-ann-acceleration-integration.md` is the ADR for optional in-process [turbovec](https://github.com/RyanCodrai/turbovec) ANN acceleration beside PostgreSQL+pgvector (SoR unchanged).
- `09-litellm-llm-gateway.md` is the ADR that accepts [LiteLLM](https://docs.litellm.ai/) as the sole LLM gateway for Astloom model calls.
- `10-model-routing-profiles-with-litellm.md` specifies `ModelRoutingProfile` → LiteLLM model alias mapping, published local/cloud defaults under `backend/configs/model-routing/`, fallbacks, and stub policy (closes GAP-003).
- `11-turbovec-for-rag.md` is the engineer/agent guide for using turbovec in RAG (IdMapIndex lifecycle, hybrid allowlist, bit-width, persistence, fallback).
- `12-litellm-environment-configuration.md` is the operator reference for every LiteLLM/code-graph env variable (defaults, change impact, examples).
- `13-storage-ownership-matrix.md` pins authoritative store and owning service per entity/event class (closes GAP-001).
- `14-embedding-lifecycle-and-refresh.md` is the ADR for embedding regenerate triggers, model-change scoped re-embed, job states, tenant isolation, pgvector SoR (`vector(1024)`), and TurboVec replica sync after SoR write (closes GAP-T03).

## Mandatory Baseline

Astloom should use:

- Next.js and TypeScript for the admin web interface and web control surface.
- Python and FastAPI for backend APIs, workers, automation, parsing, RAG orchestration, and SDK-facing services.
- PostgreSQL as the primary transactional database and durable system of record.
- pgvector as the approved vector retrieval technology for RAG embeddings inside PostgreSQL.
- PostgreSQL full-text search and pg_trgm for exact and fuzzy search over operational records, documents, symbols, and metadata.
- Neo4j as the approved graph database for code graph nodes, relationships, impact traversal, dependency traversal, graph-guided retrieval, and graph-aware code generation.
- **LiteLLM** as the approved LLM gateway for chat/completions, structured judge calls, and provider-backed embeddings initiated by Astloom services (see `09-litellm-llm-gateway.md`).
- Redis only when a cache, short-lived coordination layer, rate-limit store, session helper, queue helper, or ephemeral job state store is technically needed.
- S3-compatible object storage for large artifacts, evidence bundles, exports, logs, generated documents, diagnostics bundles, and graph snapshots.
- PostgreSQL partitions, indexes, aggregate tables, and materialized views for baseline reporting and analytics.
- Docker Compose or an equivalent container orchestration profile for infrastructure services such as PostgreSQL, Neo4j, Redis, object storage, broker, and observability tools.
- No unsupported, deprecated, end-of-life, or unmaintained technology.

## Product-Per-Role Rule

Astloom must not use multiple products for the same responsibility without a formal ADR. Each infrastructure concern has one approved baseline owner: PostgreSQL for operational relational data, pgvector for RAG vector retrieval, Neo4j for graph traversal, **LiteLLM for LLM gateway calls**, Redis for optional ephemeral cache/coordination, object storage for large binary artifacts, and OpenTelemetry-compatible tooling for observability.

## Relationship To Other Sections

- `../08-software-engineering-architecture/` defines engineering standards and modular architecture.
- `../07-code-knowledge-graph/` defines Neo4j-backed code understanding and metadata-first retrieval.
- `../02-memory-and-context/` defines memory, context, scoring, and RAG-related behavior.
- `../09-platform-governance-operations/` defines operations, reporting, retention, and observability.

---
doc_id: as.doc.sea.service-boundaries-and-modules
title: Service Boundaries and Modules
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the recommended service and module boundaries for Astloom.
  The goal is to keep the system maintainable, testable, and scalable while preventing unrelated
  concerns from collapsing into one large service.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/02-service-boundaries-and-modules.md
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

# Service Boundaries and Modules

## Purpose

This document defines the recommended service and module boundaries for Astloom. The goal is to keep the system maintainable, testable, and scalable while preventing unrelated concerns from collapsing into one large service.

## Recommended Service Boundaries

### API Gateway

Owns external HTTP/API access, authentication handoff, request validation, rate limits, and routing to internal services. It should not contain business logic for memory retrieval, graph indexing, or rule evaluation.

### Core Data Service

Owns Activity, WorkLog, Decision, Issue, Task, entity lifecycle, and audit records. It is the canonical write model for structured work.

### Memory Service

Owns MemoryItems, SemanticFacts, ContextBundles, WeightProfiles, retrieval scoring, prompt packing, consolidation, and decay workflows.

### Documentation Sync Service

Owns doc indexing, YAML frontmatter validation, doc anchors, drift findings, documentation coverage, and CI gate integration.

### Code Graph Service

Owns Tree-sitter parsing, symbol extraction, hash diffing, Neo4j-backed code graph upserts, call graph relationships, embeddings through pgvector, and graph-guided code context retrieval.

### Rule Engine Service

Owns policy evaluation, deterministic pre-checks, LLM judge orchestration, risk aggregation, escalation decisions, impact maps, and human approval workflow.

### Broker Service

Owns message publication, subscriptions, delivery retries, replay, retention, and dead-letter queues.

### Adapter Service

Owns vendor-specific integration with IDEs, external agents, model providers, ticket systems, CI systems, and department tools.

### Admin and Configuration Service

Owns tenant settings, project settings, feature flags, port profiles, model routing profiles, weight profiles, retention policies, and adapter configuration.

## Dependency Direction

The dependency direction should remain stable:

```text
External Clients -> API Gateway -> Domain Services -> Storage/Infrastructure
Domain Services -> Broker Events
Domain Services -> Configuration Service
Domain Services -> Observability
```

Domain services should communicate through APIs and events. Direct database sharing between unrelated services should be avoided unless a bounded context explicitly owns the schema.

## Module Rules

- Core Data Service should not call LLMs directly.
- Memory Service should not mutate source code.
- Rule Engine should not own source parsing.
- Code Graph Service should not approve risky actions.
- Broker Service should not interpret business policy.
- Adapter Service should not bypass tenant boundaries.
- Configuration Service should be the source of runtime settings, including development ports.

## Data Ownership

Each service owns its primary data model. Other services should read through APIs, events, or materialized views.

Examples:

- Core Data owns Issues and Tasks.
- Memory owns ContextBundles and WeightProfiles.
- Code Graph owns code symbol graph and graph retrieval profiles.
- Rule Engine owns Policy and RuleEvaluation records.
- Broker owns Channel, Subscription, DeliveryAttempt, and DeadLetter records.

## Communication Patterns

### Synchronous Calls

Use synchronous calls for request-time validation, context building, small lookups, and explicit user actions.

### Asynchronous Events

Use events for indexing, documentation generation, memory consolidation, broker delivery, drift detection, impact analysis, and long-running workflows.

### Jobs and Workers

Use background workers for expensive or retryable tasks such as embeddings, AI documentation, graph indexing, and model-based review.

## Anti-Patterns

- One service owning all platform logic.
- Hard-coded ports or endpoints inside service code.
- Direct cross-service database writes.
- LLM calls inside low-level persistence modules.
- Business policy hidden inside adapters.
- CI gates that depend on non-deterministic prompts without stored evidence.

---
doc_id: as.doc.sea.engineering-best-practices-and-implementation-standards
title: 29 - Engineering Best Practices And Implementation Standards
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines implementation standards that every Astloom module must follow.
  The goal is to make engineering quality explicit before code is written.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/29-engineering-best-practices-and-implementation-standards.md
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

# 29 - Engineering Best Practices And Implementation Standards

## Purpose

This document defines implementation standards that every Astloom module must follow. The goal is to make engineering quality explicit before code is written.

These standards are not optional style preferences. They are architectural guardrails for maintainability, testability, observability, security, and long-term extensibility.

## Required Standards

Astloom implementation must follow these standards:

- Dependency Injection and explicit composition roots.
- Dependency Inversion through ports and adapters.
- Clean separation between domain, application, infrastructure, transport, and bootstrap layers.
- Configuration-driven runtime behavior.
- Typed errors, structured validation, and safe diagnostics.
- Explicit transaction boundaries, idempotency, and concurrency control.
- Deterministic testing seams for time, ids, randomness, external tools, stores, brokers, and LLM calls.
- Contract-first APIs, events, SDK surfaces, and integration adapters.
- Observability by default: logs, metrics, traces, health checks, audit records, and correlation ids.
- Security by default: least privilege, tenant isolation, secret safety, approval boundaries, and fail-closed behavior.

## Layering Standard

Each service should separate responsibilities into layers:

- Domain: entities, value objects, domain events, invariants, and pure policies.
- Application: use cases, command handlers, query handlers, workflow orchestration, and port definitions.
- Infrastructure: database adapters, broker adapters, file adapters, external API clients, model-provider clients, and parser adapters.
- Transport: HTTP, RPC, CLI, worker consumers, scheduled job entrypoints, and serializers.
- Bootstrap: dependency wiring, config loading, lifecycle management, and process startup.

Domain must not depend on application, infrastructure, transport, or bootstrap. Application may depend on domain and ports. Infrastructure implements ports. Bootstrap wires concrete implementations.

## Dependency Direction

Allowed direction:

```text
transport -> application -> domain
bootstrap -> transport/application/infrastructure
infrastructure -> application ports and shared contracts
application -> shared-kernel and contracts
```

Forbidden direction:

```text
domain -> infrastructure
domain -> DI container
application -> concrete database client
application -> provider SDK
infrastructure -> private domain mutation outside public methods
transport -> persistence tables directly
service A -> private internals of service B
```

## Best Practice Catalogue

Astloom must document and enforce these categories:

- Dependency Injection and composition root.
- Ports and adapters.
- Validation and error handling.
- Transactions, idempotency, and concurrency.
- Configuration and feature flags.
- Observability and diagnostics.
- Security and authorization boundaries.
- Contract versioning and compatibility.
- Test seams, fakes, mocks, and contract tests.
- Background jobs, retries, and dead-letter handling.
- Repository and persistence patterns.
- Domain events and outbox/inbox patterns.
- API pagination, filtering, sorting, and idempotency keys.
- Time, ids, randomness, and deterministic behavior.
- Documentation, examples, and code ownership.

## Review Enforcement

A reviewer should reject implementation that:

- creates dependencies inside business logic instead of injecting them.
- uses a service locator outside bootstrap.
- hides runtime behavior in hard-coded constants.
- catches broad errors without typed recovery or diagnostics.
- performs retries without idempotency and observability.
- writes directly to another service database.
- mixes controllers, business rules, persistence, and provider SDK calls in one file.
- cannot be unit tested without real infrastructure.
- changes a public contract without versioning and contract tests.

## Relationship To Backend Structure

Backend modules must follow `/root/Astloom/backend/docs/ENGINEERING_STANDARDS.md`. Shared primitives belong in `/root/Astloom/backend/packages/shared-kernel/` only when they are stable, cross-cutting, and not business-specific.

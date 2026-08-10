---
doc_id: as.doc.sea.dependency-injection-and-composition-root
title: 30 - Dependency Injection And Composition Root
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how Astloom should use Dependency Injection. DI is required
  so modules remain testable, replaceable, observable, and free from hidden infrastructure
  coupling.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/30-dependency-injection-and-composition-root.md
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

# 30 - Dependency Injection And Composition Root

## Purpose

This document defines how Astloom should use Dependency Injection. DI is required so modules remain testable, replaceable, observable, and free from hidden infrastructure coupling.

## Core Rule

Dependencies must be provided from the outside. Business logic must not create databases, HTTP clients, model clients, broker clients, file clients, clocks, id generators, or configuration readers directly.

## Composition Root

Each deployable process must have one composition root. The composition root is responsible for:

- loading validated configuration.
- creating infrastructure clients.
- registering adapters for application ports.
- wiring application services and handlers.
- configuring observability.
- setting lifecycle hooks.
- validating startup readiness.

The composition root may know about concrete implementations. Domain and application logic must not.

## Allowed Patterns

### Constructor Injection

Application services receive dependencies through constructors. This is the default pattern because dependencies are visible and easy to replace in tests.

### Explicit Factory Injection

Factories are allowed when object creation needs runtime parameters or lifecycle control. The factory interface should be defined by the application layer and implemented by infrastructure or bootstrap.

### Configuration Injection

Validated typed configuration objects may be injected into application services. Raw environment reads are allowed only in bootstrap.

### Port Injection

Application services depend on ports such as Repository, EventPublisher, Clock, IdGenerator, PolicyEvaluator, MetadataReader, or ModelClient. Infrastructure adapters implement those ports.

## Forbidden Patterns

- Service locator inside domain or application logic.
- Global mutable singleton for business dependencies.
- Direct `new` of infrastructure clients inside handlers.
- Reading environment variables inside domain logic.
- Static helpers that hide network, database, filesystem, or time access.
- Dependency cycles between services or packages.

## Lifetime Rules

- Request-scoped dependencies should live only for one request or job.
- Process-wide dependencies such as connection pools must be created in bootstrap and closed during shutdown.
- Domain objects should not own infrastructure lifetime.
- Tests must be able to replace any external dependency with a fake or test adapter.

## Example Boundary

A command handler may depend on:

- task repository port.
- event publisher port.
- authorization policy port.
- clock port.
- id generator port.
- logger interface.

It must not depend directly on:

- PostgreSQL client.
- vendor SDK.
- environment variables.
- DI container API.

## Testing Requirement

Every application service must be constructible in a unit test without real databases, brokers, file systems, model providers, or network calls.

## Composition flow

```mermaid
flowchart LR
  settings[Settings] --> root[Composition root]
  root --> container[ServiceContainer]
  container --> handlers[Handlers / use cases]
  handlers --> ports[Ports]
  ports --> adapters[Adapters]
```

| Step | Actor | Action | Outcome |
| --- | --- | --- | --- |
| 1 | Bootstrap | Validate settings | Typed config |
| 2 | Composition root | Bind adapters to ports | Container |
| 3 | Handler | Use injected ports only | Testable, swappable |

## Backend migration pack

Standing principles in this file are **current**. The executable migration to uniform
`ServiceContainer` / `build_container` / `build_app` wiring is **shipped (Phases A–D)**
and specified in:

- `45-backend-di-composition-feature-specification.md`
- `46-backend-di-composition-high-level-design.md`
- `47-backend-di-composition-low-level-design.md`
- `48-backend-di-composition-risks-challenges-and-acceptance.md`

Shipped pattern: one frozen `ServiceContainer` per process from `bootstrap.build_container`,
FastAPI `app.state.container`, thin-service `ports.Store`, CLI reuse via
`astloom_cli.process_containers`.

## Acceptance Criteria

DI is implemented correctly when dependency graphs are visible at bootstrap, domain code is framework-free, application services are easy to instantiate in tests, and infrastructure can be replaced without modifying business logic.

## Related Documents

- `45-backend-di-composition-feature-specification.md` — migration feature spec
- `29-engineering-best-practices-and-implementation-standards.md` — implementation standards
- `33-testing-seams-and-contract-boundary-standards.md` — fakes and seams


---
doc_id: as.doc.backend.structure-standard
title: Backend Structure Standard
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Standard for creating folders and modules under backend/ so Astloom stays modular.
tags:
- backend
- structure
- standard
phase: backend-docs
canonical_path: backend/docs/STRUCTURE_STANDARD.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
language: en
security_classification: internal
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Backend Structure Standard

## Purpose

This document defines the standard for creating folders and modules inside `backend/`.

The standard exists so Astloom remains modular as it grows. Every new folder must have a clear owner, purpose, boundary, dependency rule, testing expectation, and README.

## Core Principles

- Use modular monorepo structure.
- Use Domain-Driven Design for business concepts.
- Use Hexagonal Architecture inside services.
- Keep deployable applications thin.
- Keep service internals private.
- Share only stable contracts and cross-cutting primitives.
- Prefer configuration over hard-coded behavior.
- Keep SDKs and public contracts first-class.
- Keep test structure close to module ownership.
- Document every new boundary before adding implementation code.

## Top-Level Folder Standard

| Folder | Responsibility |
| --- | --- |
| apps | Process entrypoints such as API gateway, worker, scheduler, and CLI. |
| services | Independently owned backend services. |
| domains | Domain language, model boundaries, events, policies, and examples. |
| packages | Shared contracts, SDKs, generated clients, and shared primitives. |
| platform | Infrastructure adapters for persistence, messaging, config, observability, and security. |
| integrations | External provider adapters and connector implementations. |
| configs | Versioned configuration templates. |
| deployments | Runtime deployment and infrastructure packaging. |
| tests | Backend-wide tests that cross module boundaries. |
| tools | Development, generation, diagnostics, and compatibility tools. |
| runbooks | Operational procedures. |
| docs | Backend-specific architecture and structure standards. |

## Service Folder Standard

Every service should use this shape:

```text
service-name/
  README.md
  src/
    domain/
    application/
    infrastructure/
    interfaces/
    contracts/
  tests/
    unit/
    integration/
    contract/
  migrations/
  config/
  docs/
```

### domain

Contains entities, value objects, aggregates, domain services, invariants, and domain events. It must not depend on infrastructure, web frameworks, databases, queues, or external providers.

### application

Contains use cases, command handlers, query handlers, transaction boundaries, and service-local orchestration. It depends on domain interfaces and ports, not concrete infrastructure implementations.

### infrastructure

Contains adapters for persistence, messaging, external services, caches, object storage, graph stores, and provider clients.

### interfaces

Contains inbound adapters such as HTTP controllers, RPC handlers, event consumers, worker handlers, scheduler handlers, and CLI bindings.

### contracts

Contains service-owned contract drafts and examples. Stable cross-service contracts must be promoted to `packages/contracts`.

## Naming Standard

- Folder names use lowercase kebab-case.
- Service folders end with `-service`.
- Integration folders use provider or capability names.
- Test folders use stable names: `unit`, `integration`, `contract`, `e2e`, `live`, `fixtures`, `load`, `security`.
- Configuration folders describe scope: `environments`, `domain-packs`, `feature-profiles`, `rule-packs`, `port-profiles`.
- Do not use vague names such as `common`, `misc`, `utils`, `helpers`, or `new`.

## README Standard

Every folder must contain a `README.md` with:

- path.
- purpose.
- modular boundary.
- allowed contents.
- dependency rules.
- status.
- owner when known.
- links to related contracts or docs when known.

## Module Creation Checklist

Before creating a new module:

1. Identify whether it is an app, service, domain, package, platform adapter, integration, config set, test asset, tool, deployment asset, or runbook.
2. Confirm no existing module already owns the responsibility.
3. Define public contracts before private implementation.
4. Define dependency direction.
5. Create README first.
6. Add tests or test plan when implementation code is added.
7. Add documentation links to the relevant index.

## Hard-Code Prevention

Do not hard-code:

- ports.
- credentials.
- tenant IDs.
- workspace IDs.
- project IDs.
- domain pack names.
- model provider names.
- external endpoints.
- feature enablement.
- rule behavior.
- memory weights.

Use config schemas, domain packs, feature profiles, rule packs, port profiles, or environment profiles.

## Acceptance Criteria

The backend structure is acceptable when:

- every folder has a README.
- top-level responsibilities are clear.
- service boundaries follow the service folder standard.
- shared packages are limited to contracts, SDKs, and stable primitives.
- infrastructure adapters do not leak into domain logic.
- future modules can be added without changing unrelated modules.

## Related Documents

- [MODULE_TEMPLATE.md](./MODULE_TEMPLATE.md)
- [NAMING_AND_BOUNDARIES.md](./NAMING_AND_BOUNDARIES.md)
- [ENGINEERING_STANDARDS.md](./ENGINEERING_STANDARDS.md)
- [README.md](./README.md)

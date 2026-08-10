# Astloom Backend

Path: `backend`

## Purpose

This directory is the modular backend workspace for Astloom. It contains deployable applications, independently owned services, domain model boundaries, shared packages, platform infrastructure modules, external integrations, configuration templates, deployment assets, tests, tools, and runbooks.

The backend is scaffolded as a modular system before implementation code is added. The goal is to make future implementation predictable, extensible, testable, and safe for a platform that coordinates agents, memory, rules, reusable common context, documents, code graphs, SDKs, code metadata, connectors, reports, and human workflows.

## Architecture Standard

The backend follows a modular monorepo pattern with Domain-Driven Design and Hexagonal Architecture:

- `apps/` contains process entrypoints only.
- `services/` contains independently owned service boundaries.
- `domains/` documents ubiquitous language and domain model boundaries.
- `packages/` contains stable shared contracts, SDKs, and cross-cutting primitives.
- `platform/` contains infrastructure adapters and platform integrations.
- `integrations/` contains external provider adapters.
- `configs/` contains environment, domain pack, feature profile, common-context profile, code-metadata profile, technology profile, rule pack, and port profile templates.
- `tests/` contains backend-wide tests that cross module boundaries.
- `tools/` contains generators, schema registry tools, SDK generation tools, diagnostics, and development utilities.
- `deployments/` contains deployment manifests and runtime packaging.
- `runbooks/` contains operational procedures.

## Dependency Direction

Allowed direction:

```text
apps -> services -> packages/contracts
services -> packages/shared-kernel
services -> packages/common-context for reusable common context contracts
services -> packages/code-metadata for metadata-first code context contracts
services -> platform through ports/interfaces
integrations -> packages/contracts and adapter SDK
tests -> public APIs, SDKs, contracts, and test fixtures
```

Forbidden direction:

```text
service A -> private internals of service B
domain -> infrastructure
packages/shared-kernel -> services
platform -> service domain internals
apps -> service persistence internals
tests -> private database tables unless explicitly testing migrations
```

## Folder Creation Rule

New folders must follow `docs/STRUCTURE_STANDARD.md`. Every folder must have a `README.md` that states purpose, boundary, allowed contents, dependency rules, and status.

## Current Status

Active modular backend foundation. Core Data and Memory vertical slices include FastAPI contracts, PostgreSQL adapters, service-owned schemas and migrations, deterministic in-memory unit-test fakes, and root-level tests. Other backend boundaries may remain scaffold-only and document their own status.

---
doc_id: as.doc.ops.api-versioning-and-contract-governance
title: API Versioning and Contract Governance
doc_type: contract
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom depends on stable contracts between services, agents, adapters, IDE plugins,
  CI systems, and external tools. Contract governance prevents hidden breaking changes.
tags:
- contract
- ops
phase: 09-platform-governance-operations
canonical_path: docs/09-platform-governance-operations/05-api-versioning-and-contract-governance.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# API Versioning and Contract Governance

## Purpose

Astloom depends on stable contracts between services, agents, adapters, IDE plugins, CI systems, and external tools. Contract governance prevents hidden breaking changes.

## Contract Types

- HTTP or RPC APIs.
- Broker events.
- Universal Agent JSON messages.
- Database schemas.
- Graph schemas.
- Markdown frontmatter schemas.
- ContextBundle schemas.
- WeightProfile and GraphRetrievalProfile schemas.
- Adapter capability profiles.

## Versioning Rules

- Breaking changes require a new version.
- Additive changes should be backward compatible.
- Consumers must tolerate unknown optional fields.
- Required field changes must go through deprecation period.
- Event schemas must be replay-safe.
- Contract versions must be visible in records and events.

## Deprecation Policy

A deprecated contract should include:

- replacement contract,
- migration guide,
- owner,
- deprecation date,
- removal date,
- affected consumers,
- compatibility guarantees.

## Compatibility Testing

CI should run contract tests for:

- producers against schema,
- consumers against previous versions,
- adapter mappings,
- broker replay,
- frontmatter parsing,
- Universal Agent JSON validation.

## Schema Registry

The platform maintains a **repository-directory** schema registry for v1:

- Authoritative schemas under `backend/configs/` (and peers).
- Discovery index: `backend/tools/schema-registry/catalog.json`.
- Normative decision: `12-schema-registry-architecture.md` (closes GAP-008).

A networked or database-backed registry requires a new ADR.

## Acceptance Criteria

- Every external contract has a version.
- Breaking changes are not released without migration path.
- Contract tests run in CI.
- Deprecated versions are visible and tracked.
- Adapter and broker events are compatible with replay.

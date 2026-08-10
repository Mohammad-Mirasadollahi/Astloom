---
doc_id: as.doc.sea.interface-and-contract-engineering
title: 08 - Interface And Contract Engineering
doc_type: contract
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how Astloom should design, version, test, and operate interfaces
  and contracts. Interfaces include APIs, events, SDKs, adapter payloads, configuration schemas,
  migration contracts, and CLI commands.
tags:
- contract
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/08-interface-and-contract-engineering.md
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

# 08 - Interface And Contract Engineering

## Purpose

This document defines how Astloom should design, version, test, and operate interfaces and contracts. Interfaces include APIs, events, SDKs, adapter payloads, configuration schemas, migration contracts, and CLI commands.

Contracts are the connective tissue of Astloom. If contracts are vague, services will couple through assumptions. If contracts are explicit, modules can evolve independently.

## Contract Types

Astloom should manage these contract types:

| Contract Type | Example | Owner | Validation |
| --- | --- | --- | --- |
| API contract | create task endpoint | exposing service | API schema tests |
| Event contract | MemoryConsolidated event | producing service | producer and consumer tests |
| Adapter contract | provider capability payload | adapter-service | mapping tests |
| SDK contract | typed client method | sdk package | generated client tests |
| Config contract | service config schema | config-service or service owner | config validation tests |
| CLI contract | command arguments and output | cli app | command tests |
| Persistence contract | migration and schema state | data owner | migration tests |
| Graph contract | node labels and edge semantics | code-graph-service | graph consistency tests |

## Contract Ownership

Each contract must have one producer owner and one or more consumer owners.

Producer responsibilities:

- define the contract schema.
- publish examples.
- version the contract.
- document compatibility guarantees.
- provide producer tests.
- announce deprecations.

Consumer responsibilities:

- validate assumptions through consumer tests.
- avoid depending on undocumented fields.
- handle unknown optional fields safely.
- report compatibility gaps.

## API Design Rules

APIs should be designed around use cases, not database tables.

API endpoints or RPC methods should:

- accept commands or queries with explicit intent.
- return stable response objects.
- include correlation IDs.
- return structured errors.
- expose idempotency keys for retryable commands.
- avoid leaking internal persistence identifiers unless they are public IDs.
- include pagination for list operations.
- include filtering only when indexes and ownership are clear.

Example command API shape:

    CreateTaskRequest
      workspace_id
      actor
      title
      reason
      source_evidence
      dependency_refs
      idempotency_key

    CreateTaskResponse
      task_id
      status
      created_at
      created_events
      audit_ref

## Event Design Rules

Events should describe facts that already happened.

Good event names:

- ActivityRecorded
- WorkLogCreated
- DecisionSuperseded
- MemoryConsolidated
- DocumentationDriftDetected
- CodeGraphSnapshotCreated
- RuleViolationDetected
- AdapterCapabilityChanged

Bad event names:

- CreateTaskEvent
- ProcessMemory
- UpdateGraphNow
- SyncDocsPlease

Every event should include:

- event_id
- event_type
- event_version
- occurred_at
- producer
- workspace_id
- actor_ref when available
- correlation_id
- causation_id
- idempotency_key when applicable
- payload
- schema_ref

## Compatibility Rules

Backward compatible changes may include:

- adding optional fields.
- adding new event types.
- adding new enum values only when consumers are designed for unknown values.
- adding response metadata that clients can ignore.

Breaking changes include:

- removing fields.
- changing field type.
- changing field meaning.
- making optional fields required.
- changing event causality semantics.
- changing idempotency behavior.
- changing error codes without compatibility mapping.

Breaking changes require:

- new contract version.
- migration notes.
- consumer compatibility plan.
- deprecation period.
- release notes.
- contract test updates.

## Versioning Strategy

Contracts should use semantic versioning or explicit date-based versioning, but the strategy must be consistent inside each contract family.

Recommended rules:

- API major version changes only when compatibility breaks.
- Event versions should be part of the event envelope.
- SDK versions should map to supported API and event contract versions.
- Config schema versions should be validated at startup.
- Graph schema versions should be stored with graph snapshots.
- Adapter mapping versions should be stored with external payload evidence.

## Error Contract

Errors should be structured and predictable.

Every public error should include:

- error_code
- message
- category
- retryable
- correlation_id
- details
- documentation_ref when useful

Categories should include:

- validation_error
- authentication_error
- authorization_error
- conflict_error
- not_found_error
- dependency_error
- rate_limit_error
- policy_error
- internal_error

Do not expose secrets, stack traces, model prompts, or raw provider payloads in public errors.

## Idempotency Contract

Commands that may be retried must support idempotency.

Idempotency should apply to:

- create task.
- record activity.
- create work log.
- record decision.
- publish adapter callback.
- ingest repository change.
- consolidate memory batch.
- evaluate rule batch.

Idempotency records should include:

- key
- command name
- request hash
- result reference
- created_at
- expires_at
- actor or producer

If the same idempotency key is reused with a different request hash, the system should return a conflict error.

## Schema Registry

Astloom maintains a **repository-directory** schema registry for v1
(`docs/09-platform-governance-operations/12-schema-registry-architecture.md`):

- schemas under `backend/configs/` (and peers),
- discovery index at `backend/tools/schema-registry/catalog.json`.

The registry should provide:

- schema discovery.
- compatibility checks (pytest / gates).
- generated examples.
- producer validation.
- consumer validation.
- changelog generation (docs).
- deprecated field reporting.
- ownership metadata.

## Contract Test Matrix

Each public contract should have tests at multiple points.

| Test Type | Purpose |
| --- | --- |
| Producer schema test | producer output matches schema |
| Consumer compatibility test | consumer handles current and previous schema versions |
| Example validation test | documented examples are valid |
| Negative validation test | invalid payloads fail clearly |
| Round trip test | SDK serializes and deserializes correctly |
| Replay test | events can be replayed safely |
| Idempotency test | retry does not duplicate state |

## SDK Engineering

SDKs should be generated or strongly typed from public contracts when possible.

SDKs should provide:

- typed commands and queries.
- typed event subscriptions.
- retry behavior with idempotency support.
- structured errors.
- correlation ID propagation.
- request timeout configuration.
- test fakes.
- examples.

SDKs should not expose service internals or database concepts.

For the complete SDK implementation architecture, package model, generation pipeline, scoped client model, Agent SDK, Adapter SDK, Admin SDK, Test SDK, CI gates, and release governance, read `27-sdk-engineering-and-contract-generation.md` and `../05-interoperability-ecosystem/07-sdk-and-developer-platform.md`.

## Acceptance Criteria

Contract engineering is acceptable when:

- every API, event, SDK, config, adapter, and graph contract has an owner.
- schemas are versioned and tested.
- examples validate against schemas.
- breaking changes require explicit migration plans.
- consumers do not rely on undocumented fields.
- idempotency and error behavior are part of public contracts.


## API Naming Standard Reference

HTTP API endpoint names, DTO names, error shapes, pagination, idempotency, operation ids, and API catalog governance must follow `../14-api-design-and-naming-standards/`.

When a future API cannot follow the standard, the exception must be documented with compatibility, SDK, contract-test, and governance impact.

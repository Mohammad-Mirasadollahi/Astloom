---
doc_id: as.doc.sea.testing-and-verification-engineering
title: 11 - Testing And Verification Engineering
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the testing and verification strategy for Astloom from a
  Software Engineering perspective.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/11-testing-and-verification-engineering.md
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

# 11 - Testing And Verification Engineering

## Purpose

This document defines the testing and verification strategy for Astloom from a Software Engineering perspective. It explains what should be tested at each layer, which tests belong inside modules, which tests belong at repository level, and how tests prove that the design is implementable.

**How to author tests (concurrent code-and-tests law, decision matrix, doubles, markers):** `37-test-authoring-standard.md`. **Fuzz / property-based:** `38-fuzzing-and-property-based-testing.md`. **Unit vs Live safety:** `25-live-and-unit-test-strategy.md`. **Seams:** `33-testing-seams-and-contract-boundary-standards.md`.

## Testing Philosophy

Astloom should use layered testing. Each layer should prove a different kind of correctness.

The goal is not only high coverage. The goal is confidence that modules preserve their contracts, domain rules, data integrity, event behavior, and operational expectations. Unit Tests and Live Tests are separate required test families; detailed requirements are defined in 25-live-and-unit-test-strategy.md.

## Test Layers

| Layer | Location | Purpose |
| --- | --- | --- |
| Unit tests | service tests/unit | deterministic module, domain, scoring, validation, and state-machine logic |
| Domain unit tests | service tests/unit | pure domain rules and invariants |
| Application tests | service tests/unit or tests/integration | use case orchestration |
| API tests | service tests/contract | request, response, error shape |
| Event contract tests | service tests/contract and repository tests/contract | producer and consumer compatibility |
| Persistence tests | service tests/integration | repository behavior and migrations |
| Worker tests | service tests/integration | event consumption, idempotency, retries |
| Cross-service tests | tests/integration | multi-service workflows |
| End-to-end tests | tests/e2e | complete user and agent flows |
| Performance tests | tests/performance | latency, throughput, graph traversal, retrieval |
| Live tests | tests/live or controlled live environment | real or production-like validation with explicit scope, data classification, mutation policy, and evidence |
| Security tests | tests/security or service tests | auth, tenant isolation, redaction |
| Docs validation | tools/docs-validator | indexes, links, required metadata |

## Domain Tests

Domain tests should be fast and deterministic.

They should cover:

- entity lifecycle transitions.
- value object validation.
- policy decisions.
- domain service calculations.
- invalid transitions.
- edge cases.

Examples:

- Task cannot move from closed to in_progress without reopening.
- Decision cannot supersede itself.
- Memory weight calculation responds to configured factor changes.
- Rule evaluation explains which evidence matched.
- Impact analyzer includes direct and transitive graph dependencies.

Domain tests should not require databases, brokers, filesystems, external APIs, model calls, or network access.

## Application Tests

Application tests should verify use cases.

They should cover:

- command handlers.
- query handlers.
- authorization checks.
- repository interaction through interfaces.
- event creation.
- idempotency behavior.
- failure handling.

Example:

CreateTaskHandler should validate input, enforce workspace permission, create a Task aggregate, persist it, store an outbox event, and return a stable Task ID.

## Contract Tests

Contract tests are mandatory for public APIs and events.

They should verify:

- schema validity.
- required fields.
- optional field behavior.
- unknown field tolerance when supported.
- error shape.
- version compatibility.
- documented examples.
- producer output.
- consumer expectations.

Contracts should fail loudly when a producer breaks a consumer assumption.

## Persistence Tests

Persistence tests should verify that repositories and migrations behave correctly against real or realistic stores.

They should cover:

- create, read, update, delete when deletion is allowed.
- lifecycle queries.
- indexes used by key queries.
- migration forward behavior.
- rollback or no-rollback handling.
- transaction boundaries.
- outbox writes.
- inbox duplicate prevention.

Graph persistence tests should verify:

- stable symbol IDs.
- correct node labels.
- correct edge types.
- graph snapshot versioning.
- stale edge policy.
- bounded traversal results.

## Worker And Event Tests

Worker tests should assume duplicate and delayed events.

They should cover:

- duplicate event handling.
- out-of-order event handling where applicable.
- retry behavior.
- dead-letter behavior.
- poison message handling.
- partial failure recovery.
- idempotent projection updates.

Example:

If ActivityRecorded is delivered twice to memory-service, only one candidate memory record should be created for the same idempotency identity.

## Cross-Service Integration Tests

Integration tests should verify flows across service boundaries without importing service internals.

Important flows:

- Activity to WorkLog to Memory update.
- CodeGraph SymbolChanged to DocumentationDriftDetected to Task creation.
- RuleViolationDetected to Escalation Task to external approval adapter.
- IDE event to api-gateway to core-data-service to broker event.
- Adapter callback to Task update to audit record.

These tests should use public APIs, event contracts, SDKs, and configured test profiles.

## End-To-End Tests

E2E tests should represent realistic user and agent journeys.

Examples:

- An agent completes a code change and records evidence, decisions, tasks, and documentation updates.
- A reviewer approves a high-risk change after rule-engine-service escalates it.
- A documentation drift is detected from a code graph change and assigned to the right owner.
- Memory retrieval returns current project truth and explains selected context.

E2E tests should be fewer than lower-level tests but should protect critical user value.

## Performance Tests

Performance tests should define budgets before implementation is considered production ready.

Areas to test:

- activity write throughput.
- broker publish and consume throughput.
- memory retrieval latency by candidate set size.
- graph ingestion time by repository size.
- graph query latency by traversal depth.
- docs drift detection latency.
- rule evaluation throughput.
- audit export time.

Performance tests should record environment, dataset size, config profile, and expected budget.

## Security Verification

Security tests should cover:

- tenant isolation.
- workspace authorization.
- prompt context filtering.
- secret redaction.
- adapter callback validation.
- approval enforcement.
- audit evidence integrity.
- permission denied paths.

Negative tests are required. The system must prove that unauthorized data is not returned.

## Documentation Verification

Docs should be tested as part of engineering.

Docs validation should check:

- index files exist.
- required sections exist for major modules.
- links resolve.
- phase files are discoverable.
- HLD and LLD stay separated where required.
- examples reference valid contracts when possible.
- port documentation matches config examples.
- gap references exist for unresolved assumptions.

## CI Test Gates

Recommended CI gates:

1. format and static analysis.
2. dependency boundary checks.
3. docs validation.
4. contract validation.
5. unit tests.
6. service integration tests.
7. cross-service integration tests for affected modules.
8. security checks for sensitive areas.
9. migration checks.
10. performance smoke tests for affected performance-sensitive modules.
11. live tests for release readiness, connector validation, migrations, production-like data validation, and post-deployment confidence when required.

## Acceptance Criteria

Testing engineering is acceptable when:

- every module has tests at the correct layer.
- contract tests protect public APIs and events.
- persistence tests cover migrations and idempotency.
- E2E tests cover critical user and agent workflows.
- docs validation is part of CI.
- performance and security are verified through explicit tests, not assumptions.

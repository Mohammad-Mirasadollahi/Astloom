---
doc_id: as.doc.sea.live-and-unit-test-strategy
title: 25 - Live And Unit Test Strategy
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom must have both Unit Tests and Live Tests.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/25-live-and-unit-test-strategy.md
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

# 25 - Live And Unit Test Strategy

## Purpose

Astloom must have both Unit Tests and Live Tests. Unit Tests prove that isolated domain logic and application behavior are correct without external dependencies. Live Tests prove that the platform works against real or production-like data, real integrations, real deployment topology, and real operational constraints.

These two test families solve different problems and must not be treated as substitutes for each other. Unit Tests provide fast deterministic confidence during development. Live Tests provide real-world confidence that agents, connectors, stores, brokers, code graph, documentation sync, memory retrieval, rules, reports, and automation behave correctly with realistic data and infrastructure.

**Authoring playbook (mandatory concurrent tests, placement, markers):** `37-test-authoring-standard.md`. This document owns Unit vs Live strategy, real-data safety, evidence, and release gates.

## Corrected Requirement

Astloom must include a formal testing strategy that separates Unit Tests from Live Tests. The system should run Unit Tests for every module and service to validate pure logic, state transitions, scoring, validation, and command behavior. The system should also support Live Tests with real or production-like data and real integrations to validate end-to-end behavior, connector health, data isolation, memory quality, documentation sync, rule execution, reporting accuracy, and operational readiness.

Live Tests must be controlled, scoped, auditable, and safe. They must not mutate production data unless explicitly approved and must not expose secrets or cross-project data.

## Professional Audience

This document is written for:

- software engineers implementing test suites and test harnesses.
- QA engineers designing verification strategy.
- platform operators running live validation in staging or controlled production-like environments.
- architects defining quality gates.
- security reviewers validating real-data test safety.
- product designers verifying workflow behavior with realistic states.

## Test Family Definitions

| Test Family | Main Question | Dependency Level | Speed | Required For |
| --- | --- | --- | --- | --- |
| Unit Test | Does isolated logic work correctly | no external dependencies | fast | every module |
| Contract Test | Do producers and consumers agree | schema and examples | fast to medium | public APIs and events |
| Integration Test | Do components work together in controlled environment | local or test dependencies | medium | service flows |
| E2E Test | Does a complete workflow work | full test stack | slower | critical journeys |
| Live Test | Does the system work with real or production-like data and integrations | real services or realistic live environment | controlled and slower | release readiness and operational confidence |

## Unit Test Strategy

Unit Tests should be deterministic, fast, isolated, and exhaustive for core logic.

Unit Tests should cover:

- domain entity lifecycle transitions.
- value object validation.
- scoring formulas using configurable profiles.
- rule evaluation logic.
- memory classification.
- question normalization.
- WorkBatch readiness decisions.
- state machine transitions.
- command validation.
- error mapping.
- permission decision helpers.
- prompt packing calculations.
- token budget calculations.
- project scope guard logic.

Unit Tests must not require:

- database.
- broker.
- graph database.
- vector store.
- filesystem state outside fixtures.
- network.
- model provider.
- external ticket system.
- real credentials.

## Unit Test Requirements By Module

| Module | Required Unit Test Focus |
| --- | --- |
| core-data-service | Activity, Decision, Issue, Task lifecycle and evidence validation |
| memory-service | classification, scoring, retrieval ranking, decay, QuestionMemory, WorkBatch logic |
| docs-sync-service | anchor resolution, drift classification, frontmatter validation |
| code-graph-service | symbol identity, edge rules, impact selection algorithms |
| rule-engine-service | deterministic policies, severity mapping, escalation decisions |
| adapter-service | payload mapping, capability normalization, error normalization |
| broker-service | retry policy decisions, idempotency helpers, dead-letter classification |
| config-service | config schema validation, profile selection, port profile validation |
| audit-service | evidence reference validation, retention classification |
| admin-console | state mapping, permission state, form validation, view model transforms |

## Unit Test Data

Unit test fixtures should be small, deterministic, and explicit.

Fixture types:

- fake Activity payloads.
- fake Task lifecycle records.
- fake MemoryItem candidates.
- fake QuestionMemory observations.
- fake WorkBatch activity sequences.
- fake rule evidence.
- fake graph nodes and edges.
- fake connector payloads.
- fake report metric inputs.

Fixtures should include negative cases and edge cases, not only happy paths.

## Live Test Strategy

Live Tests validate behavior against real or production-like systems.

Live Tests should cover:

- deployment readiness.
- service health and readiness.
- real broker publish and consume.
- real database migrations and queries.
- real graph ingestion on representative repositories.
- real documentation drift detection.
- real connector registration and validation.
- real memory retrieval with representative project data.
- real project isolation checks.
- real report generation with measurement data.
- real admin-console workflow behavior.
- real model provider call where policy allows it.

Live Tests should not replace Unit Tests. They catch integration and environment problems that Unit Tests cannot catch.

## Live Test Environments

Supported Live Test environments:

| Environment | Purpose | Data Type | Mutation Policy |
| --- | --- | --- | --- |
| live-dev | developer-controlled realistic stack | synthetic or copied sanitized data | allowed within sandbox |
| staging | release validation | production-like sanitized data | controlled mutation |
| production-read-only | safe production validation | real production data | read-only by default |
| production-canary | limited production validation | real scoped data | approved write only |
| connector-sandbox | external connector validation | provider sandbox data | provider-specific |

Live Tests must always declare environment and mutation policy.

## Real Data Safety Rules

Live Tests with real or production-like data must follow safety rules.

Rules:

- require explicit environment selection.
- require project or ProjectGroup scope.
- default to read-only for production data.
- redact secrets and sensitive fields.
- enforce tenant, workspace, and project isolation.
- record audit evidence for production-like or production Live Tests.
- block destructive operations unless explicitly approved.
- use synthetic or sandbox credentials where possible.
- avoid writing test artifacts into real user workflows unless approved.

## Live Test Scope Contract

Every Live Test run should include:

    LiveTestRun:
        run_id
        environment
        tenant_id
        workspace_id
        project_id
        project_group_id
        test_suite
        data_classification
        mutation_policy
        started_by
        started_at
        completed_at
        status
        evidence_refs
        failures
        caveats
        approval_ref

## Live Test Categories

### Installation Live Test

Validates:

- preflight checks.
- generated configuration.
- port allocation.
- database bootstrap.
- graph bootstrap.
- broker bootstrap.
- service registry.
- first-run readiness.
- smoke tests.

### Connector Live Test

Validates:

- connector registration.
- authentication.
- capability discovery.
- sample command or read operation.
- callback validation.
- error normalization.
- connector health.

### Memory Live Test

Validates:

- scoped retrieval.
- QuestionMemory behavior.
- FAQ memory reuse.
- WorkBatch consolidation.
- token budget behavior.
- explanation output.
- project isolation.

### Code Graph And Docs Live Test

Validates:

- repository ingestion.
- symbol extraction.
- graph edge creation.
- documentation anchor lookup.
- drift detection.
- documentation draft generation.

### Rule And Approval Live Test

Validates:

- deterministic rule evaluation.
- semantic rule evaluation where allowed.
- escalation routing.
- approval state transitions.
- audit evidence.

### Reporting Live Test

Validates:

- metric calculation.
- baseline selection.
- project scope filtering.
- evidence drilldown.
- dashboard state.
- export output.

## Live Test Evidence

Each Live Test should produce evidence.

Evidence should include:

- test run ID.
- environment.
- config profile.
- project scope.
- test cases executed.
- data classification.
- mutation policy.
- commands or workflows executed.
- service versions.
- contract versions.
- pass/fail result.
- logs and traces references.
- audit references.
- caveats.

Evidence must not include secrets.

## Unit Test And Live Test Gates

Recommended gates:

1. Unit Tests run on every change.
2. Contract Tests run when API, event, SDK, config, or adapter schemas change.
3. Integration Tests run for affected services.
4. E2E Tests run for critical workflow changes.
5. Live Tests run before release, after deployment, after connector changes, after migration changes, and when production-like validation is required.

Live Tests may be manually approved when they touch production-like or production data.

## Pass And Fail Criteria

Unit Test pass criteria:

- deterministic result.
- no external dependency.
- covers positive and negative paths.
- verifies edge cases.
- runs in developer and CI environments.

Live Test pass criteria:

- environment declared.
- scope declared.
- mutation policy declared.
- required workflows pass.
- evidence report generated.
- no unauthorized cross-project data access.
- no unapproved write to production data.
- failures include diagnostics and repair hints.

## Product Experience

The admin-console should expose Live Test and Unit Test status.

Views:

- latest Unit Test status by module.
- latest Live Test status by environment.
- Live Test run detail.
- failed test evidence.
- release readiness checklist.
- connector validation status.
- project isolation test status.
- report test status.

Actions:

- run approved Live Test suite.
- view evidence report.
- acknowledge caveat.
- create Task from failed test.
- create Gap from missing coverage.
- block release when required Live Tests fail.

## Anti-Patterns

Avoid:

- using Live Tests as the only safety net.
- using Unit Tests with real databases or providers.
- running write-enabled Live Tests against production without approval.
- reporting Live Test success without evidence.
- ignoring project scope in Live Tests.
- using synthetic data only and claiming real-data confidence.
- using real data without redaction or access control.

## Acceptance Criteria

The Live and Unit Test strategy is acceptable when:

- Unit Tests are required for every module and service.
- Unit Tests are deterministic, isolated, fast, and independent of external services.
- Live Tests are defined as a separate test family with real or production-like data.
- Live Tests declare environment, scope, data classification, mutation policy, and evidence.
- Live Tests cover installation, connectors, memory, code graph, docs sync, rules, approvals, reports, and admin-console workflows.
- Production Live Tests are read-only by default and require approval for writes.
- CI/CD and release gates distinguish Unit Tests from Live Tests.
- failed Live Tests produce diagnostics, repair hints, Tasks, or Gaps.

## Repository Test Layout

Executable tests must be collected under the repository-level `tests/` directory. Product source trees may keep README files, examples, fixtures, or contract documentation, but new executable tests must not be placed inside service-local `tests/` folders.

Canonical layout:

```text
tests/
  README.md
  frontend/
    README.md
  backend/
    README.md
    <service-or-app-name>/
      test_*.py
```

Backend tests are grouped by owning service or app. For example, Core Data Service tests live in `tests/backend/services/core-data-service/`. Frontend tests must live in `tests/frontend/` and may be further grouped by application, feature, or test family once a frontend package exists.

Recommended backend commands:

```bash
PYTHONPATH=backend/services/core-data-service/src .venv/bin/python -m pytest tests/backend
PYTHONPATH=backend/services/core-data-service/src .venv/bin/python -m pytest tests/backend/services/core-data-service
```

Test files should follow the Python convention `test_*.py` or `*_test.py`. Shared backend fixtures should live under `tests/backend/fixtures/` when they are genuinely reusable across multiple backend modules. Frontend fixtures should live under `tests/frontend/fixtures/`.

Service-local directories such as `backend/services/<service>/tests/` are reserved for non-executable placeholders only when a scaffold requires a boundary note. They must not contain runnable test files.


---
doc_id: as.doc.sea.testing-seams-and-contract-boundary-standards
title: 33 - Testing Seams And Contract Boundary Standards
doc_type: contract
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how Astloom modules should be designed so they can be tested
  without relying on real infrastructure, private internals, or unstable external services.
tags:
- contract
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/33-testing-seams-and-contract-boundary-standards.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols:
- tests/backend/services/core-data-service/test_core_data_service.py::ApiClient
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 33 - Testing Seams And Contract Boundary Standards

## Purpose

This document defines how Astloom modules should be designed so they can be tested without relying on real infrastructure, private internals, or unstable external services.

**Authoring and concurrent code-and-tests law:** `37-test-authoring-standard.md`. **Fuzz invariants:** `38-fuzzing-and-property-based-testing.md`. This document owns seams, ports, fakes/mocks design, and determinism rules.

## Test Seam Standard

Every module must expose seams through public contracts, ports, adapters, factories, deterministic clocks, deterministic ids, and fake infrastructure implementations.

A module is poorly designed if unit tests require real databases, real brokers, real model providers, real network calls, real time, or private cross-service imports.

## Required Test Types

- Unit tests for domain rules and pure application logic.
- Integration tests for persistence, brokers, graph stores, filesystem adapters, and provider adapters.
- Contract tests for APIs, events, SDKs, config schemas, and adapter payloads.
- Live tests for real external systems when required by the release gate.
- Security tests for authorization, secrets, tenant isolation, and unsafe operation controls.
- Regression tests for repeated failures and production incidents.

## Fake And Mock Rules

Fakes are preferred for stable ports because they model behavior. Mocks are acceptable for interaction verification but should not become a copy of implementation details.

Test doubles must be scoped to public ports and contracts. They must not depend on private persistence tables or hidden service internals.

## Contract Boundary Rule

When a module exposes an API, event, SDK method, or config schema, it must provide:

- versioned contract.
- example payloads.
- compatibility rules.
- consumer-facing error behavior.
- contract tests.
- migration notes for breaking changes.

## Determinism Rule

Tests must control time, ids, randomness, external IO, and model outputs. Non-deterministic tests must be isolated as live or integration tests with explicit evidence capture.

## LLM And Agent Test Rule

LLM-dependent behavior must be tested through deterministic wrappers, recorded fixtures, structured evaluation data, or live-test gates. Core business rules must not rely only on model output.

## Acceptance Criteria

Testing architecture is acceptable when a developer can run fast deterministic tests locally, contract changes are caught before release, live tests provide evidence without blocking all unit tests, and external dependencies can be replaced through documented ports.

## Test Placement Standard

All executable tests must live in the root `tests/` tree so test ownership, discovery, and CI commands remain predictable.

Required placement:

```text
tests/backend/<service-or-app-name>/test_*.py
tests/frontend/<app-or-feature-name>/test_*.ts
tests/frontend/<app-or-feature-name>/test_*.tsx
tests/frontend/<app-or-feature-name>/*.spec.ts
tests/frontend/<app-or-feature-name>/*.spec.tsx
```

Backend service code may expose public test seams through ports, adapters, factories, fakes, and documented contracts, but tests must import through the service public package or public contract surface. Tests should not rely on private table names, hidden module internals, or service-local cache artifacts.

Contract tests for APIs and events should sit beside the owning backend test suite, for example `tests/backend/services/core-data-service/test_core_data_service.py` until a larger suite is split into `unit`, `contract`, or `integration` subdirectories under the same owner folder.

CI and local validation should use root-level test paths, never service-local test paths. Example:

```bash
PYTHONPATH=backend/services/core-data-service/src .venv/bin/python -m pytest tests/backend/services/core-data-service
```


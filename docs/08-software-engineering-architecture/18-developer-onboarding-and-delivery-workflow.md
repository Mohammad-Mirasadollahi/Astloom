---
doc_id: as.doc.sea.developer-onboarding-and-delivery-workflow
title: 18 - Developer Onboarding And Delivery Workflow
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how a new engineer should understand Astloom and deliver
  changes safely. It connects architecture documents, repository structure, local development,
  testing, review, and release into one practical workflow.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/18-developer-onboarding-and-delivery-workflow.md
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

# 18 - Developer Onboarding And Delivery Workflow

## Purpose

This document defines how a new engineer should understand Astloom and deliver changes safely. It connects architecture documents, repository structure, local development, testing, review, and release into one practical workflow.

## Onboarding Goals

A new engineer should be able to answer:

- what Astloom is.
- which modules exist.
- which module owns each concept.
- how to run local development safely.
- how to add a service, package, contract, or adapter.
- how to test changes.
- how to update documentation.
- how to release safely.
- how to record gaps and decisions.

## First Reading Path

Recommended reading order for engineers:

1. docs/README.md.
2. docs/00-master-plan/00-index.md.
3. docs/00-master-plan/05-complete-system-blueprint.md.
4. docs/08-software-engineering-architecture/00-index.md.
5. docs/08-software-engineering-architecture/05-modular-project-structure.md.
6. docs/08-software-engineering-architecture/06-engineering-operating-model.md.
7. docs/08-software-engineering-architecture/11-testing-and-verification-engineering.md.
8. docs/08-software-engineering-architecture/13-local-development-and-environment-engineering.md.
9. docs/10-gap-analysis/00-index.md.
10. docs/11-logical-implementation-examples/00-index.md.

Then read the phase or module docs for the area being changed.

## Repository Discovery Checklist

Before implementing a change, an engineer should locate:

- owning service.
- related shared packages.
- public contracts.
- event types.
- persistence store.
- migrations.
- config schema.
- tests.
- docs.
- runbooks.
- known gaps.

If ownership is unclear, the engineer should not guess. They should record or update a gap and request architecture review.

## New Feature Workflow

1. Read relevant master plan and phase docs.
2. Identify owning bounded context.
3. Identify public APIs and events.
4. Identify persistence and migration impact.
5. Identify config and port impact.
6. Write or update design docs.
7. Add or update contracts.
8. Add domain tests.
9. Add application and integration tests.
10. Add contract tests.
11. Update observability fields.
12. Update docs and indexes.
13. Run affected verification.
14. Prepare release notes.

## New Service Workflow

1. Confirm the new service is justified by bounded context rules.
2. Add service folder under services.
3. Add service README.
4. Define domain, application, API, infrastructure, worker, test, config, and migration folders.
5. Define public contracts.
6. Add local development config and non-default port allocation.
7. Add health and readiness behavior.
8. Add observability standards.
9. Add CI test gates.
10. Add runbook entries.
11. Update Software Engineering Architecture docs if the service changes the system model.

## New Contract Workflow

1. Identify producer owner.
2. Identify consumer owners.
3. Define schema and examples.
4. Define compatibility rules.
5. Define error behavior.
6. Define idempotency behavior when relevant.
7. Add producer tests.
8. Add consumer tests.
9. Update SDK or generated clients.
10. Update release notes.

## New Adapter Workflow

1. Define external provider capability.
2. Define permission requirements.
3. Define payload mapping.
4. Define authentication and callback validation.
5. Define failure handling.
6. Add fixtures from realistic provider payloads.
7. Add contract tests.
8. Add integration tests using sandbox or fake provider.
9. Add diagnostics.
10. Document operational runbook.

## New Rule Workflow

1. Define rule purpose.
2. Define evidence inputs.
3. Define deterministic checks.
4. Define semantic checks if needed.
5. Define severity.
6. Define escalation behavior.
7. Define explanation output.
8. Add positive and negative examples.
9. Add tests.
10. Run in shadow mode before enforcement when risk is high.

## Documentation Update Workflow

Docs should change with the system.

Checklist:

- update relevant design docs.
- update index files.
- update contracts or examples if behavior changes.
- update gap analysis if assumptions remain.
- update runbooks if operation changes.
- validate links.
- keep HLD and LLD separated where required.

## Delivery Checklist

Before requesting review, the engineer should confirm:

- correct module ownership.
- no forbidden imports.
- contracts updated and validated.
- tests added at correct layers.
- migrations documented and validated.
- config documented and typed.
- ports are configurable and non-default in development.
- logs, metrics, traces, and audit behavior are considered.
- docs and indexes updated.
- gaps recorded.
- release notes prepared when needed.

## Acceptance Criteria

Developer onboarding and delivery workflow is acceptable when:

- a new engineer can find the correct docs and module boundaries.
- common change types have explicit workflows.
- delivery checklists include code, tests, docs, contracts, config, operations, and gaps.
- engineers do not need hidden tribal knowledge to make safe changes.

---
doc_id: as.doc.sea.engineering-governance-and-change-control
title: 17 - Engineering Governance And Change Control
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how engineering decisions, architecture changes, contract changes,
  module changes, and unresolved gaps should be governed. The goal is to keep Astloom flexible
  without allowing uncontrolled drift.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/17-engineering-governance-and-change-control.md
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

# 17 - Engineering Governance And Change Control

## Purpose

This document defines how engineering decisions, architecture changes, contract changes, module changes, and unresolved gaps should be governed. The goal is to keep Astloom flexible without allowing uncontrolled drift.

## Governance Principles

Engineering governance should be lightweight but explicit.

Principles:

- decisions should be recorded when they affect future work.
- contracts should not change silently.
- shared packages require stronger review than service internals.
- architecture changes require rationale and alternatives.
- unresolved assumptions become gap records.
- operational risk is reviewed before release.
- documentation changes with the system.

## Decision Records

Use decision records for choices that shape future engineering.

Decision records should include:

- title.
- status.
- context.
- decision.
- alternatives considered.
- consequences.
- affected modules.
- affected contracts.
- owner.
- review date when needed.

Examples requiring decision records:

- choosing modular monorepo.
- choosing event broker technology.
- choosing graph database technology.
- changing memory ranking strategy.
- changing service boundary.
- introducing a shared package.
- changing contract versioning strategy.

## Change Classification

Every change should be classified by risk.

| Risk Level | Examples | Required Control |
| --- | --- | --- |
| low | docs typo, internal test fixture | normal review |
| medium | service internal behavior, non-breaking API addition | module owner review |
| high | contract break, migration, shared package change | architecture and owner review |
| critical | auth, production data, approval bypass, destructive migration | security and operations review |

## Shared Package Governance

Shared packages create long-term coupling and need careful control.

Rules:

- a shared package must have a clear purpose.
- consumers must be listed.
- exported APIs must be documented.
- breaking changes require migration notes.
- business logic should not move into shared packages to avoid ownership.
- shared packages should have high test coverage and compatibility checks.

## Contract Change Control

Contract changes should follow compatibility rules.

Required steps:

1. update schema.
2. update examples.
3. run compatibility check.
4. update producer tests.
5. update consumer tests.
6. document migration or deprecation.
7. update release notes.

Breaking contract changes require explicit approval from affected consumer owners.

## Architecture Change Control

Architecture changes include:

- new service.
- removed service.
- changed service boundary.
- new persistent store.
- new broker topic family.
- new shared package.
- changed deployment topology.
- changed security boundary.
- changed port allocation range.

Architecture changes should update the relevant Software Engineering Architecture documents and master plan references.

## Gap Management

Gaps are known unknowns or unresolved design concerns.

A gap should be recorded when:

- the team lacks enough information to decide.
- implementation depends on future technology choice.
- security or operational risk remains unresolved.
- a required feature is deferred.
- a contract consumer is unknown.
- performance budget is not validated.

A gap entry should include:

- title.
- area.
- impact.
- current assumption.
- options.
- owner.
- target review date.
- closure criteria.

## Documentation Governance

Docs should be treated as engineering artifacts.

Rules:

- each major docs folder has an index.
- HLD and LLD remain separate where required.
- every new service links to relevant docs.
- every new contract links to examples and tests.
- every unresolved assumption links to gap analysis.
- docs should avoid vague future promises without acceptance criteria.

## Approval Matrix

| Change | Required Approval |
| --- | --- |
| new module | architecture owner and module owner |
| new public contract | producer owner and consumer owners |
| breaking contract | architecture owner and affected consumers |
| migration | data owner and operations owner |
| security-sensitive change | security owner |
| port allocation change | developer experience owner |
| production rollout | release owner and operations owner |
| high-risk rule change | rule owner and governance owner |

## Acceptance Criteria

Engineering governance is acceptable when:

- important decisions are recorded with rationale.
- contract and architecture changes have explicit review paths.
- shared packages do not become unowned dumping grounds.
- gaps are visible and owned.
- documentation remains part of change control.

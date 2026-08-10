---
doc_id: as.doc.sea.engineering-operating-model
title: 06 - Engineering Operating Model
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how engineering work should happen inside Astloom. It explains
  how teams should move from design to implementation, how responsibilities should be assigned,
  how work should be reviewed, and how technical decisions should become traceable system
  knowledge.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/06-engineering-operating-model.md
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

# 06 - Engineering Operating Model

## Purpose

This document defines how engineering work should happen inside Astloom. It explains how teams should move from design to implementation, how responsibilities should be assigned, how work should be reviewed, and how technical decisions should become traceable system knowledge.

Astloom is not only a set of services. It is a system for coordinated software engineering. The engineering model must therefore make ownership, decision flow, delivery flow, review flow, and evidence flow explicit.

## Engineering Goals

The engineering organization should optimize for these outcomes:

- predictable delivery without hiding architectural risk.
- clear module ownership and explicit dependency direction.
- small changes that can be reviewed with enough context.
- public contracts that do not drift from implementation.
- documentation that changes with code and decisions.
- local development that is reproducible and does not depend on default ports.
- test suites that reflect real service boundaries.
- operational behavior that can be debugged from logs, metrics, traces, events, and audit records.
- future agent work that can use structured project memory instead of stale chat history.

## Engineering Work Types

Astloom engineering work should be classified into explicit work types. Each work type has different evidence and review expectations.

| Work Type | Description | Required Evidence | Primary Review |
| --- | --- | --- | --- |
| Feature | Adds user-visible or agent-visible capability | feature spec, contracts, tests, docs links | service owner and product owner |
| Platform | Adds shared infrastructure or cross-cutting capability | architecture note, migration plan, affected modules | architecture owner |
| Contract | Changes API, event, or adapter schema | versioned schema, compatibility notes, contract tests | producer and consumer owners |
| Data | Changes persistence, graph model, indexing, or retention | migration, rollback notes, data validation tests | data owner |
| Rule | Adds or changes policy logic | rule spec, examples, explainability output | governance owner |
| Adapter | Adds external tool or vendor integration | capability mapping, failure modes, security review | integration owner |
| Documentation | Changes design, logic, runbooks, or examples | links, index update, drift check | doc owner or module owner |
| Refactor | Changes structure without expected behavior change | impacted tests, before and after dependency notes | module owner |
| Security | Changes authentication, authorization, secrets, or sensitive data handling | threat notes, audit behavior, negative tests | security owner |
| Operations | Changes deployment, observability, CI, release, or runbooks | rollout plan, metrics, rollback plan | operations owner |

## Lifecycle From Idea To Production

Engineering work should pass through a traceable lifecycle.

1. Problem framing: define the user, agent, service, or operator problem.
2. Scope classification: classify the work type and affected modules.
3. Design entry: create or update the relevant docs, contracts, and architecture notes.
4. Dependency review: identify upstream and downstream modules.
5. Implementation plan: define commands, queries, events, persistence changes, and tests.
6. Local verification: run service tests, contract tests, docs validation, and port preflight.
7. Review: reviewers inspect behavior, contracts, risk, tests, and docs alignment.
8. Release readiness: confirm migration, config, health checks, metrics, and rollback plan.
9. Production rollout: deploy with observability and audit evidence.
10. Post-release learning: record decisions, issues, follow-up tasks, and memory updates.

## Required Work Artifacts

Each meaningful change should create or update the correct artifacts.

Feature changes should include:

- updated feature documentation.
- HLD or LLD updates when architecture or behavior changes.
- command, query, API, or event contracts.
- unit tests for domain and application logic.
- integration tests for persistence or broker behavior.
- contract tests when public schemas change.
- operational notes for metrics, errors, and failure modes.
- gap entries when assumptions remain unresolved.

Infrastructure changes should include:

- configuration schema updates.
- port allocation or environment profile updates when needed.
- health and readiness behavior.
- rollback notes.
- local development instructions.
- CI validation changes.

Documentation-only changes should include:

- index updates.
- link validation.
- affected module references.
- explicit Implementation status when documentation describes designed-but-unimplemented behavior (allowed in-repo; must not read as shipped / product-ready). See `../00-master-plan/06-professional-documentation-standard.md` Designed Vs Shipped Honesty.

## Ownership Model

Every engineering area needs an owner even if one person initially fills many roles.

| Area | Owner Responsibility |
| --- | --- |
| Product architecture | feature scope, non-goals, roadmap alignment |
| System architecture | service boundaries, dependency direction, quality attributes |
| Domain modules | correctness of domain rules and lifecycle behavior |
| Contracts | API and event compatibility across producers and consumers |
| Data platform | persistence model, migrations, indexes, graph integrity |
| Memory platform | retrieval scoring, weights, decay, feedback, explainability |
| Documentation platform | doc anchors, drift detection, docs-as-code standards |
| Rule platform | semantic policy behavior, escalation, anomaly handling |
| Adapter platform | provider compatibility, vendor-specific behavior, failure handling |
| Developer experience | local setup, commands, port safety, onboarding |
| Release engineering | CI, release gates, migration gates, artifact versioning |
| Operations | monitoring, incident response, runbooks, capacity, backups |
| Security | auth, authorization, secrets, redaction, audit, tenant isolation |

Ownership does not mean isolated work. It means the owner is accountable for coherence, review quality, and long-term maintainability.

## Review Model

Reviews should be based on boundaries and risk, not only file count.

A change needs architecture review when it:

- creates a new service, package, adapter, or persistent store.
- changes dependency direction between modules.
- adds shared abstractions.
- changes runtime topology or deployment assumptions.
- changes cross-service events or API contracts.
- changes memory scoring, rule evaluation, or graph ingestion semantics.

A change needs data review when it:

- adds or modifies migrations.
- changes graph node or edge semantics.
- changes indexing, retention, archival, or deletion behavior.
- changes idempotency keys or causality metadata.

A change needs security review when it:

- changes auth, authorization, tenant isolation, secrets, or redaction.
- changes what data can be injected into prompts.
- changes external tool permissions.
- changes audit evidence or approval requirements.

## Engineering Evidence Model

Astloom should record engineering evidence as structured data.

Important evidence includes:

- which files changed.
- which contracts changed.
- which docs changed.
- which tests ran.
- which migrations ran.
- which rules were evaluated.
- which approvals were required.
- which risks were accepted.
- which gaps were recorded.
- which decisions explain the change.

The evidence should be useful both to humans and future agents.

## Definition Of Ready

A work item is ready for implementation when:

- the problem and expected outcome are clear.
- the owning module is identified.
- impacted contracts are known.
- persistence impact is known.
- expected events are known.
- test strategy is known.
- documentation updates are identified.
- unresolved assumptions are captured as gaps.
- local development requirements are known.

## Definition Of Done

A work item is done when:

- behavior is implemented behind the correct module boundary.
- public contracts are versioned and tested.
- required tests ship **in the same change** as the behavior (concurrent code-and-tests law in `37-test-authoring-standard.md`); reviewers reject material code without the mandated family.
- domain, application, integration, contract, fuzz, live, and security tests pass as applicable for the change type.
- documentation and indexes are updated.
- configuration is typed and does not hard-code environment values.
- development ports are configurable and validated.
- observability fields are present.
- failure modes are documented.
- migrations are validated.
- gap records exist for unresolved issues.
- release notes include contract, migration, config, and operational impact.

## Engineering Metrics

The team should track metrics that reveal engineering quality.

Useful metrics include:

- contract compatibility failures per release.
- time from doc drift detection to doc update.
- number of services with undocumented ports.
- number of modules importing forbidden internals.
- test coverage by layer, not only global percentage.
- failed migrations in test environments.
- dead-letter event count by event type.
- memory retrieval explanation coverage.
- graph ingestion stale edge count.
- mean time to diagnose incidents.
- number of unresolved gaps by owner and age.

Metrics should guide improvement. They should not become vanity numbers.

## Acceptance Criteria

The engineering operating model is acceptable when:

- every significant change has an owner, work type, review path, and evidence trail.
- engineers know what artifacts are required before implementation starts.
- review requirements are risk-based and documented.
- done means code, tests, docs, contracts, config, and operations are aligned.
- unresolved questions are visible in gap analysis instead of hidden in implementation.

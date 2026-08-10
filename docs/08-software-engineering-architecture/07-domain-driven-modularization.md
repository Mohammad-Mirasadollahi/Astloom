---
doc_id: as.doc.sea.domain-driven-modularization
title: 07 - Domain Driven Modularization
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how Astloom should be decomposed into domains, bounded contexts,
  modules, and services. It explains how engineering should decide where logic belongs and
  how to prevent the system from becoming a set of coupled utilities.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/07-domain-driven-modularization.md
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

# 07 - Domain Driven Modularization

## Purpose

This document defines how Astloom should be decomposed into domains, bounded contexts, modules, and services. It explains how engineering should decide where logic belongs and how to prevent the system from becoming a set of coupled utilities.

## Modularization Principles

Astloom should be modularized around business capability and system responsibility, not around technical layers alone.

The key principle is ownership of meaning. A module owns a concept when it controls the lifecycle, invariants, state transitions, and public language for that concept.

Examples:

- core-data-service owns Activity, WorkLog, Decision, Issue, and Task lifecycle.
- memory-service owns memory retrieval, consolidation, weights, decay, and context assembly.
- code-graph-service owns symbols, code edges, graph snapshots, and impact analysis.
- docs-sync-service owns documentation anchors, frontmatter validation, and drift detection.
- rule-engine-service owns semantic policy decisions and escalation flow.

## Bounded Contexts

Astloom should use the following bounded contexts.

| Context | Owned Concepts | Main Responsibility |
| --- | --- | --- |
| Work Context | Activity, WorkLog, Decision, Issue, Task | structure work and preserve evidence |
| Memory Context | MemoryItem, MemoryCluster, ContextWindow, RetrievalScore | select useful context for agents |
| Documentation Context | Document, Anchor, DocFlag, DriftSignal | keep docs linked to code and decisions |
| Code Graph Context | Repository, File, Symbol, Edge, Snapshot | represent code knowledge and impact |
| Rule Context | Rule, Policy, Evaluation, Escalation | evaluate risk and route actions |
| Broker Context | Event, Subscription, Retry, DeadLetter | deliver and replay platform events |
| Adapter Context | Provider, Capability, ExternalPayload | integrate tools and vendors |
| Configuration Context | Profile, FeatureFlag, PortAllocation | control runtime behavior safely |
| Audit Context | AuditRecord, EvidenceBundle, RetentionPolicy | preserve compliance evidence |

## Ubiquitous Language

Each bounded context should define its own vocabulary. Engineers should not reuse a word across contexts unless the meaning is intentionally shared.

Examples:

- Task in Work Context means executable follow-up work.
- Task in an external ticket system is an integration representation and must be mapped through adapter-service.
- MemoryItem in Memory Context is retrievable context with weight and provenance.
- Document Anchor in Documentation Context is a stable link between docs and system elements.
- Symbol in Code Graph Context is a parsed code element with stable identity.

Ambiguous terms should be clarified in glossary and contract docs.

## Context Mapping

Contexts communicate through explicit maps.

| Source Context | Target Context | Integration Method | Example |
| --- | --- | --- | --- |
| Work | Memory | event | WorkLogCreated creates candidate memory |
| Work | Rule | event and query | TaskCreated triggers policy evaluation |
| Code Graph | Documentation | event | SymbolChanged triggers doc drift check |
| Documentation | Work | command | DriftSignal creates Issue and Task |
| Rule | Work | command | RuleViolation creates escalation Task |
| Adapter | Work | command | external approval response updates Task |
| Configuration | All | config query | service reads feature flag or port profile |
| Audit | All | event subscription | significant events become audit records |

## Module Boundary Heuristics

Create a new module or service when:

- the concept has its own lifecycle.
- the concept has rules that change independently.
- the data model requires separate ownership.
- the module would have different scaling or deployment needs.
- the module requires different security or retention rules.
- the module has public contracts used by several consumers.

Do not create a new module when:

- the split only mirrors folder structure.
- the logic has no independent behavior.
- the module would only contain generic helper functions.
- ownership is unclear.
- the first implementation can be a package or internal component with a clear future extraction path.

## Aggregate Boundaries

Domain aggregates should protect invariants.

Examples:

- A Task aggregate should protect status transitions, assignment rules, dependency constraints, and closure evidence.
- A Decision aggregate should protect author, reason, alternatives, source evidence, and supersession state.
- A MemoryItem aggregate should protect source provenance, weight factors, trust metadata, and retention classification.
- A GraphSnapshot aggregate should protect graph version, ingestion source, parser version, and consistency markers.
- A RuleEvaluation aggregate should protect rule version, input evidence, result, explanation, and escalation action.

Aggregates should not expose mutable internal collections directly. Changes should happen through named domain operations.

## Domain Services

Use a domain service when a rule belongs to the domain but does not naturally fit one entity.

Examples:

- memory-ranker compares multiple MemoryItems using configurable weights.
- task-decomposer creates executable tasks from an Issue and dependency graph.
- impact-analyzer evaluates graph relationships between changed symbols and affected modules.
- policy-evaluator determines whether evidence violates a semantic rule.
- doc-drift-detector compares code graph changes with documentation anchors.

Domain services should be deterministic when possible and should not call databases, brokers, or external APIs directly.

## Application Services

Application services orchestrate use cases.

They should:

- load aggregates from repositories.
- call domain services.
- enforce authorization and tenant boundaries.
- save state through repositories.
- publish domain events through infrastructure adapters.
- record audit evidence.
- return application-level results.

They should not contain low-level persistence code or transport-specific parsing.

## Shared Kernel Policy

A shared kernel is allowed only for stable concepts that truly cross contexts.

Allowed shared kernel examples:

- correlation ID.
- actor identity reference.
- tenant or workspace reference.
- event envelope metadata.
- timestamp and causality metadata.
- validation error shape.

Forbidden shared kernel examples:

- Task business rules shared by all services.
- Memory scoring formula hidden in a utility package.
- Graph write logic used directly by docs-sync-service.
- Rule evaluation internals imported by api-gateway.

## Anti-Corruption Layers

Every external integration should use an anti-corruption layer.

Adapter-service should translate external concepts into Astloom concepts. It should not leak vendor-specific fields into core services unless those fields are stored as clearly named metadata.

Examples:

- Jira issue maps to Astloom Task through adapter-service.
- GitHub review maps to approval evidence through adapter-service.
- IDE command maps to Activity or Task command through api-gateway and contracts.
- Provider model capability maps to AdapterCapability and not to hard-coded provider logic inside memory-service.

## Dependency Direction

The stable dependency direction is:

    domain concepts -> application use cases -> service APIs and workers -> infrastructure adapters

Cross-context communication should go through:

- events.
- API contracts.
- commands.
- queries.
- SDK clients.
- documented projections.

Direct imports across service internals are forbidden.

## Example Flow

A repository symbol changes.

1. code-graph-service ingests the repository change.
2. code-graph-service updates symbols and edges.
3. code-graph-service emits SymbolChanged.
4. docs-sync-service consumes SymbolChanged.
5. docs-sync-service checks document anchors.
6. docs-sync-service emits DocumentationDriftDetected.
7. core-data-service creates Issue and Task records.
8. rule-engine-service evaluates risk and ownership rules.
9. memory-service updates future retrieval context.
10. audit-service records the evidence bundle.

No service directly mutates another service database in this flow.

## Acceptance Criteria

Domain modularization is acceptable when:

- every important concept has one owning context.
- cross-context communication uses public contracts.
- aggregates protect lifecycle invariants.
- domain services are deterministic and testable.
- adapter logic does not leak vendor behavior into core domains.
- shared packages contain stable primitives, not hidden business logic.

---
doc_id: as.doc.tech.index
title: 06 - Technical Logic and Verification Index
doc_type: index
status: active
schema_version: '1.0'
owner: platform-docs
summary: Phase 6 makes Phases 1 through 5 implementation-ready and verifiable.
tags:
- index
- tech
phase: 06-technical-logic
canonical_path: docs/06-technical-logic/00-index.md
lifecycle_lane: current
concern_lane: onboarding
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 06 - Technical Logic and Verification Index


## Purpose

Phase 6 makes Phases 1 through 5 implementation-ready and verifiable. Earlier phase folders define product features and service designs. This folder owns the algorithms, invariants, runtime stitching, failure handling, and technical test strategy that prove those designs can be b.

## Mission

Phase 6 makes Phases 1 through 5 implementation-ready and verifiable. Earlier phase folders define product features and service designs. This folder owns the algorithms, invariants, runtime stitching, failure handling, and technical test strategy that prove those designs can be built and checked without hidden behavior.

Phase 6 is a **first-class delivery phase** with its own roadmap gate. It is not a side annex of Phases 1 through 5, and it is not Phase 7 (Code-Knowledge Graph).

## Phase Boundary

| In scope | Out of scope |
| --- | --- |
| Cross-cutting technical logic for Phases 1 through 5 | Neo4j code-graph product features (Phase 7) |
| End-to-end runtime stitching across those domains | Full software engineering playbook (Phase 8) |
| Technical test strategy and Definition of Done | Platform governance and ops controls (Phase 9) |
| Deterministic boundaries around model judgment | New product features unrelated to verification |

## Files

### Phase design (Phase 6 package)

- `08-feature-specification.md` defines Phase 6 mission, verification features, and requirements.
- `09-high-level-design.md` defines verification actors, components, and boundaries.
- `10-low-level-design.md` defines verification modules, commands, queries, and failure handling.
- `11-data-contracts-and-events.md` defines verification evidence contracts and events.
- `12-risks-challenges-and-acceptance.md` defines risks and Phase 6 acceptance criteria.
- `13-detailed-section-design.md` provides deep rationale, edge cases, and phase output.

### Domain technical logic (owned by this phase)

- `01-core-data-model-technical-logic.md` explains entity invariants, write paths, state transitions, idempotency, audit reconstruction, and task decomposition logic.
- `02-memory-context-technical-logic.md` explains memory classification, consolidation, retrieval scoring, prompt cache invalidation, decay, and token budgeting.
- `03-docs-sync-technical-logic.md` explains code indexing, AST anchors, documentation graph linking, drift detection, Bloom filters, and CI merge gates.
- `04-rules-orchestration-technical-logic.md` explains policy evaluation, deterministic pre-checks, LLM judge constraints, escalation, impact traversal, and task routing.
- `05-interoperability-technical-logic.md` explains Universal Agent JSON validation, broker routing, delivery semantics, adapter mapping, tenancy, and dead-letter handling.
- `06-end-to-end-runtime-logic.md` explains how Phases 1 through 5 work together in one runtime flow.
- `07-technical-test-strategy.md` defines technical acceptance tests and canonical `tests/` paths.

## Related Later Phases

- `../07-code-knowledge-graph/06-technical-implementation-logic.md` defines Neo4j, Tree-sitter, hash diffing, embedding, graph upsert, and graph-guided code generation implementation logic (Phase 7).
- `../08-software-engineering-architecture/11-testing-and-verification-engineering.md` expands engineering-wide test practice (Phase 8).
- `../08-software-engineering-architecture/25-live-and-unit-test-strategy.md` defines Unit Test and Live Test operating model (Phase 8).

## Reading Order

1. Read `08-feature-specification.md` and `12-risks-challenges-and-acceptance.md` for the Phase 6 gate.
2. Read `09-high-level-design.md` and `10-low-level-design.md` for verification system shape.
3. Read `06-end-to-end-runtime-logic.md` to understand runtime flow across Phases 1 through 5.
4. Read files `01` through `05` for domain technical logic.
5. Read `07-technical-test-strategy.md` for verification layers and Definition of Done.
6. Only then proceed to Phase 7 graph implementation logic.

## Design Rule

Every automated output must be traceable to input evidence, every model-based judgment must have a deterministic boundary around it, and every risky operation must be either idempotent, reversible, or explicitly approved by a human owner.

## Configurable Weighting Requirement

Memory retrieval, memory decay, graph retrieval, and forgotten-context handling must use versioned weighting profiles instead of hard-coded constants. The detailed logic is documented in `02-memory-context-technical-logic.md` and `../07-code-knowledge-graph/06-technical-implementation-logic.md`.

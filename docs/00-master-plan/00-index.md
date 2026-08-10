---
doc_id: as.doc.master.index
title: 00 - Master Plan Index
doc_type: index
status: active
schema_version: '1.0'
owner: platform-docs
summary: This folder describes the complete Astloom plan at product and architecture level.
tags:
- index
- master
phase: 00-master-plan
canonical_path: docs/00-master-plan/00-index.md
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

# 00 - Master Plan Index

## Purpose

This folder describes the complete Astloom plan at product and architecture level. It is the entry point for professional readers who need the whole system before going into phase-specific design. The documentation is written for experienced software engineers, architects, product designers, operators, security reviewers, and technical decision makers rather than a general audience.

Product positioning starts with a wedge: Astloom connects to a codebase and improves connected AI coding outputs. The vendor-neutral control plane is the architecture destination built on that wedge. Read `01-product-scope-and-feature-catalog.md` before phase designs.

## Files

- 01-product-scope-and-feature-catalog.md explains the wedge product promise, control-plane expansion, users, full feature set, and non-goals.
- 02-roadmap-and-phase-gates.md defines implementation phases, sequencing, dependencies, and exit criteria.
- 03-global-architecture-hld.md provides the system-wide high-level architecture.
- 04-cross-cutting-challenges.md captures challenges that affect multiple phases.
- 05-complete-system-blueprint.md provides the full product and architecture narrative.
- 06-professional-documentation-standard.md defines the professional documentation standard for writing implementation-grade engineering and product design specifications, including designed-vs-shipped honesty (unimplemented design may be in git; it must not read as product-ready).
- 08-documentation-structure-and-machine-ingest-standard.md defines tree numbering, titles, frontmatter, RAG/LLMIndex/GraphRAG authoring shape, and fallback ingest tiers.
- 09-documentation-classification-and-lanes.md defines documentation lanes: lifecycle (initial/current/future), concern (design/problem/gap/cross-team/…), audience, authority, and visibility — including honest voice for future design.
- 10-documentation-standardization-procedure.md is the normative audit → remediate → split → link → accept method that keeps `docs/` Full-tier and machine-green.

## Phase Folders

- Phase 1: Core Data Model
- Phase 2: Memory and Token Optimization
- Phase 3: Docs-as-Code and Synchronization
- Phase 4: Rule Engine and Orchestration
- Phase 5: Interoperability and Enterprise Ecosystem
- Phase 6: Technical Logic and Verification (`../06-technical-logic/`, gated in `02-roadmap-and-phase-gates.md`)
- Phase 7: Code-Knowledge Graph
- Phase 8: Software Engineering Architecture
- Phase 9: Platform Governance and Operations
- Phase 10: Gap Analysis
- Phase 11: Logical Implementation Examples

## Phase 6 / Technical Section

Phase 6 is a first-class roadmap phase. Its design home is `../06-technical-logic/`. That folder contains phase-design files plus algorithms, state machines, invariants, runtime flow, failure handling, and the technical test strategy that verifies Phases 1 through 5 before Phase 7 begins.

## Code-Knowledge Graph Section

The Neo4j-backed code understanding and graph-guided code generation design is documented in ../07-code-knowledge-graph/.

## Software Engineering Architecture Section

The full software engineering playbook is documented in ../08-software-engineering-architecture/. It covers architecture principles, service boundaries, modular project structure, engineering operating model, domain-driven modularization, interface and contract engineering, data and persistence engineering, quality attributes, testing, CI/CD, release engineering, zero-touch installation, automated bootstrap, agent and resource connectivity automation, self-service operations, local and remote development, observability, extensibility, security engineering, threat modeling, governance, change control, onboarding, runtime topology, configuration model, and development port conflict prevention.

Engineers and product designers should read 06-professional-documentation-standard.md, 08-documentation-structure-and-machine-ingest-standard.md, and 09-documentation-classification-and-lanes.md before writing or reviewing new documents. Engineers should then read ../08-software-engineering-architecture/00-index.md first, and ../08-software-engineering-architecture/05-modular-project-structure.md before creating repository folders, services, packages, tools, scripts, configuration profiles, or cross-module tests.

## Platform Governance and Operations Section

Security, observability, release strategy, data retention, API governance, runbooks, automated deployment and connectivity procedures, risk register, and glossary are documented in ../09-platform-governance-operations/.

## Gap Analysis Section

Known gaps, unresolved assumptions, open decisions, and the gap triage process are documented in ../10-gap-analysis/.

## Logical Implementation Examples Section

Concrete implementation-oriented examples, runtime scenarios, and developer checklists are documented in ../11-logical-implementation-examples/.
- `07-agent-control-plane-product-boundary.md` is the normative decision that Astloom manages external agents and is not itself an agent or agent framework.

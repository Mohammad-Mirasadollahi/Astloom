---
doc_id: as.doc.sea.common-context-and-reuse-engineering
title: 28 - Common Context And Reuse Engineering
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how Astloom should engineer reusable common context so users
  do not need to repeat stable project rules, architectural constraints, documentation preferences,
  workflow expectations, and product definitions in every task.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/28-common-context-and-reuse-engineering.md
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

# 28 - Common Context And Reuse Engineering

## Purpose

This document defines how Astloom should engineer reusable common context so users do not need to repeat stable project rules, architectural constraints, documentation preferences, workflow expectations, and product definitions in every task.

The implementation must treat common context as a first-class, governed, scoped capability. It must not be implemented as hard-coded prompt text, hidden global memory, or scattered constants.

## Engineering Placement

The backend structure must include:

- `backend/domains/common-context/` for language, policies, events, use cases, examples, and model documentation.
- `backend/services/common-context-service/` for lifecycle management, proposal, scoring, bundle resolution, conflict detection, audit, and reporting signals.
- `backend/packages/common-context/` for reusable contracts, resolver interfaces, templates, and examples.
- `backend/configs/common-context-profiles/` for score weights, token budgets, approval thresholds, and feature toggles.
- `docs/12-common-context-reuse/` for feature, HLD, LLD, contracts, events, governance, and operations documentation.

## Engineering Rules

Common Context must be project-scoped by default, shareable only through explicit project-group composition, scored by configurable weights, explainable in every agent run, visible in the admin interface, tested with unit and live tests, reported through platform metrics, versioned, and auditable.

## Implementation Guidance

The resolver should run before an agent task is executed. It should receive task metadata and return a structured context bundle. The bundle should include only the most relevant common items and should preserve the reason for each selection.

Common Context should integrate with memory, but it should not become memory. Memory can provide evidence that an instruction is repeated. A reviewed common item is a separate governed artifact.

Common Context should integrate with rules, but it should not execute policy. It can reference rule packs and provide reusable rule text. Execution stays in the rule engine.

## Example

Instead of repeatedly telling the system that formal documentation must be English, HLD and LLD must be separate, and backend modules must include README files, these rules should become approved CommonItems. When a documentation or backend-structure task starts, the resolver injects only the relevant items and records the reason.

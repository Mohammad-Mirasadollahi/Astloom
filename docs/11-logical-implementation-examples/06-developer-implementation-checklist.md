---
doc_id: as.doc.examples.developer-implementation-checklist
title: Developer Implementation Checklist
doc_type: example
status: draft
schema_version: '1.0'
owner: platform-docs
summary: This checklist helps engineers translate the Astloom documentation into implementation
  tasks. It does not replace detailed design documents. It lists what must exist before each
  subsystem can be considered ready for coding or review.
tags:
- example
- examples
phase: 11-logical-implementation-examples
canonical_path: docs/11-logical-implementation-examples/06-developer-implementation-checklist.md
lifecycle_lane: current
concern_lane: example
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Developer Implementation Checklist

## Purpose

This checklist helps engineers translate the Astloom documentation into implementation tasks. It does not replace detailed design documents. It lists what must exist before each subsystem can be considered ready for coding or review.

## Core Data Model Checklist

- Entity IDs are stable and tenant-scoped.
- Activity, WorkLog, Decision, Issue, and Task schemas are versioned.
- State machines reject invalid transitions.
- Evidence references are stored before derived records are marked complete.
- Redaction runs before prompt-visible storage.
- Idempotency keys prevent duplicate logical records.
- Audit reconstruction query can follow correlation ID across records.

## Memory and Context Checklist

- Memory classifier supports working, episodic, semantic, restricted, and deprecated memory.
- WeightProfile is externalized and versioned.
- Retrieval explains included and omitted items.
- Current state wins over historical events.
- Forgotten-memory classifier handles dormant but important facts.
- ContextBundle stores source refs, token budget, static prompt version, and redaction status.
- Prompt cache invalidation is explicit.

## Docs and Code Graph Checklist

- Tree-sitter parser extracts symbols for supported languages.
- Normalized hash ignores formatting noise.
- Neo4j upsert is idempotent.
- CALLS and IMPORTS relationships have confidence values.
- Documentation frontmatter is validated.
- DriftFinding is created for stale or missing docs.
- Bloom filter negative lookup skips unnecessary graph queries.
- Generated code validation rejects unknown symbol references.

## Rule Engine Checklist

- Policies have owner, scope, severity, examples, and evaluation mode.
- Deterministic pre-checks run before LLM Judge.
- LLM Judge output is structured and evidence-bound.
- Risk aggregation handles low-confidence high-risk results.
- Escalation tickets include evidence, options, deadline, and owner.
- Expired high-risk approvals fail closed.
- Impact traversal avoids duplicate downstream Tasks.

## Interoperability Checklist

- Universal Agent JSON schema is versioned.
- Broker persists before delivery.
- Consumers are idempotent.
- Dead-letter records include failure reason and replay eligibility.
- Adapter capability profiles are explicit.
- Context injection checks tenant, project, role, sensitivity, and task assignment.
- Unauthorized subscribers do not receive restricted payloads.

## Software Engineering Checklist

- Service boundaries are explicit.
- Ports are configurable and non-default in development.
- Startup validates port availability.
- Services expose health and readiness checks.
- Configuration is layered by environment and project.
- Logs, metrics, and traces include correlation ID.
- Background jobs are retryable or resumable.

## Governance Checklist

- Security access rules are documented and tested.
- Retention and backup policies exist.
- Contract versions are tracked.
- Critical workflows have runbooks.
- Risk register has owners for high and critical gaps.
- Open decisions are converted into Decision records before implementation.

## Minimum Coding Readiness Criteria

Before coding a subsystem, engineers should have:

- feature spec,
- high-level design,
- low-level design,
- data contracts,
- technical logic,
- at least one logical example,
- test checklist,
- known gaps and open decisions.

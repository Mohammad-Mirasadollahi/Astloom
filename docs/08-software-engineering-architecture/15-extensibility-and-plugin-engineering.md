---
doc_id: as.doc.sea.extensibility-and-plugin-engineering
title: 15 - Extensibility And Plugin Engineering
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how Astloom should be engineered for extensibility. The platform
  must integrate with many agents, IDEs, repositories, ticket systems, approval systems, model
  providers, and internal tools without forcing core services to know every vendor or workflow.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/15-extensibility-and-plugin-engineering.md
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

# 15 - Extensibility And Plugin Engineering

## Purpose

This document defines how Astloom should be engineered for extensibility. The platform must integrate with many agents, IDEs, repositories, ticket systems, approval systems, model providers, and internal tools without forcing core services to know every vendor or workflow.

## Extensibility Goals

Astloom extensibility should allow teams to add capabilities without changing core domain logic.

Goals:

- integrate new providers through adapter-service.
- support new event consumers without changing producers.
- add new rules without changing unrelated services.
- add new memory scoring profiles without hard-coding logic.
- add new graph parsers without changing graph query consumers.
- add new UI views without direct database access.
- add new workflows through commands, events, and contracts.

## Extension Types

| Extension Type | Example | Primary Boundary |
| --- | --- | --- |
| agent adapter | connect a coding agent | adapter-service |
| IDE adapter | receive editor context | api-gateway and adapter-service |
| ticket adapter | create external work item | adapter-service |
| approval adapter | sync human approvals | adapter-service |
| model provider adapter | call embedding or reasoning provider | adapter-service or provider package |
| vector index accelerator | optional ANN replica (e.g. turbovec) behind `VectorIndexPort` | service infrastructure adapter; see `../13-technology-stack-and-platform-decisions/08-turbovec-ann-acceleration-integration.md` |
| rule pack | add security or compliance policy | rule-engine-service |
| memory profile | adjust retrieval weights | memory-service config |
| graph parser | parse a new language | code-graph-service parser adapter |
| UI plugin | show a new dashboard panel | admin-console public API |
| CLI plugin | add operator command | cli extension boundary |

## Plugin Boundary Principles

Extensions should use public interfaces only.

Rules:

- plugins must not import service internals.
- plugins must declare required capabilities.
- plugins must declare permissions.
- plugins must declare supported contract versions.
- plugins must validate input and output schemas.
- plugins must expose health or diagnostic behavior when long-running.
- plugins must not store secrets in source-controlled files.

## Capability Declaration

Every extension should declare capabilities.

Capability metadata should include:

- extension name.
- extension version.
- owner.
- supported Astloom contract versions.
- provided capabilities.
- required permissions.
- required configuration keys.
- emitted events.
- consumed events.
- external endpoints.
- failure modes.
- security notes.

Example capabilities:

- can_create_external_ticket.
- can_update_external_ticket_status.
- can_receive_ide_selection.
- can_generate_embedding.
- can_run_semantic_policy_check.
- can_parse_python_symbols.

## Adapter Engineering

Adapters should isolate external provider behavior.

Adapter responsibilities:

- authenticate with provider.
- validate provider payloads.
- translate external payloads into Astloom contracts.
- translate Astloom commands into provider actions.
- normalize errors.
- preserve external reference IDs.
- support retries and idempotency.
- record audit-safe evidence.

Adapters should not own core domain decisions. For example, a ticket adapter may create an external ticket, but core-data-service owns Task lifecycle.

## Rule Pack Engineering

Rule packs should be versioned and testable.

A rule pack should include:

- rule identifiers.
- owner.
- version.
- description.
- input evidence requirements.
- deterministic checks.
- semantic checks when needed.
- severity mapping.
- escalation policy.
- examples.
- tests.

Rules that use model judgment should return explanations and confidence metadata.

## Memory Profile Engineering

Memory profiles should be config-driven.

A memory profile should define:

- weight factors.
- factor ranges.
- source priority.
- recency curve.
- confidence threshold.
- project similarity behavior.
- task similarity behavior.
- risk sensitivity behavior.
- context budget.
- explanation fields.

Memory profiles should be versioned so retrieval behavior can be audited.

## Parser Extension Engineering

Code graph parser extensions should support new languages or frameworks.

Parser extension requirements:

- language identifier.
- parser version.
- supported file patterns.
- symbol extraction rules.
- edge extraction rules.
- stable symbol ID strategy.
- error handling.
- performance budget.
- fixture repository.
- graph consistency tests.

## Extension Lifecycle

Extensions should follow a lifecycle.

1. proposal.
2. capability declaration.
3. contract definition.
4. security review.
5. implementation.
6. test fixtures.
7. integration tests.
8. documentation.
9. rollout in disabled or shadow mode.
10. enablement through feature flag or config.
11. monitoring and support.

## Extension Failure Handling

Extensions fail more often than core services because external systems change.

Failure handling should include:

- timeout policy.
- retry policy.
- rate limit handling.
- provider error normalization.
- dead-letter event behavior.
- fallback behavior.
- disabled mode.
- operator diagnostics.
- audit record for failed external action.

## Acceptance Criteria

Extensibility engineering is acceptable when:

- new providers can be added through adapters without changing core domain services.
- plugins declare capabilities, permissions, contracts, and config.
- rule packs, memory profiles, and parsers are versioned and testable.
- extension failures are observable and do not corrupt core state.

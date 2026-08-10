---
doc_id: as.doc.interop.risks-challenges-and-acceptance
title: Interoperability and Enterprise Ecosystem - Risks, Challenges, and Acceptance
doc_type: gap
status: draft
schema_version: '1.0'
owner: platform-docs
summary: '- Protocol design must be strict enough for automation and flexible enough for different
  vendors. - Vendor adapters will drift as external tools change APIs and output formats.
  - Pub/Sub requires delivery guarantees, replay, ordering strategy, and dead-letter handling.
  - Cross-do.'
tags:
- gap
- interop
phase: 05-interoperability-ecosystem
canonical_path: docs/05-interoperability-ecosystem/05-risks-challenges-and-acceptance.md
lifecycle_lane: future
concern_lane: gap
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Interoperability and Enterprise Ecosystem - Risks, Challenges, and Acceptance


## Purpose

- Protocol design must be strict enough for automation and flexible enough for different vendors. - Vendor adapters will drift as external tools change APIs and output formats. - Pub/Sub requires delivery guarantees, replay, ordering strategy, and dead-letter handling. - Cross-do.

## Challenges

- Protocol design must be strict enough for automation and flexible enough for different vendors.
- Vendor adapters will drift as external tools change APIs and output formats.
- Pub/Sub requires delivery guarantees, replay, ordering strategy, and dead-letter handling.
- Cross-domain automation increases governance needs because business actions can be more sensitive than code actions.
- Enterprise customers require tenant isolation, access control, observability, and data retention guarantees.

## Mitigation Strategy

- Version every protocol and adapter contract.
- Add adapter conformance tests and capability discovery.
- Use channel-level authorization and message retention policies.
- Keep human approval available for sensitive non-code workflows.
- Track broker delivery health, replay counts, dead-letter events, and adapter failures.

## Acceptance Criteria

- A backend agent can announce API readiness and a frontend IDE plugin can receive the event without custom direct integration.
- At least two different agent vendors can exchange task state through the same protocol.
- Events can be replayed for debugging and failed deliveries are visible in a dead-letter queue.
- A code release can trigger non-code department Tasks through governed workflows.

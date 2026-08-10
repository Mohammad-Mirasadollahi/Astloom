---
doc_id: as.doc.interop.index
title: 05 - Interoperability and Enterprise Ecosystem Index
doc_type: index
status: active
schema_version: '1.0'
owner: platform-docs
summary: Connect different AI coding tools, models, IDEs, departments, humans, SDK clients,
  adapters, and external systems through a shared protocol, broker, developer platform, and
  operating model.
tags:
- index
- interop
phase: 05-interoperability-ecosystem
canonical_path: docs/05-interoperability-ecosystem/00-index.md
lifecycle_lane: current
concern_lane: onboarding
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.1.4
updated_at: 2026-08-10
---

# 05 - Interoperability and Enterprise Ecosystem Index


## Purpose

Connect different AI coding tools, models, IDEs, departments, humans, SDK clients, adapters, and external systems through a shared protocol, broker, developer platform, and operating model.

## Mission

Connect different AI coding tools, models, IDEs, departments, humans, SDK clients, adapters, and external systems through a shared protocol, broker, developer platform, and operating model.

## Files

- `01-feature-specification.md` defines interoperability features and functional requirements.
- `02-high-level-design.md` defines actors, components, broker flow, integrations, and reliability requirements.
- `03-low-level-design.md` defines protocol validation, broker routing, adapter mapping, context injection, tenant boundaries, and dead-letter behavior.
- `04-data-contracts-and-events.md` defines protocol, broker, adapter, and workflow contracts.
- `05-risks-challenges-and-acceptance.md` defines risks and acceptance criteria.
- `06-detailed-section-design.md` provides deep rationale, protocol behavior, broker design, adapter responsibilities, edge cases, and phase output.
- `07-sdk-and-developer-platform.md` defines SDK families, developer platform, Agent SDK, Adapter SDK, Admin SDK, Test SDK, scoped clients, authentication, transport, events, errors, versioning, packaging, and acceptance criteria.
- `08-agent-communication-language-and-runtime-sdk.md` defines the agent lingua franca, translator boundary, and integrations for LangChain, LangGraph, Codex, IDE-based workers, MCP, and custom runtimes.
- `09-multi-vendor-agent-network-ecosystem.md` defines the multi-vendor and federated-network ecosystem vision, topology layers, interaction patterns, and implementation map (demo vs roadmap).
- `10-external-vcs-and-tracker-mapping.md` defines anti-corruption mapping from GitHub/GitLab/Jira/Linear into Astloom Issue/Task/ChangeSet/Review aggregates (external systems are projections, not SoR).
- `11-sdk-release-and-adapter-harness.md` defines SDK release ownership, generated clients, adapter capability declarations, secret references, and contract-test gates.
- `12-external-ticketing-live-quality-assessment.md` records ExternalTicket live evidence and remediation through TQ-009 (mapping policy, dispatch worker, vendor adapters, outbound push).
- `13-external-ticketing-improvement-specification.md` is the as-built ExternalTicket hardening contract (TKT-01…TKT-09), including tracker adapters and `:push-status`.
- Adapter-service domain code for ExternalTicket lives in the modular package `backend/services/adapter-service/src/adapter_service/core/` (see phase-5 API contract module layout).

## Related Stack Integrations

- Optional local ANN acceleration with [turbovec](https://github.com/RyanCodrai/turbovec) is specified under `../13-technology-stack-and-platform-decisions/08-turbovec-ann-acceleration-integration.md` (port/adapter boundary; not a runtime translator). Worked flow: `../11-logical-implementation-examples/08-turbovec-hybrid-retrieval-example.md`.

## Features Covered

- Universal Agent JSON
- Central Message Broker and Pub/Sub
- Vendor-Agnostic Adapters
- Cross-Domain Operating System
- SDK and Developer Platform
- Agent SDK
- Adapter SDK
- Runtime Translator SDK
- Admin SDK and Test SDK
- Multi-vendor agent network and federation (vision; broker and peer gateway on roadmap)
- External VCS and tracker projection mapping (GitHub/GitLab/Jira/Linear → native ChangeSet/Issue)
- Current ExternalTicket hardening (queries, concurrency, mapping policy, dispatch, optional vendor sandbox and status push)
- AgentTicket native lifecycle (orchestration-service; distinct from ExternalTicket)

## Related Technical Logic

- `../06-technical-logic/05-interoperability-technical-logic.md` explains Universal Agent JSON validation, broker routing, delivery semantics, adapter mapping, tenancy, and dead-letter handling.

## Related SDK Design

- `07-sdk-and-developer-platform.md` should be read before implementing SDK packages, agent integrations, adapters, admin automation, or SDK contract tests.
- `../08-software-engineering-architecture/27-sdk-engineering-and-contract-generation.md` should be read before implementing SDK package architecture, generated clients, release pipelines, and contract generation.
- `08-agent-communication-language-and-runtime-sdk.md` should be read before adding a runtime-specific agent connector or translating runtime messages.

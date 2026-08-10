---
doc_id: as.doc.docs.readme
title: Astloom Documentation Plan
doc_type: readme
status: active
schema_version: '1.0'
owner: platform-docs
summary: This documentation tree replaces the legacy flat documents numbered 0 through 5 with
  an indexed, phase-based English documentation set.
tags:
- readme
- docs
phase: docs
canonical_path: docs/README.md
lifecycle_lane: current
concern_lane: onboarding
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.2
updated_at: 2026-08-10
---

# Astloom Documentation Plan


## Purpose

This documentation tree replaces the legacy flat documents numbered 0 through 5 with an indexed, phase-based English documentation set.

This documentation tree replaces the legacy flat documents numbered 0 through 5 with an indexed, phase-based English documentation set.

Astloom connects to a codebase and improves the outputs of connected AI coding tools. It builds structured code knowledge, injects task-scoped context into IDE assistants and agent runtimes, and measures whether speed, quality, rework, and token cost improved. On that wedge, Astloom expands into a vendor-neutral control plane for AI agents, human reviewers, tools, documentation, memory, policies, and cross-department workflows. Astloom is not an agent and does not replace agent runtimes or frameworks. It registers and supervises external agents through adapters, routes durable tickets by capability, governs execution, and records structured evidence so AI work does not disappear into chat history.

This documentation is written for experienced software engineers, software architects, product designers, platform operators, security reviewers, and technical decision makers. It is not written as beginner-level or general-audience product copy. Feature and architecture documents should be implementation-grade specifications that combine engineering behavior with product workflow, interaction states, permissions, diagnostics, metrics, and acceptance criteria.

## Implementation status

Executable vertical slices and **feature/service gates** live under `backend/services/`, `backend/packages/`, `backend/configs/`, and `tests/backend/`. Suites are grouped by owning service or feature (for example `tests/backend/services/memory-service/`, `tests/backend/gates/port-profile-verification/`), not by roadmap phase number. Named pytest commands and suite layout live in [tests/README.md](../tests/README.md). The repository root [README.md](../README.md) is a minimal entry (install, high-level architecture, doc map). Product design docs in this tree are the normative specification; many describe target architecture ahead of code. That is allowed. Docs must not imply product readiness beyond what gates and tests prove (for example Neo4j runtime remains a design target for the code graph). See `00-master-plan/06-professional-documentation-standard.md` (Designed Vs Shipped Honesty) and `00-master-plan/09-documentation-classification-and-lanes.md`.

**Usage Profiles** (org/person configuration + Cursor MCP): see [08-software-engineering-architecture/35-usage-profile-and-cursor-mcp-onboarding.md](08-software-engineering-architecture/35-usage-profile-and-cursor-mcp-onboarding.md). **One-command remote connect (SSH + HTTP, operator examples):** [41-one-command-cross-platform-agent-onboarding.md](08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding.md). **Every `astloom` CLI command** (why, required flags, examples, what changes): [42-astloom-cli-command-reference.md](08-software-engineering-architecture/42-astloom-cli-command-reference.md). **Server/client software upgrade:** [51-software-upgrade-server-and-client.md](08-software-engineering-architecture/51-software-upgrade-server-and-client.md).

## Architecture at a glance

High-level plane (clients → MCP/CLI → domain services → PostgreSQL / Neo4j; external agents stay outside): root [README.md § Quick architecture](../README.md#quick-architecture).

Deeper specs in this tree:

- [00-master-plan/03-global-architecture-hld.md](00-master-plan/03-global-architecture-hld.md) — system-wide HLD
- [00-master-plan/05-complete-system-blueprint.md](00-master-plan/05-complete-system-blueprint.md) — product narrative + value stack
- [backend/services/README.md](../backend/services/README.md) — service inventory

## Documentation Map

- 00-master-plan/07-agent-control-plane-product-boundary.md is the normative product-boundary decision and must be read before agent, connector, orchestration, ticket, or model-runtime work.

- 00-master-plan/ defines the product scope, full feature catalog, roadmap, global architecture, cross-cutting challenges, complete system blueprint, professional documentation standard, documentation structure / machine-ingest standard (numbering, titles, frontmatter, RAG/GraphRAG, fallbacks), and documentation classification lanes (lifecycle, concern, audience, authority, visibility).
- 01-core-data-model/ defines Activity, WorkLog, Decision, Issue, and Task foundations, plus the Astloom-native collaboration surface (ChangeSet, reviews, discussion, labels) in `07`–`08`.
- 02-memory-and-context/ defines three-tier memory, consolidation, state-over-event context, prompt caching, decay, dynamic retrieval, configurable memory weighting, autonomous question discovery, FAQ memory, curiosity scoring, missing documentation discovery, batched consolidation, deferred documentation or review workflows, chat Q&A RAG incremental documentation (including code-vs-doc contradiction disclosure), and chat-quality prior-art catalogs from license-verified OSS systems.
- 03-docs-as-code-sync/ defines the documentation knowledge graph, AST anchoring, YAML frontmatter, Bloom filter lookup, and lightweight doc flags.
- 04-rule-engine-orchestration/ defines semantic rules, escalation, anomaly detection, dependency analysis, and task routing.
- 05-interoperability-ecosystem/ defines Universal Agent JSON, Pub/Sub broker, vendor adapters, IDE integrations, SDK and Developer Platform, Agent SDK, Adapter SDK, Admin SDK, Test SDK, and cross-domain workflows.
- 06-technical-logic/ is **Phase 6 (Technical Logic and Verification)**: domain algorithms and invariants for Phases 1 through 5, end-to-end runtime logic, technical test strategy, and the gated Definition of Done before Phase 7.
- 07-code-knowledge-graph/ defines the Neo4j-backed code graph, Tree-sitter ingestion, living documentation, Repository Code Wiki (future), Code Intelligence Enhancements (explore/risk/routes), production retrieval, scored dead-code / shared-package findings (`36`/`79`), phased smell/risk design (`80`), graph-guided generation, and token optimization.
- 08-software-engineering-architecture/ defines the full software engineering playbook: principles, service boundaries, modular project structure, engineering operating model, domain modularization, contracts, persistence, quality attributes, tests, CI/CD, zero-touch installation, bootstrap automation, agent and resource connectivity automation, self-service operations, project isolation, project composition, domain packs, feature profiles, custom rule enablement, admin web interface, live testing, unit testing, local development, observability, extensibility, security, governance, onboarding, runtime topology, configuration rules, and development port conflict prevention.
- 09-platform-governance-operations/ defines security, observability, release strategy, retention, API governance, runbooks, automated deployment and connectivity procedures, impact reporting, benefit measurement, risk register, and glossary.
- 10-gap-analysis/ captures known gaps, unresolved assumptions, open decisions, and the process for reviewing and closing them.
- 11-logical-implementation-examples/ provides implementation-oriented logical examples and checklists for engineers who will code the system.
- 12-common-context-reuse/ defines governed reusable project guidance (Common Context) for scoring, approval, and pre-run bundles.
- 13-technology-stack-and-platform-decisions/ defines the selected technology stack: Next.js, TypeScript, Python, FastAPI, PostgreSQL, pgvector, Neo4j, Redis, object storage, messaging, observability, and deployment profiles.
- 14-api-design-and-naming-standards/ defines API endpoint naming, DTO naming, error format, pagination, idempotency, API catalog, OpenAPI, SDK, and contract governance.
- 15-agent-workspace-guidance/ defines Agent Workspace Guidance: project-scoped AGENTS entry, always-on rules, and on-demand skills (including MCP-first routing to Astloom tools) delivered MCP-primary (optional filesystem export) as typed Common Context projections for connected coding agents.

## Reading Order

1. Start with 00-master-plan/00-index.md.
2. Read 00-master-plan/01-product-scope-and-feature-catalog.md for the wedge promise (connect to code, improve AI outputs including measured dead-code cleanup) and control-plane expansion.
3. Read 00-master-plan/05-complete-system-blueprint.md for the full product narrative.
4. Read `00-master-plan/06-professional-documentation-standard.md`, `00-master-plan/08-documentation-structure-and-machine-ingest-standard.md`, `00-master-plan/09-documentation-classification-and-lanes.md`, and **`00-master-plan/10-documentation-standardization-procedure.md`** before writing, reviewing, or bulk-standardizing documents. Use `astloom docs-standards` as the machine gate.
5. Read each phase folder in numeric order.
6. Inside each phase, read the local index file first, then follow the phase-specific file order listed there.
7. Read 02-memory-and-context/07-autonomous-question-discovery-and-faq-memory.md for repeated questions, curiosity scoring, FAQ memory, and missing documentation discovery.
8. Read 02-memory-and-context/08-batched-memory-and-deferred-knowledge-workflows.md for WorkBatch, deferred consolidation, deferred docs, and deferred code review.
9. Read 02-memory-and-context/09-chat-qa-rag-incremental-documentation.md for chat Q&A write-back into RAG, derived-doc retention, freshness on code change, and staged code-vs-doc contradiction disclosure.
9a. Read 02-memory-and-context/10-chat-quality-prior-art-license-and-method.md then 11–13 for OSS-derived chat quality levers (retrieval, grounding, rewrite/feedback) under clean-room license rules.
10. Read 06-technical-logic/00-index.md for **Phase 6** (Technical Logic and Verification) before Phase 7 implementation.
11. Read 06-technical-logic/06-end-to-end-runtime-logic.md before the phase-level technical logic files, then 08 through 12 for the Phase 6 design package and gate.
12. Read 07-code-knowledge-graph/00-index.md for graph-backed code understanding, living documentation, and graph-guided code generation only after the Phase 6 gate is understood.
13. Read 08-software-engineering-architecture/00-index.md for the complete engineering playbook.
14. Read 08-software-engineering-architecture/05-modular-project-structure.md before creating repository folders or new modules.
15. Read 08-software-engineering-architecture/06-engineering-operating-model.md before planning implementation work.
16. Read 08-software-engineering-architecture/08-interface-and-contract-engineering.md before changing APIs, events, SDKs, config schemas, adapter payloads, or graph contracts.
17. Read 05-interoperability-ecosystem/07-sdk-and-developer-platform.md and 08-software-engineering-architecture/27-sdk-engineering-and-contract-generation.md before implementing SDK packages, generated clients, adapter SDKs, agent SDKs, admin SDKs, test SDKs, or SDK release pipelines.
18. Read 08-software-engineering-architecture/11-testing-and-verification-engineering.md before writing verification plans.
19. Read 08-software-engineering-architecture/19-zero-touch-installation-and-bootstrap-automation.md before designing installation, bootstrap, generated configuration, first-run readiness, or installation evidence reports.
20. Read 08-software-engineering-architecture/20-agent-and-resource-connectivity-automation.md before designing agent onboarding, connector registration, capability discovery, connection profiles, or resource integration.
21. Read 08-software-engineering-architecture/21-automation-control-plane-and-self-service-operations.md before designing self-service operations, automated repair, drift detection, upgrades, or diagnostics bundles.
22. Read 08-software-engineering-architecture/22-product-design-and-engineering-specification-discipline.md before writing feature specifications, product experience specifications, operator workflows, or implementation-ready technical designs.
23. Read 08-software-engineering-architecture/23-project-isolation-and-composition-architecture.md before designing multi-project, project-group, memory scope, graph scope, report scope, or connector scope behavior.
24. Read 08-software-engineering-architecture/24-admin-web-interface-and-agent-control-surface.md before designing the web interface, agent control surface, memory management, task management, rule management, feedback, or tracking workflows.
25. Read 08-software-engineering-architecture/25-live-and-unit-test-strategy.md before designing Unit Tests, Live Tests, release validation, real-data safety, or test evidence workflows.
25a. Read 08-software-engineering-architecture/37-test-authoring-standard.md before writing tests with implementation (concurrent code-and-tests law, taxonomy, mocks/fakes, placement). Read 38-fuzzing-and-property-based-testing.md for fuzz and property-based suites.
26. Read 08-software-engineering-architecture/26-domain-customization-and-feature-control.md before designing domain packs, feature profiles, user-defined rules, feature hiding, or conversation-based rule suggestions.
27. Read 08-software-engineering-architecture/13-local-development-and-environment-engineering.md before running local or remote development stacks.
28. Read 08-software-engineering-architecture/18-developer-onboarding-and-delivery-workflow.md when onboarding or preparing a delivery checklist.
29. Read 09-platform-governance-operations/10-impact-reporting-and-benefit-measurement.md before designing reports for speed, bug reduction, architecture quality, rework, or token consumption.
30. Read 09-platform-governance-operations/00-index.md for operational governance, security, observability, release, retention, automated deployment, connectivity runbooks, impact reporting, and operational procedures.
31. Read 10-gap-analysis/00-index.md to review unresolved gaps, assumptions, and decisions that need future thinking.
32. Read 11-logical-implementation-examples/00-index.md to see concrete examples of how the system should behave when implemented.
33. Read 12-common-context-reuse/00-index.md for governed reusable guidance storage before Agent Workspace Guidance projections.
34. Read 15-agent-workspace-guidance/00-index.md for connect-time AGENTS / rules / skills delivery to coding agents (MCP-primary, optional export).
35. Read `backend/docs/STRUCTURE_STANDARD.md` before creating or moving backend folders.

## compatible IDE agent documentation (not product scope)

Configuring **IDE** rules, skills, and optional team workspace packs **for developing this repository** is documented separately from Astloom product phases:

- Start at [`docs/agents/00-index.md`](agents/00-index.md). Rules/skills live under `.cursor/rules/` and `.cursor/skills/`.
- **Team documentation method for Astloom quality:** [`docs/agents/team-documentation-playbook-for-astloom.md`](agents/team-documentation-playbook-for-astloom.md).
- **Complete team handout (full lists):** [`docs/agents/TEAM-HANDOUT-astloom-documentation-complete.md`](agents/TEAM-HANDOUT-astloom-documentation-complete.md).
- Workspace rule interview: [`docs/agents/ide-workspace-rule-discovery.md`](agents/ide-workspace-rule-discovery.md) (if present).

**Product** Skills / Rules / `AGENTS.md` for customer projects connected via MCP: [`15-agent-workspace-guidance/00-index.md`](15-agent-workspace-guidance/00-index.md). That phase does not replace the platform rule engine under `04-rule-engine-orchestration/`.

## Replacement Goal

The old flat documents numbered 0 through 5 have been replaced. Combined design documents have also been split into separate phase-specific design files. The documentation now includes feature scope, separate design files, contracts, challenges, acceptance criteria, detailed rationale, scenarios, edge cases, operational design guidance, technical logic, algorithms, graph-backed code understanding, modular project structure, a broad software engineering playbook, professional product design and engineering specification discipline, zero-touch installation, automated bootstrap, agent and resource connectivity automation, self-service operations, autonomous question discovery, FAQ memory, batched knowledge workflows, project isolation, project composition, domain packs, feature profiles, custom rule authoring, conversation-based rule suggestions, SDK platform, SDK generation, SDK testing, admin web interface, impact reporting, Unit Test strategy, Live Test strategy, port conflict prevention, operational governance, runbooks, risk tracking, gap analysis, logical implementation examples, verification strategy, Common Context reuse, technology stack decisions, API naming standards, and Agent Workspace Guidance for connected coding agents.

Optional turbovec ANN acceleration: ADR `13-technology-stack-and-platform-decisions/08-turbovec-ann-acceleration-integration.md`, RAG guide `13-technology-stack-and-platform-decisions/11-turbovec-for-rag.md`, hybrid example `11-logical-implementation-examples/08-turbovec-hybrid-retrieval-example.md`.

---
doc_id: as.doc.sea.index
title: 08 - Software Engineering Architecture Index
doc_type: index
status: active
schema_version: '1.0'
owner: platform-docs
summary: This section describes Astloom from a Software Engineering architecture perspective.
  It defines how the system should be engineered, modularized, built, tested, released, operated,
  extended, secured, automated, installed, connected, isolated, measured, and maintained.
tags:
- index
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/00-index.md
lifecycle_lane: current
concern_lane: onboarding
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols:
- tests/backend/gates/port-profile-verification/run_gate.py::main
doc_version: 1.1.3
updated_at: 2026-08-10
---

# 08 - Software Engineering Architecture Index

## Purpose

This section describes Astloom from a Software Engineering architecture perspective. It defines how the system should be engineered, modularized, built, tested, released, operated, extended, secured, automated, installed, connected, isolated, measured, and maintained.

The section is intentionally broader than a classic architecture summary. It is an engineering playbook for implementers. A developer or product designer should be able to use these documents to understand what will happen in engineering, where each piece belongs, how changes should flow, how installation should be automated, how agents and resources should connect, how projects remain isolated, how the web control surface works, and which quality gates must exist before the system is considered ready.

## Files

- 01-architecture-principles.md defines engineering principles and quality attributes.
- 02-service-boundaries-and-modules.md defines service boundaries, module ownership, and dependency direction.
- 03-runtime-and-deployment-architecture.md defines runtime topology, environments, configuration, and operational constraints.
- 04-development-port-management.md defines development port allocation, conflict prevention, default-port replacement, and validation rules.
- 05-modular-project-structure.md defines the recommended modular repository tree, service layout, package boundaries, dependency rules, ownership matrix, testing structure, configuration layout, and implementation workflow for new modules.
- 06-engineering-operating-model.md defines engineering work types, lifecycle, ownership, review model, evidence model, definitions of ready and done, and engineering metrics.
- 07-domain-driven-modularization.md defines bounded contexts, ubiquitous language, aggregate boundaries, domain services, shared kernel policy, anti-corruption layers, and context mapping.
- 08-interface-and-contract-engineering.md defines API, event, SDK, adapter, config, CLI, persistence, and graph contract engineering.
- 09-data-and-persistence-engineering.md defines data ownership, store types, persistence boundaries, transactions, outbox, inbox, migrations, graph persistence, memory persistence, indexing, retention, and backups.
- 10-quality-attributes-and-nfrs.md defines reliability, auditability, maintainability, modularity, explainability, security, scalability, performance, interoperability, cost efficiency, developer experience, and operational visibility requirements.
- 11-testing-and-verification-engineering.md defines test layers, domain tests, application tests, contract tests, persistence tests, worker tests, cross-service tests, E2E tests, performance tests, security verification, docs validation, and CI gates.
- 12-ci-cd-and-release-engineering.md defines pipeline stages, boundary validation, docs validation, contract validation, test selection, artifacts, migration gates, config gates, release strategies, rollback, release notes, and post-deployment verification.
- 13-local-development-and-environment-engineering.md defines local runtime modes, environment profiles, port management, configuration, secrets, local data, developer commands, remote development, environment parity, and troubleshooting.
- 14-observability-and-debuggability-engineering.md defines logs, metrics, traces, events, audit records, health checks, readiness checks, diagnostics, workflow debugging, and alerting.
- 15-extensibility-and-plugin-engineering.md defines extension types, plugin boundaries, capability declaration, adapter engineering, rule packs, memory profiles, parser extensions, extension lifecycle, and extension failure handling.
- 16-security-and-threat-modeling-engineering.md defines security principles, trust boundaries, threat modeling, sensitive assets, authentication, authorization, tenant isolation, secret handling, prompt and memory security, external integration security, approval security, and security tests.
- 17-engineering-governance-and-change-control.md defines decision records, change classification, shared package governance, contract change control, architecture change control, gap management, documentation governance, and approval matrix.
- 18-developer-onboarding-and-delivery-workflow.md defines the practical reading path, repository discovery checklist, and workflows for new features, services, contracts, adapters, rules, documentation updates, and delivery readiness.
- 19-zero-touch-installation-and-bootstrap-automation.md defines one-command installation goals, preflight checks, dependency provisioning, config generation, automated store and broker bootstrap, service registry creation, first-run readiness, evidence reports, and resumable failure handling.
- 39-local-install-runbook.md is the operator runbook for the shipped modular root `install.sh` (prerequisites, `.venv`, Compose, verify).
- 51-software-upgrade-server-and-client.md is the operator runbook for server/client upgrade, contract handshake, and control-plane upgrade jobs.
- 43-app-docker-and-wheelhouse-runbook.md is the operator runbook for exporting `.venv` wheels to `/opt/astloom-wheelhouse`, building `mcp-gateway`, and Compose profile `app` (PATH, mounts, CLI parity).
- 40-remote-dev-client-mcp-wiring.md is HISTORICAL — the removed SSH stdio wiring path (SSH has been removed from the Astloom product).
- 41-one-command-cross-platform-agent-onboarding.md specifies the shipped single-command, API-first, cross-platform onboarding UX over HTTPS.
- Client content-push contracts (auto discovery to 20 000, HTTP batching, inventory-complete prune, live `sync jobs`) live under `docs/superpowers/specs/` (`2026-08-04-client-direct-ingest…`, `2026-08-10-client-sync-auto-discovery-inventory…`, `2026-08-10-server-client-sync-jobs-cli…`) and are summarized in 41-continued + CLI reference part 4.
- 20-agent-and-resource-connectivity-automation.md defines connector registry, agent onboarding, capability discovery, generated connection profiles, authentication automation, validation, self-service UI and CLI, dynamic discovery, connector health, and failure handling.
- 21-automation-control-plane-and-self-service-operations.md defines the automation control plane, self-service action catalog, automation jobs, safe defaults, drift detection, automated repair, upgrade automation, diagnostics bundles, and approval boundaries.
- 22-product-design-and-engineering-specification-discipline.md defines how professional product design and software engineering specifications should map roles, workflows, interaction states, information architecture, contracts, data, permissions, diagnostics, metrics, and acceptance criteria.
- 23-project-isolation-and-composition-architecture.md defines tenant, workspace, project, and project group boundaries, strict data isolation, controlled project composition, cross-project policies, scoped memory, scoped graph queries, and scoped reports.
- 24-admin-web-interface-and-agent-control-surface.md defines the web interface for tracking actions, managing memory, tasks, repeated questions, rules, batches, automation jobs, reports, agents, connectors, feedback, and audit.
- 25-live-and-unit-test-strategy.md defines the formal Unit Test and Live Test strategy, including deterministic module tests, production-like validation, real-data safety rules, live test evidence, release gates, and admin-console test visibility.
- 26-domain-customization-and-feature-control.md defines domain packs, feature profiles, custom rule enablement, non-engineering UI simplification, conversation-based rule suggestions, and effective profile calculation.
- 27-sdk-engineering-and-contract-generation.md defines SDK package architecture, contract generation, public facades, scope enforcement, idempotency, retries, typed errors, event subscriptions, adapter harnesses, agent run clients, admin SDKs, test SDKs, CI, release governance, and security requirements.
- 28-common-context-and-reuse-engineering.md defines reusable common context engineering, including project-scoped common items, configurable scoring, context bundle resolution, admin management, and structure placement.
- 29-engineering-best-practices-and-implementation-standards.md defines mandatory implementation standards including DI, dependency inversion, ports/adapters, configuration, validation, errors, transactions, observability, security, and testing seams.
- 30-dependency-injection-and-composition-root.md defines Dependency Injection, composition roots, allowed injection patterns, forbidden service locator patterns, lifetime rules, and testability requirements.
- 45-backend-di-composition-feature-specification.md specifies uniform `ServiceContainer` / composition-root wiring (**Phases A–D shipped**; read with 46–48).
- 46-backend-di-composition-high-level-design.md is the HLD topology for process containers and port/adapter boundaries.
- 47-backend-di-composition-low-level-design.md is the phased file-level migration (Phase A pathfinders → thin services → port hygiene → CLI).
- 48-backend-di-composition-risks-challenges-and-acceptance.md lists risks and acceptance checkboxes for the shipped DI composition path.
- 31-error-handling-validation-and-result-standards.md defines typed errors, validation layers, problem-details responses, safe diagnostics, recovery rules, and logging requirements.
- 32-transaction-idempotency-and-concurrency-standards.md defines transaction boundaries, idempotency keys, outbox/inbox, concurrency control, retries, dead-letter behavior, and race-condition handling.
- 33-testing-seams-and-contract-boundary-standards.md defines test seams, fakes, mocks, contract boundaries, deterministic tests, LLM test strategy, and acceptance criteria.
- 34-phase8-verification-and-acceptance.md defines the port-profile feature gate, ownership checks, and named verification commands under `tests/backend/gates/port-profile-verification/`.
- 35-usage-profile-and-cursor-mcp-onboarding.md defines Usage Profiles (org/person configuration compositions) and Cursor MCP connection materialization via the MCP gateway.
- 36-astloom-cli.md defines the `astloom` CLI install, PATH, and overview; points to the full command catalog.
- 42-astloom-cli-command-reference.md is the operator reference for every `astloom` subcommand (why, required flags, examples, what changes), including mandatory sync filters and wildcards.
- 44-mcp-token-accounting.md is the feature spec for MCP connect-cost estimates, client/scope usage attribution, and `astloom mcp tokens`.
- 37-test-authoring-standard.md is the normative test-authoring playbook: concurrent code-and-tests law, family taxonomy (unit, contract, integration, e2e, live, fuzz, security, performance, regression), doubles, placement, markers, CI selection, and Definition of Done for humans and coding agents.
- 38-fuzzing-and-property-based-testing.md defines property-based and fuzz suites: invariants, bounded generators, schema/API fuzz, corpus, shrinking, and when fuzz is mandatory with implementation.
- 49-module-contract-docstrings-standard.md defines selective, **default-deny** module-level contract docstrings (Hard Module Test; role, source of truth / invariants, allowed vs forbidden failures) for hard modules so agents do not invent the wrong durability or crash policy — and do not stamp helpers/DTOs.
- 50-package-folder-readme-standard.md defines selective package/folder `README.md` maps (purpose, boundaries, 2–5 start-here files) and rejects per-file encyclopedias in those READMEs.

## Implementation Slice

Phase 8 verification home:

- Port profile: `backend/configs/port-profiles/astloom-dev.json`
- Port loader: `backend/packages/port_profile/`
- Gate package: `tests/support/port_profile_gate/`
- Tests: `tests/backend/gates/port-profile-verification/`

```bash
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/gates/port-profile-verification -q
.venv/bin/python tests/backend/gates/port-profile-verification/run_gate.py
```

## Recommended Reading Order

1. Read 01-architecture-principles.md to understand the engineering constraints.
2. Read 02-service-boundaries-and-modules.md to understand domain ownership and service boundaries.
3. Read 05-modular-project-structure.md to understand the full project tree and module layout expected from implementers.
4. Read 06-engineering-operating-model.md to understand how engineering work is classified, reviewed, evidenced, and completed.
5. Read 07-domain-driven-modularization.md to understand bounded contexts and domain decomposition.
6. Read 08-interface-and-contract-engineering.md before changing APIs, events, SDKs, adapter payloads, config schemas, or graph contracts.
7. Read 27-sdk-engineering-and-contract-generation.md before implementing SDK packages, generated clients, adapter SDKs, agent SDKs, admin SDKs, test SDKs, or SDK release pipelines.
8. Read 28-common-context-and-reuse-engineering.md before implementing reusable common context, repeated-instruction reduction, common item scoring, context bundle resolution, or admin-managed project conventions.
9. Read 29-engineering-best-practices-and-implementation-standards.md through 33-testing-seams-and-contract-boundary-standards.md before implementing backend code, dependency wiring, validation, transactions, retries, or test seams.
10. Read 09-data-and-persistence-engineering.md before adding stores, migrations, graph data, memory persistence, indexes, retention, or backups.
11. Read 10-quality-attributes-and-nfrs.md to understand non-functional requirements and tradeoffs.
12. Read 11-testing-and-verification-engineering.md before implementing tests or CI gates.
12a. Read 37-test-authoring-standard.md before writing or generating any tests with implementation; read 38-fuzzing-and-property-based-testing.md when changing parsers, schemas, scorers, query builders, or redaction.
12b. Read 49-module-contract-docstrings-standard.md before adding or changing module-level headers on queues, workers, dual-store durability, state machines, or fail-open/fail-closed seams.
12c. Read 50-package-folder-readme-standard.md before adding or expanding package/folder `README.md` files near code (maps only; not per-file catalogs).
13. Read 12-ci-cd-and-release-engineering.md before designing pipelines, releases, migrations, rollbacks, or release notes.
14. Read 19-zero-touch-installation-and-bootstrap-automation.md before designing installation, deployment bootstrap, dependency provisioning, generated configuration, first-run readiness, or installation evidence reports.
14a. Read 39-local-install-runbook.md before changing root `install.sh` or `scripts/install/` modules.
14b. Read 51-software-upgrade-server-and-client.md before changing upgrade CLI, ping version fields, or install `--upgrade`.
15. Read 20-agent-and-resource-connectivity-automation.md before designing agent onboarding, connector registration, capability discovery, connection profiles, or resource integration.
16. Read 21-automation-control-plane-and-self-service-operations.md before designing self-service operations, automated repair, drift detection, upgrades, or diagnostics bundles.
17. Read 22-product-design-and-engineering-specification-discipline.md before writing feature specifications, product experience specifications, operator workflows, or implementation-ready technical designs.
18. Read 23-project-isolation-and-composition-architecture.md before designing multi-project, multi-repository, project group, memory scope, graph scope, report scope, or connector scope behavior.
19. Read 24-admin-web-interface-and-agent-control-surface.md before designing admin-console, tracking, memory management, task management, rule management, feedback, or agent supervision workflows.
20. Read 25-live-and-unit-test-strategy.md before designing module test suites, release validation, real-data test workflows, connector validation, or production-like test evidence.
21. Read 26-domain-customization-and-feature-control.md before designing domain packs, feature profiles, user-defined rules, feature hiding, or conversation-based rule suggestions.
21a. Read 35-usage-profile-and-cursor-mcp-onboarding.md before designing org/person Usage Profiles or Cursor MCP onboarding.
21b. Read 44-mcp-token-accounting.md before changing MCP connect-cost estimates, usage JSONL, or `astloom mcp tokens`.
21c. Read 45–48 backend DI composition docs before changing service bootstrap, `build_service`, or FastAPI/MCP wiring toward uniform composition roots.
22. Read 13-local-development-and-environment-engineering.md before running services locally or adding development configuration.
23. Read 14-observability-and-debuggability-engineering.md before adding logs, metrics, traces, diagnostics, alerts, or workflow explanations.
24. Read 15-extensibility-and-plugin-engineering.md before adding adapters, plugins, rule packs, memory profiles, or parser extensions.
25. Read 16-security-and-threat-modeling-engineering.md before implementing sensitive data, authorization, prompt context, adapters, approvals, or tenant boundaries.
26. Read 17-engineering-governance-and-change-control.md before changing architecture, shared packages, contracts, migrations, or high-risk behavior.
27. Read 18-developer-onboarding-and-delivery-workflow.md when onboarding or preparing a delivery checklist.
28. Read 03-runtime-and-deployment-architecture.md to understand deployment and runtime topology.
29. Read 04-development-port-management.md before starting local development so services do not conflict on default ports.
30. Read ../13-technology-stack-and-platform-decisions/ before selecting frameworks, databases, RAG storage, cache, analytics stores, messaging, observability, or deployment tooling.
31. Read ../14-api-design-and-naming-standards/ before implementing or changing HTTP APIs, DTOs, OpenAPI contracts, generated clients, or SDK-facing endpoints.

## Engineering Coverage Map

| Engineering Concern | Primary Document |
| --- | --- |
| engineering process and ownership | 06-engineering-operating-model.md |
| repository and module structure | 05-modular-project-structure.md |
| bounded contexts and DDD | 07-domain-driven-modularization.md |
| APIs, events, SDKs, config schemas | 08-interface-and-contract-engineering.md |
| API naming, API catalog, DTOs, OpenAPI, and contract governance | ../14-api-design-and-naming-standards/ |
| SDK packages and contract generation | 27-sdk-engineering-and-contract-generation.md |
| persistence, migrations, graph, memory storage | 09-data-and-persistence-engineering.md |
| quality attributes and NFRs | 10-quality-attributes-and-nfrs.md |
| tests and verification | 11-testing-and-verification-engineering.md |
| test authoring, concurrent code-and-tests, doubles usage | 37-test-authoring-standard.md |
| fuzzing and property-based tests | 38-fuzzing-and-property-based-testing.md |
| module contract docstrings (hard modules / SoT / fail policy) | 49-module-contract-docstrings-standard.md |
| package/folder README maps (not per-file encyclopedias) | 50-package-folder-readme-standard.md |
| CI, release, rollback | 12-ci-cd-and-release-engineering.md |
| zero-touch installation and bootstrap | 19-zero-touch-installation-and-bootstrap-automation.md |
| local modular install (`install.sh`) | 39-local-install-runbook.md |
| software upgrade (server + client + control plane) | 51-software-upgrade-server-and-client.md |
| app Docker + `/opt` wheelhouse (`mcp-gateway`) | 43-app-docker-and-wheelhouse-runbook.md |
| remote dev client MCP (SSH, historical/removed) | 40-remote-dev-client-mcp-wiring.md |
| one-command agent connect (spec, HTTPS) | 41-one-command-cross-platform-agent-onboarding.md |
| client TLS + Cursor MCP (`tls_verify` false=skip / true=CA pin, mcp-remote) | 52-client-tls-trust-and-verify.md |
| astloom CLI install / overview | 36-astloom-cli.md |
| astloom CLI full command reference | 42-astloom-cli-command-reference.md |
| MCP token accounting (`mcp tokens`) | 44-mcp-token-accounting.md |
| agent and resource connectivity | 20-agent-and-resource-connectivity-automation.md |
| self-service automation and repair | 21-automation-control-plane-and-self-service-operations.md |
| product design and engineering specification discipline | 22-product-design-and-engineering-specification-discipline.md |
| project isolation and composition | 23-project-isolation-and-composition-architecture.md |
| admin web interface and agent control surface | 24-admin-web-interface-and-agent-control-surface.md |
| live tests and unit tests | 25-live-and-unit-test-strategy.md |
| domain customization, feature profiles, and rule suggestions | 26-domain-customization-and-feature-control.md |
| reusable common context and repeated-instruction reduction | 28-common-context-and-reuse-engineering.md and ../12-common-context-reuse/ |
| engineering best practices, DI, errors, transactions, and test seams | 29-engineering-best-practices-and-implementation-standards.md through 33-testing-seams-and-contract-boundary-standards.md |
| backend DI composition (Phases A–D shipped) | 45–48 backend-di-composition-*.md |
| local and remote development | 13-local-development-and-environment-engineering.md |
| logs, metrics, traces, diagnostics | 14-observability-and-debuggability-engineering.md |
| adapters, plugins, rules, parser extensions | 15-extensibility-and-plugin-engineering.md |
| security and threat modeling | 16-security-and-threat-modeling-engineering.md |
| governance and change control | 17-engineering-governance-and-change-control.md |
| onboarding and delivery workflow | 18-developer-onboarding-and-delivery-workflow.md |
| runtime topology | 03-runtime-and-deployment-architecture.md |
| technology stack and platform decisions | ../13-technology-stack-and-platform-decisions/ |
| port conflict prevention | 04-development-port-management.md |

## Relationship to Other Sections

- ../00-master-plan/ explains product and platform vision.
- ../02-memory-and-context/ explains memory, repeated questions, FAQ memory, curiosity scoring, and batched consolidation.
- ../06-technical-logic/ explains algorithms and runtime logic.
- ../07-code-knowledge-graph/ explains graph-backed code understanding and code context retrieval.
- ../09-platform-governance-operations/ explains operational governance, runbooks, automated deployment procedures, reporting, retention, API governance, and risk registers.
- ../10-gap-analysis/ records unresolved architectural and implementation questions.
- ../11-logical-implementation-examples/ gives concrete implementation examples for engineers.
- ../12-common-context-reuse/ defines reusable common context, common item lifecycle, HLD, LLD, contracts, events, governance, project-scoped reuse, and repetition reduction.
- ../13-technology-stack-and-platform-decisions/ defines selected technologies, including Next.js, TypeScript, Python, FastAPI, PostgreSQL, pgvector, Neo4j, Redis, object storage, messaging, observability, and deployment profiles.
- ../14-api-design-and-naming-standards/ defines API endpoint naming, DTO naming, error contracts, pagination, idempotency, API catalog, OpenAPI, SDK generation, and governance.
- This section explains how the platform should be engineered, packaged, configured, deployed, installed, connected, automated, isolated, measured, tested, released, secured, extended, maintained, and specified from professional product design and software engineering perspectives.

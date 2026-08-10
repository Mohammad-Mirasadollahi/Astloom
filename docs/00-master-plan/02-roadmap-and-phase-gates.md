---
doc_id: as.doc.master.roadmap-and-phase-gates
title: Roadmap and Phase Gates
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Astloom should be delivered in dependency order. Later phases rely on stable identifiers,
  records, memory, and graph links created by earlier phases.
tags:
- standard
- master
phase: 00-master-plan
canonical_path: docs/00-master-plan/02-roadmap-and-phase-gates.md
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

# Roadmap and Phase Gates


## Purpose

Astloom should be delivered in dependency order. Later phases rely on stable identifiers, records, memory, and graph links created by earlier phases.

Astloom should be delivered in dependency order. Later phases rely on stable identifiers, records, memory, and graph links created by earlier phases.

## Phase 1 - Core Data Model

Mission: turn agent actions, decisions, issues, and tasks into durable structured knowledge.

Primary deliverables:

- Entity Registry for canonical IDs and lifecycle states.
- Activity Ingestion Service for tool use, diffs, tests, and artifacts.
- Decision Registry for ADR-like records and generated guardrails.
- Issue Tracker and Task Planner.
- Audit Query API for timelines and incident reconstruction.

Exit gate:

- Every agent session can produce WorkLog and Activity records.
- Critical Issues can be decomposed into Tasks or escalated.
- Decisions can be superseded without being physically deleted.

## Phase 2 - Memory and Context

Mission: give agents the right context at the right time while controlling cost and noise.

Primary deliverables:

- Working, episodic, and semantic memory stores.
- Consolidation worker and state reconciler.
- Decay and garbage collection process.
- Prompt cache profiles and context bundle builder.
- Retrieval interface for dynamic context injection.
- QuestionMemory, repeated question normalization, curiosity scoring, FAQ memory, and missing documentation discovery.
- WorkBatch, deferred memory consolidation, deferred documentation generation, and deferred code review.

Exit gate:

- Agents receive current state by default.
- Historical facts are injected only when relevant.
- Stable prompt sections are versioned for caching.
- Repeated questions can become scoped FAQ memory only after scoring and evidence checks.
- Missing documentation can create a draft, Task, or Gap depending on confidence.
- Memory consolidation and documentation generation can be batched until meaningful work boundaries.

## Phase 3 - Docs-as-Code and Synchronization

Mission: prevent documentation drift by linking code, docs, decisions, and tasks.

Primary deliverables:

- Code and documentation indexers.
- AST anchor and hash generator.
- YAML frontmatter validator.
- Bloom filter and doc flag coverage index.
- CI drift gate and Docs Agent task creation.

Exit gate:

- Changed documented symbols produce drift findings before merge.
- Required docs are validated automatically.
- Drift findings link to Issues and Tasks.

## Phase 4 - Rule Engine and Orchestration

Mission: coordinate agents and humans through policies, risk checks, escalation, impact analysis, and task routing.

Primary deliverables:

- Policy registry and deterministic pre-checks.
- LLM judge adapter for ambiguous semantic policies.
- Escalation ticket builder.
- Impact analyzer and task router.
- Runbook engine for repeatable workflows.

Exit gate:

- Revenue, security, compliance, and production-sensitive actions can be blocked for approval.
- LLM verdicts store rationale and evidence.
- API or schema changes generate downstream tasks.

## Phase 5 - Interoperability and Enterprise Ecosystem

Mission: connect different agents, IDEs, vendors, and departments through a shared protocol and broker.

Primary deliverables:

- Universal Agent JSON contract.
- Pub/Sub broker with replay and dead-letter handling.
- Adapter SDK for external tools and models.
- IDE integration surface for notifications and context injection.
- Department workflow layer.

Exit gate:

- At least two vendors can exchange task state through the same protocol.
- IDE plugins can receive brokered events.
- Code events can trigger governed non-code tasks.

## Phase 6 - Technical Logic and Verification

Mission: make Phases 1 through 5 implementation-ready and verifiable before expanding into the code-knowledge graph and broader platform engineering. This phase owns cross-cutting algorithms, invariants, end-to-end runtime logic, and the technical test strategy that proves earlier vertical slices behave as specified.

Primary deliverables:

- Per-domain technical logic for Core Data, Memory, Docs Sync, Rule Engine, and Interoperability.
- End-to-end runtime logic that stitches those domains into one auditable flow.
- Technical test strategy covering contracts, state machines, idempotency, redaction, retrieval, drift, rules, broker delivery, and reliability.
- Canonical `tests/` path rules and Definition of Done for phase technical completeness.
- Traceability from evidence inputs to automated outputs, with deterministic boundaries around model judgment.

Exit gate:

- Every owned vertical slice (`core-data-service` through `adapter-service`) has documented technical logic and a named canonical test command under `tests/backend/services/<service>/`.
- End-to-end runtime logic can be walked without hidden steps between domains.
- Contract, state-machine, idempotency, and redaction checks exist for those owned service surfaces.
- Risky operations are documented as idempotent, reversible, or human-approved.
- Code-graph work does not begin until the technical-logic gate at `tests/backend/gates/technical-logic-verification/` passes or is explicitly waived with an owner.

Design home: `docs/06-technical-logic/`.

## Phase 7 - Code-Knowledge Graph

Mission: build a live Neo4j-backed graph of the codebase that supports AI documentation, semantic retrieval, and graph-guided code generation.

Primary deliverables:

- Neo4j schema for Project, File, Class, Function, Method, and Import nodes.
- CONTAINS, CALLS, IMPORTS, INHERITS_FROM, DOCUMENTED_BY, and GENERATED_FROM relationships.
- Tree-sitter ingestion pipeline.
- Function-level normalized hash diffing.
- AI documentation generation for changed symbols.
- Embedding and vector search support.
- Graph-guided code generation context builder.
- Token optimization and tiered model routing strategy.

Exit gate:

- Changed functions are detected through hash comparison.
- Only changed symbols are sent to documentation generation.
- Neo4j can answer structural and semantic code queries.
- AI generation prompts use graph context instead of full repository source.
- Generated code is checked for unknown symbol references before acceptance.

Implementation home: `backend/services/code-graph-service/` (Phase 7 slice; PostgreSQL graph projection + in-memory test Store; local heuristic docs). Canonical tests: `tests/backend/services/code-graph-service/`.

## Phase 8 - Software Engineering Architecture

Mission: define Astloom as an engineered software platform with a complete software engineering playbook. This phase must explain how the repository is structured, how modules are owned, how domains are decomposed, how interfaces are contracted, how persistence is governed, how quality is verified, how CI/CD and release happen, how local and remote development work, how observability and security are engineered, how extensions are added, and how change control keeps the platform coherent.

Primary deliverables:

- Professional documentation standard for implementation-grade software engineering and product design specifications.
- Software engineering architecture principles.
- Service boundary and module ownership design.
- Full modular project structure and repository tree.
- Engineering operating model with work types, ownership, review model, evidence model, Definition of Ready, and Definition of Done.
- Domain-driven modularization with bounded contexts, context mapping, aggregate boundaries, shared kernel policy, and anti-corruption layers.
- Interface and contract engineering for APIs, events, SDKs, adapter payloads, config schemas, CLI commands, persistence contracts, and graph contracts.
- Data and persistence engineering for store ownership, transactions, outbox, inbox, migrations, graph persistence, memory persistence, indexes, retention, backup, and restore.
- Quality attributes and non-functional requirements for reliability, auditability, maintainability, modularity, explainability, security, scalability, performance, interoperability, cost efficiency, developer experience, and operational visibility.
- Testing and verification engineering across Unit Tests, Live Tests, domain tests, application tests, contract tests, persistence tests, worker tests, cross-service tests, E2E tests, performance tests, security tests, and docs validation.
- CI/CD and release engineering with boundary validation, contract validation, migration gates, config gates, artifact metadata, rollback strategy, release notes, and post-deployment verification.
- Zero-touch installation and bootstrap automation with preflight checks, dependency provisioning, generated configuration, automated store and broker setup, service registry creation, first-run readiness, evidence reports, and resumable failure handling.
- Agent and resource connectivity automation with connector registry, generated connection profiles, capability discovery, authentication automation, validation, smoke tests, connector health, and self-service onboarding.
- Automation control plane and self-service operations with action catalog, automation jobs, safe defaults, drift detection, automated repair, upgrade automation, diagnostics bundles, and approval boundaries.
- Local and remote development engineering with reproducible environment profiles, focused runtime modes, fixtures, secrets handling, troubleshooting, and port preflight.
- Observability and debuggability engineering with logs, metrics, traces, audit records, diagnostics, health checks, readiness checks, workflow explanations, and alerting.
- Extensibility and plugin engineering for adapters, rule packs, memory profiles, parser extensions, provider integrations, capability declaration, and extension lifecycle.
- Security and threat modeling engineering for trust boundaries, sensitive assets, authorization, tenant isolation, secret handling, prompt and memory security, external integration security, approval security, and security tests.
- Engineering governance and change control for decision records, shared package governance, contract change control, architecture change control, gap management, documentation governance, and approval matrix.
- Developer onboarding and delivery workflow for new features, services, contracts, adapters, rules, documentation updates, and release readiness.
- Product design and engineering specification discipline that maps roles, jobs to be done, workflows, interaction states, information architecture, contracts, data, permissions, diagnostics, metrics, and acceptance criteria.
- Project isolation and composition architecture for tenants, workspaces, projects, project groups, scoped memory, scoped graph queries, scoped connectors, scoped reports, and explicit cross-project sharing policies.
- Admin web interface and agent control surface for Activity Timeline tracking, object detail pages, memory management, repeated questions, task and ticket management, rule management, agent supervision, WorkBatch management, automation jobs, reports, structured feedback, correction workflows, and audit.
- Runtime and deployment architecture.
- Configuration layering strategy.
- Development port profile and conflict detection policy.
- Explicit requirement that development defaults use non-default, project-scoped ports.
- Port override and startup validation rules.

Exit gate:

- Every runtime service has configurable ports and endpoints.
- Development documentation uses Astloom-specific non-default ports.
- Startup checks port availability and reports conflicts clearly.
- Tests do not depend on fixed common ports.
- No service requires hard-coded port values.
- Documentation is written for experienced software engineers, architects, product designers, operators, security reviewers, and technical decision makers rather than a general audience.
- Every planned service and package has a documented owner, responsibility, and boundary.
- Public contracts have owners, versions, examples, compatibility rules, and tests.
- Data ownership, migrations, graph persistence, memory persistence, retention, backup, and restore expectations are documented.
- CI/CD gates cover boundaries, docs, contracts, tests, security, migrations, config, artifacts, and release notes.
- Local and remote development workflows are reproducible and include port preflight.
- First installation can be completed through automated bootstrap with minimal manual input.
- Agents and external resources can connect through generated profiles, connector registry, capability discovery, authentication automation, and validation smoke tests.
- Self-service automation supports setup, validation, drift detection, safe repair, upgrades, and diagnostics.
- Observability requirements exist for logs, metrics, traces, diagnostics, audit records, and workflow explanations.
- Security trust boundaries and threat modeling expectations are documented.
- Engineering governance and change control define how major decisions, gaps, shared packages, and architecture changes are approved.
- Feature specifications include product workflow, interaction states, system ownership, contracts, data impact, permissions, diagnostics, metrics, tests, and acceptance criteria.
- Unit Tests are required for deterministic module and domain behavior.
- Live Tests validate production-like behavior with real or representative data, scoped environments, mutation policies, evidence reports, and release gates.
- Project data is isolated by default across memory, graph, docs, tickets, agents, reports, connectors, and audit.
- Cross-project composition requires explicit ProjectGroup policy and authorization.
- The web interface exposes Activity Timeline tracking, object detail pages, memory management, repeated question management, task and ticket management, rule management, agent supervision, batch management, automation jobs, reports, structured FeedbackRecord correction workflows, and audit.

Implementation home: `docs/08-software-engineering-architecture/` plus `backend/configs/port-profiles/astloom-dev.json`, `backend/packages/port_profile/`, and the port-profile feature gate at `tests/backend/gates/port-profile-verification/`.

## Phase 9 - Platform Governance and Operations

Mission: complete the plan with security, observability, release governance, retention, contract versioning, runbooks, risk tracking, and shared terminology.

Primary deliverables:

- Security, access control, privacy, and prompt safety rules.
- Observability, SLO, alerting, and incident response model.
- CI/CD, release, migration, and rollback strategy.
- Data retention, backup, restore, and disaster recovery policy.
- API versioning and contract governance rules.
- Operational runbooks for critical workflows.
- Automated deployment and connectivity runbooks for first installation, connector registration, repository registration, external resources, upgrades, drift detection, and repair.
- Impact reporting and benefit measurement for initial code generation speed, bug reduction, architecture quality, rework reduction, token consumption, KPI definitions, instrumentation, baselines, project scope, evidence drilldown, and with-or-without Astloom comparison.
- Risk register and open decision tracker.
- Glossary and ubiquitous language.

Exit gate:

- Security boundaries are documented and enforceable.
- Critical workflows have runbooks.
- Automated installation, connector onboarding, upgrade, drift detection, and repair workflows have operational runbooks.
- Reports measure initial code generation speed, bug reduction, architecture quality, rework reduction, and token consumption with formal metric definitions, instrumentation, explicit scope, baseline, comparison method, time range, sample size, caveats, and evidence drilldown.
- Contracts have versioning and compatibility rules.
- Backup and restore expectations are defined.
- Risks and open decisions have owners and mitigation paths.

Implementation home: `docs/09-platform-governance-operations/` plus `backend/configs/governance/`, `backend/packages/governance_catalog/`, and the governance-catalog feature gate at `tests/backend/gates/governance-catalog-verification/`.

## Phase 10 - Gap Analysis

Mission: make unresolved assumptions, architecture gaps, technical unknowns, governance gaps, and open decisions explicit so they can be reviewed and resolved before they become implementation risk.

Primary deliverables:

- Master gap register.
- Architecture gap list.
- Technical implementation gap list.
- Governance and operations gap list.
- Gap triage and resolution process.

Exit gate:

- Critical gaps have owners.
- High-severity gaps are linked to phase gates.
- Open decisions have proposed resolution artifacts.
- Accepted risks have approvers and review dates.
- Closed gaps are reflected in the relevant documentation.

Implementation home: `docs/10-gap-analysis/` plus `backend/configs/governance/gap-register.json`, `backend/packages/governance_catalog/`, and the gap-register feature gate at `tests/backend/gates/gap-register-verification/`.

## Phase 11 - Logical Implementation Examples

Mission: provide concrete runtime examples and developer checklists so engineers can understand how the documented architecture should behave in real implementation scenarios.

Primary deliverables:

- End-to-end password migration example.
- Memory and context retrieval example.
- Docs and code graph example.
- Rule engine and human approval example.
- Interoperability and broker example.
- Developer implementation checklist.

Exit gate:

- Every major subsystem has at least one logical example.
- Examples include inputs, processing steps, outputs, state changes, and edge cases.
- Engineers can map examples to implementation tasks and tests.

Implementation home: `docs/11-logical-implementation-examples/` plus `backend/configs/logical-examples/`, `backend/packages/logical_examples/`, and the logical-examples feature gate at `tests/backend/gates/logical-examples-verification/`.

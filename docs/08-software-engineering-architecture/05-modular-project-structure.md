---
doc_id: as.doc.sea.modular-project-structure
title: 05 - Modular Project Structure
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the recommended modular project structure for Astloom from
  a Software Engineering perspective. It explains how the repository should be organized,
  how modules should depend on each other, where each type of code should live, and how engineers
  should extend.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/05-modular-project-structure.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
placeholder: 1
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 05 - Modular Project Structure

## 05 - Modular Project Structure
## Purpose

This document defines the recommended modular project structure for Astloom from a Software Engineering perspective. It explains how the repository should be organized, how modules should depend on each other, where each type of code should live, and how engineers should extend the system without creating hidden coupling.

This document is intentionally implementation-oriented. A developer should be able to use it as the first reference when creating folders, packages, services, shared libraries, tests, configuration files, migrations, or operational tooling.

## Architectural Decision

Astloom should start as a modular monorepo.

The monorepo is recommended because the early system contains many tightly related contracts: activities, work logs, decisions, tasks, memory objects, documentation anchors, graph entities, rule events, broker messages, and adapter payloads. Keeping these contracts in one repository reduces drift while the product model is still evolving.

The repository must still be modular. A monorepo is not permission to create a shared codebase without boundaries. Each service owns its domain model, use cases, persistence adapters, tests, migrations, and runtime entrypoints. Shared packages are allowed only for stable contracts, infrastructure helpers, SDKs, test utilities, and cross-cutting platform primitives.

A future multi-repo split is possible only after service contracts become stable and independent release cadence becomes valuable.

## Top-Level Project Tree

The recommended project tree is:

    Astloom/
      apps/
        api-gateway/
        admin-console/
        ide-extension/
        cli/
      services/
        core-data-service/
        memory-service/
        docs-sync-service/
        code-graph-service/
        rule-engine-service/
        broker-service/
        adapter-service/
        config-service/
        audit-service/
      packages/
        contracts/
        domain-events/
        sdk/
        auth/
        config/
        observability/
        persistence/
        queueing/
        validation/
        testkit/
      infra/
        docker/
        compose/
        kubernetes/
        terraform/
        migrations/
        local-dev/
      docs/
        00-master-plan/
        01-core-data-model/
        02-memory-and-context/
        03-docs-as-code-sync/
        04-rule-engine-orchestration/
        05-interoperability-ecosystem/
        06-technical-logic/
        07-code-knowledge-graph/
        08-software-engineering-architecture/
        09-platform-governance-operations/
        10-gap-analysis/
        11-logical-implementation-examples/
      scripts/
        dev/
        ci/
        release/
        maintenance/
      tools/
        port-preflight/
        schema-registry/
        graph-inspector/
        migration-runner/
        docs-validator/
      tests/
        integration/
        contract/
        e2e/
        performance/
        fixtures/
      examples/
        agent-workflows/
        adapter-payloads/
        memory-retrieval/
        docs-sync/
      .github/
        workflows/
      README.md

## Top-Level Folder Responsibilities

### apps

The apps folder contains user-facing or operator-facing applications. Apps may call services through APIs, SDKs, or event subscriptions, but they must not import service internals.

Expected apps:

- api-gateway exposes the external HTTP or RPC surface for agents, IDE tools, admin screens, and automation clients.
- admin-console provides operational views for work logs, tasks, memory, rules, gaps, graph health, and system status.
- ide-extension integrates Astloom with development environments and sends structured context events.
- cli provides local developer and operator commands such as validation, import, export, diagnostics, and preflight checks.

Apps own presentation logic, user workflows, command parsing, and API composition. They do not own core domain rules.

### services

The services folder contains independently deployable or independently testable backend modules. Each service owns one bounded context.

Expected services:

- core-data-service owns Activity, WorkLog, Decision, Issue, Task, relations, lifecycle transitions, and audit-safe persistence.
- memory-service owns memory tiers, retrieval scoring, weight calculation, consolidation, decay, summarization, and context assembly.
- docs-sync-service owns docs-as-code synchronization, frontmatter validation, document anchors, document graph metadata, and documentation drift detection.
- code-graph-service owns repository ingestion, Tree-sitter parsing, symbol extraction, Neo4j graph writes, impact queries, and graph-guided code context.
- rule-engine-service owns semantic rules, anomaly detection, policy execution, escalation logic, and automated routing decisions.
- broker-service owns Pub/Sub contracts, event routing, retries, dead-letter handling, idempotency keys, and replay boundaries.
- adapter-service owns vendor adapters, Universal Agent JSON conversion, provider capability mapping, and external tool integration.
- config-service owns configuration profiles, feature flags, environment policies, runtime settings, and port allocation records.
- audit-service owns immutable audit streams, retention policies, compliance exports, and evidence queries.
- common-context-service owns reusable project guidance, repeated-instruction proposals, common item lifecycle, bundle resolution, scoring, conflict detection, and reuse reporting.

A service may be deployed as a process, container, or logical module depending on project maturity. The boundary still exists even when multiple services run in one process during early development.

### packages

The packages folder contains shared libraries that are stable enough to be reused. Shared packages must stay small and boring. They should not become a place for business logic that no team wants to own.

Expected packages:

- contracts contains API schemas, event schemas, DTO definitions, and versioned public types.
- domain-events contains canonical event names, event envelopes, causality metadata, correlation IDs, and idempotency primitives.
- sdk contains typed clients for apps, agents, tools, and external integrations.
- auth contains authentication and authorization primitives that are used consistently by services and apps.
- config contains typed config loading, config validation, environment profile resolution, and no-hard-code guards.
- observability contains logging, tracing, metrics, span names, health check helpers, and structured diagnostic fields.
- persistence contains database connection helpers, transaction wrappers, migration interfaces, and repository base primitives.
- queueing contains broker clients, retry helpers, dead-letter helpers, and message acknowledgement utilities.
- validation contains schema validation helpers and common error formats.
- testkit contains builders, fake adapters, contract test harnesses, integration fixtures, and deterministic time utilities.
- common-context contains reusable common item contracts, resolver interfaces, templates, and examples so repeated guidance is centralized instead of duplicated across services.

Shared packages may depend on other shared packages only when the dependency direction is stable and explicitly documented.

### infra

The infra folder contains deployment and infrastructure definitions. It must not contain application business logic.

Expected areas:

- docker contains image definitions and base runtime images.
- compose contains local orchestration profiles.
- kubernetes contains deployment, service, ingress, secret reference, and autoscaling manifests.
- terraform contains cloud or infrastructure provisioning definitions.
- migrations contains database and graph migration assets when they are shared across services.
- local-dev contains local bootstrap profiles, development-only overrides, and generated port maps.

Development ports must not use framework defaults. Local port values must be configurable, documented, and validated before services start.

### docs

The docs folder is the source of truth for architecture, design, logic, risk, operations, and implementation examples. It must remain indexed and phase-oriented.

Every major module should link back to relevant docs. For example, memory-service should reference the memory architecture, memory technical logic, and logical retrieval examples.

### scripts

The scripts folder contains automation scripts for development, CI, release, and maintenance. Scripts must be repeatable and should fail clearly when prerequisites are missing.

Scripts should call tools and service commands. They should not contain hidden business rules.

### tools

The tools folder contains engineer-facing utilities that support the repository.

Expected tools:

- port-preflight validates that configured development ports do not conflict with local services or reserved ranges.
- schema-registry validates contract schemas, event versions, and compatibility rules.
- graph-inspector checks graph ingestion health, orphan symbols, stale references, and missing anchors.
- migration-runner executes service migrations in a controlled order.
- docs-validator checks indexes, links, required metadata, and documentation completeness.

### tests

The tests folder contains cross-module tests. Service-owned unit tests and service integration tests stay inside each service. Repository-level tests cover system behavior across boundaries.

Expected test groups:

- integration verifies service-to-service flows.
- contract verifies API and event compatibility.
- e2e verifies complete user and agent workflows.
- performance verifies ingestion, retrieval, graph query, and broker throughput targets.
- fixtures contains reusable test data and scenario payloads.

### examples

The examples folder contains realistic usage examples that developers can run or inspect. Examples should use public contracts, SDKs, and documented configuration instead of service internals.

## Standard Service Layout

Each backend service should follow this internal structure:

    services/<service-name>/
      README.md
      docs/
        design-notes.md
        operational-notes.md
      src/
        api/
          controllers/
          routes/
          serializers/
        application/
          commands/
          queries/
          handlers/
          workflows/
        domain/
          entities/
          value-objects/
          policies/
          services/
          events/
        infrastructure/
          persistence/
          messaging/
          external-clients/
          configuration/
          observability/
        workers/
          consumers/
          scheduled-jobs/
          projectors/
        bootstrap/
          dependency-injection/
          service-startup/
      tests/
        unit/
        integration/
        contract/
        fixtures/
      migrations/
      config/
        development.example.yaml
        test.example.yaml
        production.example.yaml
      package-manifest

The exact file names may change based on implementation language and framework, but the boundaries should remain stable.

## Layering Rules Inside a Service

A service should be organized around clean dependency direction.

Allowed dependency direction:

    api -> application -> domain
    workers -> application -> domain
    infrastructure -> application or domain through interfaces
    bootstrap -> api, workers, infrastructure, application

Domain rules:

- The domain layer contains business concepts and invariants.
- The domain layer does not know about HTTP, databases, brokers, filesystems, frameworks, or environment variables.
- Domain events are created by domain logic but published by application or infrastructure code.
- Domain policies should be deterministic and easy to test.

Application rules:

- The application layer contains use cases and orchestration logic.
- Commands change state and should emit events when important state changes occur.
- Queries read state and should not create side effects.
- Application handlers coordinate repositories, domain services, event publishing, and authorization checks.

API rules:

- The API layer translates external requests into application commands or queries.
- API code validates transport-level shape and authentication context.
- API code should not contain domain decisions.

Infrastructure rules:

- Infrastructure implements repositories, broker clients, graph clients, external tool clients, config loaders, and observability exporters.
- Infrastructure adapts external systems to internal interfaces.
- Infrastructure code may be replaced without rewriting domain logic.

Worker rules:

- Workers consume events, run scheduled jobs, update projections, and perform long-running tasks.
- Workers should be idempotent because broker retries are expected.
- Workers should record causality metadata for audit and replay.

## Example: Memory Service Layout

The memory-service should be structured as follows:

    services/memory-service/
      src/
        api/
          controllers/
            retrieve-context-controller
            memory-feedback-controller
          serializers/
            memory-response-serializer
        application/
          commands/
            consolidate-memory-command
            record-memory-feedback-command
          queries/
            retrieve-context-query
            explain-memory-ranking-query
          handlers/
            retrieve-context-handler
            consolidate-memory-handler
            record-memory-feedback-handler
          workflows/
            build-agent-context-workflow
        domain/
          entities/
            memory-item
            memory-cluster
            context-window
          value-objects/
            memory-weight
            recency-score
            relevance-score
            confidence-score
          policies/
            retention-policy
            decay-policy
            retrieval-policy
          services/
            memory-ranker
            memory-consolidator
            context-budgeter
          events/
            memory-recorded-event
            memory-consolidated-event
            memory-feedback-recorded-event
        infrastructure/
          persistence/
            memory-repository
            memory-cluster-repository
          messaging/
            memory-event-publisher
            activity-event-consumer
          external-clients/
            embedding-client
            summarization-client
          configuration/
            memory-config-loader
            ranking-weight-config
          observability/
            memory-metrics
            retrieval-tracing
        workers/
          consumers/
            activity-memory-consumer
          scheduled-jobs/
            memory-decay-job
            memory-consolidation-job
          projectors/
            memory-usage-projector

Important implementation logic:

- Retrieval must combine multiple configurable weights, not a hard-coded score.
- Weight factors should include relevance, recency, confidence, source quality, user feedback, task similarity, project similarity, and risk sensitivity.
- The scoring formula must be config-driven and versioned so experiments can be audited.
- The service should return an explanation of why each memory item was selected.
- Memory output should include enough metadata for downstream agents to decide whether to trust or ignore an item.

## Related Documents

- Continued in `docs/08-software-engineering-architecture/05-modular-project-structure-continued.md`

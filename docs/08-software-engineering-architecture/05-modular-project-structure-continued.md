---
doc_id: as.doc.sea.modular-project-structure-continued
title: 05 - Modular Project Structure (Continued)
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Continuation of `docs/08-software-engineering-architecture/05-modular-project-structure.md`
  — remaining sections after the soft size budget.
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/05-modular-project-structure-continued.md
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

# 05 - Modular Project Structure (Continued)

## 05 - Modular Project Structure (Continued)
## Purpose

Continuation of `docs/08-software-engineering-architecture/05-modular-project-structure.md` — remaining sections after the soft size budget.

## Example: Code Graph Service Layout

The code-graph-service should be structured as follows:

    services/code-graph-service/
      src/
        api/
          controllers/
            graph-query-controller
            impact-analysis-controller
        application/
          commands/
            ingest-repository-command
            refresh-symbol-command
          queries/
            find-symbol-query
            explain-impact-query
            retrieve-code-context-query
          handlers/
            ingest-repository-handler
            explain-impact-handler
            retrieve-code-context-handler
        domain/
          entities/
            repository
            source-file
            symbol
            code-edge
            graph-snapshot
          value-objects/
            symbol-id
            file-anchor
            graph-version
          policies/
            ingestion-policy
            stale-edge-policy
          services/
            symbol-resolver
            impact-analyzer
            graph-context-selector
          events/
            repository-ingested-event
            symbol-changed-event
            graph-snapshot-created-event
        infrastructure/
          persistence/
            neo4j-symbol-repository
            graph-snapshot-repository
          external-clients/
            tree-sitter-parser-client
            git-client
          messaging/
            code-graph-event-publisher
          configuration/
            parser-config-loader
            graph-database-config
        workers/
          consumers/
            repository-change-consumer
          scheduled-jobs/
            graph-health-check-job
          projectors/
            documentation-link-projector

Important implementation logic:

- Parsing must be incremental when possible.
- Graph writes must be idempotent and versioned.
- Symbol IDs must be stable across repeated ingestion when the code did not semantically change.
- Impact analysis must return both direct and transitive dependencies.
- Graph context selection should prefer exact symbols, then related files, then documented decisions, then recent work logs.

## Dependency Rules Between Modules

The dependency rules are:

- Apps may depend on packages and public service APIs.
- Apps must not import service internal source files.
- Services may depend on packages.
- Services must not import another service internal source files.
- Services communicate through APIs, events, shared contracts, or SDK clients.
- Packages must not depend on services or apps.
- Infra must not depend on application code.
- Tests may use testkit and public module interfaces.
- Contract tests may import schemas from packages/contracts.

Invalid examples:

- memory-service importing core-data-service repository classes directly.
- admin-console reading a service database table directly.
- docs-sync-service writing Neo4j records without going through code-graph-service or a documented graph contract.
- rule-engine-service importing API controllers from api-gateway.
- shared packages containing service-specific business decisions.

Valid examples:

- memory-service consuming ActivityCreated events from broker-service.
- rule-engine-service publishing EscalationRequested events through domain-events contracts.
- admin-console calling api-gateway endpoints.
- code-graph-service exposing impact analysis through an API and event stream.
- docs-sync-service using contracts from packages/contracts to validate documentation anchor events.

## Contract Ownership

Contracts are public promises. Every API schema, event schema, and adapter schema must have an owner.

Ownership rules:

- The service that produces an event owns the event schema.
- The service that exposes an API owns the API contract.
- packages/contracts stores the versioned shared copy of public contracts.
- Breaking changes require a migration plan and compatibility window.
- Contract tests must verify both producers and consumers.
- Deprecated fields must remain documented until fully removed.

Contract files should include:

- name
- version
- owner
- lifecycle state
- compatibility notes
- required fields
- optional fields
- validation rules
- example payload
- error behavior

## Configuration Structure

Configuration must be explicit, typed, validated, and environment-aware.

Recommended configuration layout:

    services/<service-name>/config/
      development.example.yaml
      test.example.yaml
      production.example.yaml
    infra/local-dev/
      ports.example.yaml
      services.example.yaml
    packages/config/
      src/
        config-loader
        schema-validator
        environment-profile
        secret-reference

Configuration rules:

- No service should hard-code hostnames, ports, credentials, database names, topic names, retention values, scoring weights, or feature flags.
- Development port values must be changed away from framework defaults.
- Port allocation should be stored in a local-dev config profile and validated by port-preflight before startup.
- Secrets must be referenced through secret providers or environment references, not committed as literal values.
- Runtime config should expose effective values in diagnostic mode without printing secrets.

## Development Port Strategy

Port conflict prevention is part of the architecture.

Default framework ports should not be used during development. For example, common defaults such as 3000, 5000, 5173, 5432, 6379, 7474, 7687, 8000, 8080, and 9090 should be treated as reserved or avoided unless the team explicitly configures otherwise.

Astloom development should use a documented non-default range. Example allocations are defined in the port management document and should remain configurable:

- api-gateway: 32100
- admin-console: 32101
- core-data-service: 32110
- memory-service: 32120
- docs-sync-service: 32130
- code-graph-service: 32140
- rule-engine-service: 32150
- broker-service: 32160
- adapter-service: 32170
- config-service: 32180
- neo4j-http: 32287
- neo4j-bolt: 32474
- redis-compatible-cache: 32333
- observability-dashboard: 32390

These values are examples, not hard-coded constants. The effective values must come from config files, environment profiles, or generated local development settings.

## Testing Structure

Testing should follow module boundaries.

Service-level tests:

- unit tests validate domain policies, value objects, application handlers, and pure logic.
- integration tests validate service persistence, broker interactions, graph clients, and external adapters through controlled fixtures.
- contract tests validate API and event compatibility.

Repository-level tests:

- integration tests validate cross-service workflows such as activity creation to memory retrieval.
- e2e tests validate complete user-visible flows such as IDE event to task routing to documentation update.
- performance tests validate graph ingestion, memory retrieval, broker replay, and rule execution throughput.

Testing rules:

- Domain tests must not require databases or brokers.
- Contract tests must run before integration tests.
- E2E tests should use public APIs and public event contracts.
- Fixtures should be realistic and versioned.
- Test data should include failure and edge cases, not only happy paths.

## Module Ownership Matrix

Ownership should be explicit even before teams are assigned.

| Module | Primary Responsibility | Main Consumers | Stability Level |
| --- | --- | --- | --- |
| api-gateway | External API composition and request entry | apps, agents, CLI, IDE tools | medium |
| admin-console | Operator and reviewer UI | human users | medium |
| core-data-service | Activity, WorkLog, Decision, Issue, Task | all platform services | high |
| memory-service | retrieval, weighting, consolidation, context assembly | agents, api-gateway, rule-engine | high |
| docs-sync-service | docs-as-code, anchors, drift detection | developers, code-graph, rule-engine | medium |
| code-graph-service | repository graph, symbols, impact analysis | agents, docs-sync, rule-engine | high |
| rule-engine-service | policy execution, routing, anomaly detection | core-data, broker, admin-console | high |
| broker-service | event routing, retries, replay | all services | high |
| adapter-service | provider and tool integration | external agents, IDE tools | medium |
| config-service | profiles, feature flags, runtime settings | all services | high |
| audit-service | immutable evidence and compliance export | admin-console, governance | high |
| packages/contracts | public schemas and DTOs | all modules | very high |
| packages/testkit | test support only | tests | low |

## Naming Conventions

Naming should make boundaries obvious.

Folder naming:

- top-level folders use plural nouns where they contain collections.
- services use kebab-case and end with service.
- packages use short nouns that describe reusable capability.
- tests use names that describe behavior, not only implementation details.

Domain naming:

- entity names should match documented concepts such as Activity, WorkLog, Decision, Issue, Task, MemoryItem, CodeSymbol, Rule, AdapterCapability, and AuditRecord.
- event names should be past-tense facts such as ActivityCreated, MemoryConsolidated, RuleViolated, DocumentationDriftDetected, and CodeGraphSnapshotCreated.
- command names should be imperative requests such as CreateTask, RecordDecision, RetrieveContext, IngestRepository, and EvaluateRules.
- query names should describe read intent such as GetTaskTimeline, FindRelatedMemories, ExplainImpact, and ListOpenGaps.

## Build and Release Boundaries

Each service and package should be independently buildable and testable.

Build expectations:

- A change inside one service should run that service tests and affected contract tests.
- A change inside packages/contracts should run all affected producer and consumer contract tests.
- A change inside packages/config or packages/observability should run all services that depend on it.
- A documentation-only change should run docs validation and link checks.
- A migration change should run migration validation and rollback checks where rollback is supported.

Release expectations:

- Public contracts are versioned.
- Runtime services expose health and readiness checks.
- Deployment artifacts identify the service name, version, git revision, config profile, and contract version set.
- Release notes must mention contract changes, migrations, port changes, and operational risks.

## Documentation Rules For Modules

Every service should include a README.md with:

- purpose
- owned domain concepts
- public APIs
- produced events
- consumed events
- dependencies
- configuration keys
- port configuration behavior
- persistence stores
- operational metrics
- failure modes
- local development commands
- test commands
- links to architecture docs

Every shared package should include a README.md with:

- purpose
- public API surface
- allowed consumers
- forbidden consumers
- versioning policy
- examples
- compatibility rules

## Anti-Patterns To Avoid

The project should actively avoid these patterns:

- shared domain model imported by every service without ownership.
- business logic inside API controllers.
- service-to-service database access.
- hard-coded ports, hostnames, credentials, topic names, model names, scoring weights, or feature flags.
- one global utilities package that grows without review.
- adapter code mixed into core domain services.
- tests that pass only because they use private internals.
- documentation that describes desired behavior but does not map to modules, contracts, or tests.
- graph writes from multiple services without a single ownership contract.
- memory retrieval scores that cannot be explained or tuned.

## Implementation Workflow For New Modules

When adding a new module, engineers should follow this workflow:

1. Identify the bounded context and owner.
2. Add the service or package folder under the correct top-level directory.
3. Write the module README before writing production code.
4. Define public contracts in packages/contracts when the module exposes APIs or events.
5. Add configuration schema and example environment profiles.
6. Add development port entries when the module opens a port.
7. Add domain tests for pure rules.
8. Add contract tests for public APIs and events.
9. Add integration tests for persistence, brokers, graph stores, or external tools.
10. Link the module README to the relevant documentation section.
11. Update docs indexes when the module introduces a new architectural area.
12. Run docs validation, contract tests, and affected service tests.

## Acceptance Criteria

The modular project structure is acceptable when:

- A new engineer can locate the correct folder for an app, service, package, tool, script, test, or infrastructure asset.
- No service imports another service internal implementation.
- Shared packages contain stable reusable primitives, not unowned business logic.
- Every public contract has an owner, version, examples, and tests.
- Every service has clear domain, application, API, infrastructure, worker, test, config, and migration boundaries.
- Development ports are configurable and validated before startup.
- Documentation links modules to architecture, logic, operations, and examples.
- Gaps and unresolved ownership questions are recorded in the gap-analysis section instead of being hidden in code.


## Current Backend Scaffold Reference

The live backend scaffold is located at `/root/Astloom/backend`.

Backend folder creation must follow:

- `/root/Astloom/backend/README.md`
- `/root/Astloom/backend/docs/STRUCTURE_STANDARD.md`
- `/root/Astloom/backend/docs/MODULE_TEMPLATE.md`
- `/root/Astloom/backend/docs/NAMING_AND_BOUNDARIES.md`

The current scaffold is intentionally documentation-first. It creates modular boundaries, service ownership areas, shared package boundaries, platform adapters, integration areas, configuration profiles, deployments, tests, tools, and runbooks before implementation code is added.

Every backend folder must include a README that states purpose, modular boundary, allowed contents, rules, and status. Future implementation work should update these README files instead of adding undocumented source folders.

## Related Documents

- Continued in `docs/08-software-engineering-architecture/05-modular-project-structure-continued-continued.md`

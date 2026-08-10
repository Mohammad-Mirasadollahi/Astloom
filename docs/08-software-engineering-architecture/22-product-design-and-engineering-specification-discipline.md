---
doc_id: as.doc.sea.product-design-and-engineering-specification-discipline
title: 22 - Product Design And Engineering Specification Discipline
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how Astloom specifications should be written from the combined
  perspective of an experienced software engineer and an experienced product designer. It
  turns product intent into technical behavior and turns technical behavior into usable operator
  and agent .
tags:
- standard
- sea
phase: 08-software-engineering-architecture
canonical_path: docs/08-software-engineering-architecture/22-product-design-and-engineering-specification-discipline.md
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

# 22 - Product Design And Engineering Specification Discipline

## Purpose

This document defines how Astloom specifications should be written from the combined perspective of an experienced software engineer and an experienced product designer. It turns product intent into technical behavior and turns technical behavior into usable operator and agent workflows.

The system is complex enough that engineering and product design cannot be documented separately. Astloom features often involve humans, agents, services, memory, policies, code graphs, approvals, connectors, automation jobs, and operational diagnostics in one flow. A useful specification must describe all of those dimensions.

## Specification Principle

Every significant Astloom feature should answer this question:

What must the user, agent, system, and operator each understand or do, and which technical components make that behavior reliable?

A specification should therefore connect:

- product goal.
- user or agent workflow.
- information architecture.
- interaction states.
- service ownership.
- commands and queries.
- events.
- data persistence.
- permissions.
- failure handling.
- diagnostics.
- metrics.
- tests.

## Dual-Track Specification Model

Astloom should use a dual-track specification model.

| Track | Focus | Output |
| --- | --- | --- |
| Product Design Track | roles, workflows, IA, states, ergonomics, review surfaces, onboarding | experience specification |
| Engineering Track | modules, contracts, state machines, data, events, config, tests, operations | technical specification |
| Integration Point | product behavior mapped to system behavior | implementation-ready feature spec |

The tracks should converge before implementation starts.

## Product Design Inputs

Product design input should define:

- target persona or role.
- permission level.
- job to be done.
- trigger or entry point.
- expected outcome.
- required evidence shown to the user.
- decision points.
- escalation points.
- recovery paths.
- notifications.
- audit visibility.
- usability constraints.
- success metrics.

Astloom roles may include:

- workspace admin.
- platform operator.
- developer.
- reviewer.
- security reviewer.
- product manager.
- autonomous agent.
- IDE assistant.
- integration owner.

## Engineering Inputs

Engineering input should define:

- owning bounded context.
- service and package boundaries.
- API commands and queries.
- event producers and consumers.
- schema versions.
- data ownership.
- migration impact.
- configuration keys.
- idempotency behavior.
- retry behavior.
- authorization checks.
- audit records.
- observability signals.
- test layers.
- rollout strategy.

## Product-To-System Mapping

Every product workflow should map to system behavior.

Example mapping for agent connector onboarding:

| Product Step | System Behavior | Owning Module |
| --- | --- | --- |
| Admin selects connector type | API returns supported connector types and capability templates | adapter-service |
| Admin chooses workspace | Authorization checks workspace admin permission | api-gateway and auth package |
| System generates profile | Connector registry creates draft connector and profile | adapter-service |
| Admin provides authentication method | Credential reference is stored without printing secrets | adapter-service and config-service |
| System validates connector | Automation job runs compatibility and health checks | automation control plane |
| Connector becomes ready | Registry status changes and audit event is recorded | adapter-service and audit-service |
| Agent connects | Agent uses generated profile and discovers capabilities | api-gateway |

This mapping prevents product flows from becoming disconnected from implementation ownership.

## Information Architecture Requirements

Astloom UI and CLI experiences should expose the domain model clearly.

Important product objects:

- Workspace.
- Agent.
- Connector.
- Activity.
- WorkLog.
- Decision.
- Issue.
- Task.
- MemoryItem.
- Rule.
- RuleEvaluation.
- CodeGraphSnapshot.
- DocumentAnchor.
- AutomationJob.
- AuditRecord.
- Gap.

Information architecture should define:

- object hierarchy.
- object relationships.
- primary navigation.
- filters and search behavior.
- detail views.
- timeline or activity views.
- ownership views.
- diagnostics views.
- review queues.
- approval queues.

## Interaction State Requirements

Every workflow should specify states that align frontend behavior, backend state, and user expectations.

Required state mapping:

- frontend display state.
- backend entity state.
- allowed commands.
- blocked commands.
- event emitted on transition.
- audit behavior.
- diagnostic behavior.

Example for automation job state:

| Frontend State | Backend State | Allowed Commands | Event |
| --- | --- | --- | --- |
| queued | pending | cancel | AutomationJobQueued |
| waiting for approval | waiting_for_approval | approve, reject, cancel | AutomationApprovalRequested |
| running | running | view logs, cancel if safe | AutomationJobStarted |
| succeeded | succeeded | view report, rerun if allowed | AutomationJobSucceeded |
| failed | failed | retry, view diagnostics | AutomationJobFailed |
| partially completed | partially_completed | resume, rollback if safe | AutomationJobPartiallyCompleted |

## UX Requirements For Technical Workflows

Technical workflows still need product design quality.

Installation UX should provide:

- mode selection.
- preflight status.
- generated config summary.
- dependency status.
- service readiness status.
- smoke test result.
- connection endpoints.
- evidence report.
- clear failure repair hints.

Connector UX should provide:

- connector type selection.
- capability preview.
- authentication method selection.
- least-privilege permission summary.
- validation progress.
- health state.
- generated profile access.
- troubleshooting output.

Rule evaluation UX should provide:

- rule matched.
- evidence used.
- severity.
- explanation.
- required action.
- approval path.
- audit trail.

Memory retrieval UX should provide:

- selected memory items.
- score factors.
- source evidence.
- confidence.
- freshness.
- trust indicators.
- feedback action.

## Error And Recovery Design

Error states must be designed as first-class states.

Every error should define:

- user-facing summary.
- technical code.
- probable cause.
- affected object.
- retryability.
- safe recovery action.
- diagnostics link.
- correlation ID.
- audit impact.

Example:

| Error | User Message Intent | Recovery | Engineering Mapping |
| --- | --- | --- | --- |
| connector_auth_failed | explain credential validation failed | rotate credential or edit auth mode | adapter-service validation error |
| port_conflict_detected | show conflicting port and process hint | regenerate port map or override | port-preflight failure |
| migration_blocked | explain incompatible migration state | stop rollout and review migration | migration gate failure |
| memory_context_denied | explain permission boundary | request permission or reduce scope | authorization failure before retrieval |

## Product Metrics And Engineering Metrics

Specifications should include both product and engineering metrics.

Product metrics:

- time to first successful installation.
- connector registration success rate.
- average steps to connect an agent.
- drift repair completion rate.
- approval queue resolution time.
- documentation drift closure time.
- percentage of workflows with explainability viewed.

Engineering metrics:

- failed preflight checks by category.
- automation job failure rate.
- contract compatibility failures.
- event retry and dead-letter counts.
- migration failure rate.
- service readiness failure rate.
- memory retrieval latency.
- graph ingestion latency.

## Specification Template

A complete feature specification should use this structure:

1. Purpose.
2. Target Roles.
3. Jobs To Be Done.
4. Primary Workflow.
5. Secondary Workflows.
6. Interaction State Model.
7. Information Architecture Impact.
8. System Ownership.
9. API Commands And Queries.
10. Events.
11. Data Model And Persistence.
12. Permissions And Security.
13. Configuration.
14. Observability And Diagnostics.
15. Error And Recovery Behavior.
16. Rollout And Migration.
17. Product Metrics.
18. Engineering Metrics.
19. Test Strategy.
20. Acceptance Criteria.
21. Open Gaps.

## Example: Zero-Touch Installation Specification Expectations

A professional specification for zero-touch installation should include:

- installer modes and who uses each mode.
- first-run onboarding journey.
- preflight state table.
- generated config object model.
- service registry object model.
- automation job state machine.
- dependency provisioning strategy.
- store and broker bootstrap sequence.
- secret handling model.
- readiness and smoke test contracts.
- installation evidence report schema.
- retry and resume behavior.
- operator diagnostics UX.
- product metric for time to ready.
- engineering metric for failed bootstrap step categories.

## Example: Agent Connectivity Specification Expectations

A professional specification for agent connectivity should include:

- agent roles and permission scopes.
- connector registration journey.
- capability discovery contract.
- generated connection profile schema.
- authentication mode matrix.
- validation and smoke test sequence.
- connector health state model.
- degraded connector UX.
- CLI and admin-console behavior.
- event contracts for connector readiness and failure.
- audit record requirements.
- product metric for successful first connection.
- engineering metric for connector validation failure categories.

## Acceptance Criteria

Product design and engineering specification discipline is acceptable when:

- every significant feature maps product workflow to system behavior.
- every user-facing workflow defines interaction states and recovery paths.
- every technical behavior has an owning module and public contract when it crosses boundaries.
- every feature defines product metrics and engineering metrics.
- every specification can be used by engineers without requiring undocumented product assumptions.
- every specification can be used by product designers without requiring hidden implementation knowledge.

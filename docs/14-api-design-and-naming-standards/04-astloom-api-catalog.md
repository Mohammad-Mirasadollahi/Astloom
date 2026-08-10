---
doc_id: as.doc.api.astloom-api-catalog
title: 04 - Astloom API Catalog
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the first planned API families for Astloom. It provides logical
  endpoint names that future implementation should follow unless a documented exception is
  approved.
tags:
- standard
- api
phase: 14-api-design-and-naming-standards
canonical_path: docs/14-api-design-and-naming-standards/04-astloom-api-catalog.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.1.3
updated_at: 2026-08-10
---

# 04 - Astloom API Catalog

## Purpose

This document defines the first planned API families for Astloom. It provides logical endpoint names that future implementation should follow unless a documented exception is approved.

## Identity And Access APIs

```text
GET  /api/v1/me
GET  /api/v1/me/permissions
GET  /api/v1/workspaces
POST /api/v1/workspaces
GET  /api/v1/workspaces/{workspace_id}
PATCH /api/v1/workspaces/{workspace_id}
```

## Project And Project Group APIs

```text
GET  /api/v1/projects
POST /api/v1/projects
GET  /api/v1/projects/{project_id}
PATCH /api/v1/projects/{project_id}
GET  /api/v1/project-groups
POST /api/v1/project-groups
GET  /api/v1/project-groups/{project_group_id}
POST /api/v1/project-groups/{project_group_id}:attach-project
POST /api/v1/project-groups/{project_group_id}:detach-project
```

## Agent And Agent Run APIs

```text
GET  /api/v1/projects/{project_id}/agents
POST /api/v1/projects/{project_id}/agents
GET  /api/v1/projects/{project_id}/agents/{agent_id}
PATCH /api/v1/projects/{project_id}/agents/{agent_id}
POST /api/v1/projects/{project_id}/agents/{agent_id}:enable
POST /api/v1/projects/{project_id}/agents/{agent_id}:disable
GET  /api/v1/projects/{project_id}/agent-runs
POST /api/v1/projects/{project_id}/agent-runs
GET  /api/v1/projects/{project_id}/agent-runs/{agent_run_id}
POST /api/v1/projects/{project_id}/agent-runs/{agent_run_id}:cancel
```

## Task, Activity, Decision, And Work Log APIs

```text
GET  /api/v1/projects/{project_id}/tasks
POST /api/v1/projects/{project_id}/tasks
GET  /api/v1/projects/{project_id}/tasks/{task_id}
PATCH /api/v1/projects/{project_id}/tasks/{task_id}
POST /api/v1/projects/{project_id}/tasks/{task_id}:assign
POST /api/v1/projects/{project_id}/tasks/{task_id}:complete
GET  /api/v1/projects/{project_id}/activities
POST /api/v1/projects/{project_id}/activities
GET  /api/v1/projects/{project_id}/decisions
POST /api/v1/projects/{project_id}/decisions
GET  /api/v1/projects/{project_id}/work-logs
POST /api/v1/projects/{project_id}/work-logs
```

## Agent Control Plane Ticket APIs

Owned by `orchestration-service` (implemented). Mutations require `expected_version`. Create without `agent_id` starts in `created`; with `agent_id` starts in `assigned`.

```text
GET  /api/v1/projects/{project_id}/agent-tickets
POST /api/v1/projects/{project_id}/agent-tickets
GET  /api/v1/projects/{project_id}/agent-tickets/{agent_ticket_id}
POST /api/v1/projects/{project_id}/agent-tickets/{agent_ticket_id}:claim
POST /api/v1/projects/{project_id}/agent-tickets/{agent_ticket_id}:start
POST /api/v1/projects/{project_id}/agent-tickets/{agent_ticket_id}:block
POST /api/v1/projects/{project_id}/agent-tickets/{agent_ticket_id}:submit-review
POST /api/v1/projects/{project_id}/agent-tickets/{agent_ticket_id}:complete
POST /api/v1/projects/{project_id}/agent-tickets/{agent_ticket_id}:fail
POST /api/v1/projects/{project_id}/agent-tickets/{agent_ticket_id}:cancel
POST /api/v1/projects/{project_id}/agent-tickets/{agent_ticket_id}:reassign
POST /api/v1/projects/{project_id}/agents/{agent_id}:heartbeat
POST /api/v1/projects/{project_id}/agents/{agent_id}:set-state
```

Contract: `backend/services/orchestration-service/docs/phase-orchestration-api-contract.md`.

Do not treat ExternalTicket smoke tests as evidence that AgentTicket is ready; they are separate aggregates.

## External Ticket Mirror APIs

Owned by `adapter-service` (implemented). ExternalTicket is a local mirror of an optional tracker projection, not the AgentTicket control-plane aggregate. Domain commands live in modular `adapter_service.core.tickets` (composed by `AdapterService`).

```text
POST /api/v1/projects/{project_id}/external-tickets
GET  /api/v1/projects/{project_id}/external-tickets
GET  /api/v1/projects/{project_id}/external-tickets/{ticket_id}
POST /api/v1/projects/{project_id}/external-tickets/{ticket_id}:sync-status
POST /api/v1/projects/{project_id}/external-tickets/{ticket_id}:retry-dispatch
POST /api/v1/projects/{project_id}/external-tickets/{ticket_id}:record-dispatch-result
POST /api/v1/projects/{project_id}/external-tickets/{ticket_id}:push-status
```

Contract: `backend/services/adapter-service/docs/phase-5-api-contract.md` (includes `adapter_service/core/` module layout). Spec: `docs/05-interoperability-ecosystem/13-external-ticketing-improvement-specification.md`. Unit focus: `tests/backend/services/adapter-service/test_external_tickets.py`.

The isolated hackathon API uses `/managed-agents` instead of `/agents` to make the external managed-resource boundary unmistakable in the judged demo. This is a documented temporary naming exception; product promotion should converge on the canonical `/agents` family with the same contracts.

## Memory And Context APIs

Owned by `memory-service` (implemented Phase 2 slice). Browse + human remember/forget:

```text
GET  /api/v1/projects/{project_id}/memory-items
POST /api/v1/projects/{project_id}/memory-items
GET  /api/v1/projects/{project_id}/memory-items/{memory_item_id}
PATCH /api/v1/projects/{project_id}/memory-items/{memory_item_id}
POST /api/v1/projects/{project_id}/memory-items/{memory_item_id}:promote
POST /api/v1/projects/{project_id}/memory-items/{memory_item_id}:deprecate
POST /api/v1/projects/{project_id}/memory-promotions
POST /api/v1/projects/{project_id}/memory-consolidations
POST /api/v1/projects/{project_id}/memory-decays
POST /api/v1/projects/{project_id}/context-bundles
GET  /api/v1/projects/{project_id}/context-bundles:explain
GET  /api/v1/projects/{project_id}/stale-memory
```

Contract: `backend/services/memory-service/docs/phase-2-api-contract.md`. UI spec (browser only): `docs/02-memory-and-context/14-memory-browser-and-long-term-selection-ui.md`.

## Common Context APIs

```text
GET  /api/v1/projects/{project_id}/common-context-items
POST /api/v1/projects/{project_id}/common-context-items
GET  /api/v1/projects/{project_id}/common-context-items/{common_context_item_id}
PATCH /api/v1/projects/{project_id}/common-context-items/{common_context_item_id}
POST /api/v1/projects/{project_id}/common-context-items/{common_context_item_id}:approve
POST /api/v1/projects/{project_id}/common-context-items/{common_context_item_id}:suppress
POST /api/v1/projects/{project_id}/common-context-items/{common_context_item_id}:promote
POST /api/v1/projects/{project_id}/common-context-bundles:resolve
```

## Rule And Policy APIs

```text
GET  /api/v1/projects/{project_id}/rules
POST /api/v1/projects/{project_id}/rules
GET  /api/v1/projects/{project_id}/rules/{rule_id}
PATCH /api/v1/projects/{project_id}/rules/{rule_id}
POST /api/v1/projects/{project_id}/rules/{rule_id}:approve
POST /api/v1/projects/{project_id}/rule-evaluations
GET  /api/v1/projects/{project_id}/rule-evaluations/{rule_evaluation_id}
```

## Code Graph And Code Metadata APIs

```text
GET  /api/v1/projects/{project_id}/repositories
POST /api/v1/projects/{project_id}/repositories
GET  /api/v1/projects/{project_id}/repositories/{repository_id}
POST /api/v1/projects/{project_id}/repositories/{repository_id}:reindex
GET  /api/v1/projects/{project_id}/repositories/{repository_id}/code-metadata
POST /api/v1/projects/{project_id}/repositories/{repository_id}/code-metadata:search
GET  /api/v1/projects/{project_id}/code-symbols/{symbol_id}
POST /api/v1/projects/{project_id}/code-context-packs:resolve
GET  /api/v1/projects/{project_id}/graph/symbols/{symbol_id}
GET  /api/v1/projects/{project_id}/graph/symbols/{symbol_id}/neighbors
POST /api/v1/projects/{project_id}/graph/symbols/{symbol_id}/callers
POST /api/v1/projects/{project_id}/graph/symbols/{symbol_id}/impact
POST /api/v1/projects/{project_id}/graph/symbols/{symbol_id}/community
POST /api/v1/projects/{project_id}/graph/symbols/{symbol_id}/call-path
POST /api/v1/projects/{project_id}/graph/explore
POST /api/v1/projects/{project_id}/graph/detect-changes
POST /api/v1/projects/{project_id}/graph/architecture-overview
POST /api/v1/projects/{project_id}/graph/path
POST /api/v1/projects/{project_id}/graph/search:hybrid
GET  /api/v1/projects/{project_id}/graph/freshness
```

Canonical Phase 7 contract: `backend/services/code-graph-service/docs/phase-7-api-contract.md`.
Codebase-Memory hybrid (Neo4j): `docs/07-code-knowledge-graph/44`–`47`.
## Documentation Sync APIs

```text
GET  /api/v1/projects/{project_id}/documents
POST /api/v1/projects/{project_id}/documents:sync
GET  /api/v1/projects/{project_id}/documentation-drift-findings
POST /api/v1/projects/{project_id}/documentation-drift-findings/{finding_id}:resolve
```

## Connector And Resource APIs

```text
GET  /api/v1/projects/{project_id}/connectors
POST /api/v1/projects/{project_id}/connectors
GET  /api/v1/projects/{project_id}/connectors/{connector_id}
PATCH /api/v1/projects/{project_id}/connectors/{connector_id}
POST /api/v1/projects/{project_id}/connectors/{connector_id}:test
POST /api/v1/projects/{project_id}/connectors/{connector_id}:enable
POST /api/v1/projects/{project_id}/connectors/{connector_id}:disable
```

## Reporting And Analytics APIs

```text
GET  /api/v1/projects/{project_id}/reports/code-generation-speed
GET  /api/v1/projects/{project_id}/reports/bug-reduction
GET  /api/v1/projects/{project_id}/reports/architecture-quality
GET  /api/v1/projects/{project_id}/reports/rework-reduction
GET  /api/v1/projects/{project_id}/reports/token-usage
GET  /api/v1/projects/{project_id}/reports/agent-activity
```

## Test Evidence APIs

```text
GET  /api/v1/projects/{project_id}/test-runs
POST /api/v1/projects/{project_id}/test-runs
GET  /api/v1/projects/{project_id}/test-runs/{test_run_id}
GET  /api/v1/projects/{project_id}/live-test-runs
POST /api/v1/projects/{project_id}/live-test-runs
GET  /api/v1/projects/{project_id}/live-test-runs/{live_test_run_id}
```

## Automation APIs

```text
GET  /api/v1/projects/{project_id}/automation-jobs
POST /api/v1/projects/{project_id}/automation-jobs
GET  /api/v1/projects/{project_id}/automation-jobs/{automation_job_id}
POST /api/v1/projects/{project_id}/automation-jobs/{automation_job_id}:cancel
POST /api/v1/projects/{project_id}/automation-jobs/{automation_job_id}:retry
```

## Catalog Rule

New API families must be added to this catalog before implementation. If an implementation needs a different naming style, the exception must reference the API standard and document why the standard does not fit.

## Phase 1 Core Data Additions

```text
GET  /api/v1/projects/{project_id}/activities
POST /api/v1/projects/{project_id}/activities
GET  /api/v1/projects/{project_id}/work-logs
POST /api/v1/projects/{project_id}/work-logs
GET  /api/v1/projects/{project_id}/decisions
POST /api/v1/projects/{project_id}/decisions
POST /api/v1/projects/{project_id}/decisions/{decision_id}:supersede
GET  /api/v1/projects/{project_id}/issues
POST /api/v1/projects/{project_id}/issues
GET  /api/v1/projects/{project_id}/open-issues
GET  /api/v1/projects/{project_id}/tasks
POST /api/v1/projects/{project_id}/tasks
POST /api/v1/projects/{project_id}/tasks/{task_id}:transition
GET  /api/v1/projects/{project_id}/task-board
GET  /api/v1/projects/{project_id}/decision-history
GET  /api/v1/projects/{project_id}/related-work
GET  /api/v1/projects/{project_id}/evidence-bundles/{evidence_ref}
GET  /api/v1/projects/{project_id}/timeline
```

The transition and supersede commands are documented command-style exceptions to PATCH because they record lifecycle reasons, expected versions or idempotency keys, and audit events.

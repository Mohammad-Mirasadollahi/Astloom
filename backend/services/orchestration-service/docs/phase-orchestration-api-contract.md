---
doc_id: as.doc.orchestration.phase-orchestration-api-contract
title: Astloom Orchestration API Contract
doc_type: contract
status: active
schema_version: '1.0'
owner: orchestration-service
summary: 'API contract for orchestration-service work batches, assignments, and AgentTicket lifecycle.'
tags:
- api
- contract
- orchestration
- agent-ticket
- phase-orchestration
phase: phase-orchestration
canonical_path: backend/services/orchestration-service/docs/phase-orchestration-api-contract.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
doc_version: 1.1.1
updated_at: 2026-08-10
linked_symbols:
- backend/services/orchestration-service/src/orchestration_service/api.py::build_app
- backend/services/orchestration-service/src/orchestration_service/core.py::OrchestrationService
---

# Astloom Orchestration API Contract

## Purpose

Vertical slice for `orchestration-service`: work batches, assignments, and native AgentTicket lifecycle.

- Scope headers: `X-Tenant-Id`, `X-Workspace-Id`, `X-Actor-Id`
- Idempotency: `Idempotency-Key` on mutating routes
- Persistence target env: `ASTLOOM_ORCHESTRATION_DATABASE_URL`
- Tests: `tests/backend/services/orchestration-service/`

## Work batch and assignment routes

```text
POST /api/v1/projects/{project_id}/work-batches
POST /api/v1/projects/{project_id}/work-batches/{batch_id}:close
POST /api/v1/projects/{project_id}/assignments
POST /api/v1/projects/{project_id}/assignments/{assignment_id}:complete
GET  /api/v1/projects/{project_id}/assignments
```

## AgentTicket routes

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
```

List filters: `status`, `agent_id`, `task_id`.

Mutations require `expected_version`. Create without `agent_id` starts in `created`; create with `agent_id` starts in `assigned`. `:reassign` moves a non-terminal ticket to `assigned` with a new `agent_id`. `:submit-review` may optionally attach `changeset_id` / `changeset_revision` (soft link; hard ChangeSet gate is not required in this MVP).

States: `created`, `assigned`, `claimed`, `in_progress`, `blocked`, `review`, `completed`, `failed`, `canceled`.

### Outbox events

- `AgentTicketCreated`
- `AgentTicketClaimed`
- `AgentTicketStarted`
- `AgentTicketBlocked`
- `AgentTicketSubmittedForReview`
- `AgentTicketCompleted`
- `AgentTicketFailed`
- `AgentTicketCanceled`
- `AgentTicketReassigned`

## Live verification

Process HTTP smoke against a restarted orchestration-service (with adapter-service) passed on 2026-07-31: create with `agent_id` → `assigned`, then `:claim` → `claimed`, `:start` → `in_progress`. Script: `tests/live/adapter-service/smoke_ticketing_quality.py`.

## Related Documents

- `backend/docs/API_NAMING_AND_CONTRACT_STANDARD.md` — HTTP naming and contract conventions
- API catalog: `docs/14-api-design-and-naming-standards/04-astloom-api-catalog.md`
- Collaboration surface: `docs/01-core-data-model/07-agent-collaboration-work-surface.md`
- ExternalTicket (distinct): `docs/05-interoperability-ecosystem/13-external-ticketing-improvement-specification.md`

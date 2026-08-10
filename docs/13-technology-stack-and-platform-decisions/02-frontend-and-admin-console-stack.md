---
doc_id: as.doc.stack.frontend-and-admin-console-stack
title: 02 - Frontend And Admin Console Stack
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the technology stack for the Astloom web interface, admin
  console, and operator control surface.
tags:
- standard
- stack
phase: 13-technology-stack-and-platform-decisions
canonical_path: docs/13-technology-stack-and-platform-decisions/02-frontend-and-admin-console-stack.md
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

# 02 - Frontend And Admin Console Stack

## Purpose

This document defines the technology stack for the Astloom web interface, admin console, and operator control surface.

## Required Stack

| Layer | Technology | Role |
| --- | --- | --- |
| Framework | Next.js | admin console, routing, server-side rendering where useful, API integration, deployment flexibility |
| Language | TypeScript | type safety, generated API clients, safer refactors |
| UI Runtime | React | component model and ecosystem |
| API Clients | generated TypeScript clients from OpenAPI | contract-first communication with FastAPI services |
| Testing | Playwright, Vitest, Testing Library | E2E, component behavior, and unit-level UI logic |
| Forms | schema-driven forms | validation aligned with backend contracts |
| Observability | OpenTelemetry browser instrumentation where applicable | frontend traces, correlation ids, UI error visibility |

## Admin Console Responsibilities

The admin console must support:

- tracking agent actions and workflow history.
- managing common context, rules, memory, tasks, tickets, and feedback.
- reviewing agent mistakes and converting corrections into reusable rules or common context.
- managing project isolation and project-group composition.
- viewing RAG, metadata, graph, and context-pack evidence.
- viewing live test and unit test evidence.
- managing connector health and agent/resource connectivity.
- viewing reporting metrics such as initial code generation speed, bug reduction, architecture quality, rework reduction, and token usage.

## Type Safety Rule

Frontend data models must come from backend contracts wherever possible. Do not duplicate API DTOs manually when generated clients or shared contract schemas can be used.

## UI Architecture Rule

The admin console should be workflow-oriented, not a marketing landing page. It should prioritize dense but readable operational screens, fast filtering, auditability, status visibility, and repeated daily use.

## State Management Rule

Use server state libraries or framework-native data loading for remote data. Keep local state limited to UI interaction state. Persistent business state belongs in backend services, not browser state.

## Security Rule

The frontend must not enforce authorization alone. It may hide unavailable controls, but backend services must enforce permissions, tenant isolation, project isolation, and approval boundaries.

## Testing Rule

Every critical admin workflow must have E2E coverage: rule creation, common context approval, agent feedback, task assignment, memory review, report viewing, connector setup, and live-test evidence review.

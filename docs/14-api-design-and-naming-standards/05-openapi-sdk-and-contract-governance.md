---
doc_id: as.doc.api.openapi-sdk-and-contract-governance
title: 05 - OpenAPI, SDK, And Contract Governance
doc_type: contract
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines how Astloom API contracts should be generated, versioned,
  tested, published, and consumed by frontend clients, SDKs, agents, and external integrations.
tags:
- contract
- api
phase: 14-api-design-and-naming-standards
canonical_path: docs/14-api-design-and-naming-standards/05-openapi-sdk-and-contract-governance.md
lifecycle_lane: current
concern_lane: contract
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 05 - OpenAPI, SDK, And Contract Governance

## Purpose

This document defines how Astloom API contracts should be generated, versioned, tested, published, and consumed by frontend clients, SDKs, agents, and external integrations.

## OpenAPI Rule

FastAPI OpenAPI output is the primary HTTP API contract source. The OpenAPI document must be generated in CI and validated against the API standards.

Every endpoint must include:

- operation_id.
- tags.
- summary.
- request schema where applicable.
- response schema.
- structured error responses.
- authentication and authorization requirements.
- examples.
- pagination details for list endpoints.
- idempotency requirement for retryable commands.

## Operation ID Naming

Use stable operation ids with this pattern:

```text
{domain}_{action}_{resource}
```

Examples:

```text
projects_create_project
projects_get_project
agent_runs_cancel_agent_run
common_context_approve_item
code_metadata_search_repository_metadata
reports_get_token_usage_report
```

Do not let framework defaults produce unstable operation ids.

## SDK Generation

TypeScript clients for Next.js and external SDKs should be generated from OpenAPI when possible. Generated clients must preserve error types, request types, response types, pagination types, and idempotency headers.

SDKs must not expose database concepts or service internals.

## Contract Test Requirements

CI must validate:

- OpenAPI schema generation succeeds.
- documented examples match schemas.
- operation ids are stable.
- endpoint names follow the naming standard.
- list endpoints include pagination.
- retryable commands document idempotency.
- error responses match the standard error contract.
- generated TypeScript clients compile.

## Versioning

The default API path is `/api/v1`. Breaking changes require one of:

- a new versioned endpoint.
- a compatibility adapter.
- a documented deprecation period and migration guide.

Do not introduce breaking changes silently.

## Deprecation

Deprecated endpoints must document:

- replacement endpoint.
- deprecation date.
- removal date.
- affected clients.
- migration guide.
- compatibility behavior.

## Governance Workflow

Before implementing a new API:

1. Add the API family or endpoint to `04-astloom-api-catalog.md`.
2. Define request and response schemas under `backend/packages/contracts/api/` when implementation begins.
3. Add examples under `backend/packages/contracts/examples/`.
4. Generate or update OpenAPI.
5. Add contract tests.
6. Update SDK generation if the API is public or frontend-facing.
7. Update documentation indexes when a new API family is introduced.

## Acceptance Criteria

An API is ready for implementation when the endpoint name follows the standard, schemas are named, errors are structured, idempotency and pagination are defined where needed, OpenAPI operation ids are stable, and SDK generation impact is understood.

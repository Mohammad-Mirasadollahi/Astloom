---
doc_id: as.doc.api.dto-schema-error-pagination-and-idempotency-standard
title: 03 - DTO, Schema, Error, Pagination, And Idempotency Standard
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the payload, schema, error, pagination, filtering, sorting,
  and idempotency standards for Astloom APIs.
tags:
- standard
- api
phase: 14-api-design-and-naming-standards
canonical_path: docs/14-api-design-and-naming-standards/03-dto-schema-error-pagination-and-idempotency-standard.md
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

# 03 - DTO, Schema, Error, Pagination, And Idempotency Standard

## Purpose

This document defines the payload, schema, error, pagination, filtering, sorting, and idempotency standards for Astloom APIs.

## Field Naming

JSON fields must use snake_case.

Good:

```json
{
  "project_id": "proj_123",
  "created_at": "2026-07-09T18:30:00Z",
  "idempotency_key": "cmd_abc"
}
```

Bad:

```json
{
  "projectId": "proj_123",
  "createdAt": "2026-07-09T18:30:00Z"
}
```

TypeScript clients may expose camelCase internally only if generated mapping is explicit and contract-safe. Wire format remains snake_case.

## DTO Naming

Use explicit request and response names.

Patterns:

```text
CreateTaskRequest
CreateTaskResponse
UpdateTaskRequest
TaskResponse
TaskListResponse
ResolveContextBundleRequest
ResolveContextBundleResponse
ApproveRuleRequest
ApproveRuleResponse
```

Avoid vague names:

```text
TaskDto
Payload
Data
RequestBody
ApiResponse
```

## Standard Response Shape

Single-resource responses should return a named object:

```json
{
  "task": {},
  "audit_ref": "audit_123",
  "correlation_id": "corr_123"
}
```

List responses should use:

```json
{
  "items": [],
  "page": {
    "next_page_token": null,
    "page_size": 50,
    "has_more": false
  },
  "correlation_id": "corr_123"
}
```

## Pagination Standard

Use IDE pagination for mutable collections.

Query parameters:

```text
page_size
page_token
sort
```

Rules:

- default page size must be documented.
- maximum page size must be enforced.
- unbounded list endpoints are forbidden.
- sort fields must be allowlisted.

## Filtering Standard

Use explicit query parameters for common filters:

```text
status
owner_id
created_after
created_before
updated_after
updated_before
tag
risk_level
workflow_type
```

Complex filters should use POST search endpoints only when GET query parameters become too large or when structured filter logic is required.

Example:

```text
POST /api/v1/projects/{project_id}/tasks:search
```

## Error Format

Public errors must use this structure:

```json
{
  "error": {
    "error_code": "task_not_found",
    "category": "not_found_error",
    "message": "Task was not found.",
    "retryable": false,
    "correlation_id": "corr_123",
    "details": {},
    "documentation_ref": "docs/errors/task_not_found"
  }
}
```

Required categories:

- validation_error
- authentication_error
- authorization_error
- conflict_error
- not_found_error
- dependency_error
- rate_limit_error
- policy_error
- internal_error

Do not expose secrets, stack traces, raw prompts, model payloads, provider credentials, or private infrastructure details.

## Idempotency Standard

Retryable POST commands must accept an idempotency key.

Preferred header:

```text
Idempotency-Key: <stable-client-generated-key>
```

The server must store:

- idempotency key.
- command name.
- actor or producer.
- project scope.
- request hash.
- response reference.
- created_at.
- expires_at.

If the same key is reused with a different request hash, return `409 conflict_error`.

## Correlation Headers

APIs should accept and return:

```text
X-Correlation-Id
X-Request-Id
```

If the caller does not provide a correlation id, the server must create one.

## Time And IDs

Use ISO 8601 UTC timestamps. Public IDs should be stable, opaque, and prefixed by domain where helpful, such as `proj_`, `task_`, `agent_`, `mem_`, `rule_`, `ctx_`, `repo_`, `sym_`, and `run_`.

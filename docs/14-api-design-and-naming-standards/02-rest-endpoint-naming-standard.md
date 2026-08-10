---
doc_id: as.doc.api.rest-endpoint-naming-standard
title: 02 - REST Endpoint Naming Standard
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: This document defines the endpoint naming format for Astloom REST APIs.
tags:
- standard
- api
phase: 14-api-design-and-naming-standards
canonical_path: docs/14-api-design-and-naming-standards/02-rest-endpoint-naming-standard.md
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

# 02 - REST Endpoint Naming Standard

## Purpose

This document defines the endpoint naming format for Astloom REST APIs.

## Base Path

Public API paths should use this pattern:

```text
/api/v1/{resource}
/api/v1/projects/{project_id}/{resource}
/api/v1/project-groups/{project_group_id}/{resource}
```

Internal service APIs may use internal routing, but public contracts must still follow the same naming logic unless a documented exception exists.

## Resource Naming

Use lowercase kebab-case plural nouns for collection resources.

Good:

```text
/projects
/project-groups
/agent-runs
/memory-items
/context-bundles
/common-context-items
/code-metadata
/rule-evaluations
/live-test-runs
```

Bad:

```text
/getProject
/ProjectGroup
/agentRunList
/memory_item
/commonContextItem
```

## HTTP Method Rules

| Method | Usage |
| --- | --- |
| GET | read a resource or list resources |
| POST | create a resource or execute a command that creates server-side work |
| PATCH | partial update of a resource |
| PUT | full replacement only when replacement semantics are clear |
| DELETE | delete, archive, or revoke when supported |

## Standard Resource Patterns

```text
GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{project_id}
PATCH  /api/v1/projects/{project_id}
DELETE /api/v1/projects/{project_id}
```

## Project-Scoped Resource Patterns

```text
GET  /api/v1/projects/{project_id}/tasks
POST /api/v1/projects/{project_id}/tasks
GET  /api/v1/projects/{project_id}/tasks/{task_id}
PATCH /api/v1/projects/{project_id}/tasks/{task_id}
```

Project-scoped resources must not be exposed through unscoped endpoints unless there is a strong admin reason and explicit authorization.

## Command Subresource Pattern

Use command subresources for domain actions that are not standard CRUD.

Pattern:

```text
POST /api/v1/projects/{project_id}/{resource}/{resource_id}:{command}
```

Examples:

```text
POST /api/v1/projects/{project_id}/tasks/{task_id}:assign
POST /api/v1/projects/{project_id}/rules/{rule_id}:approve
POST /api/v1/projects/{project_id}/common-context-items/{item_id}:promote
POST /api/v1/projects/{project_id}/repositories/{repository_id}:reindex
POST /api/v1/projects/{project_id}/agent-runs/{agent_run_id}:cancel
```

Use verbs only after the colon command marker. Do not create paths such as `/approveRule` or `/runAgentNow`.

## Nested Resource Rule

Allow nesting when the child resource cannot be understood without the parent scope. Avoid deep nesting beyond two levels.

Good:

```text
/projects/{project_id}/tasks/{task_id}/comments
/projects/{project_id}/repositories/{repository_id}/code-metadata
```

Avoid:

```text
/workspaces/{workspace_id}/projects/{project_id}/repositories/{repository_id}/files/{file_id}/symbols/{symbol_id}/events
```

For deep relationships, use filters on a collection endpoint.

## Query Parameter Naming

Use snake_case query parameters.

Examples:

```text
?status=active
?created_after=2026-01-01T00:00:00Z
?include_archived=false
?sort=-created_at
?page_size=50
?page_token=abc
```

## Include And Expand Pattern

Use `include` for optional related data. Keep includes explicit and bounded.

```text
GET /api/v1/projects/{project_id}/tasks/{task_id}?include=assignee,latest_activity
```

Do not return large nested graphs by default.

## Naming Exceptions

If a future API cannot follow this REST standard, the exception must document:

- why REST naming is not appropriate.
- the alternative pattern.
- compatibility impact.
- SDK generation impact.
- contract test requirements.

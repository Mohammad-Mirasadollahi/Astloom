---
doc_id: as.doc.api.index
title: 14 - API Design And Naming Standards Index
doc_type: index
status: active
schema_version: '1.0'
owner: platform-docs
summary: This section defines the API design and naming standards for Astloom. It gives
  future implementers a consistent format for endpoint names, resource names, DTO names, error
  contracts, pagination, filtering, idempotency, versioning, OpenAPI generation, and API catalogs.
tags:
- index
- api
phase: 14-api-design-and-naming-standards
canonical_path: docs/14-api-design-and-naming-standards/00-index.md
lifecycle_lane: current
concern_lane: onboarding
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
doc_version: 1.0.1
updated_at: 2026-08-10
---

# 14 - API Design And Naming Standards Index

## Purpose

This section defines the API design and naming standards for Astloom. It gives future implementers a consistent format for endpoint names, resource names, DTO names, error contracts, pagination, filtering, idempotency, versioning, OpenAPI generation, and API catalogs.

The goal is not to freeze every future endpoint forever. The goal is to define a strong standard so that if new APIs are added later, they follow the same naming logic and contract style.

## Files

- `01-api-design-principles.md` defines API design principles, resource modeling, command/query separation, versioning, and contract-first rules.
- `02-rest-endpoint-naming-standard.md` defines URL naming, HTTP method usage, path parameters, query parameters, nested resources, actions, and examples.
- `03-dto-schema-error-pagination-and-idempotency-standard.md` defines request/response DTO naming, field naming, error format, pagination, filtering, sorting, idempotency, and correlation headers.
- `04-astloom-api-catalog.md` defines the first planned API groups and logical endpoint families for Astloom.
- `05-openapi-sdk-and-contract-governance.md` defines OpenAPI, generated clients, SDK alignment, contract tests, deprecation, and governance rules.

## Baseline API Style

Astloom should use HTTP APIs exposed by FastAPI and documented through OpenAPI. REST-style resource endpoints should be the default for external and admin APIs. Command-style subresources may be used when the operation is not a simple CRUD update.

API names must be stable, readable, project-scoped where required, versioned, and aligned with domain language.

## Relationship To Other Sections

- `../08-software-engineering-architecture/08-interface-and-contract-engineering.md` defines broader contract engineering.
- `../09-platform-governance-operations/05-api-versioning-and-contract-governance.md` defines contract governance.
- `../13-technology-stack-and-platform-decisions/03-backend-api-and-service-stack.md` defines FastAPI and OpenAPI as the backend API stack.
- `../../backend/packages/contracts/api/` is the future location for shared API contracts.

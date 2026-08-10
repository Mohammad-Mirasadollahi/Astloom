---
doc_id: as.doc.backend.api-naming-and-contract-standard
title: API Naming And Contract Standard
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Backend pointer to API naming and contract rules; defers to docs/14-api-design-and-naming-standards.
tags:
- backend
- api
- contracts
phase: backend-docs
canonical_path: backend/docs/API_NAMING_AND_CONTRACT_STANDARD.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
- platform-engineering
- agents
authority: normative
visibility: internal
linked_symbols: []
language: en
security_classification: internal
doc_version: 1.0.1
updated_at: 2026-08-10
---

# API Naming And Contract Standard

Path: `backend/docs/API_NAMING_AND_CONTRACT_STANDARD.md`

## Purpose

Defines the backend implementation reference for API naming and contracts.

## Required Reference

All backend APIs must follow `docs/14-api-design-and-naming-standards/`.

## Mandatory Rules

- Use `/api/v1` for public API versioning.
- Use lowercase kebab-case plural resource names.
- Use snake_case JSON wire fields.
- Use explicit DTO names such as CreateTaskRequest and CreateTaskResponse.
- Use IDE pagination for list endpoints.
- Use structured public errors.
- Use Idempotency-Key for retryable POST commands.
- Use stable OpenAPI operation ids.
- Add contract examples and contract tests before implementation is considered complete.

## Status

Documentation standard. Implementation lives in services and packages; this file is the backend-local pointer to the normative API docs under `docs/14-…`.

## Related Documents

- [docs/14-api-design-and-naming-standards/00-index.md](../../docs/14-api-design-and-naming-standards/00-index.md)
- [ENGINEERING_STANDARDS.md](./ENGINEERING_STANDARDS.md)

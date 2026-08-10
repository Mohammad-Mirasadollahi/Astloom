---
doc_id: as.doc.backend.module-template
title: Backend Module README Template
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: README template for new backend folders and modules under backend/.
tags:
- backend
- template
- readme
phase: backend-docs
canonical_path: backend/docs/MODULE_TEMPLATE.md
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

# Backend Module README Template

## Purpose

Provide the required README shape when adding a new backend folder so every module records path, ownership, boundary, contracts, and status.

Use this template when adding a new backend folder.

```markdown
# Module Name

Path: `backend/path/to/module`

## Purpose

Explain why this module exists.

## Owner

Name the owning team or role when known.

## Modular Boundary

Define what this module owns and what it must not own.

## Public Interfaces

List APIs, events, SDK methods, config schemas, or adapter contracts exposed by this module. If this module exposes HTTP APIs, state how it follows `backend/docs/API_NAMING_AND_CONTRACT_STANDARD.md`.

## Engineering Standards

State how this module follows `backend/docs/ENGINEERING_STANDARDS.md`, including Dependency Injection, ports/adapters, error handling, validation, transactions, idempotency, configuration, observability, and testing seams.

## Dependencies

Allowed dependencies:

- ...

Forbidden dependencies:

- ...

## Testing

Explain required unit, integration, contract, live, or security tests.

## Operational Notes

Document configuration, observability, health checks, and runbook links.

## Status

Draft, scaffold, active, deprecated, or removed.
```

## Related Documents

- [STRUCTURE_STANDARD.md](./STRUCTURE_STANDARD.md)
- [ENGINEERING_STANDARDS.md](./ENGINEERING_STANDARDS.md)
- [API_NAMING_AND_CONTRACT_STANDARD.md](./API_NAMING_AND_CONTRACT_STANDARD.md)

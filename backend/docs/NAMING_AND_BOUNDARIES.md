---
doc_id: as.doc.backend.naming-and-boundaries
title: Naming And Boundary Rules
doc_type: standard
status: active
schema_version: '1.0'
owner: platform-docs
summary: Naming and modular boundary rules for folders and imports under backend/.
tags:
- backend
- naming
- boundaries
phase: backend-docs
canonical_path: backend/docs/NAMING_AND_BOUNDARIES.md
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

# Naming And Boundary Rules

## Purpose

This document defines naming and boundary rules for `backend/`.

## Folder Naming

- Use lowercase kebab-case.
- Use explicit names that describe ownership.
- Use `-service` for backend services.
- Use provider names only under `integrations/`.
- Use stable test category names under `tests/`.

## Boundary Naming

Every boundary should answer:

- What does this module own?
- Which public contracts does it expose?
- Which modules may call it?
- Which modules may not call it?
- Which data does it own?
- Which configuration controls it?

## Forbidden Names

Avoid:

- common.
- shared without a clear contract.
- misc.
- utils.
- helpers.
- temp.
- old.
- new.
- experiments in production module paths.

Experimental work should live under an explicit experimental path only after approval.

## Dependency Naming

Imports and package names should make direction obvious. Domain code should not import infrastructure packages. Shared packages must not import services.

## Related Documents

- [STRUCTURE_STANDARD.md](./STRUCTURE_STANDARD.md)
- [MODULE_TEMPLATE.md](./MODULE_TEMPLATE.md)

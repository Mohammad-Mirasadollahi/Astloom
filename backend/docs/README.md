---
doc_id: as.doc.backend.docs-readme
title: Backend Documentation
doc_type: readme
status: active
schema_version: '1.0'
owner: platform-docs
summary: Index for backend structure and engineering standards under backend/docs.
tags:
- backend
- documentation
- index
phase: backend-docs
canonical_path: backend/docs/README.md
lifecycle_lane: current
concern_lane: onboarding
audience_lane:
- platform-engineering
- agents
authority: informative
visibility: internal
linked_symbols: []
language: en
security_classification: internal
doc_version: 1.0.1
updated_at: 2026-08-10
---

# Backend Documentation

Path: `backend/docs`

## Purpose

This folder documents the backend structure standard for Astloom. It is the local reference for creating backend folders, modules, services, packages, integrations, tests, tools, deployments, and runbooks.

## Documents

- `STRUCTURE_STANDARD.md` defines the required backend folder standard, service layout, dependency direction, README standard, naming rules, hard-code prevention, and module creation checklist.
- `MODULE_TEMPLATE.md` provides the README template for new backend modules.
- `NAMING_AND_BOUNDARIES.md` defines naming rules, forbidden vague names, and boundary definition requirements.
- `ENGINEERING_STANDARDS.md` defines mandatory backend implementation standards such as Dependency Injection, ports and adapters, validation, errors, transactions, idempotency, configuration, testing seams, and observability.
- `API_NAMING_AND_CONTRACT_STANDARD.md` defines backend API naming and contract rules and points to the full API standards under `docs/14-api-design-and-naming-standards/`.

## Required Rule

Every backend folder must contain a `README.md`. A folder without a README is considered structurally incomplete.

## Implementation Status

Backend services and shared packages now include vertical-slice implementations with canonical tests under `tests/backend/`. Roadmap Phases 1–11 have executable slices and/or verification gates. See the repository root [README.md](../../README.md) for the phase map and named pytest commands.

Scaffold-only language in older module READMEs should be treated as outdated when the module's Status section (or service `src/`) shows an implemented slice.

## Related Documents

- [STRUCTURE_STANDARD.md](./STRUCTURE_STANDARD.md)
- [ENGINEERING_STANDARDS.md](./ENGINEERING_STANDARDS.md)
- [docs/agents/TEAM-HANDOUT-astloom-documentation-complete.md](../../docs/agents/TEAM-HANDOUT-astloom-documentation-complete.md)

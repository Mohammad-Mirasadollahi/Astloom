# Src

Path: `backend/services/adapter-service/src`

## Purpose

Service source root. Parent service: `services/adapter-service`.

## Modular Boundary

This directory is part of the Astloom backend modular architecture. It must expose behavior through documented contracts, public interfaces, configuration, or events. It must not import private internals from sibling modules.

## Allowed Contents

- README and design notes for this boundary.
- Source, configuration, fixtures, tests, or generated artifacts that belong to this boundary.
- Subdirectories that follow the backend structure standard.

## Rules

- Keep ownership clear and local to this boundary.
- Do not hard-code ports, credentials, tenant IDs, project IDs, model names, provider endpoints, or feature behavior.
- Prefer dependency inversion: domain and application logic should not depend on infrastructure implementation details.
- Use shared packages only for stable contracts or cross-cutting primitives.
- Add or update tests and documentation when this boundary receives implementation code.

## Status

The runnable service package lives under `adapter_service/` (not the scaffold folders below). Domain logic is modularized in `adapter_service/core/` (`models`, `tickets`, `connectors`, `broker`, `context`, `helpers`, `service`, …). Scaffold directories (`domain/`, `application/`, `infrastructure/`, `interfaces/`, `contracts/`) remain design placeholders and do not hold the active implementation.

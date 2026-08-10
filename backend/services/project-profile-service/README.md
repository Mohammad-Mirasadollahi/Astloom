# Project Profile Service

Path: `backend/services/project-profile-service`

## Purpose

Owns projects, project groups, domain packs, feature profiles, and Usage Profile activation (including Cursor MCP connection export).

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

Vertical slice implemented, including **Usage Profile** activation and Cursor MCP export. Canonical tests live under `tests/backend/services/project-profile-service/`.

```bash
PYTHONPATH=backend/services/project-profile-service/src:backend/packages \
  .venv/bin/python -m pytest tests/backend/services/project-profile-service -q
```

Usage Profile API: [docs/usage-profile-api.md](docs/usage-profile-api.md)  
Design: `docs/08-software-engineering-architecture/35-usage-profile-and-cursor-mcp-onboarding.md`

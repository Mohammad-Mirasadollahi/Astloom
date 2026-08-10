# Services

Path: `backend/services`

## Purpose

Independently owned backend services.

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

## Local HTTP entrypoints

Each FastAPI service package under `src/<pkg>/` exposes `python -m <pkg>` via `__main__.py` (uvicorn `factory=True` on `api:app`). Port comes from the matching `ASTLOOM_*_PORT` env var; defaults match `backend/configs/port-profiles/astloom-dev.json`.

Example:

```bash
PYTHONPATH=backend/services/core-data-service/src .venv/bin/python -m core_data_service
```

`mcp-gateway-service` remains a stdio MCP process (`python -m mcp_gateway_service`), not an HTTP uvicorn app.

## Status

Vertical slices are implemented for roadmap and platform services. Canonical tests live under `tests/backend/<service>/` or phase verification folders. See the repository root `README.md` for the phase map.

| Service | Role |
|---------|------|
| `core-data-service` | Phase 1 |
| `memory-service` | Phase 2 |
| `docs-sync-service` | Phase 3 |
| `rule-engine-service` | Phase 4 |
| `adapter-service` | Phase 5 |
| `code-graph-service` | Phase 7 |
| `audit-service` | Audit / evidence trails |
| `identity-access-service` | Identity and authorization |
| `orchestration-service` | Work batches and routing |
| `reporting-service` | Impact / KPI reporting |
| `project-profile-service` | Projects, packs, groups |
| `common-context-service` | Reusable common context items |
| `mcp-gateway-service` | MCP stdio gateway for Cursor (Usage Profile tools) |

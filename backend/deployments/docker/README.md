# Docker

Path: `backend/deployments/docker`

## Purpose

Dockerfile and image build boundaries for Astloom application containers.

## Status

MCP gateway application image is implemented (`Dockerfile.mcp-gateway`). Infrastructure (Postgres / Neo4j) remains under `backend/deployments/compose/`.

**Normative operator runbook:** [`docs/08-software-engineering-architecture/43-app-docker-and-wheelhouse-runbook.md`](../../../docs/08-software-engineering-architecture/43-app-docker-and-wheelhouse-runbook.md)

## Quick facts (PATH / mounts / CLI / client boundary)

| Question | Answer |
| --- | --- |
| Who is Dockerized? | **Server only** (Postgres/Neo4j + optional `mcp-gateway`). |
| Are coding-agent clients Dockerized? | **No.** Cursor / remote laptop / `astloom connect` stay on the client machine. |
| Does `docker compose up` put `astloom` on the **server** `PATH`? | **No by itself** — `install.sh` installs the server PATH shim (`~/.local/bin`). |
| Can I use the same `astloom …` operator commands inside the container? | **Partial.** `astloom version` works via `docker exec`; sync/connect orchestration remain **server** host CLI workflows. |
| Is server `.astloom/` state bind-mounted into `mcp-gateway`? | **No.** Source is copied at image build; DB data lives in Compose named volumes. |
| What should clients call? | Server MCP HTTP on port `32500` (`/health`, `/mcp`) via `astloom connect`. |

## Wheelhouse (offline deps)

Host `.venv` packages are exported as wheels to `/opt/astloom-wheelhouse` (override with `ASTLOOM_WHEELHOUSE`):

```bash
bash scripts/build-wheelhouse.sh
```

Images install with `pip install --no-index --find-links=/opt/astloom-wheelhouse` so the container does not hit PyPI at build time.

## Build and run MCP gateway

```bash
# 1) Export wheels from .venv → /opt/astloom-wheelhouse
bash scripts/build-wheelhouse.sh

# 2) Build + start app profile (requires core infra healthy)
docker compose --env-file backend/deployments/compose/.env.local \
  -f backend/deployments/compose/compose.yaml \
  --profile core --profile app up -d --build postgres neo4j mcp-gateway
```

Health: `GET http://127.0.0.1:32500/health`  
MCP: `POST http://127.0.0.1:32500/mcp` with `Authorization: Bearer <ASTLOOM_MCP_HTTP_TOKEN>`

Smoke: `bash tests/e2e/docker/run-app-docker-smoke.sh`

## Image And Venv Policy

Local Python dependency installation on the host must use the project `.venv`. Container images install from the `/opt` wheelhouse into an isolated image environment and must not depend on host global Python packages.

Dockerfiles must not hard-code ports, credentials, tenant ids, project ids, model names, provider endpoints, or feature behavior. Runtime configuration must come from environment profiles, compose profiles, or deployment configuration.

## Modular Boundary

This directory is part of the Astloom backend modular architecture. It must expose behavior through documented contracts, public interfaces, configuration, or events. It must not import private internals from sibling modules.

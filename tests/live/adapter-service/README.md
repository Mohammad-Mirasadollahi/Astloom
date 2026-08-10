# Adapter Service Live Tests

## Purpose

Verify the shipped Adapter Service composition against the main Astloom PostgreSQL infrastructure, plus an optional vendor sandbox.

## Main-Infrastructure Rule

`test_external_ticketing_main_infrastructure.py` imports the production `build_container()` and `build_app()` functions. It must not use `InMemoryStore`, a fake FastAPI application, a test-only database, or a parallel ticket implementation.

The test creates uniquely scoped live-test records in the main `adapter` schema and verifies:

- connector readiness;
- ticket creation and idempotency;
- optimistic concurrency conflict;
- project isolation;
- status synchronization and dispatch evidence;
- process-level store reconstruction and durable retrieval;
- list filtering, retry dispatch, and outbox events.

Apply migrations through `0004_external_ticket_mapping_policy.sql` before running.

Domain implementation for these flows is the modular package `adapter_service.core` (`core/tickets.py`, `core/models.py`, …). Offline unit coverage for ExternalTicket gaps lives in `tests/backend/services/adapter-service/test_external_tickets.py`.

## Opt-in Vendor Sandbox

`test_external_ticketing_vendor_sandbox.py` is skipped unless vendor credentials are present. It exercises remote create dispatch and outbound `:push-status` against one of Jira, Linear, or GitHub Issues.

| Vendor | Env vars |
|---|---|
| Jira | `ASTLOOM_JIRA_BASE_URL`, `ASTLOOM_JIRA_EMAIL`, `ASTLOOM_JIRA_API_TOKEN`, `ASTLOOM_JIRA_PROJECT_KEY` |
| Linear | `ASTLOOM_LINEAR_API_KEY`, `ASTLOOM_LINEAR_TEAM_ID`, and for status push `ASTLOOM_LINEAR_DONE_STATE_ID` |
| GitHub Issues | `ASTLOOM_GITHUB_TOKEN`, `ASTLOOM_GITHUB_OWNER`, `ASTLOOM_GITHUB_REPO` |

Adapters live under `backend/integrations/tickets/`. Registry composition: `adapter_service.trackers.build_tracker_registry`.

## Run

Apply the service migrations to the main PostgreSQL database, then run:

```bash
tests/live/adapter-service/run-main-infrastructure.sh
```

### Process HTTP quality smoke

Small end-to-end check against **restarted** adapter-service and orchestration-service HTTP listeners (not TestClient). Covers ExternalTicket local-adapter quality plus a short AgentTicket claim/start path.

1. Apply migrations through `0004_external_ticket_mapping_policy.sql` (adapter) and `0003_agent_ticket.sql` (orchestration).
2. Restart both services pointed at main PostgreSQL (example ports `:32170` / `:32192`).
3. Run:

```bash
PYTHONPATH=backend/packages:backend/services/adapter-service/src \
  .venv/bin/python tests/live/adapter-service/smoke_ticketing_quality.py
```

Expect `LIVE_SMOKE_PASS`. Verified on 2026-07-31 against `127.0.0.1:32170` and `127.0.0.1:32192`.

Vendor sandbox (optional):

```bash
PYTHONPATH=backend/services/adapter-service/src \
  .venv/bin/python -m pytest tests/live/adapter-service/test_external_ticketing_vendor_sandbox.py -m live -q
```

The main-infrastructure wrapper loads the normal repository environment and points Adapter Service at the same PostgreSQL database used by Astloom. It does not start substitute infrastructure.

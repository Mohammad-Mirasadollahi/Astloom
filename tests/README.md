# Tests

All executable tests live under this directory.

**Authoring law:** write required tests in the same change as production code. Normative playbook: [docs/08-software-engineering-architecture/37-test-authoring-standard.md](../docs/08-software-engineering-architecture/37-test-authoring-standard.md). Fuzz/property-based: [38-fuzzing-and-property-based-testing.md](../docs/08-software-engineering-architecture/38-fuzzing-and-property-based-testing.md). Live vs Unit: [25-live-and-unit-test-strategy.md](../docs/08-software-engineering-architecture/25-live-and-unit-test-strategy.md).

## Layout

```text
tests/
  support/                 Feature-gate harness packages
  backend/
    services/              One suite per backend service
    gates/                 Feature verification gates
    packages/              Shared package loaders
    tools/                 CLI, outbox relay, usage-profile
    platform/              Cross-cutting platform smokes
    legacy/                Archived Change Society suites
  frontend/
  e2e/
  live/
```

Do not add executable tests under service-local source folders such as `backend/services/<service>/tests/`. Keep tests grouped here by owner so local commands and CI discovery stay predictable.

## Backend — services

```bash
PYTHONPATH=backend/services/core-data-service/src .venv/bin/python -m pytest tests/backend/services/core-data-service -q
PYTHONPATH=backend/services/memory-service/src .venv/bin/python -m pytest tests/backend/services/memory-service -q
PYTHONPATH=backend/services/docs-sync-service/src .venv/bin/python -m pytest tests/backend/services/docs-sync-service -q
PYTHONPATH=backend/services/rule-engine-service/src .venv/bin/python -m pytest tests/backend/services/rule-engine-service -q
PYTHONPATH=backend/services/adapter-service/src .venv/bin/python -m pytest tests/backend/services/adapter-service -q
PYTHONPATH=backend/services/code-graph-service/src .venv/bin/python -m pytest tests/backend/services/code-graph-service -q
```

## Backend — feature gates

```bash
PYTHONPATH=tests/support .venv/bin/python -m pytest tests/backend/gates/technical-logic-verification -q
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/gates/port-profile-verification -q
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/gates/governance-catalog-verification -q
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/gates/gap-register-verification -q
PYTHONPATH=tests/support:backend/packages .venv/bin/python -m pytest tests/backend/gates/logical-examples-verification -q
```

## Backend — packages, tools, platform

```bash
PYTHONPATH=backend/packages .venv/bin/python -m pytest tests/backend/packages -q
PYTHONPATH=backend/packages .venv/bin/python -m pytest tests/backend/tools/usage-profile -q
PYTHONPATH=backend/packages .venv/bin/python -m pytest tests/backend/tools/outbox-relay -q
PYTHONPATH=backend/packages .venv/bin/python -m pytest tests/backend/tools/astloom-cli -q
PYTHONPATH=backend/packages .venv/bin/python -m pytest tests/backend/tools/install -q
PYTHONPATH=backend/services .venv/bin/python -m pytest tests/backend/platform -q

# Install E2E smoke (host path; Docker optional)
bash tests/e2e/install/run-install-smoke.sh
SMOKE_SKIP_DOCKER=1 bash tests/e2e/install/run-install-smoke.sh

PYTHONPATH=backend/services/audit-service/src .venv/bin/python -m pytest tests/backend/services/audit-service -q
PYTHONPATH=backend/services/identity-access-service/src .venv/bin/python -m pytest tests/backend/services/identity-access-service -q
PYTHONPATH=backend/services/orchestration-service/src .venv/bin/python -m pytest tests/backend/services/orchestration-service -q
PYTHONPATH=backend/services/reporting-service/src .venv/bin/python -m pytest tests/backend/services/reporting-service -q
PYTHONPATH=backend/services/project-profile-service/src .venv/bin/python -m pytest tests/backend/services/project-profile-service -q
PYTHONPATH=backend/services/common-context-service/src .venv/bin/python -m pytest tests/backend/services/common-context-service -q
```

See also [tests/backend/README.md](backend/README.md) and [docs/06-technical-logic/07-technical-test-strategy.md](../docs/06-technical-logic/07-technical-test-strategy.md).

## Frontend

Frontend tests belong under `tests/frontend/`.

## Legacy Change Society

Archived demo assets live under `archives/hackathon/`. Historical suites live under `tests/backend/legacy/change-society-service/`, `tests/e2e/change-society/`, and `tests/live/change-society/`; they are not the primary Astloom platform path.

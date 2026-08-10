# Install E2E smoke

| Runner | Purpose |
|--------|---------|
| [`run-install-smoke.sh`](run-install-smoke.sh) | Smoke against the current checkout |
| [`run-isolated-install-smoke.sh`](run-isolated-install-smoke.sh) | Temp tree + offset ports + Compose project + auto cleanup |

```bash
# From repository root
bash tests/e2e/install/run-install-smoke.sh
SMOKE_SKIP_DOCKER=1 bash tests/e2e/install/run-install-smoke.sh

bash tests/e2e/install/run-isolated-install-smoke.sh
SMOKE_REQUIRE_DOCKER=1 bash tests/e2e/install/run-isolated-install-smoke.sh
SMOKE_KEEP=1 bash tests/e2e/install/run-isolated-install-smoke.sh

.venv/bin/python -m pytest tests/backend/tools/install/test_install_smoke.py -q
.venv/bin/python -m pytest tests/backend/tools/install/test_install_smoke.py -m live -q
```

Isolated defaults: Postgres `42332`, Neo4j Bolt `42387`, HTTP `42574`, Compose project `astloomiso…`.

Evidence: `tmp/install-smoke/`. Runbook: [`docs/08-software-engineering-architecture/39-local-install-runbook.md`](../../docs/08-software-engineering-architecture/39-local-install-runbook.md).

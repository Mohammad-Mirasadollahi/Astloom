# App Docker E2E smoke

| Runner | Purpose |
|--------|---------|
| [`run-app-docker-smoke.sh`](run-app-docker-smoke.sh) | Wheelhouse → build `mcp-gateway` → Compose up → `/health` + MCP `initialize` |

```bash
# From repository root
bash tests/e2e/docker/run-app-docker-smoke.sh
SKIP_WHEELHOUSE=1 bash tests/e2e/docker/run-app-docker-smoke.sh
```

Requires Docker, `backend/deployments/compose/.env.local`, and (unless skipped) a buildable host `.venv`.

Evidence: `tmp/docker-app-smoke/`.

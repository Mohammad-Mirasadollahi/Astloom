# E2E Graph Probe

Tiny sample used to prove Astloom wiring:

`source files → Neo4j code graph → MCP queries → optional LiteLLM docs`

## Layout

```text
src/auth.py       hash_password, verify_password
src/service.py    login → verify_password, require_login → login
docs/overview.md  human documentation (not parsed as code)
```

## Expected relationships

| Caller | Callee |
|--------|--------|
| `verify_password` | `hash_password` |
| `login` | `verify_password` |
| `require_login` | `login` |

## Run the probe

```bash
set -a && source .env && set +a
PYTHONPATH=backend/services/code-graph-service/src:backend/packages:backend/services/mcp-gateway-service/src:backend/services/core-data-service/src:backend/services/memory-service/src:backend/services/docs-sync-service/src:backend/services/common-context-service/src \
  .venv/bin/python samples/e2e-graph-probe/run_probe.py
```

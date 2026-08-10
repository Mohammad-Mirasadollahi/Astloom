# Live: code-graph-service

## Purpose

Repeatable live probes against a running Astloom stack (Compose Neo4j/Postgres + MCP HTTP).

## Tests

| File | Requires | What it proves |
| --- | --- | --- |
| `test_unused_candidates_mcp_http_live.py` | MCP HTTP up; `.astloom/mcp-http.secret` | Ingests tiny fixture into project `deadcode-live`, then proves scored unused_candidates (orphan `old_helper_orphan`) + `kpi_hints` / triage |
| `test_unwired_shared_package_mcp_http_live.py` | MCP HTTP up; synced `astloom` graph | `adapter_harness` → `unwired_shared_package` / `recommendation=keep_public` / not `safe_to_delete` |

TLS: default URL is `https://127.0.0.1:32500` with verify off for local self-signed certs. Set `ASTLOOM_MCP_HTTP_TLS_VERIFY=1` when using a trusted CA.

## Run

```bash
astloom service restart   # load current code into MCP HTTP
cd /opt/Astloom
.venv/bin/python -m pytest tests/live/code-graph-service/ -m live -v
```

Artifacts:

- `tests/artifacts/code-graph-live/unused-candidates-live.json`
- `tests/artifacts/code-graph-live/unwired-shared-package-live.json`

# Live: mcp-gateway-service

## Purpose

Repeatable MCP HTTP probes against a running Astloom MCP gateway (`:32500`).

## Tests

| File | Requires | What it proves |
| --- | --- | --- |
| `test_cursor_audit_fixes_live.py` | MCP HTTP up; `.astloom/mcp-http.secret`; ThinkingSOC project JSON | Cursor audit P0/P1: memory `pinned` column, graph tools finish under budget (no `-32001` on neighborhood tools), `quality_audit` finishes under budget on sshfs pin (may be `degraded`), `docs_catalog` not `/opt/Astloom`, IDE/`sync` path visibility, search fail-soft, `backup_status` scope |
| `test_mcp_read_tools_matrix_live.py` | Same | Each listed read tool returns without `-32001` and under ~24s on ThinkingSOC scope |

TLS: default URL is `https://127.0.0.1:32500` with verify off for local self-signed certs. Set `ASTLOOM_MCP_HTTP_TLS_VERIFY=1` when using a trusted CA.

## Run

```bash
# load current gateway code
# MCP-only: stop/start MCP HTTP, or:
astloom service restart
cd /opt/Astloom
.venv/bin/python -m pytest tests/live/mcp-gateway-service/ -m live -v
```

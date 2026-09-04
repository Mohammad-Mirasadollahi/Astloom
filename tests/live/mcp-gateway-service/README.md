# Live: mcp-gateway-service

## Purpose

Repeatable MCP HTTP probes against a running Astloom MCP gateway (`:32500`).

## Tests

| File | Requires | What it proves |
| --- | --- | --- |
| `test_cursor_audit_fixes_live.py` | MCP HTTP up; `.astloom/mcp-http.secret`; ThinkingSOC project JSON | Cursor audit P0/P1: memory `pinned` column, graph tools finish or structured `-32001`, `quality_audit` not `/opt/Astloom`, IDE `root_path` permission-aware, search fail-soft, `backup_status` scope |

TLS: default URL is `https://127.0.0.1:32500` with verify off for local self-signed certs. Set `ASTLOOM_MCP_HTTP_TLS_VERIFY=1` when using a trusted CA.

## Run

```bash
# load current gateway code
# MCP-only: stop/start MCP HTTP, or:
astloom service restart
cd /opt/Astloom
.venv/bin/python -m pytest tests/live/mcp-gateway-service/ -m live -v
```

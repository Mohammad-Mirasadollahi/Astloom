# Live: mcp-gateway-service

## Purpose

Repeatable MCP HTTP probes against a running Astloom MCP gateway (`:32500`).

## Tests

| File | Requires | What it proves |
| --- | --- | --- |
| `test_cursor_audit_fixes_live.py` | MCP HTTP up; `.astloom/mcp-http.secret`; Astloom project JSON | Cursor audit P0/P1: memory `pinned` column; graph neighborhood tools under budget; `quality_audit` completes without `-32001` and **`degraded` is not true** on a visible sshfs pin; small-batch `sync` (`max_files=1`) under ~24s; `docs_catalog` not `/opt/Astloom`; IDE path visibility; search fail-soft; `backup_status` scope |
| `test_mcp_read_tools_matrix_live.py` | Same | Listed tools (including `quality_audit` + `sync` `max_files=1`) return without `-32001` and under ~24s on `demo-app` scope when that pin exists |
| `test_mcp_tool_payload_quality_live.py` | Same + `/opt/Astloom` pin | Semantic payload checks on **astloom**: scope, search hits/scores, sync mode, `quality_audit` not degraded + correct repo pin, architecture/detect/neighbors shape, memory write→retrieve |

TLS: default URL is `https://127.0.0.1:32500` with verify off for local self-signed certs. Set `ASTLOOM_MCP_HTTP_TLS_VERIFY=1` when using a trusted CA.

Normative contracts: `docs/07-code-knowledge-graph/83-mcp-tool-budget-and-small-batch-sync.md`.

## Run

```bash
# load current gateway code
# MCP-only: stop/start MCP HTTP, or:
astloom service restart
cd /opt/Astloom
.venv/bin/python -m pytest tests/live/mcp-gateway-service/ -m live -v
```

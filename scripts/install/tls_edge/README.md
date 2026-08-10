# TLS edge (Caddy)

HTTPS termination in front of Astloom MCP and connect APIs. Backends stay on loopback; clients hit one public hostname.

## Quick start

1. **Ensure certs** (auto-generates under `<ASTLOOM_DATA_ROOT>/certs/` when missing):

   ```bash
   export ASTLOOM_DATA_ROOT=/opt/Astloom-data   # or your install data root
   export ASTLOOM_PUBLIC_HOSTNAME=astloom.example.internal
   source scripts/install/tls_edge/ensure_certs.sh
   ```

   Operator-supplied paths win when both exist: `ASTLOOM_TLS_CERT` + `ASTLOOM_TLS_KEY`.

2. **Configure Caddy** — copy [`Caddyfile.example`](./Caddyfile.example), set hostname and cert env vars, start Caddy.

3. **Point clients** at `https://$ASTLOOM_PUBLIC_HOSTNAME` (MCP `/mcp`, connect APIs `/api/…`).

## Routing

| Path | Backend (loopback) |
| --- | --- |
| `/mcp*` | MCP HTTP (`ASTLOOM_MCP_HTTP_PORT`, default `32500`) |
| `/api/*` | Project-profile / connect API (`ASTLOOM_PROJECT_PROFILE_PORT`, default `32194`) |

Run `astloom service start` (or Docker `mcp-gateway`) before the edge so backends are listening.

## Files

| File | Role |
| --- | --- |
| `ensure_certs.sh` | Calls `astloom_cli.tls_certs.ensure_tls_material`; exports cert/key paths |
| `Caddyfile.example` | Example reverse-proxy site block |

Implementation: [`backend/packages/astloom_cli/tls_certs.py`](../../../backend/packages/astloom_cli/tls_certs.py).

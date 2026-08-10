#!/usr/bin/env bash
# MCP gateway container entrypoint — normalize DB hosts for Compose DNS.
set -euo pipefail

# When Compose injects service hostnames, prefer them over host-loopback URLs.
if [[ -n "${ASTLOOM_POSTGRES_HOST:-}" && -n "${ASTLOOM_POSTGRES_PASSWORD:-}" ]]; then
  pg_user="${ASTLOOM_POSTGRES_USER:-astloom}"
  pg_db="${ASTLOOM_POSTGRES_DATABASE:-astloom}"
  pg_host="${ASTLOOM_POSTGRES_HOST}"
  pg_port="${ASTLOOM_POSTGRES_PORT:-5432}"
  export ASTLOOM_DATABASE_URL="postgresql://${pg_user}:${ASTLOOM_POSTGRES_PASSWORD}@${pg_host}:${pg_port}/${pg_db}"
  export ASTLOOM_MCP_STORE_MODE="${ASTLOOM_MCP_STORE_MODE:-postgres}"
fi

if [[ -n "${ASTLOOM_NEO4J_HOST:-}" ]]; then
  neo_user="${ASTLOOM_NEO4J_USER:-neo4j}"
  neo_port="${ASTLOOM_NEO4J_BOLT_PORT:-7687}"
  export ASTLOOM_NEO4J_URI="bolt://${ASTLOOM_NEO4J_HOST}:${neo_port}"
  export ASTLOOM_NEO4J_USER="${neo_user}"
  export ASTLOOM_CODE_GRAPH_STORE="${ASTLOOM_CODE_GRAPH_STORE:-neo4j}"
  export ASTLOOM_MCP_GRAPH_MODE="${ASTLOOM_MCP_GRAPH_MODE:-neo4j}"
fi

# Prefer JWT signing secret from install; shared HTTP token is lab fallback only.
if [[ -z "${ASTLOOM_MCP_TOKEN_SECRET:-}" && -z "${ASTLOOM_MCP_HTTP_TOKEN:-}" ]]; then
  export ASTLOOM_MCP_HTTP_TOKEN="${ASTLOOM_MCP_HTTP_TOKEN:-astloom-docker-dev-token}"
fi

export ASTLOOM_ROOT="${ASTLOOM_ROOT:-/opt/Astloom}"
export ASTLOOM_MCP_HTTP_HOST="${ASTLOOM_MCP_HTTP_HOST:-0.0.0.0}"
export ASTLOOM_MCP_HTTP_PORT="${ASTLOOM_MCP_HTTP_PORT:-32500}"

# Default HTTPS when data-root certs are mounted at /certs (compose).
if [[ -z "${ASTLOOM_MCP_TLS_CERTFILE:-}" && -f /certs/server.pem ]]; then
  export ASTLOOM_MCP_TLS_CERTFILE=/certs/server.pem
fi
if [[ -z "${ASTLOOM_MCP_TLS_KEYFILE:-}" && -f /certs/server.key ]]; then
  export ASTLOOM_MCP_TLS_KEYFILE=/certs/server.key
fi
if [[ -n "${ASTLOOM_MCP_TLS_CERTFILE:-}" && -n "${ASTLOOM_MCP_TLS_KEYFILE:-}" ]]; then
  if [[ -z "${ASTLOOM_MCP_HTTP_PUBLIC_URL:-}" ]]; then
    export ASTLOOM_MCP_HTTP_PUBLIC_URL="https://127.0.0.1:${ASTLOOM_MCP_HTTP_PORT}"
  elif [[ "${ASTLOOM_MCP_HTTP_PUBLIC_URL}" == http://* ]]; then
    export ASTLOOM_MCP_HTTP_PUBLIC_URL="https://${ASTLOOM_MCP_HTTP_PUBLIC_URL#http://}"
  fi
fi

exec "$@"

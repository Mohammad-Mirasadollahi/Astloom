#!/usr/bin/env bash
# Smoke: wheelhouse → build mcp-gateway image → Compose up → /health + MCP initialize.
#
# Prerequisites: Docker, Compose v2, existing or buildable /opt/astloom-wheelhouse,
#                backend/deployments/compose/.env.local (install.sh stage 03).
#
# Usage (repo root):
#   bash tests/e2e/docker/run-app-docker-smoke.sh
#   SKIP_WHEELHOUSE=1 bash tests/e2e/docker/run-app-docker-smoke.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT}"

WHEELHOUSE="${ASTLOOM_WHEELHOUSE:-/opt/astloom-wheelhouse}"
COMPOSE_ENV="${ROOT}/backend/deployments/compose/.env.local"
COMPOSE_FILE="${ROOT}/backend/deployments/compose/compose.yaml"
EVIDENCE_DIR="${ROOT}/tmp/docker-app-smoke"
EVIDENCE_LOG="${EVIDENCE_DIR}/evidence-$(date +%Y%m%d%H%M%S).log"
TOKEN="${ASTLOOM_MCP_HTTP_TOKEN:-astloom-docker-dev-token}"
PORT="${ASTLOOM_MCP_HTTP_PORT:-32500}"
SKIP_WHEELHOUSE="${SKIP_WHEELHOUSE:-0}"

mkdir -p "${EVIDENCE_DIR}"

log() { printf '[docker-app-smoke] %s\n' "$*" | tee -a "${EVIDENCE_LOG}"; }
ok() { log "OK  $*"; }
fail() { log "FAIL $*"; exit 1; }

require_file() { [[ -f "$1" ]] || fail "missing file: $1"; }

banner() {
  log "================================================================"
  log "$*"
  log "================================================================"
}

compose() {
  docker compose --env-file "${COMPOSE_ENV}" -f "${COMPOSE_FILE}" "$@"
}

banner "Astloom app Docker smoke"
log "root=${ROOT}"
log "wheelhouse=${WHEELHOUSE}"
log "evidence=${EVIDENCE_LOG}"

require_file "${COMPOSE_ENV}"
require_file "${COMPOSE_FILE}"
require_file "${ROOT}/backend/deployments/docker/Dockerfile.mcp-gateway"
require_file "${ROOT}/scripts/build-wheelhouse.sh"

command -v docker >/dev/null 2>&1 || fail "docker not found"
docker info >/dev/null 2>&1 || fail "docker daemon not reachable"
docker compose version >/dev/null 2>&1 || fail "docker compose plugin missing"

if [[ "${SKIP_WHEELHOUSE}" != "1" ]]; then
  banner "1/4 Wheelhouse from .venv → ${WHEELHOUSE}"
  if ! ASTLOOM_WHEELHOUSE="${WHEELHOUSE}" bash "${ROOT}/scripts/build-wheelhouse.sh" >>"${EVIDENCE_LOG}" 2>&1; then
    fail "wheelhouse build (see ${EVIDENCE_LOG})"
  fi
  ok "wheelhouse"
else
  banner "1/4 Wheelhouse skipped (SKIP_WHEELHOUSE=1)"
  [[ -d "${WHEELHOUSE}" ]] || fail "wheelhouse missing: ${WHEELHOUSE}"
  ok "using existing wheelhouse"
fi

whl_count="$(find "${WHEELHOUSE}" -maxdepth 1 -name '*.whl' 2>/dev/null | wc -l | tr -d ' ')"
[[ "${whl_count}" -gt 0 ]] || fail "no .whl files in ${WHEELHOUSE}"
ok "${whl_count} wheels present"

banner "2/4 Compose core + app (build mcp-gateway)"
# Host ``astloom service start`` also binds MCP HTTP; free the port for the container.
if command -v ss >/dev/null 2>&1 && ss -lptn "sport = :${PORT}" 2>/dev/null | grep -q LISTEN; then
  log "port ${PORT} busy on host; stopping host MCP HTTP if managed by Astloom"
  if [[ -x "${ROOT}/.venv/bin/python" ]]; then
    ROOT="${ROOT}" "${ROOT}/.venv/bin/python" - <<'PY' >>"${EVIDENCE_LOG}" 2>&1 || true
import os
from pathlib import Path
from astloom_cli.service_runtime.mcp import stop_mcp_http
stop_mcp_http(Path(os.environ["ROOT"]))
PY
  fi
fi
if ! ASTLOOM_WHEELHOUSE="${WHEELHOUSE}" ASTLOOM_MCP_HTTP_TOKEN="${TOKEN}" \
  compose --profile core --profile app up -d --build postgres neo4j mcp-gateway \
  >>"${EVIDENCE_LOG}" 2>&1; then
  fail "compose up --build (see ${EVIDENCE_LOG})"
fi
ok "compose up"

banner "3/4 Wait for mcp-gateway health"
healthy=0
for _ in $(seq 1 60); do
  status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' astloom-mcp-gateway-1 2>/dev/null || true)"
  if [[ "${status}" == "healthy" ]]; then
    healthy=1
    break
  fi
  if [[ "${status}" == "exited" || "${status}" == "dead" ]]; then
    docker logs astloom-mcp-gateway-1 >>"${EVIDENCE_LOG}" 2>&1 || true
    fail "mcp-gateway container ${status}"
  fi
  sleep 2
done
[[ "${healthy}" -eq 1 ]] || fail "mcp-gateway not healthy within timeout"
ok "mcp-gateway healthy"

banner "4/4 HTTP probes"
health_code="$(curl -s -o /tmp/ac-health.json -w '%{http_code}' "http://127.0.0.1:${PORT}/health" || true)"
[[ "${health_code}" == "200" ]] || fail "/health returned ${health_code}"
ok "/health 200"

init_code="$(curl -s -o /tmp/ac-mcp-init.json -w '%{http_code}' \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: docker-smoke" \
  -H "X-Workspace-Id: docker-smoke" \
  -H "X-Project-Id: docker-smoke" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  "http://127.0.0.1:${PORT}/mcp" || true)"
[[ "${init_code}" == "200" ]] || {
  cat /tmp/ac-mcp-init.json >>"${EVIDENCE_LOG}" 2>/dev/null || true
  fail "MCP initialize returned ${init_code}"
}
ok "MCP initialize 200"

banner "SMOKE PASSED"
log "evidence: ${EVIDENCE_LOG}"
echo "OK: Astloom app Docker smoke passed"
echo "Evidence: ${EVIDENCE_LOG}"

#!/usr/bin/env bash
# Astloom modular install smoke test.
#
# Exercises root install.sh end-to-end so a beginner install path is proven,
# not only unit-checked. Safe to re-run (idempotent).
#
# Usage (from repository root):
#   bash tests/e2e/install/run-install-smoke.sh
#   SMOKE_REQUIRE_DOCKER=1 bash tests/e2e/install/run-install-smoke.sh
#   SMOKE_SKIP_DOCKER=1 bash tests/e2e/install/run-install-smoke.sh
#
# Exit codes:
#   0  smoke passed (docker sections skipped only when allowed)
#   1  smoke failed
#   2  docker required but unavailable
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT}"

SMOKE_SKIP_DOCKER="${SMOKE_SKIP_DOCKER:-0}"
SMOKE_REQUIRE_DOCKER="${SMOKE_REQUIRE_DOCKER:-0}"
SMOKE_COMPOSE_TIMEOUT="${SMOKE_COMPOSE_TIMEOUT:-180}"
EVIDENCE_DIR="${ROOT}/tmp/install-smoke"
EVIDENCE_LOG="${EVIDENCE_DIR}/evidence-$(date +%Y%m%d%H%M%S).log"
INSTALL_SH="${ROOT}/install.sh"
CLI="${ROOT}/.venv/bin/astloom"

mkdir -p "${EVIDENCE_DIR}"

log() { printf '[install-smoke] %s\n' "$*" | tee -a "${EVIDENCE_LOG}"; }
ok() { log "OK  $*"; }
fail() { log "FAIL $*"; exit 1; }

run_capture() {
  local label="$1"
  shift
  log "→ ${label}: $*"
  if "$@" >>"${EVIDENCE_LOG}" 2>&1; then
    ok "${label}"
  else
    fail "${label} (see ${EVIDENCE_LOG})"
  fi
}

docker_ready() {
  command -v docker >/dev/null 2>&1 \
    && docker info >/dev/null 2>&1 \
    && docker compose version >/dev/null 2>&1
}

require_file() {
  [[ -f "$1" ]] || fail "missing file: $1"
}

require_exec() {
  [[ -x "$1" ]] || fail "missing executable: $1"
}

banner() {
  log "================================================================"
  log "$*"
  log "================================================================"
}

banner "Astloom install smoke"
log "root=${ROOT}"
log "evidence=${EVIDENCE_LOG}"
log "SMOKE_SKIP_DOCKER=${SMOKE_SKIP_DOCKER} SMOKE_REQUIRE_DOCKER=${SMOKE_REQUIRE_DOCKER}"

require_file "${INSTALL_SH}"
require_file "${ROOT}/scripts/install/load.sh"
require_file "${ROOT}/docs/08-software-engineering-architecture/39-local-install-runbook.md"

# --- 1) CLI surface ---------------------------------------------------------
banner "1/6 Help and stage list"
run_capture "install --help" bash "${INSTALL_SH}" --help
run_capture "install --list-stages" bash "${INSTALL_SH}" --list-stages
if ! grep -q "01_prerequisites" "${EVIDENCE_LOG}"; then
  fail "list-stages missing 01_prerequisites"
fi
if ! grep -q "05_verify" "${EVIDENCE_LOG}"; then
  fail "list-stages missing 05_verify"
fi
if ! grep -q "06_runtime_bringup" "${EVIDENCE_LOG}"; then
  fail "list-stages missing 06_runtime_bringup"
fi

# --- 2) Host path (no Docker) -----------------------------------------------
banner "2/6 Host install path (--skip-infra)"
run_capture "install --skip-infra" \
  bash "${INSTALL_SH}" --non-interactive --role server --runtime host --skip-infra --skip-prerequisites
run_capture "install --check --skip-infra" \
  bash "${INSTALL_SH}" --non-interactive --role server --runtime host --check --skip-infra

require_exec "${ROOT}/.venv/bin/python"
require_exec "${CLI}"

# --- 3) CLI smoke after install ---------------------------------------------
banner "3/6 astloom CLI after install"
run_capture "astloom doctor" "${CLI}" doctor
run_capture "astloom version" "${CLI}" version
run_capture "astloom profile list" "${CLI}" profile list
run_capture "astloom ports show" "${CLI}" ports show

# Core imports (same bar as ensure-venv)
run_capture "venv imports" "${ROOT}/.venv/bin/python" -c \
  "import fastapi,httpx,pytest,psycopg,astloom_cli,usage_profile; print('imports ok')"

# --- 4) Per-stage dispatch --------------------------------------------------
banner "4/6 Single-stage dispatch"
run_capture "stage 01 (check-ish via skip-prereqs)" \
  bash "${INSTALL_SH}" --non-interactive --role server --runtime host --stage 01_prerequisites --skip-prerequisites --skip-infra
run_capture "stage 02_venv" \
  bash "${INSTALL_SH}" --non-interactive --role server --runtime host --stage 02_venv
run_capture "stage 05_verify --skip-infra" \
  bash "${INSTALL_SH}" --non-interactive --role server --runtime host --stage 05_verify --skip-infra

# --- 5) Compose env (no containers) -----------------------------------------
banner "5/6 Compose env generation (stage 03)"
run_capture "stage 03_compose_env" \
  bash "${INSTALL_SH}" --non-interactive --role server --runtime host --stage 03_compose_env
ENV_FILE="${ROOT}/backend/deployments/compose/.env.local"
require_file "${ENV_FILE}"
if grep -q "replace-with-a-local-secret" "${ENV_FILE}"; then
  fail "compose env still has placeholder secrets"
fi
ok "compose env has non-placeholder secrets (values not logged)"

# --- 6) Docker infra (optional / required) ----------------------------------
banner "6/6 Docker infrastructure"
if [[ "${SMOKE_SKIP_DOCKER}" == "1" ]]; then
  log "SKIP docker section (SMOKE_SKIP_DOCKER=1)"
elif docker_ready; then
  run_capture "full install.sh" \
    bash "${INSTALL_SH}" --non-interactive --role server --runtime host --skip-prerequisites --compose-timeout "${SMOKE_COMPOSE_TIMEOUT}"
  run_capture "install --check" \
    bash "${INSTALL_SH}" --non-interactive --role server --runtime host --check --compose-timeout "${SMOKE_COMPOSE_TIMEOUT}"

  # Direct health evidence
  if [[ -x "${ROOT}/backend/deployments/compose/wait-healthy.sh" ]]; then
    PG_ID="$(docker compose --env-file "${ENV_FILE}" \
      -f "${ROOT}/backend/deployments/compose/compose.yaml" ps -q postgres 2>/dev/null | head -1 || true)"
    NEO_ID="$(docker compose --env-file "${ENV_FILE}" \
      -f "${ROOT}/backend/deployments/compose/compose.yaml" ps -q neo4j 2>/dev/null | head -1 || true)"
    PG_NAME="astloom-postgres-1"
    NEO_NAME="astloom-neo4j-1"
    if [[ -n "${PG_ID}" ]]; then
      PG_NAME="$(docker inspect --format '{{.Name}}' "${PG_ID}" | sed 's#^/##')"
    fi
    if [[ -n "${NEO_ID}" ]]; then
      NEO_NAME="$(docker inspect --format '{{.Name}}' "${NEO_ID}" | sed 's#^/##')"
    fi
    run_capture "wait-healthy" \
      bash "${ROOT}/backend/deployments/compose/wait-healthy.sh" \
      --timeout 30 "${PG_NAME}" "${NEO_NAME}"
  fi
  ok "docker infra smoke passed"
else
  log "WARN docker daemon not reachable on this host"
  if [[ "${SMOKE_REQUIRE_DOCKER}" == "1" ]]; then
    log "FAIL docker required (SMOKE_REQUIRE_DOCKER=1)"
    exit 2
  fi
  log "SKIP docker section (set SMOKE_REQUIRE_DOCKER=1 to fail here)"
fi

banner "SMOKE PASSED"
log "evidence: ${EVIDENCE_LOG}"
echo
echo "OK: Astloom install smoke passed"
echo "Evidence: ${EVIDENCE_LOG}"

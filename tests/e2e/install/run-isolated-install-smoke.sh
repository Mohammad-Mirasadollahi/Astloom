#!/usr/bin/env bash
# Isolated Astloom install smoke in a temp tree with non-colliding ports.
#
# - Copies the repo into tmp/iso-install-<id>/tree (excludes .venv/.git/tmp/…)
# - Uses offset Compose ports so it will not clash with a live Astloom stack
# - Runs modular install.sh inside the copy
# - Starts Compose Postgres+Neo4j when Docker is reachable
# - Always tears down containers, volumes, and the temp tree on exit
#
# Usage (repo root):
#   bash tests/e2e/install/run-isolated-install-smoke.sh
#   SMOKE_KEEP=1 bash tests/e2e/install/run-isolated-install-smoke.sh
#   SMOKE_REQUIRE_DOCKER=1 bash tests/e2e/install/run-isolated-install-smoke.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
STAMP="$(date +%Y%m%d%H%M%S)-$$"
ISO_BASE="${ISO_BASE:-${REPO_ROOT}/tmp/iso-install-${STAMP}}"
ISO_TREE="${ISO_BASE}/tree"
EVIDENCE="${ISO_BASE}/evidence.log"
COMPOSE_PROJECT="astloomiso${STAMP//[^a-zA-Z0-9]/}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:0:20}"

# Non-colliding ports (defaults are 32232 / 32287 / 32474)
ISO_PG_PORT="${ISO_PG_PORT:-42332}"
ISO_NEO4J_BOLT_PORT="${ISO_NEO4J_BOLT_PORT:-42387}"
ISO_NEO4J_HTTP_PORT="${ISO_NEO4J_HTTP_PORT:-42574}"

SMOKE_KEEP="${SMOKE_KEEP:-0}"
SMOKE_REQUIRE_DOCKER="${SMOKE_REQUIRE_DOCKER:-0}"
SMOKE_COMPOSE_TIMEOUT="${SMOKE_COMPOSE_TIMEOUT:-300}"

mkdir -p "${ISO_BASE}"
: >"${EVIDENCE}"

log() { printf '[iso-install-smoke] %s\n' "$*" | tee -a "${EVIDENCE}"; }
ok() { log "OK  $*"; }
fail() { log "FAIL $*"; exit 1; }

docker_ready() {
  command -v docker >/dev/null 2>&1 \
    && docker info >/dev/null 2>&1 \
    && docker compose version >/dev/null 2>&1
}

cleanup() {
  local rc=$?
  set +e
  log "cleanup begin (exit=${rc})"
  if [[ -d "${ISO_TREE}" ]] && docker_ready; then
    local envf="${ISO_TREE}/backend/deployments/compose/.env.local"
    local cf="${ISO_TREE}/backend/deployments/compose/compose.yaml"
    if [[ -f "${envf}" && -f "${cf}" ]]; then
      log "compose down -v project=${COMPOSE_PROJECT}"
      docker compose -p "${COMPOSE_PROJECT}" --env-file "${envf}" -f "${cf}" \
        --profile core down -v --remove-orphans >>"${EVIDENCE}" 2>&1 || true
    fi
  fi
  mkdir -p "${REPO_ROOT}/tmp/install-smoke"
  if [[ -f "${EVIDENCE}" ]]; then
    cp -f "${EVIDENCE}" "${REPO_ROOT}/tmp/install-smoke/iso-last-evidence.log" 2>/dev/null || true
  fi
  if [[ "${SMOKE_KEEP}" == "1" ]]; then
    printf '[iso-install-smoke] SMOKE_KEEP=1 — leaving %s\n' "${ISO_BASE}"
  else
    printf '[iso-install-smoke] removing %s\n' "${ISO_BASE}"
    rm -rf "${ISO_BASE}"
  fi
  printf '[iso-install-smoke] cleanup done\n'
  exit "${rc}"
}
trap cleanup EXIT

banner() {
  log "================================================================"
  log "$*"
  log "================================================================"
}

run_capture() {
  local label="$1"
  shift
  log "→ ${label}: $*"
  if "$@" >>"${EVIDENCE}" 2>&1; then
    ok "${label}"
  else
    fail "${label} (see ${EVIDENCE})"
  fi
}

banner "Isolated install smoke"
log "repo=${REPO_ROOT}"
log "iso_tree=${ISO_TREE}"
log "compose_project=${COMPOSE_PROJECT}"
log "ports postgres=${ISO_PG_PORT} neo4j_bolt=${ISO_NEO4J_BOLT_PORT} neo4j_http=${ISO_NEO4J_HTTP_PORT}"

banner "1/5 Copy isolated tree"
mkdir -p "${ISO_TREE}"
rsync -a \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude 'tmp/' \
  --exclude 'node_modules/' \
  --exclude '.smoke-temp/' \
  --exclude 'ai-toolstack/data/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude 'archives/' \
  "${REPO_ROOT}/" "${ISO_TREE}/"
ok "rsync complete"

banner "2/5 Host install inside isolated tree (--skip-infra first)"
chmod +x "${ISO_TREE}/install.sh"
# Keep PATH/symlink side effects inside the isolated tree (do not touch host HOME).
ISO_HOME="${ISO_BASE}/home"
mkdir -p "${ISO_HOME}/.local/bin"
export HOME="${ISO_HOME}"
export PATH="${ISO_HOME}/.local/bin:${ISO_TREE}/.ac-venv/bin:${PATH}"
# Avoid Cursor sandbox RO bind mounts on paths literally named ".venv".
export ASTLOOM_VENV_DIR=".ac-venv"
run_capture "iso install --skip-infra" \
  bash "${ISO_TREE}/install.sh" --non-interactive --runtime host --skip-infra --skip-prerequisites
run_capture "iso install --check --skip-infra" \
  bash "${ISO_TREE}/install.sh" --non-interactive --runtime host --check --skip-infra
run_capture "iso astloom doctor" \
  env ASTLOOM_VENV_DIR=".ac-venv" "${ISO_TREE}/.ac-venv/bin/astloom" doctor
banner "3/5 Compose env with offset ports"
# Force a fresh env file with isolated ports/secrets (do not reuse host .env.local).
ENV_FILE="${ISO_TREE}/backend/deployments/compose/.env.local"
EXAMPLE="${ISO_TREE}/backend/deployments/compose/neo4j.example.env"
[[ -f "${EXAMPLE}" ]] || fail "missing ${EXAMPLE}"
PG_SECRET="$(openssl rand -hex 16)"
NEO_SECRET="$(openssl rand -hex 16)"
cp "${EXAMPLE}" "${ENV_FILE}"
chmod 600 "${ENV_FILE}"
sed -i \
  -e "s|^ASTLOOM_POSTGRES_PASSWORD=.*|ASTLOOM_POSTGRES_PASSWORD=${PG_SECRET}|" \
  -e "s|^ASTLOOM_NEO4J_PASSWORD=.*|ASTLOOM_NEO4J_PASSWORD=${NEO_SECRET}|" \
  -e "s|^ASTLOOM_POSTGRES_PORT=.*|ASTLOOM_POSTGRES_PORT=${ISO_PG_PORT}|" \
  -e "s|^ASTLOOM_NEO4J_BOLT_PORT=.*|ASTLOOM_NEO4J_BOLT_PORT=${ISO_NEO4J_BOLT_PORT}|" \
  -e "s|^ASTLOOM_NEO4J_HTTP_PORT=.*|ASTLOOM_NEO4J_HTTP_PORT=${ISO_NEO4J_HTTP_PORT}|" \
  "${ENV_FILE}"
ok "wrote isolated compose env (secrets not logged)"
grep -E '^(ASTLOOM_POSTGRES_PORT|ASTLOOM_NEO4J_BOLT_PORT|ASTLOOM_NEO4J_HTTP_PORT)=' "${ENV_FILE}" \
  | tee -a "${EVIDENCE}"

banner "4/5 Docker Compose infra (isolated project + ports)"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT}"
if ! docker_ready; then
  log "WARN Docker API not reachable from this environment"
  if [[ "${SMOKE_REQUIRE_DOCKER}" == "1" ]]; then
    fail "Docker required (SMOKE_REQUIRE_DOCKER=1) but daemon/API unavailable"
  fi
  log "SKIP docker infra — host/venv path already verified in isolation"
else
  COMPOSE=(docker compose -p "${COMPOSE_PROJECT}" --env-file "${ENV_FILE}"
    -f "${ISO_TREE}/backend/deployments/compose/compose.yaml")
  run_capture "compose pull" "${COMPOSE[@]}" --profile core pull postgres neo4j
  run_capture "compose up" "${COMPOSE[@]}" --profile core up -d postgres neo4j

  PG_ID="$("${COMPOSE[@]}" ps -q postgres | head -1 || true)"
  NEO_ID="$("${COMPOSE[@]}" ps -q neo4j | head -1 || true)"
  [[ -n "${PG_ID}" && -n "${NEO_ID}" ]] || fail "compose did not start postgres/neo4j"
  PG_NAME="$(docker inspect --format '{{.Name}}' "${PG_ID}" | sed 's#^/##')"
  NEO_NAME="$(docker inspect --format '{{.Name}}' "${NEO_ID}" | sed 's#^/##')"
  run_capture "wait-healthy" \
    bash "${ISO_TREE}/backend/deployments/compose/wait-healthy.sh" \
    --timeout "${SMOKE_COMPOSE_TIMEOUT}" "${PG_NAME}" "${NEO_NAME}"

  # TCP proof on isolated ports
  run_capture "tcp postgres :${ISO_PG_PORT}" \
    bash -c "exec 3<>/dev/tcp/127.0.0.1/${ISO_PG_PORT}"
  run_capture "tcp neo4j bolt :${ISO_NEO4J_BOLT_PORT}" \
    bash -c "exec 3<>/dev/tcp/127.0.0.1/${ISO_NEO4J_BOLT_PORT}"

  # install.sh compose helpers honor COMPOSE_PROJECT_NAME
  run_capture "iso install --check (with infra)" \
    env COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT}" \
    bash "${ISO_TREE}/install.sh" --non-interactive --runtime host --check --skip-prerequisites --compose-timeout 60
  ok "docker infra smoke on isolated ports passed"
fi

banner "5/5 Done (cleanup via trap)"
log "ISO_INSTALL_SMOKE_PASSED"
echo
echo "OK: isolated install smoke finished"
echo "Evidence (until cleanup): ${EVIDENCE}"

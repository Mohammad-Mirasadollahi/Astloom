#!/usr/bin/env bash
# Full local install + release-candidate smoke (100% gates, no Qwen Cloud calls).
# Isolated copy under .smoke-temp/ by default; tears down systemd/docker/postgres at end.
#
# Usage (from repository root):
#   bash tests/e2e/change-society/run-full-install-smoke.sh
#   SMOKE_KEEP=1 bash tests/e2e/change-society/run-full-install-smoke.sh
#   SMOKE_SKIP_DOCKER=1 bash tests/e2e/change-society/run-full-install-smoke.sh
#   SMOKE_SKIP_SYSTEMD=1 bash tests/e2e/change-society/run-full-install-smoke.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SMOKE_BASE="${SMOKE_INSTALL_ROOT:-$ROOT/.smoke-temp/full-$(date +%Y%m%d%H%M%S)}"
SMOKE_KEEP="${SMOKE_KEEP:-0}"
SMOKE_SKIP_DOCKER="${SMOKE_SKIP_DOCKER:-0}"
SMOKE_SKIP_SYSTEMD="${SMOKE_SKIP_SYSTEMD:-0}"
COMPOSE_SMOKE="archives/hackathon/deployments/compose.smoke.yaml"
DEV_PG_COMPOSE="archives/hackathon/deployments/compose.dev-postgres.yaml"
PROJECT_NAME_SMOKE="change-society-smoke"
PROJECT_NAME_DEVPG="change-society-dev-postgres"

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  source "$NVM_DIR/nvm.sh"
fi

log() { printf '\n=== %s ===\n' "$*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

rsync_tree() {
  local dest="$1"
  /bin/rm -rf "$dest"
  mkdir -p "$dest"
  rsync -a \
    --exclude '.venv' \
    --exclude 'node_modules' \
    --exclude 'archives/hackathon/frontend/node_modules' \
    --exclude 'archives/hackathon/frontend/.next' \
    --exclude 'archives/hackathon/.env' \
    --exclude '.git' \
    --exclude '.smoke-temp' \
    --exclude 'ai-toolstack/data' \
    --exclude '__pycache__' \
    "$ROOT/" "$dest/"
}

set_env_kv() {
  local env_file="$1" key="$2" value="$3"
  if grep -q "^${key}=" "$env_file" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
  else
    printf '\n%s=%s\n' "$key" "$value" >>"$env_file"
  fi
}

ensure_docker_install_env() {
  local tree="$1"
  local env_file="$tree/archives/hackathon/.env"
  [[ -f "$env_file" ]] || fail "missing $env_file"
  set_env_kv "$env_file" ASTLOOM_POSTGRES_PASSWORD "smoke-local-password"
  set_env_kv "$env_file" QWEN_API_KEY "smoke-local-not-used"
}

docker_ok() {
  command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
  else
    return 1
  fi
}

wait_http() {
  local url="$1" tries="${2:-60}"
  local i=1
  while (( i <= tries )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
    (( i++ )) || true
  done
  return 1
}

teardown_systemd_units() {
  if ! command -v systemctl >/dev/null 2>&1; then
    return 0
  fi
  systemctl --user disable --now change-society-api.service change-society-web.service 2>/dev/null || true
  /bin/rm -f "$HOME/.config/systemd/user/change-society-api.service" \
    "$HOME/.config/systemd/user/change-society-web.service"
  systemctl --user daemon-reload 2>/dev/null || true
}

teardown_docker_stack() {
  local tree="$1" compose_rel="$2" project="$3"
  docker_ok || return 0
  local cc
  cc="$(compose_cmd)" || return 0
  local env_args=()
  if [[ -f "$tree/archives/hackathon/.env" ]]; then
    env_args=(--env-file "$tree/archives/hackathon/.env")
  fi
  # shellcheck disable=SC2086
  $cc "${env_args[@]}" -f "$tree/$compose_rel" -p "$project" down -v --remove-orphans 2>/dev/null || true
}

interactive_install() {
  local tree="$1"
  shift
  local inputs="$1"
  cd "$tree"
  printf '%s\n' "$inputs" | script -qefc 'bash archives/hackathon/install.sh' /dev/null
}

run_release_gates() {
  local tree="$1"
  cd "$tree"
  export PYTHONPATH="archives/hackathon/backend/change-society-service/src:archives/hackathon/sdk/python"

  log "Gate: backend pytest"
  .venv/bin/python -m pytest tests/backend/legacy/change-society-service -q

  log "Gate: production config rejects fake model"
  if CHANGE_SOCIETY_ENVIRONMENT=production \
    CHANGE_SOCIETY_MODEL_PROVIDER=fake \
    CHANGE_SOCIETY_STORE=memory \
    .venv/bin/python -c "
from change_society.bootstrap.config import Settings
try:
    Settings.load()
except ValueError:
    pass
else:
    raise SystemExit('expected ValueError for production+fake')
"; then
    :
  else
    fail "production+fake guard"
  fi

  log "Gate: frontend typecheck"
  (cd archives/hackathon/frontend && npm run typecheck)

  log "Gate: frontend production build"
  (cd archives/hackathon/frontend && npm run build)

  log "Gate: frontend unit tests"
  bash "$ROOT/tests/frontend/change-society/run-frontend-tests.sh"

  log "Gate: deterministic real-test suite"
  bash "$ROOT/tests/e2e/change-society/run-deterministic-regression.sh"
}

log "Sync isolated tree -> $SMOKE_BASE"
rsync_tree "$SMOKE_BASE"

log "Interactive menu: production profile (hints only)"
interactive_install "$SMOKE_BASE" "3"

log "Interactive menu: verify + manual + no apt + no optional postgres"
interactive_install "$SMOKE_BASE" $'2\nn\n1\nn'

run_release_gates "$SMOKE_BASE"

ensure_docker_install_env "$SMOKE_BASE"

log "Install dry-run matrix (all profiles/runtimes)"
cd "$SMOKE_BASE"
export CHANGE_SOCIETY_COMPOSE_FILE="$COMPOSE_SMOKE"
for profile in demo verify production; do
  for runtime in manual systemd docker none; do
    python3 archives/hackathon/scripts/install.py --dry-run --non-interactive --profile "$profile" --runtime "$runtime"
  done
done
unset CHANGE_SOCIETY_COMPOSE_FILE

log "Install dry-run: demo + skip-frontend + with-postgres flags"
python3 archives/hackathon/scripts/install.py --dry-run --non-interactive --profile demo --runtime none --skip-frontend --with-postgres

if [[ "$SMOKE_SKIP_DOCKER" != "1" ]] && docker_ok; then
  log "Optional dev PostgreSQL (--with-postgres path)"
  cd "$SMOKE_BASE"
  bash archives/hackathon/install.sh --non-interactive --profile demo --runtime none --with-postgres
  cc="$(compose_cmd)"
  # shellcheck disable=SC2086
  $cc -f "$DEV_PG_COMPOSE" -p "$PROJECT_NAME_DEVPG" ps | grep -q postgres || fail "dev postgres not running"
  teardown_docker_stack "$SMOKE_BASE" "$DEV_PG_COMPOSE" "$PROJECT_NAME_DEVPG"

  log "Docker runtime via install.sh (compose.smoke.yaml, fake model + PostgreSQL)"
  ensure_docker_install_env "$SMOKE_BASE"
  set -a
  # shellcheck disable=SC1090
  source "$SMOKE_BASE/archives/hackathon/.env"
  set +a
  export CHANGE_SOCIETY_COMPOSE_FILE="$COMPOSE_SMOKE"
  cd "$SMOKE_BASE"
  bash archives/hackathon/install.sh --non-interactive --profile demo --runtime docker
  wait_http "http://127.0.0.1:32500/health" 90 || fail "docker api /health"
  curl -fsS "http://127.0.0.1:32500/ready" >/dev/null
  curl -fsS "http://127.0.0.1:3000/" >/dev/null || true
  teardown_docker_stack "$SMOKE_BASE" "$COMPOSE_SMOKE" "$PROJECT_NAME_SMOKE"
  unset CHANGE_SOCIETY_COMPOSE_FILE
else
  log "Skipping Docker gates (SMOKE_SKIP_DOCKER=1 or docker unavailable)"
fi

if [[ "$SMOKE_SKIP_SYSTEMD" != "1" ]] && command -v systemctl >/dev/null 2>&1; then
  log "Systemd runtime (user units)"
  SYSTEMD_TREE="$SMOKE_BASE-systemd"
  rsync_tree "$SYSTEMD_TREE"
  teardown_systemd_units
  cd "$SYSTEMD_TREE"
  bash archives/hackathon/install.sh --non-interactive --profile demo --runtime systemd
  wait_http "http://127.0.0.1:32500/health" 90 || fail "systemd api /health"
  teardown_systemd_units
  /bin/rm -rf "$SYSTEMD_TREE"
else
  log "Skipping systemd gate (SMOKE_SKIP_SYSTEMD=1 or systemctl missing)"
fi

teardown_systemd_units
teardown_docker_stack "$SMOKE_BASE" "$COMPOSE_SMOKE" "$PROJECT_NAME_SMOKE"
teardown_docker_stack "$SMOKE_BASE" "$DEV_PG_COMPOSE" "$PROJECT_NAME_DEVPG"

if [[ "$SMOKE_KEEP" == "1" ]]; then
  log "SMOKE_KEEP=1 — leaving $SMOKE_BASE"
else
  log "Cleanup smoke tree"
  /bin/rm -rf "$SMOKE_BASE" "${SMOKE_BASE}-systemd" "$ROOT/.smoke-temp"
fi

log "FULL INSTALL SMOKE PASSED"

# Stage 06: bring Astloom application runtime up (host MCP or Docker mcp-gateway).
# shellcheck shell=bash

_compose_app() {
  docker compose --env-file "${COMPOSE_ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

_venv_cli() {
  printf '%s/%s/bin/astloom\n' "${ASTLOOM_ROOT}" "${ASTLOOM_VENV_DIR:-.venv}"
}

_print_client_usage_profile_next_steps() {
  local py="${ASTLOOM_ROOT}/${ASTLOOM_VENV_DIR:-.venv}/bin/python"
  if [[ -x "${py}" ]]; then
    ASTLOOM_ROOT="${ASTLOOM_ROOT}" "${py}" -c \
      'from astloom_cli.client_next_steps import print_client_connect_next_steps; print_client_connect_next_steps()' \
      >&2
    return 0
  fi
  cat >&2 <<'EOF'

Usage Profile id (set at connect — not during client install/upgrade):

  List ids:
    astloom profile list

  Interactive (from your app repo):
    cd /path/to/YourApp
    astloom connect
    # Wizard asks for Usage Profile: enter an id or list number

  Non-interactive — remote Astloom server (SSH):
    astloom connect --usage-profile programming-cursor-mcp \
      --tenant TENANT --workspace WORKSPACE \
      --ssh user@astloom-host

  Non-interactive — same-host dogfood (local stdio):
    astloom connect --local --usage-profile programming-cursor-mcp \
      --tenant TENANT --workspace WORKSPACE

  Non-interactive — connect.yaml already has usage_profile: <id>:
    astloom connect --config .astloom/connect.yaml

  Multi-app:
    astloom connect /opt/App1,/opt/App2 --usage-profile programming-cursor-mcp \
      --tenant TENANT --workspace WORKSPACE --ssh user@astloom-host

EOF
}

stage_06_runtime_bringup_check() {
  local errors=0
  local runtime="${INSTALL_RUNTIME:-venv}"

  if ! user_cli_on_path; then
    warn "astloom not on user PATH (${HOME}/.local/bin/astloom)"
    errors=1
  else
    ok "user PATH shim present"
  fi

  case "${runtime}" in
    venv|host)
      if [[ "${INSTALL_SKIP_INFRA}" == "1" || "${INSTALL_ROLE:-}" == "client" ]]; then
        ok "venv/client: infra skipped; CLI/PATH only — next: astloom connect"
        return "${errors}"
      fi
      if ! stage_04_docker_infra_check; then
        warn "venv runtime needs healthy postgres/neo4j"
        errors=1
      fi
      ;;
    docker)
      local status
      status="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
        astloom-mcp-gateway-1 2>/dev/null || echo missing)"
      if [[ "${status}" != "healthy" ]]; then
        warn "mcp-gateway status=${status} (want healthy)"
        errors=1
      else
        ok "mcp-gateway healthy"
      fi
      ;;
    *)
      warn "unknown INSTALL_RUNTIME=${runtime}"
      errors=1
      ;;
  esac

  return "${errors}"
}

_stage_06_bringup_host() {
  local cli
  cli="$(_venv_cli)"
  # Prefer host MCP: stop container listener if present so :32500 is free.
  # Both profiles required — mcp-gateway depends_on postgres/neo4j (core).
  info "Stopping mcp-gateway container if running (host MCP will own the port)…"
  _compose_app --profile core --profile app stop mcp-gateway >/dev/null 2>&1 || true
  info "Starting host runtime (Compose core + MCP HTTP via astloom service start)…"
  run "${cli}" service start
}

_stage_06_bringup_docker() {
  local wheelhouse_script
  wheelhouse_script="${ASTLOOM_ROOT}/scripts/build-wheelhouse.sh"
  require_file "${wheelhouse_script}"
  require_file "${ASTLOOM_ROOT}/backend/deployments/docker/Dockerfile.mcp-gateway"

  # Free MCP host port without tearing down Postgres/Neo4j.
  info "Stopping host MCP HTTP if running (frees MCP port for container)…"
  ASTLOOM_ROOT="${ASTLOOM_ROOT}" \
    "${ASTLOOM_ROOT}/${ASTLOOM_VENV_DIR:-.venv}/bin/python" - <<'PY' || true
import os
from pathlib import Path
from astloom_cli.service_runtime.mcp import stop_mcp_http
stop_mcp_http(Path(os.environ["ASTLOOM_ROOT"]))
PY

  if [[ ! -d "${ASTLOOM_WHEELHOUSE}" ]] || ! find "${ASTLOOM_WHEELHOUSE}" -maxdepth 1 -name '*.whl' 2>/dev/null | grep -q .; then
    info "Building wheelhouse at ${ASTLOOM_WHEELHOUSE}…"
    run env ASTLOOM_WHEELHOUSE="${ASTLOOM_WHEELHOUSE}" bash "${wheelhouse_script}"
  else
    ok "Wheelhouse present: ${ASTLOOM_WHEELHOUSE}"
  fi

  info "Starting Compose profiles core+app (postgres, neo4j, mcp-gateway)…"
  ASTLOOM_WHEELHOUSE="${ASTLOOM_WHEELHOUSE}" _compose_app \
    --profile core --profile app up -d --build postgres neo4j mcp-gateway

  local i status
  status="missing"
  for i in $(seq 1 60); do
    status="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
      astloom-mcp-gateway-1 2>/dev/null || echo missing)"
    if [[ "${status}" == "healthy" ]]; then
      break
    fi
    if [[ "${status}" == "exited" || "${status}" == "dead" ]]; then
      docker logs astloom-mcp-gateway-1 2>&1 | tail -80 || true
      fail "mcp-gateway container ${status}"
    fi
    sleep 2
  done
  [[ "${status}" == "healthy" ]] || fail "mcp-gateway not healthy (status=${status})"
  ok "mcp-gateway healthy on port ${ASTLOOM_MCP_HTTP_PORT:-32500}"
}

stage_06_runtime_bringup_run() {
  local runtime="${INSTALL_RUNTIME:-venv}"
  local role="${INSTALL_ROLE:-server}"
  banner "Stage 06/06 — Bring up runtime (${runtime}, role=${role})"

  # PATH in every mode (including check / skip-infra).
  if [[ "${INSTALL_CHECK_ONLY}" != "1" ]]; then
    ensure_astloom_on_path
  fi

  if [[ "${INSTALL_CHECK_ONLY}" == "1" ]]; then
    stage_06_runtime_bringup_check || fail "runtime bring-up check failed"
    mark_stage "06_runtime_bringup" "checked"
    return 0
  fi

  if [[ "${INSTALL_SKIP_INFRA}" == "1" || "${role}" == "client" ]]; then
    info "Skipping application bring-up (client / --skip-infra); PATH still installed"
    mark_stage "06_runtime_bringup" "skipped"
    echo >&2
    if [[ "${INSTALL_ACTION:-install}" == "upgrade" ]]; then
      banner "Client upgrade finished"
    else
      banner "Client install finished"
    fi
    cat >&2 <<EOF
Next steps:
  1. Open a new shell if needed so astloom is on PATH (~/.local/bin)
  2. cd into your app repo (Usage Profile id is set at connect — not during install/upgrade)
EOF
    _print_client_usage_profile_next_steps || true
    cat >&2 <<EOF
  3. Docs: docs/08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding.md
EOF
    return 0
  fi

  # JWT signing + bootstrap secrets before MCP start (never overwrite existing).
  resolve_install_api_key
  ensure_server_auth_secrets_py

  case "${runtime}" in
    venv|host) _stage_06_bringup_host ;;
    docker) _stage_06_bringup_docker ;;
    *) fail "unknown INSTALL_RUNTIME=${runtime}" ;;
  esac

  if [[ "${INSTALL_MINT_API_KEY:-0}" == "1" ]]; then
    mint_install_api_key_py || fail "API key mint failed"
  fi

  stage_06_runtime_bringup_check || fail "runtime bring-up verification failed"
  mark_stage "06_runtime_bringup" "ok"
  ok "Stage 06 complete (runtime=${runtime})"
  stamp_astloom_install_root_markers || warn "install-root marker stamp failed (non-fatal)"

  echo >&2
  if [[ "${role}" == "both" ]]; then
    banner "Astloom BOTH (dogfood) install finished"
    cat >&2 <<EOF
Next steps:
  1. astloom is on PATH via ~/.local/bin (open a new shell if \`command -v astloom\` fails)
  2. Local stack + MCP mode: ${runtime} — run: astloom sync
  3. Same-host IDE connect: astloom connect
     (Usage Profile id is chosen at connect — see astloom profile list)
     Bootstrap secret file: ${ASTLOOM_ROOT}/.astloom/connect-bootstrap.secret
     JWT signing secret:    ${ASTLOOM_ROOT}/.astloom/mcp-http.secret
  4. Run:  astloom --help && astloom doctor
  5. MCP health: curl -sk https://127.0.0.1:${ASTLOOM_MCP_HTTP_PORT:-32500}/health
  6. Docs:  docs/08-software-engineering-architecture/39-local-install-runbook.md

Compose env (secrets): ${COMPOSE_ENV_FILE}
Re-check anytime:       bash install.sh --check --non-interactive --role both --runtime ${runtime}
EOF
    _print_client_usage_profile_next_steps || true
  else
    banner "Astloom SERVER install finished"
    cat >&2 <<EOF
Next steps:
  1. astloom is on the SERVER PATH via ~/.local/bin (open a new shell if \`command -v astloom\` fails)
  2. Server MCP mode: ${runtime}
  3. Auth secrets (auto-created; preserved on upgrade):
       JWT signing:  ${ASTLOOM_ROOT}/.astloom/mcp-http.secret
       Bootstrap:    ${ASTLOOM_ROOT}/.astloom/connect-bootstrap.secret
     Optional API key: minted only when you answered yes / --mint-api-key
  4. On coding-agent machines: bash install.sh --role client   then from each app repo:
       astloom connect
     (Usage Profile id is chosen at connect on the client — not during client install)
     Or multi-app: astloom connect /opt/App1,/opt/App2
     Same-host dogfood instead: bash install.sh --role both
  5. Run:  astloom --help && astloom doctor
  6. MCP health: curl -sk https://127.0.0.1:${ASTLOOM_MCP_HTTP_PORT:-32500}/health
  7. Docs:  docs/08-software-engineering-architecture/39-local-install-runbook.md
            docs/08-software-engineering-architecture/41-one-command-cross-platform-agent-onboarding.md

Compose env (secrets): ${COMPOSE_ENV_FILE}
Re-check anytime:       bash install.sh --check --non-interactive --role server --runtime ${runtime}
EOF
  fi
}

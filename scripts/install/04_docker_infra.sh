# Stage 04: start local infrastructure (PostgreSQL + Neo4j) via Compose.
# shellcheck shell=bash

_compose() {
  # Honor COMPOSE_PROJECT_NAME when set (isolated smoke / parallel stacks).
  docker compose --env-file "${COMPOSE_ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

_compose_container_name() {
  # Prefer docker compose ps -q then inspect Name; fall back to conventional names.
  local service="$1"
  local id name
  id="$(_compose ps -q "${service}" 2>/dev/null | head -1 || true)"
  if [[ -n "${id}" ]]; then
    name="$(docker inspect --format '{{.Name}}' "${id}" 2>/dev/null | sed 's#^/##')"
    if [[ -n "${name}" ]]; then
      printf '%s\n' "${name}"
      return 0
    fi
  fi
  printf 'astloom-%s-1\n' "${service}"
}

stage_04_docker_infra_check() {
  local errors=0
  local pg neo

  if [[ "${INSTALL_SKIP_INFRA}" == "1" ]]; then
    ok "infra skipped by flag"
    return 0
  fi

  require_file "${COMPOSE_FILE}"
  require_file "${COMPOSE_ENV_FILE}" "run stage 03 first"

  if ! docker info >/dev/null 2>&1; then
    warn "docker daemon not reachable"
    return 1
  fi

  pg="$(_compose_container_name postgres)"
  neo="$(_compose_container_name neo4j)"

  local st
  for st in "${pg}" "${neo}"; do
    local status
    status="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${st}" 2>/dev/null || echo missing)"
    if [[ "${status}" != "healthy" ]]; then
      warn "${st} status=${status} (want healthy)"
      errors=1
    else
      ok "${st} healthy"
    fi
  done

  return "${errors}"
}

stage_04_docker_infra_run() {
  banner "Stage 04/06 — Docker infrastructure (PostgreSQL + Neo4j)"

  if [[ "${INSTALL_SKIP_INFRA}" == "1" ]]; then
    info "Skipping Docker infra (--skip-infra)"
    mark_stage "04_docker_infra" "skipped"
    return 0
  fi

  if [[ "${INSTALL_CHECK_ONLY}" == "1" ]]; then
    stage_04_docker_infra_check || fail "infra check failed — start compose or re-run install"
    mark_stage "04_docker_infra" "checked"
    return 0
  fi

  if stage_04_docker_infra_check; then
    ok "Infrastructure already healthy"
    mark_stage "04_docker_infra" "ok"
    return 0
  fi

  require_file "${COMPOSE_FILE}"
  require_file "${COMPOSE_ENV_FILE}"
  require_file "${WAIT_HEALTHY}"

  ensure_astloom_data_root
  # Best-effort one-shot migrate from legacy named Docker volumes into bind dirs.
  if [[ -x "${ASTLOOM_ROOT}/${ASTLOOM_VENV_DIR:-.venv}/bin/python" ]]; then
    ASTLOOM_ROOT="${ASTLOOM_ROOT}" ASTLOOM_DATA_ROOT="${ASTLOOM_DATA_ROOT}" \
      "${ASTLOOM_ROOT}/${ASTLOOM_VENV_DIR:-.venv}/bin/python" - <<'PY' || true
from pathlib import Path
import os
from astloom_cli.data_root import ensure_data_root
from astloom_cli.data_root_migrate import migrate_named_volumes_to_data_root
root = Path(os.environ["ASTLOOM_ROOT"])
data = ensure_data_root(install_root=root)
migrated = migrate_named_volumes_to_data_root(data)
if migrated:
    print(f"migrated volumes → {data}: {', '.join(migrated)}")
PY
  fi

  run_port_preflight

  info "Pulling/starting compose profile core (postgres + neo4j)…"
  run _compose --profile core up -d postgres neo4j

  local pg neo
  pg="$(_compose_container_name postgres)"
  neo="$(_compose_container_name neo4j)"

  info "Waiting for healthy containers (timeout ${INSTALL_COMPOSE_TIMEOUT}s)…"
  run bash "${WAIT_HEALTHY}" --timeout "${INSTALL_COMPOSE_TIMEOUT}" "${pg}" "${neo}"

  stage_04_docker_infra_check || fail "infra still unhealthy after compose up"
  mark_stage "04_docker_infra" "ok"
  ok "Stage 04 complete"
}

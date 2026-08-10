# Stage 03: local Compose env file (secrets + ports).
# shellcheck shell=bash

stage_03_compose_env_check() {
  local errors=0

  if [[ ! -f "${COMPOSE_ENV_FILE}" ]]; then
    warn "missing ${COMPOSE_ENV_FILE}"
    return 1
  fi
  ok "compose env: ${COMPOSE_ENV_FILE}"

  local key
  for key in \
    ASTLOOM_DATA_ROOT \
    ASTLOOM_POSTGRES_PASSWORD \
    ASTLOOM_NEO4J_PASSWORD \
    ASTLOOM_POSTGRES_PORT \
    ASTLOOM_NEO4J_BOLT_PORT; do
    if [[ -z "$(env_key_value "${COMPOSE_ENV_FILE}" "${key}" || true)" ]]; then
      warn "missing key ${key} in compose env"
      errors=1
    fi
  done

  if env_has_placeholder_secret "${COMPOSE_ENV_FILE}" "ASTLOOM_POSTGRES_PASSWORD"; then
    warn "ASTLOOM_POSTGRES_PASSWORD is still a placeholder"
    errors=1
  fi
  if env_has_placeholder_secret "${COMPOSE_ENV_FILE}" "ASTLOOM_NEO4J_PASSWORD"; then
    warn "ASTLOOM_NEO4J_PASSWORD is still a placeholder"
    errors=1
  fi

  return "${errors}"
}

_stage_03_write_env() {
  require_file "${COMPOSE_ENV_EXAMPLE}" "compose example env missing"

  local pg_secret neo_secret
  pg_secret="$(random_secret)"
  neo_secret="$(random_secret)"

  info "Writing ${COMPOSE_ENV_FILE} from example (generated local secrets)…"
  # Copy example then replace placeholders — never commit .env.local.
  cp "${COMPOSE_ENV_EXAMPLE}" "${COMPOSE_ENV_FILE}"
  chmod 600 "${COMPOSE_ENV_FILE}"

  local data_root
  data_root="${ASTLOOM_DATA_ROOT:-$(default_astloom_data_root)}"

  # Prefer sed -i; fall back to temp file if needed.
  if sed --version >/dev/null 2>&1; then
    sed -i \
      -e "s|^ASTLOOM_DATA_ROOT=.*|ASTLOOM_DATA_ROOT=${data_root}|" \
      -e "s|^ASTLOOM_POSTGRES_PASSWORD=.*|ASTLOOM_POSTGRES_PASSWORD=${pg_secret}|" \
      -e "s|^ASTLOOM_NEO4J_PASSWORD=.*|ASTLOOM_NEO4J_PASSWORD=${neo_secret}|" \
      "${COMPOSE_ENV_FILE}"
  else
    local tmp
    tmp="$(mktemp)"
    sed \
      -e "s|^ASTLOOM_DATA_ROOT=.*|ASTLOOM_DATA_ROOT=${data_root}|" \
      -e "s|^ASTLOOM_POSTGRES_PASSWORD=.*|ASTLOOM_POSTGRES_PASSWORD=${pg_secret}|" \
      -e "s|^ASTLOOM_NEO4J_PASSWORD=.*|ASTLOOM_NEO4J_PASSWORD=${neo_secret}|" \
      "${COMPOSE_ENV_FILE}" >"${tmp}"
    mv "${tmp}" "${COMPOSE_ENV_FILE}"
    chmod 600 "${COMPOSE_ENV_FILE}"
  fi

  export ASTLOOM_DATA_ROOT="${data_root}"
  ensure_astloom_data_root

  ok "Generated local secrets in ${COMPOSE_ENV_FILE} (not printed)"
}

stage_03_compose_env_run() {
  banner "Stage 03/06 — Compose environment file"

  # Always seed repo-root templates (idempotent; also covers --stage 03 alone).
  if [[ "${INSTALL_CHECK_ONLY}" != "1" ]]; then
    seed_repo_operator_files
  fi

  if [[ "${INSTALL_SKIP_INFRA}" == "1" ]]; then
    info "Skipping compose env (--skip-infra)"
    mark_stage "03_compose_env" "skipped"
    return 0
  fi

  if [[ "${INSTALL_CHECK_ONLY}" == "1" ]]; then
    stage_03_compose_env_check || fail "compose env check failed — re-run install without --check"
    mark_stage "03_compose_env" "checked"
    return 0
  fi

  # Ensure data root + ASTLOOM_DATA_ROOT in .env.local before the key check.
  ensure_astloom_data_root

  if stage_03_compose_env_check; then
    ok "Compose env already valid"
    mark_stage "03_compose_env" "ok"
    return 0
  fi

  if [[ -f "${COMPOSE_ENV_FILE}" ]]; then
    # File exists but has placeholders or missing keys — repair secrets only.
    if env_has_placeholder_secret "${COMPOSE_ENV_FILE}" "ASTLOOM_POSTGRES_PASSWORD" \
      || env_has_placeholder_secret "${COMPOSE_ENV_FILE}" "ASTLOOM_NEO4J_PASSWORD"; then
      info "Replacing placeholder secrets in existing ${COMPOSE_ENV_FILE}…"
      local pg_secret neo_secret
      pg_secret="$(random_secret)"
      neo_secret="$(random_secret)"
      if env_has_placeholder_secret "${COMPOSE_ENV_FILE}" "ASTLOOM_POSTGRES_PASSWORD"; then
        sed -i "s|^ASTLOOM_POSTGRES_PASSWORD=.*|ASTLOOM_POSTGRES_PASSWORD=${pg_secret}|" "${COMPOSE_ENV_FILE}"
      fi
      if env_has_placeholder_secret "${COMPOSE_ENV_FILE}" "ASTLOOM_NEO4J_PASSWORD"; then
        sed -i "s|^ASTLOOM_NEO4J_PASSWORD=.*|ASTLOOM_NEO4J_PASSWORD=${neo_secret}|" "${COMPOSE_ENV_FILE}"
      fi
      chmod 600 "${COMPOSE_ENV_FILE}"
    fi
  else
    _stage_03_write_env
  fi

  stage_03_compose_env_check || fail "compose env still invalid after generation"
  ensure_astloom_data_root
  mark_stage "03_compose_env" "ok"
  ok "Stage 03 complete"
}

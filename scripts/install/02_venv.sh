# Stage 02: project virtualenv + editable astloom CLI on PATH.
# shellcheck shell=bash

_venv_dir() {
  printf '%s\n' "${ASTLOOM_VENV_DIR:-.venv}"
}

_venv_path() {
  printf '%s/%s\n' "${ASTLOOM_ROOT}" "$(_venv_dir)"
}

# Virtualenv + imports only (PATH shim checked separately).
stage_02_venv_only_check() {
  local errors=0
  local venv_path py cli role_cli
  venv_path="$(_venv_path)"
  py="${venv_path}/bin/python"
  cli="${venv_path}/bin/astloom"
  role_cli="$(role_venv_cli 2>/dev/null || printf '%s\n' "${cli}")"

  if [[ ! -x "${py}" ]]; then
    warn "missing ${py}"
    errors=1
  else
    ok "venv python: $(${py} --version 2>&1)"
  fi

  if [[ ! -x "${cli}" ]]; then
    warn "missing ${cli} (editable install incomplete)"
    errors=1
  else
    ok "venv astloom present"
  fi

  if [[ ! -x "${role_cli}" ]]; then
    warn "missing ${role_cli} (role CLI incomplete)"
    errors=1
  else
    ok "role CLI present: ${role_cli##*/}"
  fi

  if [[ -x "${py}" ]]; then
    if ! "${py}" -c 'import fastapi, httpx, pytest, psycopg, astloom_cli, usage_profile'; then
      warn "required Python imports failed inside venv"
      errors=1
    else
      ok "core Python imports OK"
    fi
    if [[ "$(role_cli_name 2>/dev/null)" == "astloom-client" ]]; then
      if ! "${py}" -c 'import astloom_client'; then
        warn "astloom_client import failed inside venv"
        errors=1
      fi
    fi
  fi

  return "${errors}"
}

stage_02_venv_check() {
  local errors=0
  local shim_name
  shim_name="$(role_cli_name 2>/dev/null || printf '%s\n' astloom)"
  stage_02_venv_only_check || errors=1

  if ! user_cli_on_path; then
    warn "missing ${HOME}/.local/bin/${shim_name} (PATH shim)"
    errors=1
  else
    ok "user PATH shim: ${HOME}/.local/bin/${shim_name}"
  fi

  return "${errors}"
}

stage_02_venv_run() {
  local venv_dir venv_path
  venv_dir="$(_venv_dir)"
  venv_path="$(_venv_path)"
  banner "Stage 02/06 — Python virtualenv (${venv_dir})"

  if [[ "${INSTALL_CHECK_ONLY}" == "1" ]]; then
    stage_02_venv_check || fail "venv check failed — run: bash install.sh (or bash scripts/ensure-venv.sh)"
    mark_stage "02_venv" "checked"
    return 0
  fi

  if ! stage_02_venv_only_check; then
    require_file "${ASTLOOM_ROOT}/scripts/ensure-venv.sh" "repo scripts missing"
    require_file "${ASTLOOM_ROOT}/pyproject.toml" "run install from Astloom repo root"
    require_file "${ASTLOOM_ROOT}/requirements-dev.txt"

    local py
    py="$(python_bin)" || fail "Python 3.12+ required before creating venv"
    python_ensurepip_ok "${py}" \
      || fail "Python ensurepip missing (Debian/Ubuntu: apt install python3.12-venv), then re-run install"

    info "Creating/refreshing ${venv_dir} with ${py}…"
    if [[ "${py}" == "python3.12" ]] && [[ ! -x "${venv_path}/bin/python" ]]; then
      run "${py}" -m venv "${venv_path}"
    fi
    run env ASTLOOM_VENV_DIR="${venv_dir}" bash "${ASTLOOM_ROOT}/scripts/ensure-venv.sh"
    stage_02_venv_only_check || fail "venv verification failed after ensure-venv.sh"
  else
    ok "Virtualenv already ready"
  fi

  # Always (re)install PATH shim + shell rc — never skip when venv was already OK.
  install_cli_on_path "$(role_venv_cli)"
  stage_02_venv_check || fail "venv/PATH verification failed after path install"
  seed_repo_operator_files
  mark_stage "02_venv" "ok"
  ok "Stage 02 complete"
}

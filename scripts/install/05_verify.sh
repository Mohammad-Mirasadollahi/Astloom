# Stage 05: end-to-end verification (doctor + optional ai-toolstack).
# shellcheck shell=bash

_venv_cli() {
  printf '%s/%s/bin/astloom\n' "${ASTLOOM_ROOT}" "${ASTLOOM_VENV_DIR:-.venv}"
}

stage_05_verify_check() {
  local errors=0
  local cli
  cli="$(_venv_cli)"

  if [[ ! -x "${cli}" ]]; then
    warn "astloom CLI missing at ${cli}"
    return 1
  fi

  if ! "${cli}" doctor >/dev/null; then
    warn "astloom doctor failed"
    "${cli}" doctor || true
    errors=1
  else
    ok "astloom doctor passed"
  fi

  if [[ "${INSTALL_SKIP_INFRA}" != "1" ]]; then
    if ! stage_04_docker_infra_check; then
      warn "infra not healthy during verify"
      errors=1
    fi
  fi

  if ! user_cli_on_path; then
    warn "astloom not on user PATH (${HOME}/.local/bin/astloom)"
    errors=1
  else
    ok "user PATH shim present"
  fi

  return "${errors}"
}

stage_05_verify_run() {
  banner "Stage 05/06 — Verify installation"

  if [[ "${INSTALL_CHECK_ONLY}" == "1" ]]; then
    stage_01_prerequisites_check || fail "prerequisites failed"
    stage_02_venv_check || fail "venv failed"
    if [[ "${INSTALL_SKIP_INFRA}" != "1" ]]; then
      stage_03_compose_env_check || fail "compose env failed"
      stage_04_docker_infra_check || fail "infra failed"
    fi
    stage_05_verify_check || fail "verify failed"
    mark_stage "05_verify" "checked"
    ok "Check-only mode: all selected checks passed"
    return 0
  fi

  stage_05_verify_check || fail "verification failed — earlier stages incomplete"
  mark_stage "05_verify" "ok"

  if [[ "${INSTALL_WITH_AI_TOOLSTACK}" == "1" ]]; then
    banner "Optional — ai-toolstack (Cursor rules/skills)"
    local toolstack="${ASTLOOM_ROOT}/ai-toolstack/scripts/install-astloom.sh"
    require_file "${toolstack}" "ai-toolstack missing from this checkout"
    run bash "${toolstack}"
    ok "ai-toolstack install finished (Reload Cursor window if open)"
  fi

  ok "Stage 05 complete (runtime bring-up follows in stage 06)"
  stamp_astloom_install_root_markers || warn "install-root marker stamp failed (non-fatal)"
}

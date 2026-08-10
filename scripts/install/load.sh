# Load Astloom install modules and run selected stages.
# shellcheck shell=bash

: "${ASTLOOM_ROOT:?ASTLOOM_ROOT must be set}"
: "${ASTLOOM_INSTALL_LIB:?ASTLOOM_INSTALL_LIB must be set}"

# shellcheck source=common.sh
source "${ASTLOOM_INSTALL_LIB}/common.sh"
# shellcheck source=01_prerequisites.sh
source "${ASTLOOM_INSTALL_LIB}/01_prerequisites.sh"
# shellcheck source=02_venv.sh
source "${ASTLOOM_INSTALL_LIB}/02_venv.sh"
# shellcheck source=03_compose_env.sh
source "${ASTLOOM_INSTALL_LIB}/03_compose_env.sh"
# shellcheck source=04_docker_infra.sh
source "${ASTLOOM_INSTALL_LIB}/04_docker_infra.sh"
# shellcheck source=05_verify.sh
source "${ASTLOOM_INSTALL_LIB}/05_verify.sh"
# shellcheck source=06_runtime_bringup.sh
source "${ASTLOOM_INSTALL_LIB}/06_runtime_bringup.sh"

INSTALL_STAGES=(
  "01_prerequisites:stage_01_prerequisites_run"
  "02_venv:stage_02_venv_run"
  "03_compose_env:stage_03_compose_env_run"
  "04_docker_infra:stage_04_docker_infra_run"
  "05_verify:stage_05_verify_run"
  "06_runtime_bringup:stage_06_runtime_bringup_run"
)

list_install_stages() {
  local entry name
  echo "Astloom install stages (in order):"
  for entry in "${INSTALL_STAGES[@]}"; do
    name="${entry%%:*}"
    echo "  - ${name}"
  done
  echo "Roles: client | server — then SERVER MCP mode: venv | docker (alias: host→venv)"
}

run_install_stage() {
  local want="$1"
  local entry name fn
  for entry in "${INSTALL_STAGES[@]}"; do
    name="${entry%%:*}"
    fn="${entry#*:}"
    if [[ "${name}" == "${want}" ]]; then
      if [[ "${name}" == "06_runtime_bringup" ]]; then
        resolve_install_role
        resolve_install_runtime
        resolve_install_data_root
      fi
      "${fn}"
      return $?
    fi
  done
  fail "unknown stage: ${want} (use --list-stages)"
}

run_install_stages_only() {
  local entry fn
  for entry in "${INSTALL_STAGES[@]}"; do
    fn="${entry#*:}"
    "${fn}"
  done
}

run_install_all() {
  local entry fn
  ensure_state_dir

  # Interactive / flagged choice before stages that depend on it.
  resolve_install_role
  resolve_install_runtime
  resolve_install_data_root

  # Human full installs must install OS prerequisites (ignore accidental skip).
  if [[ "${INSTALL_NONINTERACTIVE}" != "1" && "${INSTALL_SKIP_PREREQS}" == "1" ]]; then
    warn "Ignoring --skip-prerequisites for interactive install (prerequisites are required)"
    INSTALL_SKIP_PREREQS=0
    export INSTALL_SKIP_PREREQS
  fi

  run_install_stages_only
}

# Backup install-state, re-run stages, stamp product/contract via CLI finalize.
run_install_upgrade() {
  local stamp backup_dir cli runtime_arg
  local persisted=""
  ensure_state_dir
  if [[ ! -f "${INSTALL_STATE_FILE}" ]]; then
    fail "upgrade requires an existing install (missing ${INSTALL_STATE_FILE}); run bash install.sh first"
  fi

  banner "Upgrade existing Astloom install"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup_dir="${INSTALL_STATE_DIR}/upgrade-backups/install-${stamp}"
  mkdir -p "${backup_dir}"
  cp -a "${INSTALL_STATE_FILE}" "${backup_dir}/install-state.env"
  if [[ -f "${ASTLOOM_ROOT}/astloom.sync.yaml" ]]; then
    cp -a "${ASTLOOM_ROOT}/astloom.sync.yaml" "${backup_dir}/astloom.sync.yaml"
  fi
  # Auth secrets stay in place on upgrade (never regenerated); copy for operator backup only.
  mkdir -p "${backup_dir}/auth"
  for _auth in mcp-http.secret connect-bootstrap.secret install-api-key.secret install-api-key.meta.json; do
    if [[ -f "${ASTLOOM_ROOT}/.astloom/${_auth}" ]]; then
      cp -a "${ASTLOOM_ROOT}/.astloom/${_auth}" "${backup_dir}/auth/${_auth}"
    fi
  done
  ok "backup → ${backup_dir}"

  # Prefer persisted role/runtime; heal garbage from older prompt-capture bugs.
  if [[ -z "${INSTALL_ROLE}" ]]; then
    persisted="$(install_stdout_token "$(env_key_value "${INSTALL_STATE_FILE}" "role" || true)")"
    if INSTALL_ROLE="$(normalize_install_role "${persisted}" 2>/dev/null)"; then
      export INSTALL_ROLE
    else
      if [[ -n "${persisted}" ]]; then
        warn "Ignoring invalid persisted role='${persisted}'"
      fi
      INSTALL_ROLE=""
      export INSTALL_ROLE
    fi
  fi
  if [[ -z "${INSTALL_RUNTIME}" ]]; then
    persisted="$(install_stdout_token "$(env_key_value "${INSTALL_STATE_FILE}" "runtime" || true)")"
    if INSTALL_RUNTIME="$(normalize_install_runtime "${persisted}" 2>/dev/null)"; then
      export INSTALL_RUNTIME
    else
      if [[ -n "${persisted}" ]]; then
        warn "Ignoring invalid persisted runtime='${persisted}'"
      fi
      INSTALL_RUNTIME=""
      export INSTALL_RUNTIME
    fi
  fi

  # Resolve while TTY prompts are still allowed (if role was cleared as invalid).
  resolve_install_role
  resolve_install_runtime
  resolve_install_data_root

  local saved_ni="${INSTALL_NONINTERACTIVE:-0}"
  INSTALL_NONINTERACTIVE=1
  export INSTALL_NONINTERACTIVE

  if [[ "${INSTALL_SKIP_PREREQS}" == "1" ]]; then
    warn "Ignoring --skip-prerequisites for upgrade (prerequisites are required)"
    INSTALL_SKIP_PREREQS=0
    export INSTALL_SKIP_PREREQS
  fi

  run_install_stages_only

  INSTALL_NONINTERACTIVE="${saved_ni}"
  export INSTALL_NONINTERACTIVE

  cli="${ASTLOOM_ROOT}/.venv/bin/astloom"
  # Prefer role-correct binary (client-only → astloom-client).
  if [[ -x "${ASTLOOM_ROOT}/.venv/bin/astloom-client" ]] && {
    [[ "${INSTALL_ROLE:-}" == "client" ]] || grep -q '^role=client$' "${ASTLOOM_ROOT}/.astloom/install-state.env" 2>/dev/null
  }; then
    cli="${ASTLOOM_ROOT}/.venv/bin/astloom-client"
  fi
  runtime_arg="${INSTALL_RUNTIME:-venv}"
  if [[ -x "${cli}" ]]; then
    info "Stamping upgrade evidence via ${cli##*/} upgrade finalize"
    case "${runtime_arg}" in
      venv) runtime_arg="host" ;;
    esac
    run "${cli}" upgrade finalize --runtime "${runtime_arg}"
  else
    warn "CLI missing after upgrade; wrote backup only at ${backup_dir}"
  fi
  ok "upgrade complete (runtime=${INSTALL_RUNTIME:-venv})"
}

install_main() {
  local mode="${1:-all}"
  local stage_name="${2:-}"
  local action=""

  case "${mode}" in
    list)
      list_install_stages
      ;;
    stage)
      [[ -n "${stage_name}" ]] || fail "--stage requires a stage name"
      run_install_stage "${stage_name}"
      ;;
    prerequisites-only)
      # Always install/check OS deps; no runtime prompt.
      INSTALL_SKIP_PREREQS=0
      export INSTALL_SKIP_PREREQS
      run_install_stage "01_prerequisites"
      ;;
    upgrade)
      INSTALL_ACTION_LOCKED=1
      export INSTALL_ACTION_LOCKED
      resolve_install_action "upgrade"
      run_install_upgrade
      ;;
    all|*)
      resolve_install_action ""
      action="${INSTALL_ACTION}"
      if [[ "${action}" == "upgrade" ]]; then
        run_install_upgrade
      else
        run_install_all
      fi
      ;;
  esac
}

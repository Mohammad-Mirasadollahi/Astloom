# Shared helpers for Astloom modular install.
# Sourced by load.sh — do not execute directly.
# shellcheck shell=bash

: "${ASTLOOM_ROOT:?ASTLOOM_ROOT must be set}"

INSTALL_LOG_PREFIX="${INSTALL_LOG_PREFIX:-[astloom-install]}"
INSTALL_STATE_DIR="${ASTLOOM_ROOT}/.astloom"
INSTALL_STATE_FILE="${INSTALL_STATE_DIR}/install-state.env"
COMPOSE_DIR="${ASTLOOM_ROOT}/backend/deployments/compose"
COMPOSE_FILE="${COMPOSE_DIR}/compose.yaml"
COMPOSE_ENV_FILE="${COMPOSE_DIR}/.env.local"
COMPOSE_ENV_EXAMPLE="${COMPOSE_DIR}/neo4j.example.env"
WAIT_HEALTHY="${COMPOSE_DIR}/wait-healthy.sh"

# Durable data sibling of the install (override with ASTLOOM_DATA_ROOT).
default_astloom_data_root() {
  printf '%s/%s-data\n' "$(dirname "${ASTLOOM_ROOT}")" "$(basename "${ASTLOOM_ROOT}")"
}

ensure_astloom_data_root() {
  local data_root
  data_root="${ASTLOOM_DATA_ROOT:-$(default_astloom_data_root)}"
  export ASTLOOM_DATA_ROOT="${data_root}"
  mkdir -p \
    "${data_root}/postgres" \
    "${data_root}/neo4j" \
    "${data_root}/backup" \
    "${data_root}/cache" \
    "${data_root}/mcp-usage" \
    "${data_root}/sync-usage"
  mkdir -p "${ASTLOOM_ROOT}/.astloom"
  printf '%s\n' "${data_root}" >"${ASTLOOM_ROOT}/.astloom/data-root"
  chmod 644 "${ASTLOOM_ROOT}/.astloom/data-root" 2>/dev/null || true
  chmod 755 "${ASTLOOM_ROOT}/.astloom" 2>/dev/null || true
  if [[ -f "${COMPOSE_ENV_FILE}" ]]; then
    if grep -q '^ASTLOOM_DATA_ROOT=' "${COMPOSE_ENV_FILE}" 2>/dev/null; then
      sed -i "s|^ASTLOOM_DATA_ROOT=.*|ASTLOOM_DATA_ROOT=${data_root}|" "${COMPOSE_ENV_FILE}"
    else
      printf '\nASTLOOM_DATA_ROOT=%s\n' "${data_root}" >>"${COMPOSE_ENV_FILE}"
    fi
    chmod 600 "${COMPOSE_ENV_FILE}" || true
  fi
  ok "data root: ${data_root}"
}

# Repo-root operator templates (never overwrite existing files).
REPO_ENV_FILE="${ASTLOOM_ROOT}/.env"
REPO_ENV_EXAMPLE="${ASTLOOM_ROOT}/.env.example"
REPO_SYNC_FILE="${ASTLOOM_ROOT}/astloom.sync.yaml"
REPO_SYNC_EXAMPLE="${ASTLOOM_ROOT}/astloom.sync.yaml.example"

INSTALL_CHECK_ONLY="${INSTALL_CHECK_ONLY:-0}"
INSTALL_NONINTERACTIVE="${INSTALL_NONINTERACTIVE:-0}"
INSTALL_SKIP_PREREQS="${INSTALL_SKIP_PREREQS:-0}"
INSTALL_SKIP_INFRA="${INSTALL_SKIP_INFRA:-0}"
INSTALL_WITH_FRONTEND="${INSTALL_WITH_FRONTEND:-0}"
INSTALL_WITH_AI_TOOLSTACK="${INSTALL_WITH_AI_TOOLSTACK:-0}"
INSTALL_COMPOSE_TIMEOUT="${INSTALL_COMPOSE_TIMEOUT:-300}"
# Runtime bring-up (SERVER only): venv MCP | docker mcp-gateway. Empty until resolved.
# Canonical values: venv | docker. Legacy alias: host → venv.
INSTALL_RUNTIME="${INSTALL_RUNTIME:-}"
# Install target: client (CLI only) | server (infra + MCP). Empty until resolved.
INSTALL_ROLE="${INSTALL_ROLE:-}"
# Top-level action: install | upgrade. Empty until resolved (interactive asks).
INSTALL_ACTION="${INSTALL_ACTION:-}"
# Skip the "type yes" confirmation (CI / --yes).
INSTALL_ASSUME_YES="${INSTALL_ASSUME_YES:-0}"
ASTLOOM_WHEELHOUSE="${ASTLOOM_WHEELHOUSE:-/opt/astloom-wheelhouse}"

log() { printf '%s %s\n' "${INSTALL_LOG_PREFIX}" "$*" >&2; }
info() { log "INFO  $*"; }
ok() { log "OK    $*"; }
warn() { log "WARN  $*" >&2; }
fail() {
  log "FAIL  $*" >&2
  exit 1
}

# Block bring-up when profile ports conflict (writes .astloom/run/port-map.json).
run_port_preflight() {
  local cli="${ASTLOOM_ROOT}/${ASTLOOM_VENV_DIR:-.venv}/bin/astloom"
  local map_path="${ASTLOOM_ROOT}/.astloom/run/port-map.json"
  local rc=0

  if [[ ! -x "${cli}" ]]; then
    fail "port preflight requires ${cli} (run stage 02 / venv first)"
  fi

  info "Port preflight (blocks on foreign port conflicts)…"
  set +e
  "${cli}" ports check --write-map "${map_path}"
  rc=$?
  set -e
  if [[ "${rc}" -ne 0 ]]; then
    fail "port preflight failed (exit ${rc}) — free conflicting ports or set ASTLOOM_*_PORT; see ${map_path}"
  fi
  ok "port preflight passed (map: ${map_path})"
}

# curl|bash leaves stdin as the script pipe. Prompt via /dev/tty when needed.
install_can_prompt() {
  if [[ "${INSTALL_NONINTERACTIVE}" == "1" ]]; then
    return 1
  fi
  if [[ -t 0 ]]; then
    return 0
  fi
  if { true <>/dev/tty; } 2>/dev/null; then
    return 0
  fi
  return 1
}

# Read one operator line (stdin TTY, else /dev/tty). Prints the answer on stdout.
install_read_line() {
  local prompt="$1"
  local ans=""
  if [[ -t 0 ]]; then
    printf '%s' "${prompt}" >&2
    read -r ans || true
  elif { true <>/dev/tty; } 2>/dev/null; then
    printf '%s' "${prompt}" >/dev/tty 2>/dev/null || true
    read -r ans </dev/tty 2>/dev/null || true
    printf '\n' >/dev/tty 2>/dev/null || true
  else
    fail "cannot prompt (no TTY); pass --yes / --non-interactive"
  fi
  printf '%s\n' "${ans}"
}

# Last non-empty line from a captured prompt (guards banner leaks into $()).
install_stdout_token() {
  printf '%s' "${1:-}" | tr -d '\r' | awk 'NF { line = $0 } END { print line }'
}

banner() {
  local title="$1"
  log "================================================================"
  log "${title}"
  log "================================================================"
}

run() {
  info "→ $*"
  "$@"
}

as_root() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    fail "need root or sudo to run: $*"
  fi
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

python_bin() {
  local candidate
  for candidate in python3.12 python3; do
    if have_cmd "${candidate}" \
      && "${candidate}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

# Debian/Ubuntu often ship python3.12 without ensurepip until python3.12-venv is installed.
python_ensurepip_ok() {
  local py="${1:-}"
  if [[ -z "${py}" ]]; then
    py="$(python_bin)" || return 1
  fi
  "${py}" -c 'import ensurepip' 2>/dev/null
}

linux_debian_family() {
  [[ -f /etc/os-release ]] || return 1
  grep -qE '^(ID=debian|ID=ubuntu|ID_LIKE=.*(debian|ubuntu))' /etc/os-release
}

ensure_state_dir() {
  mkdir -p "${INSTALL_STATE_DIR}"
}

mark_stage() {
  local stage="$1"
  local status="${2:-ok}"
  ensure_state_dir
  touch "${INSTALL_STATE_FILE}"
  if grep -q "^${stage}=" "${INSTALL_STATE_FILE}" 2>/dev/null; then
    # portable in-place replace without relying on GNU sed -i semantics alone
    local tmp
    tmp="$(mktemp)"
    grep -v "^${stage}=" "${INSTALL_STATE_FILE}" >"${tmp}" || true
    printf '%s=%s\n' "${stage}" "${status}" >>"${tmp}"
    mv "${tmp}" "${INSTALL_STATE_FILE}"
  else
    printf '%s=%s\n' "${stage}" "${status}" >>"${INSTALL_STATE_FILE}"
  fi
}

# Well-known install-root markers for client SSH discovery (no root required to read).
# Writes: <ASTLOOM_ROOT>/.astloom/install-root, $HOME/.astloom/install-root,
# and SUDO_USER home when install ran via sudo.
stamp_astloom_install_root_markers() {
  local root="${ASTLOOM_ROOT}"
  local marker_dir marker payload sudo_home=""
  [[ -n "${root}" ]] || return 1
  root="$(cd "${root}" 2>/dev/null && pwd)" || return 1
  payload="${root}"
  marker_dir="${root}/.astloom"
  mkdir -p "${marker_dir}" || return 1
  marker="${marker_dir}/install-root"
  printf '%s\n' "${payload}" >"${marker}" || return 1
  chmod 644 "${marker}" 2>/dev/null || true
  chmod 755 "${marker_dir}" 2>/dev/null || true

  mkdir -p "${HOME}/.astloom" 2>/dev/null || true
  if [[ -d "${HOME}/.astloom" ]]; then
    printf '%s\n' "${payload}" >"${HOME}/.astloom/install-root" || true
    chmod 644 "${HOME}/.astloom/install-root" 2>/dev/null || true
  fi

  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    if command -v getent >/dev/null 2>&1; then
      sudo_home="$(getent passwd "${SUDO_USER}" | cut -d: -f6 || true)"
    fi
    if [[ -z "${sudo_home}" && -d "/home/${SUDO_USER}" ]]; then
      sudo_home="/home/${SUDO_USER}"
    fi
    if [[ -n "${sudo_home}" ]]; then
      mkdir -p "${sudo_home}/.astloom" 2>/dev/null || true
      if printf '%s\n' "${payload}" >"${sudo_home}/.astloom/install-root" 2>/dev/null; then
        chown "${SUDO_USER}:" "${sudo_home}/.astloom/install-root" 2>/dev/null || true
        chmod 644 "${sudo_home}/.astloom/install-root" 2>/dev/null || true
      fi
    fi
  fi
  ok "install-root marker → ${marker}"
  return 0
}

stage_status() {
  local stage="$1"
  [[ -f "${INSTALL_STATE_FILE}" ]] || return 1
  grep -E "^${stage}=" "${INSTALL_STATE_FILE}" 2>/dev/null | tail -1 | cut -d= -f2-
}

require_file() {
  local path="$1"
  local hint="${2:-}"
  [[ -f "${path}" ]] || fail "missing file: ${path}${hint:+ — ${hint}}"
}

suggest_fix() {
  local msg="$1"
  warn "fix: ${msg}"
}

random_secret() {
  if have_cmd openssl; then
    openssl rand -hex 24
    return 0
  fi
  # Fallback: urandom hex (48 chars)
  head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n'
}

env_key_value() {
  local file="$1"
  local key="$2"
  [[ -f "${file}" ]] || return 1
  # shellcheck disable=SC2002
  grep -E "^${key}=" "${file}" 2>/dev/null | tail -1 | cut -d= -f2-
}

env_has_placeholder_secret() {
  local file="$1"
  local key="$2"
  local val
  val="$(env_key_value "${file}" "${key}" || true)"
  [[ -z "${val}" ]] && return 0
  [[ "${val}" == "replace-with-a-local-secret" ]] && return 0
  [[ "${val}" == "changeme" ]] && return 0
  return 1
}

copy_example_if_missing() {
  local example="$1"
  local dest="$2"
  local label="$3"
  if [[ -f "${dest}" ]]; then
    ok "${label} present: ${dest}"
    return 0
  fi
  require_file "${example}" "missing template ${example}"
  info "Copying ${example} → ${dest}"
  cp "${example}" "${dest}"
  ok "Created ${dest} (edit as needed; re-install will not overwrite)"
}

# Seed repo-root .env and astloom.sync.yaml from *.example when absent.
seed_repo_operator_files() {
  copy_example_if_missing "${REPO_ENV_EXAMPLE}" "${REPO_ENV_FILE}" "repo .env"
  copy_example_if_missing "${REPO_SYNC_EXAMPLE}" "${REPO_SYNC_FILE}" "astloom.sync.yaml"
}

# Role-correct venv CLI path (client-only → astloom-client; else astloom).
role_venv_cli() {
  local root="${ASTLOOM_ROOT}/${ASTLOOM_VENV_DIR:-.venv}/bin"
  if [[ "${INSTALL_ROLE:-}" == "client" ]] || grep -q '^role=client$' "${ASTLOOM_ROOT}/.astloom/install-state.env" 2>/dev/null; then
    printf '%s\n' "${root}/astloom-client"
  else
    printf '%s\n' "${root}/astloom"
  fi
}

# Role-correct PATH shim name.
role_cli_name() {
  if [[ "${INSTALL_ROLE:-}" == "client" ]] || grep -q '^role=client$' "${ASTLOOM_ROOT}/.astloom/install-state.env" 2>/dev/null; then
    printf '%s\n' "astloom-client"
  else
    printf '%s\n' "astloom"
  fi
}

# Symlink the role-correct CLI onto ~/.local/bin and ensure PATH export in shell rc.
install_cli_on_path() {
  local cli="${1:?}"
  local link_name
  link_name="$(role_cli_name)"
  local link="${HOME}/.local/bin/${link_name}"
  [[ -x "${cli}" ]] || fail "CLI missing at ${cli}"

  # Always persist PATH into the user's shell rc (path install creates rc if missing).
  # ASTLOOM_SHELL_RC overrides auto-detect (.bashrc/.profile or .zshrc).
  # --quiet: install logs stay on our banners; skip JSON dump from the CLI.
  if [[ -n "${ASTLOOM_SHELL_RC:-}" ]]; then
    run "${cli}" path install --quiet --shell-rc "${ASTLOOM_SHELL_RC}"
  else
    run "${cli}" path install --quiet
  fi

  if [[ ! -e "${link}" && ! -L "${link}" ]]; then
    fail "PATH install failed: missing ${link} (${link_name} must be on user PATH)"
  fi
  # Current process + child stages see the CLI immediately.
  export PATH="${HOME}/.local/bin:${PATH}"
  if ! command -v "${link_name}" >/dev/null 2>&1; then
    fail "PATH install failed: ${link_name} not resolvable after exporting ${HOME}/.local/bin"
  fi
  ok "${link_name} PATH shim: ${link}"
}

user_cli_on_path() {
  local link_name
  link_name="$(role_cli_name)"
  local link="${HOME}/.local/bin/${link_name}"
  [[ -e "${link}" || -L "${link}" ]]
}

# True when the role-correct ~/.local/bin shim already points at this checkout's venv CLI.
path_shim_matches_venv() {
  local cli="${1:?}"
  local link_name
  link_name="$(role_cli_name)"
  local link="${HOME}/.local/bin/${link_name}"
  [[ -x "${cli}" ]] || return 1
  [[ -L "${link}" || -e "${link}" ]] || return 1
  local want have
  want="$(readlink -f "${cli}" 2>/dev/null || true)"
  have="$(readlink -f "${link}" 2>/dev/null || true)"
  [[ -n "${want}" && "${want}" == "${have}" ]]
}

# Always ensure ~/.local/bin is exported for this process and present on disk.
ensure_astloom_on_path() {
  local venv_cli link_name
  venv_cli="$(role_venv_cli)"
  link_name="$(role_cli_name)"
  export PATH="${HOME}/.local/bin:${PATH}"
  [[ -x "${venv_cli}" ]] || fail "cannot install PATH: missing ${venv_cli} (stage 02 incomplete)"
  if path_shim_matches_venv "${venv_cli}" && command -v "${link_name}" >/dev/null 2>&1; then
    ok "PATH ready: ${HOME}/.local/bin/${link_name}"
    return 0
  fi
  install_cli_on_path "${venv_cli}"
  user_cli_on_path || fail "${link_name} still not on user PATH after install"
  ok "PATH ready: ${HOME}/.local/bin/${link_name}"
}

# Normalize INSTALL_ROLE → client|server|both.
normalize_install_role() {
  local raw="${1:-}"
  case "${raw}" in
    client|CLIENT) printf '%s\n' "client" ;;
    server|SERVER) printf '%s\n' "server" ;;
    both|BOTH|hybrid|HYBRID|all|ALL|dogfood|DOGFOOD) printf '%s\n' "both" ;;
    *) return 1 ;;
  esac
}

# Normalize INSTALL_ACTION → install|upgrade.
normalize_install_action() {
  local raw="${1:-}"
  case "${raw}" in
    install|INSTALL|new) printf '%s\n' "install" ;;
    upgrade|UPGRADE|update) printf '%s\n' "upgrade" ;;
    *) return 1 ;;
  esac
}

prompt_install_action() {
  local choice=""
  banner "Install new or upgrade existing?"
  cat >&2 <<'EOF'
  1) install — Fresh / full bootstrap (client or server prompts follow)
  2) upgrade — Re-run stages on an existing install (needs prior install-state)

  Tip: non-interactive — bash install.sh --non-interactive …
       force upgrade — bash install.sh --upgrade --yes
EOF
  while true; do
    choice="$(install_read_line 'Select action [1=install / 2=upgrade]: ')"
    choice="$(install_stdout_token "${choice}")"
    case "${choice}" in
      1|install|INSTALL) printf '%s\n' "install"; return 0 ;;
      2|upgrade|UPGRADE) printf '%s\n' "upgrade"; return 0 ;;
      "")
        warn "Choose 1 or 2 (no default)"
        ;;
      *) warn "Enter 1/install or 2/upgrade" ;;
    esac
  done
}

# Normalize yes/no answers (y/yes / n/no). Empty → fail (no silent default).
normalize_yes_no() {
  local raw
  raw="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
  case "${raw}" in
    y | yes) printf '%s\n' "yes" ;;
    n | no) printf '%s\n' "no" ;;
    *) return 1 ;;
  esac
}

# After choosing install/upgrade: require explicit yes/y or no/n (no default).
confirm_install_action() {
  local action="${1:-}"
  local answer=""
  local normalized=""
  if [[ "${INSTALL_ASSUME_YES}" == "1" || "${INSTALL_NONINTERACTIVE}" == "1" ]]; then
    info "Confirmation skipped (--yes or --non-interactive); proceeding with ${action}"
    return 0
  fi
  if ! install_can_prompt; then
    fail "refusing ${action} without TTY confirmation; re-run interactively or pass --yes / --non-interactive"
  fi
  banner "Confirm ${action}"
  while true; do
    answer="$(install_read_line "Continue with ${action}? [y/n]: ")"
    if normalized="$(normalize_yes_no "${answer}" 2>/dev/null)"; then
      if [[ "${normalized}" == "yes" ]]; then
        ok "Confirmed ${action}"
        return 0
      fi
      fail "aborted: ${action} not confirmed (answered no)"
    fi
    warn "Type y/yes or n/no (no default)"
  done
}

# Resolve INSTALL_ACTION (install|upgrade), then require yes confirmation when interactive.
# Optional preferred arg locks the action (e.g. --upgrade → upgrade) but still asks for yes.
resolve_install_action() {
  local resolved=""
  local preferred="${1:-}"

  if [[ -n "${INSTALL_ACTION}" ]]; then
    resolved="$(normalize_install_action "${INSTALL_ACTION}" || true)"
    [[ -n "${resolved}" ]] || fail "invalid INSTALL_ACTION='${INSTALL_ACTION}' (want: install|upgrade)"
  elif [[ "${INSTALL_ACTION_LOCKED:-0}" == "1" && -n "${preferred}" ]]; then
    resolved="$(normalize_install_action "${preferred}" || true)"
    [[ -n "${resolved}" ]] || fail "invalid action '${preferred}' (want: install|upgrade)"
  elif install_can_prompt; then
    resolved="$(prompt_install_action)"
  elif [[ -n "${preferred}" ]]; then
    resolved="$(normalize_install_action "${preferred}" || true)"
    [[ -n "${resolved}" ]] || fail "invalid action '${preferred}' (want: install|upgrade)"
  else
    resolved="install"
    info "Non-interactive: default action=install (pass --upgrade for upgrade)"
  fi

  INSTALL_ACTION="$(install_stdout_token "${resolved}")"
  INSTALL_ACTION="$(normalize_install_action "${INSTALL_ACTION}" || true)"
  [[ -n "${INSTALL_ACTION}" ]] || fail "invalid install action '${resolved}' (want: install|upgrade)"
  export INSTALL_ACTION
  confirm_install_action "${INSTALL_ACTION}"
  ok "Install action: ${INSTALL_ACTION}"
}

# Normalize INSTALL_RUNTIME → venv|docker (legacy host → venv).
normalize_install_runtime() {
  local raw="${1:-}"
  case "${raw}" in
    venv|VENV|host|HOST) printf '%s\n' "venv" ;;
    docker|DOCKER) printf '%s\n' "docker" ;;
    *) return 1 ;;
  esac
}

prompt_install_role() {
  local choice=""
  banner "Install client, server, or both?"
  cat >&2 <<'EOF'
  1) client — Coding-agent machine: CLI + venv only (no Postgres/Neo4j Compose).
              Next step after install: astloom connect
  2) server — Astloom platform host: Compose stores + MCP gateway
  3) both   — Same-host dogfood: server stack + local sync AND IDE connect (client tooling)

  Tip: non-interactive flags — --role client | --role server | --role both
       client shortcut: --skip-infra
       After client install: cd /your/app && astloom connect
       (or: astloom connect /app1,/app2) — that path is the sync project
EOF
  while true; do
    choice="$(install_read_line 'Select install target [1=client / 2=server / 3=both]: ')"
    choice="$(install_stdout_token "${choice}")"
    case "${choice}" in
      1|client|CLIENT) printf '%s\n' "client"; return 0 ;;
      2|server|SERVER) printf '%s\n' "server"; return 0 ;;
      3|both|BOTH|hybrid|HYBRID|all|ALL|dogfood|DOGFOOD) printf '%s\n' "both"; return 0 ;;
      "")
        warn "Choose 1, 2, or 3 (no default)"
        ;;
      *) warn "Enter 1/client, 2/server, or 3/both" ;;
    esac
  done
}

prompt_install_runtime() {
  local choice=""
  banner "Choose how the SERVER runs MCP"
  cat >&2 <<'EOF'
  Infra (Postgres + Neo4j) always uses Compose on the server. Pick where MCP runs:

  1) venv   — MCP HTTP from this machine's Python .venv (recommended)
  2) docker — MCP HTTP inside the mcp-gateway Compose container

  (Legacy name for venv was "host"; --runtime host still works as an alias.)
EOF
  while true; do
    choice="$(install_read_line 'Select SERVER MCP mode [1=venv / 2=docker]: ')"
    choice="$(install_stdout_token "${choice}")"
    case "${choice}" in
      1|venv|VENV|host|HOST) printf '%s\n' "venv"; return 0 ;;
      2|docker|DOCKER) printf '%s\n' "docker"; return 0 ;;
      "")
        warn "Choose 1 or 2 (no default)"
        ;;
      *) warn "Enter 1/venv or 2/docker" ;;
    esac
  done
}

# Resolve INSTALL_ROLE (client|server|both). Client forces --skip-infra.
# Persists role=<value> in install-state.env. ``both`` installs like server
# (Compose + MCP) and keeps IDE connect / client tooling on the same host.
resolve_install_role() {
  local resolved=""
  local persisted=""
  local raw="${INSTALL_ROLE:-}"

  # Drop garbage from older prompt-capture bugs (banner text in env / state).
  if [[ -n "${raw}" ]]; then
    raw="$(install_stdout_token "${raw}")"
    if resolved="$(normalize_install_role "${raw}" 2>/dev/null)"; then
      :
    else
      warn "Ignoring invalid INSTALL_ROLE='${raw}' (want: client|server|both)"
      INSTALL_ROLE=""
      export INSTALL_ROLE
      resolved=""
    fi
  fi

  if [[ -n "${resolved}" ]]; then
    :
  elif [[ "${INSTALL_SKIP_INFRA}" == "1" ]]; then
    resolved="client"
    info "Install role=client (from --skip-infra)"
  elif [[ -n "${INSTALL_RUNTIME}" ]]; then
    # Explicit MCP mode implies a host with local stack (server or both).
    # Keep persisted both; otherwise default to server.
    if [[ -f "${INSTALL_STATE_FILE}" ]]; then
      persisted="$(install_stdout_token "$(env_key_value "${INSTALL_STATE_FILE}" "role" || true)")"
    fi
    if [[ "${persisted}" == "both" ]]; then
      resolved="both"
      info "Install role=both (from --runtime + persisted both)"
    else
      resolved="server"
      info "Install role=server (from --runtime)"
    fi
  elif install_can_prompt; then
    resolved="$(install_stdout_token "$(prompt_install_role)")"
    resolved="$(normalize_install_role "${resolved}" || true)"
    [[ -n "${resolved}" ]] || fail "invalid role choice (want: client|server|both)"
  else
    if [[ -f "${INSTALL_STATE_FILE}" ]]; then
      persisted="$(install_stdout_token "$(env_key_value "${INSTALL_STATE_FILE}" "role" || true)")"
    fi
    if resolved="$(normalize_install_role "${persisted}" 2>/dev/null)"; then
      info "Using persisted role=${resolved}"
    else
      if [[ -n "${persisted}" ]]; then
        warn "Ignoring invalid persisted role='${persisted}'"
      fi
      resolved="server"
      info "Non-interactive install: default role=server (pass --role client for CLI-only, --role both for dogfood)"
    fi
  fi

  INSTALL_ROLE="${resolved}"
  export INSTALL_ROLE
  if [[ "${INSTALL_ROLE}" == "client" ]]; then
    INSTALL_SKIP_INFRA=1
    export INSTALL_SKIP_INFRA
  fi
  ensure_state_dir
  mark_stage "role" "${INSTALL_ROLE}"
  ok "Install role: ${INSTALL_ROLE}"
}

# Resolve INSTALL_RUNTIME from flag, TTY prompt, or default venv.
# Persists choice to install-state.env as runtime=<value>.
resolve_install_runtime() {
  local resolved=""
  local persisted=""
  local raw="${INSTALL_RUNTIME:-}"

  if [[ "${INSTALL_ROLE:-}" == "client" ]]; then
    # Client never brings up MCP here; keep a stable label for state/check.
    INSTALL_RUNTIME="venv"
    export INSTALL_RUNTIME
    ensure_state_dir
    mark_stage "runtime" "${INSTALL_RUNTIME}"
    ok "Install runtime: venv (client — infra skipped; use astloom connect next)"
    return 0
  fi

  if [[ -n "${raw}" ]]; then
    raw="$(install_stdout_token "${raw}")"
    if resolved="$(normalize_install_runtime "${raw}" 2>/dev/null)"; then
      :
    else
      warn "Ignoring invalid INSTALL_RUNTIME='${raw}' (want: venv|docker)"
      INSTALL_RUNTIME=""
      export INSTALL_RUNTIME
      resolved=""
    fi
  fi

  if [[ -n "${resolved}" ]]; then
    :
  elif install_can_prompt; then
    resolved="$(install_stdout_token "$(prompt_install_runtime)")"
    resolved="$(normalize_install_runtime "${resolved}" || true)"
    [[ -n "${resolved}" ]] || fail "invalid runtime choice (want: venv|docker)"
  else
    if [[ -f "${INSTALL_STATE_FILE}" ]]; then
      persisted="$(install_stdout_token "$(env_key_value "${INSTALL_STATE_FILE}" "runtime" || true)")"
    fi
    if resolved="$(normalize_install_runtime "${persisted}" 2>/dev/null)"; then
      info "Using persisted runtime=${resolved}"
    else
      if [[ -n "${persisted}" ]]; then
        warn "Ignoring invalid persisted runtime='${persisted}'"
      fi
      resolved="venv"
      info "Non-interactive install: default runtime=venv (pass --runtime docker to override)"
    fi
  fi

  if [[ "${resolved}" == "docker" && "${INSTALL_SKIP_INFRA}" == "1" ]]; then
    fail "runtime=docker requires Compose infra (remove --skip-infra / use --role server)"
  fi

  INSTALL_RUNTIME="${resolved}"
  export INSTALL_RUNTIME
  ensure_state_dir
  mark_stage "runtime" "${INSTALL_RUNTIME}"
  ok "Install runtime: ${INSTALL_RUNTIME}"
}

# Resolve ASTLOOM_DATA_ROOT (sibling <install>-data by default).
# Prompt only for server/both when interactive; --data-root / env / persisted win.
# Persists data_root=<path> in install-state.env.
prompt_install_data_root() {
  local default_root="$1"
  local choice=""
  banner "Choose durable data directory"
  cat >&2 <<EOF
  Postgres, Neo4j, usage logs, and caches live here
  (not inside the code tree).

  Default: ${default_root}

  Tip: non-interactive — --data-root /path  or  ASTLOOM_DATA_ROOT=/path
EOF
  choice="$(install_read_line "Data root [Enter = default]: ")"
  choice="$(install_stdout_token "${choice}")"
  if [[ -z "${choice}" ]]; then
    printf '%s\n' "${default_root}"
  else
    printf '%s\n' "${choice}"
  fi
}

normalize_data_root_path() {
  local raw="${1:-}"
  raw="$(install_stdout_token "${raw}")"
  [[ -n "${raw}" ]] || return 1
  # Expand leading ~ ; require absolute after that.
  if [[ "${raw}" == "~"* ]]; then
    raw="${HOME}${raw:1}"
  fi
  if [[ "${raw}" != /* ]]; then
    raw="$(pwd)/${raw}"
  fi
  # Collapse . / .. without requiring the path to exist yet.
  (cd "$(dirname "${raw}")" 2>/dev/null && printf '%s/%s\n' "$(pwd)" "$(basename "${raw}")") \
    || printf '%s\n' "${raw}"
}

resolve_install_data_root() {
  local resolved=""
  local persisted=""
  local default_root
  local raw="${ASTLOOM_DATA_ROOT:-}"

  default_root="$(default_astloom_data_root)"

  if [[ "${INSTALL_ROLE:-}" == "client" || "${INSTALL_SKIP_INFRA}" == "1" ]]; then
    info "Data root skipped (client / --skip-infra — no local Compose stores)"
    return 0
  fi

  if [[ -n "${raw}" ]]; then
    raw="$(install_stdout_token "${raw}")"
    if resolved="$(normalize_data_root_path "${raw}" 2>/dev/null)"; then
      :
    else
      warn "Ignoring invalid ASTLOOM_DATA_ROOT='${raw}'"
      ASTLOOM_DATA_ROOT=""
      export ASTLOOM_DATA_ROOT
      resolved=""
    fi
  fi

  if [[ -n "${resolved}" ]]; then
    :
  elif [[ -f "${INSTALL_STATE_FILE}" ]]; then
    persisted="$(install_stdout_token "$(env_key_value "${INSTALL_STATE_FILE}" "data_root" || true)")"
    if [[ -n "${persisted}" ]] && resolved="$(normalize_data_root_path "${persisted}" 2>/dev/null)"; then
      info "Using persisted data_root=${resolved}"
    else
      resolved=""
    fi
  fi

  if [[ -n "${resolved}" ]]; then
    :
  elif install_can_prompt; then
    resolved="$(install_stdout_token "$(prompt_install_data_root "${default_root}")")"
    resolved="$(normalize_data_root_path "${resolved}" || true)"
    [[ -n "${resolved}" ]] || fail "invalid data root path"
  else
    resolved="${default_root}"
    info "Non-interactive install: default data root=${resolved} (pass --data-root to override)"
  fi

  ASTLOOM_DATA_ROOT="${resolved}"
  export ASTLOOM_DATA_ROOT
  ensure_state_dir
  mark_stage "data_root" "${ASTLOOM_DATA_ROOT}"
  ensure_astloom_data_root
  ok "Data root: ${ASTLOOM_DATA_ROOT}"
}

# ---------------------------------------------------------------------------
# Server auth: JWT signing secret + bootstrap (always ensure); optional API key
# ---------------------------------------------------------------------------
# INSTALL_MINT_API_KEY: unset=ask on interactive install; 0=no; 1=yes
# Upgrade never mints unless INSTALL_MINT_API_KEY=1 (or --mint-api-key).
INSTALL_MINT_API_KEY="${INSTALL_MINT_API_KEY:-}"
INSTALL_API_KEY_TTL_SECONDS="${INSTALL_API_KEY_TTL_SECONDS:-0}"
INSTALL_API_KEY_TENANT="${INSTALL_API_KEY_TENANT:-}"
INSTALL_API_KEY_WORKSPACE="${INSTALL_API_KEY_WORKSPACE:-}"
INSTALL_API_KEY_PROJECT="${INSTALL_API_KEY_PROJECT:-}"

prompt_mint_api_key() {
  local choice=""
  banner "Create an API access token (API key)?"
  cat >&2 <<'AUTHPROMPT'
  JWT signing secret and connect-bootstrap secret are created automatically
  (existing files are preserved on upgrade).

  An API key is a scoped Bearer (as1.*) for clients / HTTP APIs.
  ttl_seconds=0 means non-expiring.
  Tip: non-interactive — --mint-api-key / --no-mint-api-key
AUTHPROMPT
  while true; do
    choice="$(install_read_line 'Mint an API key now? [y/n]: ')"
    if normalized="$(normalize_yes_no "${choice}" 2>/dev/null)"; then
      printf '%s\n' "${normalized}"
      return 0
    fi
    warn "Type y/yes or n/no (no default)"
  done
}

prompt_api_key_scope_and_ttl() {
  local tenant workspace project ttl
  tenant="$(install_read_line "API key tenant_id [default: astloom]: ")"
  tenant="$(install_stdout_token "${tenant}")"
  [[ -n "${tenant}" ]] || tenant="astloom"
  workspace="$(install_read_line "API key workspace_id [default: dev]: ")"
  workspace="$(install_stdout_token "${workspace}")"
  [[ -n "${workspace}" ]] || workspace="dev"
  project="$(install_read_line "API key project_id [default: default]: ")"
  project="$(install_stdout_token "${project}")"
  [[ -n "${project}" ]] || project="default"
  ttl="$(install_read_line "API key ttl_seconds [default: 0 = non-expiring]: ")"
  ttl="$(install_stdout_token "${ttl}")"
  [[ -n "${ttl}" ]] || ttl="0"
  INSTALL_API_KEY_TENANT="${tenant}"
  INSTALL_API_KEY_WORKSPACE="${workspace}"
  INSTALL_API_KEY_PROJECT="${project}"
  INSTALL_API_KEY_TTL_SECONDS="${ttl}"
  export INSTALL_API_KEY_TENANT INSTALL_API_KEY_WORKSPACE INSTALL_API_KEY_PROJECT INSTALL_API_KEY_TTL_SECONDS
}

# Resolve whether to mint an API key. Sets INSTALL_MINT_API_KEY to 0 or 1.
resolve_install_api_key() {
  local role="${INSTALL_ROLE:-server}"
  local action="${INSTALL_ACTION:-install}"
  local choice=""

  if [[ "${role}" == "client" || "${INSTALL_SKIP_INFRA}" == "1" ]]; then
    INSTALL_MINT_API_KEY=0
    export INSTALL_MINT_API_KEY
    return 0
  fi

  if [[ "${INSTALL_MINT_API_KEY}" == "1" || "${INSTALL_MINT_API_KEY}" == "0" ]]; then
    export INSTALL_MINT_API_KEY
    if [[ "${INSTALL_MINT_API_KEY}" == "1" ]]; then
      [[ -n "${INSTALL_API_KEY_TENANT}" ]] || INSTALL_API_KEY_TENANT="astloom"
      [[ -n "${INSTALL_API_KEY_WORKSPACE}" ]] || INSTALL_API_KEY_WORKSPACE="dev"
      [[ -n "${INSTALL_API_KEY_PROJECT}" ]] || INSTALL_API_KEY_PROJECT="default"
      [[ -n "${INSTALL_API_KEY_TTL_SECONDS}" ]] || INSTALL_API_KEY_TTL_SECONDS="0"
      export INSTALL_API_KEY_TENANT INSTALL_API_KEY_WORKSPACE INSTALL_API_KEY_PROJECT INSTALL_API_KEY_TTL_SECONDS
    fi
    ok "API key mint: $([[ "${INSTALL_MINT_API_KEY}" == "1" ]] && echo yes || echo no)"
    return 0
  fi

  # Upgrade: preserve — do not mint unless explicitly requested.
  if [[ "${action}" == "upgrade" ]]; then
    INSTALL_MINT_API_KEY=0
    export INSTALL_MINT_API_KEY
    info "Upgrade: preserving auth secrets; API key mint skipped (pass --mint-api-key to create one)"
    return 0
  fi

  if install_can_prompt && [[ "${INSTALL_NONINTERACTIVE}" != "1" ]]; then
    choice="$(prompt_mint_api_key)"
    if [[ "${choice}" == "yes" ]]; then
      INSTALL_MINT_API_KEY=1
      prompt_api_key_scope_and_ttl
    else
      INSTALL_MINT_API_KEY=0
    fi
  else
    INSTALL_MINT_API_KEY=0
    info "Non-interactive install: skipping API key mint (pass --mint-api-key to create one)"
  fi
  export INSTALL_MINT_API_KEY
  ok "API key mint: $([[ "${INSTALL_MINT_API_KEY}" == "1" ]] && echo yes || echo no)"
}

ensure_server_auth_secrets_py() {
  local py="${ASTLOOM_ROOT}/${ASTLOOM_VENV_DIR:-.venv}/bin/python"
  [[ -x "${py}" ]] || fail "venv python missing for auth secrets (${py})"
  info "Ensuring JWT signing + connect-bootstrap secrets (preserve if present)…"
  ASTLOOM_ROOT="${ASTLOOM_ROOT}" "${py}" - <<'PYAUTH'
import json, os
from pathlib import Path
from astloom_cli.install_auth import ensure_server_auth_secrets, print_auth_summary
root = Path(os.environ["ASTLOOM_ROOT"])
report = ensure_server_auth_secrets(root)
print_auth_summary(report)
print(json.dumps({"ok": True, "jwt_action": report["jwt"]["action"], "bootstrap_action": report["bootstrap"]["action"]}))
PYAUTH
}

mint_install_api_key_py() {
  local py="${ASTLOOM_ROOT}/${ASTLOOM_VENV_DIR:-.venv}/bin/python"
  local tenant="${INSTALL_API_KEY_TENANT:-astloom}"
  local workspace="${INSTALL_API_KEY_WORKSPACE:-dev}"
  local project="${INSTALL_API_KEY_PROJECT:-default}"
  local ttl="${INSTALL_API_KEY_TTL_SECONDS:-0}"
  [[ -x "${py}" ]] || fail "venv python missing for API key mint (${py})"
  info "Minting scoped API key (ttl_seconds=${ttl})…"
  ASTLOOM_ROOT="${ASTLOOM_ROOT}" \
  INSTALL_API_KEY_TENANT="${tenant}" \
  INSTALL_API_KEY_WORKSPACE="${workspace}" \
  INSTALL_API_KEY_PROJECT="${project}" \
  INSTALL_API_KEY_TTL_SECONDS="${ttl}" \
  "${py}" - <<'PYMINT'
import json, os
from pathlib import Path
from astloom_cli.install_auth import mint_install_api_key, print_auth_summary, ensure_server_auth_secrets
root = Path(os.environ["ASTLOOM_ROOT"])
report = ensure_server_auth_secrets(root)
mint = mint_install_api_key(
    root,
    tenant_id=os.environ["INSTALL_API_KEY_TENANT"],
    workspace_id=os.environ["INSTALL_API_KEY_WORKSPACE"],
    project_id=os.environ["INSTALL_API_KEY_PROJECT"],
    ttl_seconds=int(os.environ["INSTALL_API_KEY_TTL_SECONDS"]),
)
print_auth_summary(report, mint=mint)
print(json.dumps({"ok": True, "token_id": mint["token_id"], "expires_in": mint["expires_in"], "registry": mint["registry"]}))
PYMINT
}

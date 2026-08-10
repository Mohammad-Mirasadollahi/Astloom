# Stage 01: system prerequisites (Python 3.12+, curl, git; Docker only for server).
# shellcheck shell=bash

stage_01_prerequisites_check() {
  local errors=0
  local py

  if ! py="$(python_bin)"; then
    warn "Python 3.12+ not found on PATH"
    errors=1
  else
    ok "Python: $(${py} --version 2>&1)"
    if ! python_ensurepip_ok "${py}"; then
      warn "Python venv support missing (ensurepip) — install python3.12-venv"
      errors=1
    else
      ok "Python ensurepip/venv available"
    fi
  fi

  if ! have_cmd curl; then
    warn "curl missing"
    errors=1
  else
    ok "curl: $(curl --version | head -1)"
  fi

  if ! have_cmd git; then
    warn "git missing"
    errors=1
  else
    ok "git: $(git --version)"
  fi

  if [[ "${INSTALL_SKIP_INFRA}" == "1" ]]; then
    ok "Docker checks skipped (client / --skip-infra)"
  else
    if ! have_cmd docker; then
      warn "docker missing"
      errors=1
    else
      ok "docker: $(docker --version 2>&1)"
      if ! docker info >/dev/null 2>&1; then
        warn "docker daemon not reachable (start Docker or add your user to the docker group)"
        errors=1
      else
        ok "docker daemon reachable"
      fi
    fi

    if ! have_cmd docker || ! docker compose version >/dev/null 2>&1; then
      warn "docker compose plugin missing"
      errors=1
    else
      ok "compose: $(docker compose version 2>&1 | head -1)"
    fi
  fi

  if [[ "${INSTALL_WITH_FRONTEND}" == "1" ]]; then
    local major=0
    if have_cmd node; then
      major="$(node --version | sed 's/^v//' | cut -d. -f1)"
    fi
    if [[ "${major}" -lt 18 ]]; then
      warn "Node.js 18+ required for frontend (found: ${major:-none})"
      errors=1
    else
      ok "node: $(node --version) npm: $(npm --version 2>/dev/null || echo missing)"
    fi
  fi

  return "${errors}"
}

_stage_01_install_node20() {
  local major=0
  if have_cmd node; then
    major="$(node --version | sed 's/^v//' | cut -d. -f1)"
  fi
  [[ "${major}" -ge 18 ]] && return 0

  info "Installing Node.js 20.x (NodeSource)…"
  as_root apt-get install -y ca-certificates curl gnupg
  local tmp
  tmp="$(mktemp -d)"
  curl -fsSL https://deb.nodesource.com/setup_20.x -o "${tmp}/nodesource-setup.sh"
  as_root bash "${tmp}/nodesource-setup.sh"
  rm -rf "${tmp}"
  as_root apt-get install -y nodejs
}

_stage_01_ensure_python312() {
  local py=""
  # Python may already be on PATH while ensurepip (python3.12-venv) is still missing.
  if py="$(python_bin 2>/dev/null)" && python_ensurepip_ok "${py}"; then
    return 0
  fi
  info "Installing Python 3.12 + venv…"
  if ! as_root apt-get install -y python3.12 python3.12-venv python3.12-dev; then
    if grep -q 'VERSION_ID="22.04"' /etc/os-release 2>/dev/null; then
      info "Ubuntu 22.04: enabling deadsnakes PPA for Python 3.12…"
      as_root apt-get install -y software-properties-common
      as_root add-apt-repository -y ppa:deadsnakes/ppa
      as_root apt-get update
      as_root apt-get install -y python3.12 python3.12-venv python3.12-dev
    fi
  fi
  py="$(python_bin)" || fail "Python 3.12+ still missing after apt install"
  python_ensurepip_ok "${py}" || fail "Python ensurepip still missing after apt install (need python3.12-venv)"
}

stage_01_prerequisites_run() {
  banner "Stage 01/06 — System prerequisites"

  if [[ "${INSTALL_SKIP_PREREQS}" == "1" ]]; then
    info "Skipping prerequisite install (--skip-prerequisites)"
    stage_01_prerequisites_check || fail "prerequisites check failed; remove --skip-prerequisites or install missing tools"
    mark_stage "01_prerequisites" "ok"
    return 0
  fi

  if [[ "${INSTALL_CHECK_ONLY}" == "1" ]]; then
    stage_01_prerequisites_check || fail "prerequisites check failed"
    mark_stage "01_prerequisites" "checked"
    return 0
  fi

  if stage_01_prerequisites_check; then
    ok "Prerequisites already satisfied"
    mark_stage "01_prerequisites" "ok"
    return 0
  fi

  if ! linux_debian_family; then
    if [[ "${INSTALL_SKIP_INFRA}" == "1" ]]; then
      cat >&2 <<'EOF'
FAIL: automatic OS package install supports Debian/Ubuntu (apt) only.

Install manually, then re-run (client / --skip-infra):
  - Python 3.12+ with venv module
  - curl, git, ca-certificates
EOF
    else
      cat >&2 <<'EOF'
FAIL: automatic OS package install supports Debian/Ubuntu (apt) only.

Install manually, then re-run:
  - Python 3.12+ with venv module
  - curl, git, ca-certificates
  - Docker Engine + Docker Compose v2 plugin
  - (optional) Node.js 18+ if you pass --with-frontend
EOF
    fi
    fail "unsupported OS for auto prerequisite install"
  fi

  info "Installing missing OS packages via apt…"
  as_root apt-get update
  as_root apt-get install -y ca-certificates curl git openssl
  _stage_01_ensure_python312

  # Client / --skip-infra: CLI + venv only — never install or start Docker.
  if [[ "${INSTALL_SKIP_INFRA}" != "1" ]]; then
    if ! have_cmd docker || ! docker compose version >/dev/null 2>&1; then
      info "Installing Docker Engine + Compose plugin…"
      as_root apt-get install -y docker.io docker-compose-v2
    fi

    if have_cmd docker; then
      as_root systemctl enable --now docker 2>/dev/null \
        || as_root service docker start 2>/dev/null \
        || true
    fi

    # Non-root users need docker group for daemon access without sudo.
    if [[ "${EUID:-$(id -u)}" -ne 0 ]] && have_cmd docker; then
      if ! groups | grep -qw docker; then
        info "Adding ${USER} to docker group (re-login may be required)…"
        as_root usermod -aG docker "${USER}" || true
        warn "If docker still fails, log out and back in (or run: newgrp docker)"
      fi
    fi
  else
    info "Skipping Docker Engine install (client / --skip-infra)"
  fi

  if [[ "${INSTALL_WITH_FRONTEND}" == "1" ]]; then
    _stage_01_install_node20
  fi

  stage_01_prerequisites_check || fail "prerequisites still failing after install"
  mark_stage "01_prerequisites" "ok"
  ok "Stage 01 complete"
}

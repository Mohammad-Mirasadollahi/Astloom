#!/usr/bin/env bash
# Astloom one-command modular installer (beginner-safe, resumable, checkable).
#
# Usage:
#   # Empty machine (recommended one-liner):
#   curl -fsSL https://raw.githubusercontent.com/Mohammad-Mirasadollahi/Astloom/refs/heads/main/scripts/get-astloom.sh | bash
#   bash install.sh
#   bash install.sh --role server --runtime venv
#   bash install.sh --role server --runtime docker
#   bash install.sh --role server --data-root /srv/astloom-data
#   bash install.sh --role client
#   bash install.sh --role both --runtime venv
#   bash install.sh --non-interactive --role server --runtime venv
#   bash install.sh --upgrade
#   bash install.sh --check
#   bash install.sh --prerequisites-only
#   bash install.sh --skip-infra
#   bash install.sh --with-frontend
#   bash install.sh --with-ai-toolstack
#   bash install.sh --stage 02_venv
#   bash install.sh --list-stages
#
# Docs:
#   docs/08-software-engineering-architecture/39-local-install-runbook.md
#   docs/08-software-engineering-architecture/43-app-docker-and-wheelhouse-runbook.md
#   docs/08-software-engineering-architecture/51-software-upgrade-server-and-client.md
# Fetch helper: scripts/get-astloom.sh (release vs main from GitHub)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="${ROOT}/scripts/install"

if [[ ! -f "${LIB}/load.sh" ]]; then
  echo "install.sh: missing ${LIB}/load.sh — incomplete checkout?" >&2
  exit 1
fi

export ASTLOOM_ROOT="${ROOT}"
export ASTLOOM_INSTALL_LIB="${LIB}"
export PATH="${HOME}/.local/bin:${PATH}"

MODE="all"
STAGE_NAME=""

usage() {
  cat <<'EOF'
Astloom installer — modular local-dev bootstrap

Empty machine (fetch from GitHub, then this installer):
  curl -fsSL https://raw.githubusercontent.com/Mohammad-Mirasadollahi/Astloom/refs/heads/main/scripts/get-astloom.sh | bash
  # prompts: release (latest GitHub Release) or main (tip of main), then install.sh menus

Already cloned — from the repository root:
  bash install.sh [options]

Options:
  --role ROLE             client | server | both (skips role prompt)
  --runtime MODE          SERVER MCP mode: venv | docker (alias: host→venv)
  --data-root PATH        Durable data dir (Postgres/Neo4j/usage/…); default <install>-data
  --non-interactive       No prompts; default action=install, role=server, runtime=venv
  --yes, -y               Skip the interactive y/n confirmation
  --upgrade               Upgrade existing install (still asks y/n unless --yes/--non-interactive)
  --check                 Verify stages only (no installs / no compose changes)
  --prerequisites-only    Install/check OS deps (Python, Docker, curl, git) then exit
  --skip-prerequisites    Do not apt-install (non-interactive/CI only; ignored interactively)
  --skip-infra            Client shortcut: same as --role client (skip Compose + MCP bring-up)
  --with-frontend         Also ensure Node.js 18+ (for frontend/)
  --with-ai-toolstack     After verify, run ai-toolstack/scripts/install-astloom.sh
  --stage NAME            Run a single stage (see --list-stages)
  --list-stages           Print stage names and exit
  --compose-timeout SEC   Health wait timeout (default 180)
  --mint-api-key          After server bring-up, mint a scoped API key (as1.*)
  --no-mint-api-key       Do not mint an API key (default for non-interactive)
  --api-key-ttl SEC       API key ttl_seconds (default 0 = non-expiring)
  --api-key-tenant ID     API key tenant_id (default astloom)
  --api-key-workspace ID  API key workspace_id (default dev)
  --api-key-project ID    API key project_id (default default)
  -h, --help              Show this help

Interactive (TTY, no flags):
  1) install or upgrade? (no default — choose 1 or 2)
  2) confirm with y/yes or n/no (no default)
  3) if install → client, server, or both? (no default)
  4) if server/both → venv or docker MCP? (no default)
  5) if server/both → data root path (Enter = sibling <install>-data)
  6) if server/both install → mint API key? y/n (JWT+bootstrap secrets always auto-created;
     upgrade preserves existing secrets and skips API key mint unless --mint-api-key)

Roles:
  client  Coding-agent machine: CLI + .venv only; then run astloom connect
  server  Astloom platform: Compose Postgres/Neo4j + MCP
  both    Same-host dogfood: server stack + local sync AND IDE connect (client tooling)

SERVER MCP modes (infra always Compose; used by server and both):
  venv    MCP HTTP from this machine's Python .venv (recommended; was formerly "host")
  docker  MCP HTTP in mcp-gateway container

Default flow (all stages):
  01_prerequisites → 02_venv → 03_compose_env → 04_docker_infra → 05_verify → 06_runtime_bringup
  (client role skips compose/infra/bring-up stages that respect --skip-infra)

Upgrade flow (--upgrade or interactive choice "upgrade"):
  confirm yes → backup install-state → same stages → astloom upgrade finalize

EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --runtime)
      [[ $# -ge 2 ]] || { echo "error: --runtime needs venv|docker (alias: host)" >&2; exit 64; }
      export INSTALL_RUNTIME="$2"
      shift 2
      ;;
    --role)
      [[ $# -ge 2 ]] || { echo "error: --role needs client|server|both" >&2; exit 64; }
      export INSTALL_ROLE="$2"
      shift 2
      ;;
    --data-root)
      [[ $# -ge 2 ]] || { echo "error: --data-root needs a path" >&2; exit 64; }
      export ASTLOOM_DATA_ROOT="$2"
      shift 2
      ;;
    --upgrade)
      MODE="upgrade"
      shift
      ;;
    --yes|-y)
      export INSTALL_ASSUME_YES=1
      shift
      ;;
    --check)
      export INSTALL_CHECK_ONLY=1
      shift
      ;;
    --prerequisites-only)
      MODE="prerequisites-only"
      shift
      ;;
    --skip-prerequisites)
      export INSTALL_SKIP_PREREQS=1
      shift
      ;;
    --skip-infra)
      export INSTALL_SKIP_INFRA=1
      shift
      ;;
    --with-frontend)
      export INSTALL_WITH_FRONTEND=1
      shift
      ;;
    --with-ai-toolstack)
      export INSTALL_WITH_AI_TOOLSTACK=1
      shift
      ;;
    --stage)
      [[ $# -ge 2 ]] || { echo "error: --stage needs a name" >&2; exit 64; }
      MODE="stage"
      STAGE_NAME="$2"
      shift 2
      ;;
    --list-stages)
      MODE="list"
      shift
      ;;
    --compose-timeout)
      [[ $# -ge 2 ]] || { echo "error: --compose-timeout needs seconds" >&2; exit 64; }
      export INSTALL_COMPOSE_TIMEOUT="$2"
      shift 2
      ;;
    --non-interactive)
      export INSTALL_NONINTERACTIVE=1
      shift
      ;;
    --mint-api-key)
      export INSTALL_MINT_API_KEY=1
      shift
      ;;
    --no-mint-api-key)
      export INSTALL_MINT_API_KEY=0
      shift
      ;;
    --api-key-ttl)
      [[ $# -ge 2 ]] || { echo "error: --api-key-ttl needs seconds (>=0; 0=non-expiring)" >&2; exit 64; }
      export INSTALL_API_KEY_TTL_SECONDS="$2"
      shift 2
      ;;
    --api-key-tenant)
      [[ $# -ge 2 ]] || { echo "error: --api-key-tenant needs an id" >&2; exit 64; }
      export INSTALL_API_KEY_TENANT="$2"
      shift 2
      ;;
    --api-key-workspace)
      [[ $# -ge 2 ]] || { echo "error: --api-key-workspace needs an id" >&2; exit 64; }
      export INSTALL_API_KEY_WORKSPACE="$2"
      shift 2
      ;;
    --api-key-project)
      [[ $# -ge 2 ]] || { echo "error: --api-key-project needs an id" >&2; exit 64; }
      export INSTALL_API_KEY_PROJECT="$2"
      shift 2
      ;;
    *)
      echo "error: unknown option: $1 (try --help)" >&2
      exit 64
      ;;
    esac
done

# Client never needs Compose/Docker — set before any stage (including --stage / prerequisites-only).
case "${INSTALL_ROLE:-}" in
  client | CLIENT)
    export INSTALL_SKIP_INFRA=1
    ;;
esac

# shellcheck source=scripts/install/load.sh
source "${LIB}/load.sh"
install_main "${MODE}" "${STAGE_NAME}"

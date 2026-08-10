#!/usr/bin/env bash
# Astloom one-line bootstrap: fetch from GitHub, then run install.sh.
#
# Empty machine:
#   curl -fsSL https://raw.githubusercontent.com/Mohammad-Mirasadollahi/Astloom/refs/heads/main/scripts/get-astloom.sh | bash
# Prefer refs/heads/main over /main/ — GitHub raw CDN often serves a stale /main/ tip.
#
# Channels:
#   release — latest GitHub Release (immutable tag + source tarball)
#   main    — tip of the default branch (may be unreleased)
#
# Env overrides:
#   ASTLOOM_ROOT          Install directory (default /opt/Astloom)
#   ASTLOOM_CHANNEL       release | main
#   ASTLOOM_GIT_HTTPS     Clone URL (default fixed public repo)
#   ASTLOOM_SKIP_INSTALL  1 = fetch only (tests / dry fetch)
#   ASTLOOM_CURL          curl binary (tests)
#   GITHUB_TOKEN            Optional; sent as Authorization for API/git over HTTPS
#
# shellcheck shell=bash
set -euo pipefail

ASTLOOM_REPO_SLUG="${ASTLOOM_REPO_SLUG:-Mohammad-Mirasadollahi/Astloom}"
ASTLOOM_GIT_HTTPS="${ASTLOOM_GIT_HTTPS:-https://github.com/${ASTLOOM_REPO_SLUG}.git}"
ASTLOOM_GITHUB_API="${ASTLOOM_GITHUB_API:-https://api.github.com/repos/${ASTLOOM_REPO_SLUG}}"
ASTLOOM_CODELOAD="${ASTLOOM_CODELOAD:-https://codeload.github.com/${ASTLOOM_REPO_SLUG}}"
ASTLOOM_DEFAULT_ROOT="${ASTLOOM_DEFAULT_ROOT:-/opt/Astloom}"
ASTLOOM_DEFAULT_BRANCH="${ASTLOOM_DEFAULT_BRANCH:-main}"

CURL_BIN="${ASTLOOM_CURL:-curl}"

log() { printf '[astloom-get] %s\n' "$*" >&2; }
info() { log "INFO  $*"; }
ok() { log "OK    $*"; }
warn() { log "WARN  $*" >&2; }
fail() {
  log "FAIL  $*" >&2
  exit 1
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

require_cmds() {
  local missing=()
  local c
  for c in "$@"; do
    have_cmd "${c}" || missing+=("${c}")
  done
  if ((${#missing[@]})); then
    fail "missing required commands: ${missing[*]}"
  fi
}

curl_github() {
  local url="$1"
  shift
  local args=(-fsSL)
  if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    args+=(-H "Authorization: Bearer ${GITHUB_TOKEN}" -H "X-GitHub-Api-Version: 2022-11-28")
  fi
  args+=(-H "Accept: application/vnd.github+json")
  "${CURL_BIN}" "${args[@]}" "$@" "${url}"
}

# Like curl_github but does not fail on HTTP errors (caller checks body / exit).
curl_github_soft() {
  local url="$1"
  shift
  local args=(-sSL)
  if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    args+=(-H "Authorization: Bearer ${GITHUB_TOKEN}" -H "X-GitHub-Api-Version: 2022-11-28")
  fi
  args+=(-H "Accept: application/vnd.github+json")
  "${CURL_BIN}" "${args[@]}" "$@" "${url}" || true
}

parse_json_field() {
  local json="$1"
  local field="$2"
  if have_cmd python3; then
    printf '%s' "${json}" | python3 -c "import json,sys
raw=sys.stdin.read().strip()
if not raw:
  raise SystemExit(0)
data=json.loads(raw)
if isinstance(data, dict):
  print(data.get('${field}') or '')
elif isinstance(data, list) and data and isinstance(data[0], dict):
  print(data[0].get('${field}') or '')
"
  else
    printf '%s' "${json}" | sed -n "s/.*\"${field}\"[[:space:]]*:[[:space:]]*\"\\([^\"]*\\)\".*/\\1/p" | head -n1
  fi
}

latest_release_tag() {
  local json tag
  json="$(curl_github_soft "${ASTLOOM_GITHUB_API}/releases/latest")"
  tag="$(parse_json_field "${json}" tag_name)"
  if [[ -n "${tag}" ]]; then
    printf '%s\n' "${tag}"
    return 0
  fi
  warn "No GitHub Release found; falling back to newest git tag"
  json="$(curl_github_soft "${ASTLOOM_GITHUB_API}/tags?per_page=1")"
  tag="$(parse_json_field "${json}" name)"
  if [[ -n "${tag}" ]]; then
    printf '%s\n' "${tag}"
    return 0
  fi
  return 1
}

normalize_channel() {
  local raw="${1:-}"
  case "${raw}" in
    release | stable | latest-release) printf '%s\n' release ;;
    main | edge | tip | latest) printf '%s\n' main ;;
    *) return 1 ;;
  esac
}

# curl|bash leaves stdin as the script pipe (not a TTY). Prompt via /dev/tty instead.
can_prompt() {
  if [[ "${ASTLOOM_NONINTERACTIVE:-0}" == "1" ]]; then
    return 1
  fi
  if [[ -t 0 ]]; then
    return 0
  fi
  # Path may exist while open fails (non-interactive CI / no controlling terminal).
  if { true <>/dev/tty; } 2>/dev/null; then
    return 0
  fi
  return 1
}

# Read one line from the operator (stdin TTY, or /dev/tty when piped).
read_prompt() {
  local prompt="$1"
  local ans=""
  if [[ -t 0 ]]; then
    read -r -p "${prompt}" ans || true
  elif { true <>/dev/tty; } 2>/dev/null; then
    # Prompt on the real terminal; do not consume the curl|bash script pipe.
    printf '%s' "${prompt}" >/dev/tty 2>/dev/null || true
    read -r ans </dev/tty 2>/dev/null || true
    printf '\n' >/dev/tty 2>/dev/null || true
  else
    fail "cannot prompt (no TTY); pass --channel release|main and optional --root"
  fi
  printf '%s\n' "${ans}"
}

prompt_channel() {
  if [[ -n "${ASTLOOM_CHANNEL:-}" ]]; then
    normalize_channel "${ASTLOOM_CHANNEL}" || fail "invalid ASTLOOM_CHANNEL=${ASTLOOM_CHANNEL} (use release|main)"
    return 0
  fi
  if ! can_prompt; then
    fail "non-interactive: pass --channel release|main (or ASTLOOM_CHANNEL)"
  fi
  echo >&2
  echo "Fetch channel:" >&2
  echo "  1) release  — latest GitHub Release (or newest tag if none)" >&2
  echo "  2) main     — latest commits on ${ASTLOOM_DEFAULT_BRANCH} (may be unreleased)" >&2
  local ans=""
  while true; do
    ans="$(read_prompt "Choose [1/2]: ")"
    case "${ans}" in
      1 | release | r | R) printf '%s\n' release; return 0 ;;
      2 | main | m | M) printf '%s\n' main; return 0 ;;
      "")
        echo "Choose 1 or 2 (no default)" >&2
        ;;
      *)
        if normalize_channel "${ans}" >/dev/null 2>&1; then
          normalize_channel "${ans}"
          return 0
        fi
        echo "Enter 1/release or 2/main" >&2
        ;;
    esac
  done
}

prompt_root() {
  # Local CLI checkout only. Never ask interactively — operators override with
  # --root or ASTLOOM_ROOT. The Astloom path *on the server* is discovered
  # later by `astloom connect` (install-root markers), not here.
  local root="${ASTLOOM_ROOT:-${ASTLOOM_DEFAULT_ROOT}}"
  printf '%s\n' "${root}"
}

is_astloom_git_checkout() {
  local root="$1"
  [[ -d "${root}/.git" ]] || return 1
  local url
  url="$(git -C "${root}" remote get-url origin 2>/dev/null || true)"
  [[ -n "${url}" ]] || return 1
  case "${url}" in
    *"${ASTLOOM_REPO_SLUG}"* | *"${ASTLOOM_REPO_SLUG%.git}"*) return 0 ;;
    *) return 1 ;;
  esac
}

preserve_paths() {
  cat <<'EOF'
.astloom
.env
.venv
astloom.sync.yaml
backend/deployments/compose/.env.local
EOF
}

sync_tree_preserving() {
  local staging="$1"
  local root="$2"
  mkdir -p "${root}"

  if have_cmd rsync; then
    local excludes=()
    local p
    while IFS= read -r p; do
      [[ -n "${p}" ]] || continue
      excludes+=(--exclude "${p}")
    done < <(preserve_paths)
    rsync -a --delete "${excludes[@]}" "${staging}/" "${root}/"
    return 0
  fi

  # Fallback without rsync: copy staging over root while skipping preserve paths.
  local tmp_keep
  tmp_keep="$(mktemp -d)"
  while IFS= read -r p; do
    [[ -n "${p}" ]] || continue
    if [[ -e "${root}/${p}" ]]; then
      mkdir -p "${tmp_keep}/$(dirname "${p}")"
      mv "${root}/${p}" "${tmp_keep}/${p}"
    fi
  done < <(preserve_paths)

  # Wipe root contents then move staging in.
  find "${root}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  # shellcheck disable=SC2045
  for item in "${staging}"/* "${staging}"/.[!.]* "${staging}"/..?*; do
    [[ -e "${item}" ]] || continue
    mv "${item}" "${root}/"
  done

  while IFS= read -r p; do
    [[ -n "${p}" ]] || continue
    if [[ -e "${tmp_keep}/${p}" ]]; then
      mkdir -p "${root}/$(dirname "${p}")"
      rm -rf "${root}/${p}"
      mv "${tmp_keep}/${p}" "${root}/${p}"
    fi
  done < <(preserve_paths)
  rm -rf "${tmp_keep}"
}

fetch_release_into() {
  local root="$1"
  local tag tarball staging
  require_cmds "${CURL_BIN}" tar mktemp
  if ! tag="$(latest_release_tag)"; then
    warn "No GitHub Release/tag on ${ASTLOOM_REPO_SLUG}; using channel main instead"
    fetch_main_into "${root}"
    return 0
  fi
  info "Latest release tag: ${tag}"
  tarball="$(mktemp /tmp/astloom-release.XXXXXX)"
  staging="$(mktemp -d /tmp/astloom-stage.XXXXXX)"
  cleanup_release() {
    rm -rf "${staging}" "${tarball}"
  }
  trap cleanup_release EXIT

  info "Downloading source tarball for ${tag}"
  curl_github "${ASTLOOM_CODELOAD}/tar.gz/refs/tags/${tag}" -o "${tarball}"
  tar -xzf "${tarball}" -C "${staging}" --strip-components=1
  [[ -f "${staging}/install.sh" ]] || fail "tarball missing install.sh (bad extract?)"
  sync_tree_preserving "${staging}" "${root}"
  mkdir -p "${root}/.astloom"
  printf '%s\n' "${tag}" >"${root}/.astloom/fetched-release-tag"
  ok "Tree updated from release ${tag} → ${root}"
  trap - EXIT
  cleanup_release
}

# Drop local setuptools dirt after editable installs.
# Does not touch operator state (.astloom, .env, compose .env.local, …).
discard_generated_checkout_dirt() {
  local root="$1"
  local dir
  [[ -d "${root}/.git" ]] || return 0

  while IFS= read -r dir; do
    [[ -n "${dir}" ]] || continue
    # Reset tracked copies first (channel sync may delete them once clean).
    git -C "${root}" checkout -- "${dir}" >/dev/null 2>&1 || true
    git -C "${root}" clean -fd -- "${dir}" >/dev/null 2>&1 || true
    rm -rf "${dir}"
  done < <(find "${root}" -type d -name '*.egg-info' ! -path '*/.git/*' 2>/dev/null)

  # Any remaining modified tracked egg-info paths.
  while IFS= read -r dir; do
    [[ -n "${dir}" ]] || continue
    git -C "${root}" checkout -- "${dir}" >/dev/null 2>&1 || true
  done < <(git -C "${root}" diff --name-only --diff-filter=M -- '*.egg-info/*' '**/*.egg-info/**' 2>/dev/null || true)
}

# Converge an existing Astloom git checkout to origin/<branch>.
# get/bootstrap applies the channel tip (same overwrite semantics as release
# tarball sync). Tracked local edits and non-ff local commits are discarded.
# Operator state in preserve_paths is gitignored / untracked and stays.
sync_git_checkout_to_origin() {
  local root="$1"
  local branch="$2"
  local tip="origin/${branch}"

  discard_generated_checkout_dirt "${root}"
  git -C "${root}" fetch --tags origin
  git -C "${root}" checkout "${branch}"

  if ! git -C "${root}" rev-parse --verify "${tip}" >/dev/null 2>&1; then
    fail "missing ${tip} after fetch"
  fi

  if ! git -C "${root}" diff-index --quiet HEAD -- 2>/dev/null; then
    warn "Discarding local tracked changes so ${branch} tip can apply (operator paths preserved)"
  elif [[ "$(git -C "${root}" rev-parse HEAD)" != "$(git -C "${root}" rev-parse "${tip}")" ]]; then
    # Ahead/behind or diverged: still converge; warn only when rewriting local commits.
    if [[ -n "$(git -C "${root}" rev-list --max-count=1 "${tip}..HEAD" 2>/dev/null || true)" ]]; then
      warn "Discarding local commits not on ${tip} so channel tip can apply"
    fi
  fi

  git -C "${root}" reset --hard "${tip}"
}

fetch_main_into() {
  local root="$1"
  require_cmds git
  if is_astloom_git_checkout "${root}"; then
    info "Updating existing git checkout at ${root}"
    sync_git_checkout_to_origin "${root}" "${ASTLOOM_DEFAULT_BRANCH}"
    ok "Synced ${ASTLOOM_DEFAULT_BRANCH} → ${root}"
    return 0
  fi

  if [[ -e "${root}" ]] && [[ -n "$(ls -A "${root}" 2>/dev/null || true)" ]]; then
    local staging
    staging="$(mktemp -d /tmp/astloom-clone.XXXXXX)"
    cleanup_clone() {
      rm -rf "${staging}"
    }
    trap cleanup_clone EXIT
    info "Cloning ${ASTLOOM_DEFAULT_BRANCH} into staging (preserving local state under ${root})"
    git clone --branch "${ASTLOOM_DEFAULT_BRANCH}" --depth 1 "${ASTLOOM_GIT_HTTPS}" "${staging}/repo"
    sync_tree_preserving "${staging}/repo" "${root}"
    ok "Synced ${ASTLOOM_DEFAULT_BRANCH} → ${root}"
    trap - EXIT
    cleanup_clone
    return 0
  fi

  mkdir -p "$(dirname "${root}")"
  info "Cloning ${ASTLOOM_GIT_HTTPS} (${ASTLOOM_DEFAULT_BRANCH}) → ${root}"
  git clone --branch "${ASTLOOM_DEFAULT_BRANCH}" --depth 1 "${ASTLOOM_GIT_HTTPS}" "${root}"
  ok "Cloned → ${root}"
}

run_install() {
  local root="$1"
  shift
  [[ -f "${root}/install.sh" ]] || fail "missing ${root}/install.sh after fetch"
  if [[ "${ASTLOOM_SKIP_INSTALL:-0}" == "1" ]]; then
    info "ASTLOOM_SKIP_INSTALL=1 — not running install.sh"
    return 0
  fi

  local args=()
  local has_yes=0
  local has_noninteractive=0
  local has_role=0
  local a
  for a in "$@"; do
    case "${a}" in
      --yes | -y) has_yes=1 ;;
      --non-interactive) has_noninteractive=1 ;;
      --role) has_role=1 ;;
    esac
    args+=("${a}")
  done
  # CLI --role means agent/CI: no menus. Also skip "type yes" (unattended).
  if [[ "${has_role}" == "1" && "${has_noninteractive}" != "1" ]]; then
    args=(--non-interactive "${args[@]}")
    has_noninteractive=1
  fi
  if [[ "${has_noninteractive}" == "1" && "${has_yes}" != "1" ]]; then
    args=(--yes "${args[@]}")
  fi

  info "Running: bash install.sh ${args[*]}"
  (cd "${root}" && bash install.sh "${args[@]}")
}

usage() {
  cat <<EOF
Astloom get/bootstrap — fetch from GitHub then run install.sh

Usage:
  curl -fsSL https://raw.githubusercontent.com/${ASTLOOM_REPO_SLUG}/refs/heads/main/scripts/get-astloom.sh | bash
  bash scripts/get-astloom.sh [get-options] [-- install.sh options...]

Get options:
  --channel release|main   Fetch channel (prompted on TTY if omitted)
  --root PATH              Local install directory (default ${ASTLOOM_DEFAULT_ROOT}; no prompt)
  --yes, -y                Skip install.sh "type yes" (also implied by --non-interactive / --role)
  --skip-install           Fetch only (do not run install.sh)
  -h, --help               Show this help

Any other flags are passed through to install.sh (--role, --runtime, --upgrade, …).
Passing --role enables --non-interactive and --yes (unattended). Interactive runs still ask
install/upgrade, type yes, then client/server/both (and server MCP mode).
Remote Astloom root on the server is not asked here — `astloom connect` discovers it.

Channels:
  release  Latest GitHub Release tag (immutable); recommended for servers
  main     Tip of ${ASTLOOM_DEFAULT_BRANCH} (may be unreleased)
EOF
}

parse_and_run() {
  local channel=""
  local root=""
  local assume_yes=0
  local skip_install=0
  local install_args=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h | --help)
        usage
        exit 0
        ;;
      --channel)
        [[ $# -ge 2 ]] || fail "--channel needs release|main"
        channel="$(normalize_channel "$2")" || fail "invalid --channel $2"
        shift 2
        ;;
      --root)
        [[ $# -ge 2 ]] || fail "--root needs a path"
        root="$2"
        shift 2
        ;;
      --yes | -y)
        assume_yes=1
        install_args+=(--yes)
        shift
        ;;
      --skip-install)
        skip_install=1
        shift
        ;;
      --)
        shift
        install_args+=("$@")
        break
        ;;
      *)
        install_args+=("$1")
        shift
        ;;
    esac
  done

  if [[ -n "${channel}" ]]; then
    ASTLOOM_CHANNEL="${channel}"
  fi
  if [[ -n "${root}" ]]; then
    ASTLOOM_ROOT="${root}"
  fi
  if [[ "${skip_install}" == "1" ]]; then
    ASTLOOM_SKIP_INSTALL=1
  fi
  if [[ "${assume_yes}" == "1" ]]; then
    export INSTALL_ASSUME_YES=1
  else
    # Do not inherit a stale INSTALL_ASSUME_YES from the operator environment.
    unset INSTALL_ASSUME_YES || true
  fi

  channel="$(prompt_channel)"
  root="$(prompt_root)"
  root="$(cd / && readlink -f "${root}" 2>/dev/null || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "${root}")"

  info "Channel=${channel}  root=${root}"
  mkdir -p "${root}"

  case "${channel}" in
    release) fetch_release_into "${root}" ;;
    main) fetch_main_into "${root}" ;;
    *) fail "internal: bad channel ${channel}" ;;
  esac

  run_install "${root}" "${install_args[@]+"${install_args[@]}"}"
}

# Allow unit tests to source helpers without executing main.
if [[ "${GET_ASTLOOM_LIB_ONLY:-0}" == "1" ]]; then
  return 0 2>/dev/null || exit 0
fi

parse_and_run "$@"

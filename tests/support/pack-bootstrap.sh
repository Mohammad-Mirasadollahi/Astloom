# shellcheck shell=bash
# Resolve hackathon pack root (archives/hackathon, legacy hackathon/, or standalone publish root) and load pack-env.
if [[ -n "${PACK_ROOT:-}" && -n "${PACK_PYTHON:-}" ]]; then
  return 0 2>/dev/null || true
fi

_bootstrap_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTS_ROOT="$(cd "${_bootstrap_dir}/.." && pwd)"
REPO_ROOT="$(cd "${TESTS_ROOT}/.." && pwd)"

_resolve_pack_root() {
  if [[ -f "${REPO_ROOT}/archives/hackathon/install.sh" && -f "${REPO_ROOT}/archives/hackathon/scripts/install.py" ]]; then
    echo "${REPO_ROOT}/archives/hackathon"
    return 0
  fi
  if [[ -f "${REPO_ROOT}/hackathon/install.sh" && -f "${REPO_ROOT}/hackathon/scripts/install.py" ]]; then
    echo "${REPO_ROOT}/hackathon"
    return 0
  fi
  if [[ -f "${REPO_ROOT}/install.sh" && -f "${REPO_ROOT}/scripts/install.py" ]]; then
    echo "${REPO_ROOT}"
    return 0
  fi
  echo "Cannot resolve hackathon pack (expected install.sh + scripts/install.py under ${REPO_ROOT}/archives/hackathon, ${REPO_ROOT}/hackathon, or ${REPO_ROOT})." >&2
  return 1
}

PACK_ROOT="$(_resolve_pack_root)" || exit 1
export PACK_ROOT
export TESTS_ROOT
export TESTS_E2E_CS="${TESTS_ROOT}/e2e/change-society"
export TESTS_LIVE_CS="${TESTS_ROOT}/live/change-society"
# shellcheck source=/dev/null
source "${PACK_ROOT}/scripts/pack-env.sh"

#!/usr/bin/env bash
# Create/refresh the Astloom project virtualenv, install deps + editable CLI,
# and put `astloom` on the user PATH (~/.local/bin).
#
# Override location with ASTLOOM_VENV_DIR (default: .venv). Isolated smoke uses
# .ac-venv to avoid Cursor sandbox read-only binds on paths named ".venv".
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

VENV_DIR="${ASTLOOM_VENV_DIR:-.venv}"
VENV_PATH="${ROOT}/${VENV_DIR}"

if ! python3 -m venv "${VENV_PATH}"; then
  echo "ERROR: failed to create ${VENV_PATH} (ensurepip / python3-venv missing?)" >&2
  echo "On Debian/Ubuntu: sudo apt install python3.12-venv" >&2
  exit 1
fi
"${VENV_PATH}/bin/python" -m pip install --upgrade pip
"${VENV_PATH}/bin/pip" install -r requirements-dev.txt
"${VENV_PATH}/bin/pip" install -e "${ROOT}"

echo "OK: ${VENV_PATH} ready"
"${VENV_PATH}/bin/python" -c "import fastapi,httpx,pytest,psycopg,astloom_cli,astloom_backup,usage_profile; print('imports ok')"

# Install CLI onto ~/.local/bin and optionally update shell rc for PATH.
SHELL_RC=""
if [[ -n "${ASTLOOM_SHELL_RC:-}" ]]; then
  SHELL_RC="${ASTLOOM_SHELL_RC}"
elif [[ "${SHELL:-}" == */zsh ]] && [[ -f "${HOME}/.zshrc" ]]; then
  SHELL_RC=".zshrc"
elif [[ -f "${HOME}/.bashrc" ]]; then
  SHELL_RC=".bashrc"
fi

PATH_ARGS=(path install)
if [[ -n "${SHELL_RC}" ]]; then
  PATH_ARGS+=(--shell-rc "${SHELL_RC}")
fi
"${VENV_PATH}/bin/astloom" "${PATH_ARGS[@]}"

echo
echo "Use: ${VENV_PATH}/bin/astloom --help"
echo "Or:  source ${VENV_PATH}/bin/activate && astloom --help"

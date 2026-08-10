#!/usr/bin/env bash
# Export packages from the Astloom .venv into a local wheelhouse under /opt.
#
# Usage (from repository root or anywhere):
#   bash scripts/build-wheelhouse.sh
#   ASTLOOM_WHEELHOUSE=/opt/astloom-wheelhouse bash scripts/build-wheelhouse.sh
#
# Default destination: /opt/astloom-wheelhouse
# Offline reinstall later:
#   pip install --no-index --find-links="$ASTLOOM_WHEELHOUSE" -r "$ASTLOOM_WHEELHOUSE/requirements.txt"
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ASTLOOM_VENV_DIR:-${ROOT}/.venv}"
WHEELHOUSE="${ASTLOOM_WHEELHOUSE:-/opt/astloom-wheelhouse}"
PIP="${VENV}/bin/pip"
PYTHON="${VENV}/bin/python"

if [[ ! -x "${PIP}" ]]; then
  echo "error: missing venv pip at ${PIP} (run install.sh / ensure-venv.sh first)" >&2
  exit 1
fi

mkdir -p "${WHEELHOUSE}"
REQS="${WHEELHOUSE}/requirements.txt"
META="${WHEELHOUSE}/MANIFEST.txt"

echo "[wheelhouse] root=${ROOT}"
echo "[wheelhouse] venv=${VENV}"
echo "[wheelhouse] dest=${WHEELHOUSE}"

# Freeze installed pins; drop editable/VCS lines (we build astloom from local source).
"${PIP}" freeze | grep -vE '^-e |@ git\+|@ file:|^astloom==' > "${REQS}.raw" || true
# Keep a clean requirements list for --no-index install (wheels only).
cp "${REQS}.raw" "${REQS}"

# Ensure wheel tooling is present in the venv (usually already is).
"${PIP}" install -q wheel packaging

echo "[wheelhouse] downloading/building wheels for frozen venv packages…"
# Prefer existing pip cache; allow public indexes only to materialize wheels already
# present in this venv (including torch CPU local version).
set +e
"${PIP}" download \
  --dest "${WHEELHOUSE}" \
  --requirement "${REQS}" \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  --timeout 120
DOWNLOAD_RC=$?
set -e
if [[ "${DOWNLOAD_RC}" -ne 0 ]]; then
  echo "[wheelhouse] batch download had failures; retrying per-package…"
  while IFS= read -r line; do
    [[ -z "${line}" || "${line}" == \#* ]] && continue
    echo "[wheelhouse]   → ${line}"
    set +e
    "${PIP}" download \
      --dest "${WHEELHOUSE}" \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      --timeout 120 \
      "${line}"
    rc=$?
    set -e
    if [[ "${rc}" -ne 0 ]]; then
      echo "[wheelhouse] WARN: could not fetch wheel for ${line}" >&2
    fi
  done < "${REQS}"
fi

echo "[wheelhouse] building local astloom wheel from ${ROOT}…"
"${PIP}" wheel --no-deps --wheel-dir "${WHEELHOUSE}" "${ROOT}"

# requirements for image install: frozen third-party + astloom (no VCS).
AC_VER="$(
  "${PYTHON}" -c "import tomllib; print(tomllib.load(open('${ROOT}/pyproject.toml','rb'))['project']['version'])"
)"
{
  grep -vE '^-e |@ git\+|@ file:|^astloom==' "${REQS}.raw" || true
  echo "astloom==${AC_VER}"
} > "${REQS}"

{
  echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "source_venv=${VENV}"
  echo "wheel_count=$(find "${WHEELHOUSE}" -maxdepth 1 -name '*.whl' | wc -l)"
  echo "requirements=${REQS}"
} > "${META}"

echo "[wheelhouse] OK: $(find "${WHEELHOUSE}" -maxdepth 1 -name '*.whl' | wc -l) wheels → ${WHEELHOUSE}"
cat "${META}"

#!/usr/bin/env bash
# Ensure TLS cert/key exist; export ASTLOOM_TLS_CERT and ASTLOOM_TLS_KEY.
# Source after setting ASTLOOM_DATA_ROOT (and optional ASTLOOM_PUBLIC_HOSTNAME).
# shellcheck shell=bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASTLOOM_ROOT="${ASTLOOM_ROOT:-$(cd "${SCRIPT_DIR}/../../.." && pwd)}"
PY="${ASTLOOM_ROOT}/${ASTLOOM_VENV_DIR:-.venv}/bin/python"

if [[ ! -x "${PY}" ]]; then
  printf '%s FAIL  missing venv python at %s (run install stage 02)\n' "[tls_edge]" "${PY}" >&2
  exit 1
fi

: "${ASTLOOM_DATA_ROOT:?ASTLOOM_DATA_ROOT must be set}"
export ASTLOOM_PUBLIC_HOSTNAME="${ASTLOOM_PUBLIC_HOSTNAME:-localhost}"

eval "$(
  ASTLOOM_DATA_ROOT="${ASTLOOM_DATA_ROOT}" \
  ASTLOOM_PUBLIC_HOSTNAME="${ASTLOOM_PUBLIC_HOSTNAME}" \
  "${PY}" -c '
import os
from pathlib import Path
from astloom_cli.tls_certs import ensure_tls_material

data_root = Path(os.environ["ASTLOOM_DATA_ROOT"])
hostname = os.environ.get("ASTLOOM_PUBLIC_HOSTNAME", "localhost")
material = ensure_tls_material(data_root=data_root, hostname=hostname)
print(f"export ASTLOOM_TLS_CERT={material.cert_path}")
print(f"export ASTLOOM_TLS_KEY={material.key_path}")
print(f"export ASTLOOM_TLS_GENERATED={1 if material.generated else 0}")
'
)"

printf '%s OK    hostname=%s cert=%s generated=%s\n' \
  "[tls_edge]" "${ASTLOOM_PUBLIC_HOSTNAME}" "${ASTLOOM_TLS_CERT}" "${ASTLOOM_TLS_GENERATED:-0}" >&2

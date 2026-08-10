#!/usr/bin/env bash
# Backend tests (pack-relative PYTHONPATH; avoids broken .venv/bin/pytest shebang on relocated trees).
set -euo pipefail
# shellcheck source=../../support/pack-bootstrap.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/support/pack-bootstrap.sh"

TEST_DIR="$(pack_pytest_dir)" || {
  echo "No tests/backend/legacy/change-society-service under ${PACK_ROOT} or parent." >&2
  exit 1
}

exec "$PACK_PYTHON" -m pytest "$TEST_DIR" "$@"

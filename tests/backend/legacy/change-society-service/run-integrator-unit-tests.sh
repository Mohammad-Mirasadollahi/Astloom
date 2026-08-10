#!/usr/bin/env bash
# Run integrator unit tests (reference worker + registry + webhook bridge).
set -euo pipefail
# shellcheck source=../../support/pack-bootstrap.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/support/pack-bootstrap.sh"

TEST_DIR="$(pack_pytest_dir)" || {
  echo "No tests/backend/legacy/change-society-service directory found." >&2
  exit 1
}
export PYTHONPATH="${PACK_ROOT}/backend/change-society-service/src:${PACK_ROOT}/sdk/python:${TEST_DIR}"
export ASTLOOM_WEBHOOK_SHARED_SECRET="${ASTLOOM_WEBHOOK_SHARED_SECRET:-integrator-demo-secret-change-me}"
exec "$PACK_PYTHON" -m pytest "$TEST_DIR" -k "integrator" -q "$@"

#!/usr/bin/env bash
# Frontend unit tests (Node test runner + TypeScript strip-types; pack-relative paths).
set -euo pipefail
# shellcheck source=../../support/pack-bootstrap.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/support/pack-bootstrap.sh"

TEST_DIR="$(pack_frontend_test_dir)" || {
  echo "No tests/frontend/change-society under ${PACK_ROOT} or parent." >&2
  exit 1
}

exec node --experimental-strip-types --test "${TEST_DIR}"/*.test.mjs "$@"

#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=../../support/pack-bootstrap.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/support/pack-bootstrap.sh"
E2E_DIR="${TESTS_E2E_CS}"

ENV_FILE="${CHANGE_SOCIETY_ENV_FILE:-${PACK_ROOT}/.env}"
SUITE_DIR="${PACK_ROOT}/evidence/live/suite"
mkdir -p "$SUITE_DIR"

if [[ -f "$ENV_FILE" ]]; then set -a; source "$ENV_FILE"; set +a; fi
: "${QWEN_API_KEY:?Set QWEN_API_KEY in .env}"

export CHANGE_SOCIETY_MODEL_PROVIDER="${CHANGE_SOCIETY_MODEL_PROVIDER:-qwen}"

"$PACK_PYTHON" "${E2E_DIR}/run_real_test_suite.py" \
  --output-dir "$SUITE_DIR" \
  --live

cp "$SUITE_DIR/checkout-api-refactor.json" "${PACK_ROOT}/evidence/live/society-live-test.json"
echo "Wrote live golden report: evidence/live/society-live-test.json"

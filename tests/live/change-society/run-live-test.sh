#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=../../support/pack-bootstrap.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/support/pack-bootstrap.sh"
E2E_DIR="${TESTS_E2E_CS}"

MODE="${1:-remote}"
ENV_FILE="${CHANGE_SOCIETY_ENV_FILE:-${PACK_ROOT}/.env}"
REPORT="${PACK_ROOT}/evidence/live/society-live-test.json"

if [[ -f "$ENV_FILE" ]]; then set -a; source "$ENV_FILE"; set +a; fi

if [[ "$MODE" == "compose" ]]; then
  : "${QWEN_API_KEY:?QWEN_API_KEY is required}"
  : "${ASTLOOM_POSTGRES_PASSWORD:?ASTLOOM_POSTGRES_PASSWORD is required}"
  docker compose -f "${PACK_ROOT}/deployments/compose.yaml" up -d --build
  BASE_URL="${CHANGE_SOCIETY_LIVE_API_URL:-http://127.0.0.1:32500}"
elif [[ "$MODE" == "remote" ]]; then
  BASE_URL="${CHANGE_SOCIETY_LIVE_API_URL:?required for remote mode}"
else
  echo "usage: $0 [remote|compose]" >&2
  exit 2
fi

"$PACK_PYTHON" "${E2E_DIR}/verify_society_run.py" --base-url "$BASE_URL" --output "$REPORT" --expect-production

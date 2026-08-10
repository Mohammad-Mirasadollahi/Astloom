#!/usr/bin/env bash
# Judge demo: all 7 scenarios end-to-end with REAL Qwen API (compatible-mode / free tier friendly).
set -euo pipefail
# shellcheck source=../../support/pack-bootstrap.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/support/pack-bootstrap.sh"
E2E_DIR="${TESTS_E2E_CS}"

ENV_FILE="${CHANGE_SOCIETY_ENV_FILE:-${PACK_ROOT}/.env}"
OUT_DIR="${PACK_ROOT}/evidence/live/judge-seven-scenarios"
PORT="${CHANGE_SOCIETY_JUDGE_SUITE_PORT:-32504}"
LOG="$OUT_DIR/run.log"

mkdir -p "$OUT_DIR"
if [[ -f "$ENV_FILE" ]]; then set -a; source "$ENV_FILE"; set +a; fi
: "${QWEN_API_KEY:?Set QWEN_API_KEY in .env}"

export CHANGE_SOCIETY_ENVIRONMENT=development
export CHANGE_SOCIETY_MODEL_PROVIDER=qwen
export CHANGE_SOCIETY_STORE=memory
export CHANGE_SOCIETY_QWEN_RUN_TOKEN_BUDGET="${CHANGE_SOCIETY_JUDGE_RUN_TOKEN_BUDGET:-80000}"
export QWEN_MODEL="${QWEN_JUDGE_MODEL:-${QWEN_MODEL:-qwen-flash}}"
export QWEN_TIMEOUT_SECONDS="${QWEN_JUDGE_TIMEOUT_SECONDS:-120}"
export CHANGE_SOCIETY_ENABLE_QWEN_ROLE_TOOLS="${CHANGE_SOCIETY_JUDGE_ROLE_TOOLS:-0}"
export CHANGE_SOCIETY_ALLOWED_ORIGINS=http://localhost:3000

echo "==> Judge live 7-scenario suite (real Qwen agents, short requests, model=${QWEN_MODEL}, port=${PORT})" | tee "$LOG"

"$PACK_PYTHON" -m uvicorn change_society.main:app --host 127.0.0.1 --port "$PORT" >>"$LOG" 2>&1 &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT

for _ in $(seq 1 90); do
  if curl -sf "http://127.0.0.1:${PORT}/ready" >/dev/null 2>&1; then break; fi
  sleep 0.5
done

"$PACK_PYTHON" "${E2E_DIR}/run_real_test_suite.py" \
  --base-url "http://127.0.0.1:${PORT}" \
  --output-dir "$OUT_DIR" \
  --profile judge-live \
  --skip-cross-session-follow-up \
  2>&1 | tee -a "$LOG"

"$PACK_PYTHON" "${E2E_DIR}/write_judge_seven_summary.py" --manifest "$OUT_DIR/manifest.json"

cp "$OUT_DIR/checkout-api-refactor.json" "${PACK_ROOT}/evidence/live/society-live-test.json" 2>/dev/null || true

echo "Done. Open: evidence/live/judge-seven-scenarios/judge-summary.json"

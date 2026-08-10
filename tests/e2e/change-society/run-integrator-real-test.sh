#!/usr/bin/env bash
# Real test: Astloom Change Society (control plane) + LangGraph Change Analyst (webhook worker).
set -euo pipefail
# shellcheck source=../../support/pack-bootstrap.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/support/pack-bootstrap.sh"
E2E_DIR="${TESTS_E2E_CS}"

WORKER_DIR="${PACK_ROOT}/examples/external-change-analyst-worker"
INTEGRATOR_JSON="${PACK_ROOT}/backend/change-society-service/config/managed-agents.integrator.example.json"
SECRET="${CHANGE_SOCIETY_WEBHOOK_AGENT_SECRET:-integrator-demo-secret-change-me}"
WORKER_PORT="${WORKER_PORT:-32510}"
API_PORT="${CHANGE_SOCIETY_INTEGRATOR_API_PORT:-32503}"
SCENARIO="${INTEGRATOR_REAL_SCENARIO:-checkout-api-refactor}"
LOG_DIR="${PACK_ROOT}/evidence/real/integrator-langgraph"
mkdir -p "$LOG_DIR"

export ASTLOOM_WEBHOOK_SHARED_SECRET="$SECRET"
export CHANGE_SOCIETY_WEBHOOK_AGENT_SECRET="$SECRET"
export CHANGE_SOCIETY_MANAGED_AGENTS_CONFIG="$INTEGRATOR_JSON"
export CHANGE_SOCIETY_MODEL_PROVIDER="${INTEGRATOR_REAL_MODEL:-fake}"
export CHANGE_SOCIETY_STORE="${CHANGE_SOCIETY_STORE:-memory}"
if [[ "${CHANGE_SOCIETY_MODEL_PROVIDER}" == "qwen" ]]; then
  export CHANGE_SOCIETY_QWEN_RUN_TOKEN_BUDGET="${CHANGE_SOCIETY_QWEN_RUN_TOKEN_BUDGET:-80000}"
fi

WORKER_PID=""
API_PID=""
cleanup() {
  [[ -n "$WORKER_PID" ]] && kill "$WORKER_PID" 2>/dev/null || true
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "==> LangGraph worker (:${WORKER_PORT})"
export PYTHONPATH="${WORKER_DIR}/src:${PACK_ROOT}/sdk/python"
"$PACK_PYTHON" "$WORKER_DIR/src/run_worker.py" >"${LOG_DIR}/worker.log" 2>&1 &
WORKER_PID=$!
for _ in $(seq 1 40); do curl -sf "http://127.0.0.1:${WORKER_PORT}/ready" >/dev/null && break; sleep 0.25; done
curl -sf "http://127.0.0.1:${WORKER_PORT}/ready" | tee "${LOG_DIR}/worker-ready.json"

echo "==> Astloom society API (:${API_PORT}) integrator registry"
export PYTHONPATH="${PACK_ROOT}/backend/change-society-service/src:${PACK_ROOT}/sdk/python"
"$PACK_PYTHON" -m uvicorn change_society.bootstrap.container:build_app --factory --host 127.0.0.1 --port "$API_PORT" \
  >"${LOG_DIR}/api.log" 2>&1 &
API_PID=$!
for _ in $(seq 1 60); do curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1 && break; sleep 0.3; done
curl -sf "http://127.0.0.1:${API_PORT}/ready" | tee "${LOG_DIR}/api-ready.json"

echo "==> Real integrator verify (scenario=${SCENARIO})"
"$PACK_PYTHON" "${E2E_DIR}/run_integrator_real_test.py" \
  --base-url "http://127.0.0.1:${API_PORT}" \
  --scenario "$SCENARIO" \
  --output-dir "$LOG_DIR"

echo "Evidence: ${LOG_DIR}/manifest.json"
echo "Integrator LangGraph real test passed."

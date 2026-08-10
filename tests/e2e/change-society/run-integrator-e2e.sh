#!/usr/bin/env bash
# Full integrator smoke: LangGraph worker (32510) + society API (32500) + checkout-api-refactor run.
set -euo pipefail
# shellcheck source=../../support/pack-bootstrap.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/support/pack-bootstrap.sh"
E2E_DIR="${TESTS_E2E_CS}"

WORKER_DIR="${PACK_ROOT}/examples/external-change-analyst-worker"
INTEGRATOR_JSON="${PACK_ROOT}/backend/change-society-service/config/managed-agents.integrator.example.json"
SECRET="${CHANGE_SOCIETY_WEBHOOK_AGENT_SECRET:-integrator-demo-secret-change-me}"
WORKER_PORT="${WORKER_PORT:-32510}"
API_PORT="${CHANGE_SOCIETY_PORT:-32500}"

export ASTLOOM_WEBHOOK_SHARED_SECRET="$SECRET"
export CHANGE_SOCIETY_WEBHOOK_AGENT_SECRET="$SECRET"
export CHANGE_SOCIETY_MANAGED_AGENTS_CONFIG="$INTEGRATOR_JSON"
export CHANGE_SOCIETY_MODEL_PROVIDER="${CHANGE_SOCIETY_MODEL_PROVIDER:-fake}"

WORKER_PID=""
API_PID=""
cleanup() {
  [[ -n "$WORKER_PID" ]] && kill "$WORKER_PID" 2>/dev/null || true
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "==> Worker contract tests"
export PYTHONPATH="${WORKER_DIR}/src:${PACK_ROOT}/sdk/python"
"$PACK_PYTHON" -m pytest "$WORKER_DIR/tests" -q

echo "==> Starting LangGraph worker on :$WORKER_PORT"
"$PACK_PYTHON" "$WORKER_DIR/src/run_worker.py" &
WORKER_PID=$!
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${WORKER_PORT}/ready" >/dev/null; then break; fi
  sleep 0.2
done
curl -sf "http://127.0.0.1:${WORKER_PORT}/ready" >/dev/null || {
  echo "Worker failed to become ready on port $WORKER_PORT" >&2
  exit 1
}

echo "==> Starting change-society-service on :$API_PORT"
export PYTHONPATH="${PACK_ROOT}/backend/change-society-service/src:${PACK_ROOT}/sdk/python"
"$PACK_PYTHON" -m uvicorn change_society.bootstrap.container:build_app --factory --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!
for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then break; fi
  sleep 0.3
done

echo "==> Creating society run (checkout-api-refactor)"
export PYTHONPATH="${PACK_ROOT}/sdk/python"
"$PACK_PYTHON" <<PY
import sys
import time
from change_society_sdk import ChangeSocietyClient, Scope

base = "http://127.0.0.1:${API_PORT}"
client = ChangeSocietyClient(base, Scope("demo-tenant", "demo-workspace", "demo-project", "integrator-e2e"))
run = client.create_run("checkout-api-refactor")
run_id = run["run_id"]
print("run_id", run_id, "state", run.get("state"))

found_external = False
for attempt in range(90):
    tickets = client.list_agent_tickets(run_id)
    for ticket in tickets:
        metrics = ticket.get("execution_metrics") or {}
        runtime = metrics.get("runtime") or ""
        capability = ticket.get("capability") or ""
        if "interpret_ambiguous" in capability or ticket.get("assigned_role") == "change_analyst":
            if ticket.get("state") in {"completed", "failed"}:
                print("change_analyst_ticket", ticket.get("ticket_id"), "state", ticket.get("state"), "runtime", runtime)
                if "langgraph" in runtime or runtime == "langgraph-worker":
                    found_external = True
                elif runtime and runtime not in {"fake", "qwen-cloud", "deterministic"}:
                    found_external = True
            elif ticket.get("state") == "in_progress":
                print("waiting for change_analyst ticket...", ticket.get("ticket_id"))
    if found_external:
        print("INTEGRATOR_E2E_OK external change analyst execution confirmed")
        sys.exit(0)
    time.sleep(0.5)

print("INTEGRATOR_E2E_FAIL did not observe external worker runtime on change_analyst ticket", file=sys.stderr)
for ticket in client.list_agent_tickets(run_id):
    print("ticket", ticket.get("ticket_id"), ticket.get("capability"), ticket.get("state"), ticket.get("execution_metrics"))
sys.exit(1)
PY

echo "Integrator E2E passed."

#!/usr/bin/env bash
# Default E2E: Astloom control plane + LangGraph worker (one scenario, short judge request).
set -euo pipefail
export INTEGRATOR_LIVE_SUITE=0
export INTEGRATOR_REAL_SCENARIO="${CHANGE_SOCIETY_DEFAULT_VERIFY_SCENARIO:-checkout-api-refactor}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "${ROOT}/tests/live/change-society/run-langgraph-sdk-live-seven-scenarios.sh"

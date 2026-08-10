#!/usr/bin/env bash
# Real integrator test: LangGraph agents (all roles) + astloom_agent_sdk webhook + Astloom control plane.
set -euo pipefail
# shellcheck source=../../support/pack-bootstrap.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/support/pack-bootstrap.sh"
LIVE_DIR="${TESTS_LIVE_CS}"

export CHANGE_SOCIETY_MANAGED_AGENTS_CONFIG="${CHANGE_SOCIETY_MANAGED_AGENTS_CONFIG:-${PACK_ROOT}/backend/change-society-service/config/managed-agents.integrator-live-all.example.json}"
exec bash "${LIVE_DIR}/run-integrator-live-test.sh" "$@"

#!/usr/bin/env bash
# Default multi-domain proof: seven LangGraph worker scenarios + Astloom control plane.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "${ROOT}/tests/live/change-society/run-langgraph-sdk-live-seven-scenarios.sh" "$@"

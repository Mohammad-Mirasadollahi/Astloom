#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

TICKETING_DATABASE_URL="${ASTLOOM_ADAPTER_SERVICE_DATABASE_URL:-${ASTLOOM_DATABASE_URL:-${ASTLOOM_CODE_GRAPH_DATABASE_URL:-}}}"
if [[ -z "$TICKETING_DATABASE_URL" ]]; then
  echo "ASTLOOM_ADAPTER_SERVICE_DATABASE_URL (or the main ASTLOOM_DATABASE_URL) is required" >&2
  exit 2
fi

export ASTLOOM_ADAPTER_SERVICE_DATABASE_URL="$TICKETING_DATABASE_URL"
export PYTHONPATH="backend/packages:backend/services/adapter-service/src${PYTHONPATH:+:$PYTHONPATH}"

exec .venv/bin/python -m pytest \
  tests/live/adapter-service/test_external_ticketing_main_infrastructure.py \
  -m live -v

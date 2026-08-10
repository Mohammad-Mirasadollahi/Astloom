#!/usr/bin/env bash
# Smoke test: Qwen Cloud free-tier compatible-mode API (uses .env when present).
set -euo pipefail
# shellcheck source=../../support/pack-bootstrap.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/support/pack-bootstrap.sh"
LIVE_DIR="${TESTS_LIVE_CS}"

exec "$PACK_PYTHON" "${LIVE_DIR}/smoke_qwen_free_api.py" "$@"

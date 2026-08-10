#!/usr/bin/env bash
# Quick stack check: Change Society API + Next.js UI proxy (run from hackathon pack root).
set -euo pipefail

API="${CHANGE_SOCIETY_CHECK_API:-http://127.0.0.1:32500}"
UI="${CHANGE_SOCIETY_CHECK_UI:-http://127.0.0.1:32501}"
PROJECT="${NEXT_PUBLIC_CHANGE_SOCIETY_PROJECT_ID:-demo-project}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

echo "== API /ready ($API) =="
ready="$(curl -fsS "$API/ready")" || fail "API not listening on $API (start: python run.py)"
echo "$ready" | head -c 200
echo

echo "== API demo-scenarios =="
curl -fsS \
  -H "X-Tenant-Id: demo-tenant" \
  -H "X-Workspace-Id: demo-workspace" \
  "$API/api/v1/projects/$PROJECT/demo-scenarios" >/dev/null || fail "demo-scenarios failed"

echo "== UI proxy /change-society-api/ready ($UI) =="
curl -fsS "$UI/change-society-api/ready" >/dev/null || fail "UI not up or proxy broken (start: cd frontend && npm run dev)"

echo "OK: backend and frontend proxy reachable"

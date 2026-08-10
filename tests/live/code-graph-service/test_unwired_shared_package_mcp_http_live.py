#!/usr/bin/env python3
"""Live MCP HTTP: unwired_shared_package keep_public on adapter_harness (astloom graph)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
import pytest
from usage_profile.mcp_tokens import mint_connect_token

ROOT = Path(__file__).resolve().parents[3]
SECRET = ROOT / ".astloom" / "mcp-http.secret"
MCP_URL = os.environ.get("ASTLOOM_MCP_HTTP_PUBLIC_URL", "https://127.0.0.1:32500").rstrip("/")
if not MCP_URL.endswith("/mcp"):
    MCP_URL = f"{MCP_URL}/mcp"
_VERIFY_RAW = (os.environ.get("ASTLOOM_MCP_HTTP_TLS_VERIFY") or "").strip().lower()
MCP_TLS_VERIFY = _VERIFY_RAW in {"1", "true", "yes", "on"}

TENANT = "mir"
WORKSPACE = "dev"
PROJECT = "astloom"
PATH_PREFIX = "backend/packages/adapter_harness"


def _payload(result: dict) -> dict:
    sc = result.get("structuredContent")
    if isinstance(sc, dict):
        return sc
    for part in result.get("content") or []:
        if part.get("type") == "text":
            return json.loads(part.get("text") or "{}")
    raise AssertionError(f"no structured payload: {result!r}")


@pytest.mark.live
def test_live_unwired_shared_package_keep_public_via_mcp_http():
    if not SECRET.is_file():
        pytest.skip(f"missing MCP secret at {SECRET}")

    secret = SECRET.read_text(encoding="utf-8").strip()
    os.environ["ASTLOOM_MCP_TOKEN_SECRET"] = secret
    token = mint_connect_token(
        tenant_id=TENANT, workspace_id=WORKSPACE, project_id=PROJECT, ttl_seconds=3600
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def rpc(method: str, params: dict | None = None, rid: int = 1) -> dict:
        response = httpx.post(
            MCP_URL,
            headers=headers,
            json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}},
            timeout=180.0,
            verify=MCP_TLS_VERIFY,
        )
        response.raise_for_status()
        body = response.json()
        assert "error" not in body, body
        return body

    init = rpc(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "live-unwired-packages", "version": "0"},
        },
        1,
    )
    assert "result" in init, init

    search = rpc(
        "tools/call",
        {
            "name": "mcp_search_tools",
            "arguments": {"query": "unused candidates shared package", "limit": 10},
        },
        2,
    )
    search_payload = _payload(search.get("result") or {})
    hits = list(search_payload.get("results") or [])
    by_name = {str(h.get("tool_name") or ""): h for h in hits if isinstance(h, dict)}
    assert "astloom_code_graph_unused_candidates" in by_name, search_payload
    server_name = str(by_name["astloom_code_graph_unused_candidates"].get("server_name") or "")
    assert server_name

    call = rpc(
        "tools/call",
        {
            "name": "mcp_execute_tool",
            "arguments": {
                "tool_name": "astloom_code_graph_unused_candidates",
                "server_name": server_name,
                "arguments": {
                    "scope_mode": "project_scan",
                    "path_prefix": PATH_PREFIX,
                    "min_confidence": 0.0,
                    "max_results": 50,
                    "include_uncertain": True,
                    "repo_root": str(ROOT),
                },
            },
        },
        3,
    )
    payload = _payload(call.get("result") or {})
    assert payload.get("freshness") in {"ok", "pending_sync", "stale"}, payload
    assert payload.get("path_prefix") == PATH_PREFIX, payload

    rows = list(payload.get("candidates") or []) + list(payload.get("skipped_uncertain") or [])
    pkg_rows = [
        r
        for r in rows
        if r.get("finding_kind") in {"unwired_shared_package", "zombie_package"}
        and str(r.get("path") or "").startswith(PATH_PREFIX)
    ]
    assert pkg_rows, {
        "msg": "expected package finding for adapter_harness",
        "row_kinds": [
            {"finding_kind": r.get("finding_kind"), "path": r.get("path"), "symbol": r.get("symbol")}
            for r in rows[:30]
        ],
    }
    row = pkg_rows[0]
    assert row.get("finding_kind") == "unwired_shared_package"
    assert row.get("recommendation") == "keep_public"
    assert row.get("safe_to_delete") is False

    out = {
        "http_mcp_ok": True,
        "server_name": server_name,
        "project_id": PROJECT,
        "path_prefix": PATH_PREFIX,
        "freshness": payload.get("freshness"),
        "graph_mode": payload.get("graph_mode"),
        "package": {
            "finding_kind": row.get("finding_kind"),
            "recommendation": row.get("recommendation"),
            "path": row.get("path"),
            "score": row.get("score"),
            "safe_to_delete": row.get("safe_to_delete"),
            "blockers": row.get("blockers"),
        },
    }
    artifact = ROOT / "tests" / "artifacts" / "code-graph-live" / "unwired-shared-package-live.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    sys.path[:0] = [str(ROOT / "backend" / "packages")]
    test_live_unwired_shared_package_keep_public_via_mcp_http()
    print("HTTP_MCP_UNWIRED_SHARED_PACKAGE_OK")

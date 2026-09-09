#!/usr/bin/env python3
"""Live MCP: Next.js App Router re-export / JSX must not be safe_to_delete."""

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
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "nextjs_app_router"
MCP_URL = os.environ.get("ASTLOOM_MCP_HTTP_PUBLIC_URL", "https://127.0.0.1:32500").rstrip("/")
if not MCP_URL.endswith("/mcp"):
    MCP_URL = f"{MCP_URL}/mcp"
_VERIFY_RAW = (os.environ.get("ASTLOOM_MCP_HTTP_TLS_VERIFY") or "").strip().lower()
MCP_TLS_VERIFY = _VERIFY_RAW in {"1", "true", "yes", "on"}

TENANT = "mir"
WORKSPACE = "dev"
PROJECT = "nextjs-live-roots"
PATH_PREFIX = "frontend/app/dashboard"


def _payload(result: dict) -> dict:
    sc = result.get("structuredContent")
    if isinstance(sc, dict):
        return sc
    for part in result.get("content") or []:
        if part.get("type") == "text":
            return json.loads(part.get("text") or "{}")
    raise AssertionError(f"no structured payload: {result!r}")


def _sources() -> list[tuple[str, Path]]:
    return [
        (
            "frontend/app/dashboard/overview/page.tsx",
            FIXTURES / "overview" / "page.tsx",
        ),
        (
            "frontend/app/dashboard/executive/ExecutiveOverviewPage.tsx",
            FIXTURES / "executive" / "ExecutiveOverviewPage.tsx",
        ),
        (
            "frontend/app/dashboard/executive/components/ValueFunnelHero.tsx",
            FIXTURES / "executive" / "components" / "ValueFunnelHero.tsx",
        ),
        (
            "frontend/app/dashboard/executive/deadHelper.ts",
            FIXTURES / "executive" / "deadHelper.ts",
        ),
    ]


@pytest.mark.live
def test_live_nextjs_app_router_roots_not_safe_to_delete():
    if not SECRET.is_file():
        pytest.skip(f"missing MCP secret at {SECRET}")
    for _, path in _sources():
        if not path.is_file():
            pytest.skip(f"missing fixture {path}")

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
            timeout=120.0,
            verify=MCP_TLS_VERIFY,
        )
        response.raise_for_status()
        body = response.json()
        assert "error" not in body, body
        return body

    rpc(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "live-nextjs-roots", "version": "0"},
        },
        1,
    )
    listed = rpc("tools/list", {}, 2)
    names = {t.get("name") for t in (listed.get("result") or {}).get("tools") or []}
    assert "mcp_execute_tool" in names

    search = rpc(
        "tools/call",
        {
            "name": "mcp_search_tools",
            "arguments": {"query": "unused candidates ingest file", "limit": 10},
        },
        3,
    )
    hits = list((_payload(search.get("result") or {})).get("results") or [])
    by_name = {str(h.get("tool_name") or ""): h for h in hits if isinstance(h, dict)}
    assert "astloom_code_graph_unused_candidates" in by_name
    server_name = str(by_name["astloom_code_graph_unused_candidates"].get("server_name") or "")

    def execute(tool_name: str, tool_args: dict, rid: int) -> dict:
        call = rpc(
            "tools/call",
            {
                "name": "mcp_execute_tool",
                "arguments": {
                    "tool_name": tool_name,
                    "server_name": server_name,
                    "arguments": tool_args,
                },
            },
            rid,
        )
        return _payload(call.get("result") or {})

    rid = 4
    for file_path, src in _sources():
        lang = "typescript"
        ingest = execute(
            "astloom_code_graph_ingest_file",
            {
                "file_path": file_path,
                "language": lang,
                "source": src.read_text(encoding="utf-8"),
            },
            rid,
        )
        rid += 1
        assert ingest.get("ok") is not False, ingest

    # Relink neighbors after all peers exist.
    for file_path, src in _sources():
        ingest = execute(
            "astloom_code_graph_ingest_file",
            {
                "file_path": file_path,
                "language": "typescript",
                "source": src.read_text(encoding="utf-8"),
            },
            rid,
        )
        rid += 1
        assert ingest.get("ok") is not False, ingest

    payload = execute(
        "astloom_code_graph_unused_candidates",
        {
            "scope_mode": "project_scan",
            "path_prefix": PATH_PREFIX,
            "min_confidence": 0.5,
            "max_results": 50,
            "include_uncertain": True,
        },
        rid,
    )
    rows = list(payload.get("candidates") or []) + list(payload.get("skipped_uncertain") or [])
    live_names = ("ExecutiveOverviewPage", "ValueFunnelHero", "Page")
    live_safe = [
        r
        for r in (payload.get("candidates") or [])
        if r.get("safe_to_delete")
        and any(n in str(r.get("symbol") or "") for n in live_names)
    ]
    assert not live_safe, {
        "live_safe": live_safe,
        "rows": [
            {
                "symbol": r.get("symbol"),
                "safe_to_delete": r.get("safe_to_delete"),
                "blockers": r.get("blockers"),
                "finding_kind": r.get("finding_kind"),
            }
            for r in rows
        ],
    }

    # Dead helper may be candidate or uncertain — either way it is not a live root.
    dead_rows = [
        r for r in rows if "deadOverviewHelper" in str(r.get("symbol") or "")
    ]
    assert dead_rows, {"rows": [{"symbol": r.get("symbol")} for r in rows]}

    callers = execute(
        "astloom_code_graph_callers",
        {
            "qualified_name": (
                "frontend.app.dashboard.executive.components.ValueFunnelHero.ValueFunnelHero"
            ),
            "max_depth": 2,
        },
        rid + 1,
    )
    caller_count = int(callers.get("total") or len(callers.get("callers") or []) or 0)

    out = {
        "http_mcp_ok": True,
        "project_id": PROJECT,
        "live_safe_count": 0,
        "dead_helper_surfaced": True,
        "value_funnel_callers": caller_count,
        "row_count": len(rows),
        "index_coverage": payload.get("index_coverage"),
    }
    artifact = ROOT / "tests" / "artifacts" / "code-graph-live" / "nextjs-app-router-live.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    sys.path[:0] = [str(ROOT / "backend" / "packages")]
    test_live_nextjs_app_router_roots_not_safe_to_delete()
    print("HTTP_MCP_NEXTJS_ROOTS_OK")

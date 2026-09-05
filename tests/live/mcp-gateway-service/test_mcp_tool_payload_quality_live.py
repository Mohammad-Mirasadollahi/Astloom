"""Live MCP HTTP: semantic quality of tool payloads (not only timeout)."""

from __future__ import annotations

import json
import os
import time
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

SCOPES = (
    ("astloom", "/opt/Astloom", "ai-toolstack/lib/cli/__init__.py"),
)


def _payload(result: dict) -> dict:
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    for part in result.get("content") or []:
        if part.get("type") == "text":
            try:
                return json.loads(part.get("text") or "{}")
            except json.JSONDecodeError:
                return {}
    return {}


@pytest.mark.live
@pytest.mark.parametrize("project,root,probe", SCOPES)
def test_live_mcp_tool_payload_quality(project: str, root: str, probe: str):
    if not SECRET.is_file():
        pytest.skip(f"missing MCP secret at {SECRET}")
    if not Path(root).is_dir():
        pytest.skip(f"missing project root {root}")

    health = httpx.get(MCP_URL.replace("/mcp", "/health"), timeout=8.0, verify=MCP_TLS_VERIFY)
    if health.status_code != 200:
        pytest.skip(f"MCP HTTP not healthy: {health.status_code}")

    os.environ["ASTLOOM_MCP_TOKEN_SECRET"] = SECRET.read_text(encoding="utf-8").strip()
    token = mint_connect_token(
        tenant_id="mir", workspace_id="dev", project_id=project, ttl_seconds=3600
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    rid = {"n": 0}

    def rpc(method: str, params: dict | None = None, *, timeout: float = 50.0) -> dict:
        rid["n"] += 1
        response = httpx.post(
            MCP_URL,
            headers=headers,
            json={"jsonrpc": "2.0", "id": rid["n"], "method": method, "params": params or {}},
            timeout=timeout,
            verify=MCP_TLS_VERIFY,
        )
        response.raise_for_status()
        return response.json()

    def execute(name: str, args: dict) -> dict:
        body = rpc(
            "tools/call",
            {
                "name": "mcp_execute_tool",
                "arguments": {
                    "tool_name": name,
                    "server_name": server,
                    "arguments": args,
                },
            },
        )
        assert body.get("error") is None, body.get("error")
        return _payload(body.get("result") or {})

    init = rpc(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "live-tool-quality", "version": "0"},
        },
    )
    server = str((init.get("result") or {}).get("serverInfo", {}).get("name") or "")
    assert server

    def expect_scope(data: dict) -> None:
        scope = data.get("scope") or {}
        assert scope.get("tenant_id") == "mir"
        assert scope.get("project_id") == project

    search = execute("astloom_code_graph_search", {"query": "path", "top_k": 3})
    expect_scope(search)
    symbols = search.get("symbols") or []
    assert symbols, search
    inner = symbols[0].get("symbol") if isinstance(symbols[0].get("symbol"), dict) else symbols[0]
    seed = str(inner.get("id") or "")
    assert seed
    assert isinstance(symbols[0].get("score"), (int, float))

    t0 = time.monotonic()
    sync = execute("astloom_code_graph_sync", {"max_files": 1})
    assert time.monotonic() - t0 < 24.0
    expect_scope(sync)
    sync_body = sync.get("sync") if isinstance(sync.get("sync"), dict) else sync
    assert sync_body.get("mode") in {"incremental", "noop", "full"} or "truncated" in sync_body

    t1 = time.monotonic()
    audit = execute("astloom_quality_audit", {"create_tasks": False, "top_n": 5})
    assert time.monotonic() - t1 < 24.0
    expect_scope(audit)
    assert audit.get("ok") is True
    assert audit.get("degraded") is not True
    assert isinstance(audit.get("findings"), list)
    assert "/opt/Astloom" in str(audit.get("repo") or "")

    arch = execute("astloom_code_graph_architecture_overview", {"top_n": 5})
    expect_scope(arch)
    assert arch.get("hubs") is not None or arch.get("communities") is not None

    detect = execute(
        "astloom_code_graph_detect_changes",
        {"changed_files": [probe], "include_flows": False},
    )
    expect_scope(detect)
    assert "risk_score" in detect or "changed_files" in detect

    neighbors = execute(
        "astloom_code_graph_neighbors",
        {"symbol_id": seed, "max_depth": 1, "top_k": 5},
    )
    expect_scope(neighbors)
    assert "edges" in neighbors or "reference_kind" in neighbors

    stamp = f"live-quality-{project}-{int(time.time())}"
    written = execute(
        "astloom_write",
        {"resource": "memory", "title": stamp, "body": f"live quality body {project}"},
    )
    assert written.get("written") == "memory" or written.get("memory")
    retrieved = execute("astloom_memory_retrieve", {"query": stamp})
    assert isinstance(retrieved.get("items"), list)
    assert retrieved["items"], retrieved

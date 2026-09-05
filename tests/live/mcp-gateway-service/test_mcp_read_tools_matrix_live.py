"""Live MCP HTTP: each read tool finishes under budget (no -32001)."""

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

TOOLS: list[tuple[str, dict]] = [
    ("astloom_ping", {}),
    ("astloom_get_effective_profile", {}),
    ("astloom_memory_retrieve", {"query": "live matrix"}),
    ("astloom_context_stats", {}),
    ("astloom_code_graph_freshness", {}),
    ("astloom_code_graph_search", {"query": "quality audit timeout", "top_k": 3}),
    ("astloom_code_graph_hybrid_search", {"query": "quality audit", "top_k": 3}),
    (
        "astloom_code_graph_explore",
        {"query": "quality audit", "top_k": 3, "max_depth": 1, "budget_chars": 1200},
    ),
    ("astloom_code_graph_language_profile", {}),
    ("astloom_code_graph_architecture_overview", {"top_n": 5}),
    ("astloom_code_graph_unused_candidates", {}),
    ("astloom_docs_status", {}),
    ("astloom_docs_catalog", {"refresh": False, "limit": 5}),
    ("astloom_docs_authoring_standards", {}),
    ("astloom_guidance_resolve", {}),
    ("astloom_guidance_list_skills", {}),
    ("astloom_quality_audit", {"create_tasks": False, "top_n": 5}),
    # Small-batch write: must finish under the 25s MCP tool budget.
    ("astloom_code_graph_sync", {"max_files": 1}),
    ("astloom_backup_status", {}),
]


def _payload(result: dict) -> dict:
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    for part in result.get("content") or []:
        if part.get("type") == "text":
            try:
                return json.loads(part.get("text") or "{}")
            except json.JSONDecodeError:
                return {"text": (part.get("text") or "")[:200]}
    return {}


@pytest.mark.live
def test_live_mcp_read_tools_no_hard_timeout():
    if not SECRET.is_file():
        pytest.skip(f"missing MCP secret at {SECRET}")

    health = httpx.get(
        MCP_URL.replace("/mcp", "/health"),
        timeout=8.0,
        verify=MCP_TLS_VERIFY,
    )
    if health.status_code != 200:
        pytest.skip(f"MCP HTTP not healthy: {health.status_code}")

    secret = SECRET.read_text(encoding="utf-8").strip()
    os.environ["ASTLOOM_MCP_TOKEN_SECRET"] = secret
    # Exercise the sshfs-backed demo-app pin (the timeout regression surface).
    token = mint_connect_token(
        tenant_id="mir", workspace_id="dev", project_id="demo-app", ttl_seconds=3600
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

    init = rpc(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "live-mcp-tool-matrix", "version": "0"},
        },
    )
    assert "result" in init, init
    server = str((init.get("result") or {}).get("serverInfo", {}).get("name") or "")
    assert server

    failures: list[str] = []
    for name, args in TOOLS:
        t0 = time.monotonic()
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
            timeout=50.0,
        )
        elapsed = time.monotonic() - t0
        err = body.get("error")
        if isinstance(err, dict) and err.get("code") == -32001:
            failures.append(f"{name}: -32001 after {elapsed:.1f}s ({err.get('message')})")
            continue
        if elapsed >= 24.0:
            failures.append(f"{name}: slow {elapsed:.1f}s (near hard budget)")
            continue
        result = body.get("result") or {}
        if result.get("isError") and name == "astloom_quality_audit":
            failures.append(f"{name}: tool isError {_payload(result)}")

    assert not failures, "\n".join(failures)

#!/usr/bin/env python3
"""Live MCP: ThinkingSOC-reported agent-facing QA fixes (#4/#5/#6).

Requires MCP HTTP up after code load (``astloom service`` / MCP restart).
Uses mir/dev/astloom pin at /opt/Astloom.
"""

from __future__ import annotations

import json
import os
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
SAMPLE_DOC = "docs/07-code-knowledge-graph/41-hybrid-documentation-coverage.md"


def _payload(result: dict) -> dict:
    sc = result.get("structuredContent")
    if isinstance(sc, dict):
        return sc
    for part in result.get("content") or []:
        if part.get("type") == "text":
            try:
                return json.loads(part.get("text") or "{}")
            except json.JSONDecodeError:
                return {"text": part.get("text")}
    return {}


@pytest.mark.live
def test_live_mcp_agent_facing_qa_fixes():
    if not SECRET.is_file():
        pytest.skip(f"missing MCP secret at {SECRET}")
    if not (ROOT / SAMPLE_DOC).is_file():
        pytest.skip(f"missing sample doc {SAMPLE_DOC}")

    health = httpx.get(
        MCP_URL.replace("/mcp", "/health"),
        timeout=8.0,
        verify=MCP_TLS_VERIFY,
    )
    if health.status_code != 200:
        pytest.skip(f"MCP HTTP not healthy: {health.status_code}")

    os.environ["ASTLOOM_MCP_TOKEN_SECRET"] = SECRET.read_text(encoding="utf-8").strip()
    token = mint_connect_token(
        tenant_id=TENANT, workspace_id=WORKSPACE, project_id=PROJECT, ttl_seconds=3600
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    rid = {"n": 0}

    def rpc(method: str, params: dict | None = None, *, timeout: float = 45.0) -> dict:
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
            "clientInfo": {"name": "live-agent-facing-qa", "version": "0"},
        },
    )
    server = str((init.get("result") or {}).get("serverInfo", {}).get("name") or "")
    assert server

    def execute(name: str, args: dict, *, timeout: float = 45.0) -> dict:
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
            timeout=timeout,
        )
        assert body.get("error") is None, body.get("error")
        result = body.get("result") or {}
        assert not result.get("isError"), result
        return _payload(result)

    search_body = rpc(
        "tools/call",
        {
            "name": "mcp_search_tools",
            "arguments": {"query": "quality_audit", "limit": 5},
        },
    )
    assert search_body.get("error") is None, search_body.get("error")
    hits = _payload(search_body.get("result") or {}).get("results") or []
    qa = next((h for h in hits if h.get("tool_name") == "astloom_quality_audit"), None)
    assert qa is not None, hits
    props = (qa.get("inputSchema") or {}).get("properties") or {}
    assert "repo_root" in props, props
    assert "root_path" in props, props

    # #4 — file_path must validate the on-disk Full-tier file (Body-tier gate).
    validated = execute("astloom_docs_write", {"mode": "validate", "file_path": SAMPLE_DOC})
    assert validated.get("ok") is True, validated
    assert validated.get("source") == "path", validated
    assert validated.get("file_read") is True, validated
    assert validated.get("tier") == "body", validated
    assert validated.get("frontmatter", {}).get("doc_id") == (
        "as.doc.ckg.hybrid-documentation-coverage"
    ), validated

    unread = execute(
        "astloom_docs_write",
        {"mode": "validate", "file_path": "docs/definitely-missing-xyz.md"},
    )
    assert unread.get("ok") is False, unread
    assert unread.get("file_read") is False, unread
    assert any("file not read" in str(e).lower() for e in (unread.get("errors") or [])), unread

    # #5 — missing roots must not look like “there are no docs”.
    missing = execute(
        "astloom_docs_catalog",
        {"roots": ["frontend/docs"], "query": "executive overview", "refresh": True},
    )
    assert missing.get("ok") is False, missing
    assert "frontend/docs" in (missing.get("missing_roots") or []), missing
    assert int((missing.get("stats") or {}).get("document_count") or 0) == 0

    # Real docs root still catalogs under the astloom pin.
    catalog = execute(
        "astloom_docs_catalog",
        {"roots": ["docs"], "query": "hybrid documentation", "limit": 5, "refresh": True},
    )
    assert catalog.get("ok") is True, catalog
    assert int((catalog.get("stats") or {}).get("document_count") or 0) > 0, catalog
    assert "/opt/Astloom" in str(catalog.get("repo") or "")

    # #6 — schema-advertised repo_root is accepted at runtime.
    audit = execute(
        "astloom_quality_audit",
        {"create_tasks": False, "top_n": 3, "repo_root": str(ROOT)},
        timeout=60.0,
    )
    assert audit.get("ok") is True or "findings" in audit, audit

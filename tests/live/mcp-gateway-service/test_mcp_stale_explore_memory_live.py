#!/usr/bin/env python3
"""Live MCP: #3 memory supersede + #2 explore body redaction on already-indexed file."""

from __future__ import annotations

import json
import os
import time
import uuid
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
def test_live_mcp_memory_supersede_ranking():
    if not SECRET.is_file():
        pytest.skip(f"missing MCP secret at {SECRET}")
    health = httpx.get(MCP_URL.replace("/mcp", "/health"), timeout=8.0, verify=MCP_TLS_VERIFY)
    if health.status_code != 200:
        pytest.skip(f"MCP HTTP not healthy: {health.status_code}")

    os.environ["ASTLOOM_MCP_TOKEN_SECRET"] = SECRET.read_text(encoding="utf-8").strip()
    token = mint_connect_token(
        tenant_id=TENANT, workspace_id=WORKSPACE, project_id=PROJECT, ttl_seconds=3600
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    rid = {"n": 0}

    def rpc(method: str, params: dict | None = None, *, timeout: float = 40.0) -> dict:
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
            "clientInfo": {"name": "live-memory-supersede", "version": "0"},
        },
    )
    server = str((init.get("result") or {}).get("serverInfo", {}).get("name") or "")
    assert server

    def execute(name: str, args: dict) -> dict:
        body = rpc(
            "tools/call",
            {
                "name": "mcp_execute_tool",
                "arguments": {"tool_name": name, "server_name": server, "arguments": args},
            },
        )
        assert body.get("error") is None, body.get("error")
        result = body.get("result") or {}
        assert not result.get("isError"), result
        return _payload(result)

    stamp = f"live-supersede-{uuid.uuid4().hex[:8]}"
    older = execute(
        "astloom_write",
        {
            "resource": "memory",
            "title": f"{stamp} bilingual EN FA",
            "body": f"{stamp} two-line bilingual EN/FA splitPairedLabel law",
            "tags": ["live-qa", stamp, "i18n"],
            "confidence": 0.7,
        },
    )
    old_id = (older.get("memory") or {}).get("id")
    assert old_id, older
    time.sleep(0.2)
    newer = execute(
        "astloom_write",
        {
            "resource": "memory",
            "title": f"{stamp} locale pure",
            "body": f"{stamp} locale-pure Intelligence i18n law (current)",
            "tags": ["live-qa", stamp, "i18n"],
            "confidence": 0.95,
            "supersedes": [old_id],
        },
    )
    assert old_id in (newer.get("superseded_ids") or []), newer
    retrieved = execute("astloom_memory_retrieve", {"query": stamp})
    items = retrieved.get("items") or []
    assert items, retrieved
    top = items[0].get("memory") if isinstance(items[0].get("memory"), dict) else items[0]
    assert top.get("id") == (newer.get("memory") or {}).get("id"), retrieved
    selected_ids = {
        (row.get("memory") or row).get("id") for row in items if isinstance(row, dict)
    }
    assert old_id not in selected_ids


@pytest.mark.live
def test_live_mcp_explore_redacts_stale_disk_bodies():
    if not SECRET.is_file():
        pytest.skip(f"missing MCP secret at {SECRET}")
    health = httpx.get(MCP_URL.replace("/mcp", "/health"), timeout=8.0, verify=MCP_TLS_VERIFY)
    if health.status_code != 200:
        pytest.skip(f"MCP HTTP not healthy: {health.status_code}")

    os.environ["ASTLOOM_MCP_TOKEN_SECRET"] = SECRET.read_text(encoding="utf-8").strip()
    token = mint_connect_token(
        tenant_id=TENANT, workspace_id=WORKSPACE, project_id=PROJECT, ttl_seconds=3600
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    rid = {"n": 0}

    def rpc(method: str, params: dict | None = None, *, timeout: float = 40.0) -> dict:
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
            "clientInfo": {"name": "live-stale-explore", "version": "0"},
        },
    )
    server = str((init.get("result") or {}).get("serverInfo", {}).get("name") or "")
    assert server

    def execute(name: str, args: dict) -> dict:
        body = rpc(
            "tools/call",
            {
                "name": "mcp_execute_tool",
                "arguments": {"tool_name": name, "server_name": server, "arguments": args},
            },
        )
        assert body.get("error") is None, body.get("error")
        result = body.get("result") or {}
        assert not result.get("isError"), result
        return _payload(result)

    baseline = execute(
        "astloom_code_graph_explore",
        {"query": "code_graph_service ingest_file GraphService", "top_k": 12, "max_depth": 1},
    )
    sections = baseline.get("sections") or []
    if not sections:
        baseline = execute(
            "astloom_code_graph_explore",
            {"query": "cli path", "top_k": 8, "max_depth": 1},
        )
        sections = baseline.get("sections") or []
    assert sections, baseline
    target_rel = None
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        rel = str(sec.get("file_path") or "").replace("\\", "/").strip()
        if not rel:
            continue
        path = ROOT / rel
        if path.is_file():
            target_rel = rel
            break
    if not target_rel:
        pytest.skip("explore returned no on-disk file to mutate")

    path = ROOT / target_rel
    original = path.read_text(encoding="utf-8")
    try:
        path.write_text(original + "\n# astloom-live-stale-marker\n", encoding="utf-8")
        explored = execute(
            "astloom_code_graph_explore",
            {
                "query": "code_graph_service ingest_file GraphService"
                if target_rel.endswith((".py", ".ts", ".tsx", ".js"))
                else "cli path",
                "top_k": 12,
                "max_depth": 1,
            },
        )
        freshness = explored.get("freshness") or {}
        hit = [
            sec
            for sec in (explored.get("sections") or [])
            if isinstance(sec, dict) and str(sec.get("file_path") or "").replace("\\", "/") == target_rel
        ]
        assert freshness.get("is_stale") is True or freshness.get("must_sync") is True, {
            "freshness": freshness,
            "target": target_rel,
        }
        assert hit, {"target": target_rel, "sections": explored.get("sections")}
        assert freshness.get("bodies_redacted") is True or any(
            isinstance(sym, dict) and sym.get("body_redacted")
            for sec in hit
            for sym in (sec.get("symbols") or [])
        ), explored
        for sec in hit:
            for sym in sec.get("symbols") or []:
                if isinstance(sym, dict) and sym.get("body_redacted"):
                    assert sym.get("body") == ""

        audit = execute("astloom_quality_audit", {"create_tasks": False, "top_n": 50})
        findings = audit.get("findings") or []
        cats = {str(f.get("category") or "") for f in findings if isinstance(f, dict)}
        paths = {str(f.get("path") or "") for f in findings if isinstance(f, dict)}
        assert "code.stale_edited" in cats or any(target_rel in p for p in paths) or audit.get(
            "degraded"
        ), {"cats": sorted(cats), "paths": sorted(paths)[:30], "target": target_rel}
    finally:
        path.write_text(original, encoding="utf-8")

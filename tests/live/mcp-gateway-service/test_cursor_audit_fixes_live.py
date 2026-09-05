#!/usr/bin/env python3
"""Live MCP HTTP: Cursor audit P0/P1 fixes on ThinkingSOC scope (mir/dev/ThinkingSOC).

Requires MCP HTTP up after code load (``astloom service`` / MCP restart).
Pins are read from ``.astloom/projects/mir/dev/ThinkingSOC.json``.
"""

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

TENANT = "mir"
WORKSPACE = "dev"
PROJECT = "ThinkingSOC"


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


def _blob(obj: object) -> str:
    return json.dumps(obj, default=str).lower()


@pytest.mark.live
def test_live_cursor_audit_fixes_thinkingSOC_mcp_http():
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
            "clientInfo": {"name": "live-cursor-audit-fixes", "version": "0"},
        },
    )
    assert "result" in init, init
    server_name = str((init.get("result") or {}).get("serverInfo", {}).get("name") or "")
    assert server_name

    def execute(tool_name: str, tool_args: dict, *, timeout: float = 40.0) -> tuple[dict, dict | None]:
        body = rpc(
            "tools/call",
            {
                "name": "mcp_execute_tool",
                "arguments": {
                    "tool_name": tool_name,
                    "server_name": server_name,
                    "arguments": tool_args,
                },
            },
            timeout=timeout,
        )
        err = body.get("error")
        if isinstance(err, dict):
            return {}, err
        result = body.get("result") or {}
        if result.get("isError"):
            return _payload(result), {"code": -32000, "message": _blob(result)}
        return _payload(result), None

    # BUG-1: memory write/retrieve must not fail on missing pinned column.
    stamp = int(time.time())
    written, write_err = execute(
        "astloom_write",
        {
            "resource": "memory",
            "title": f"audit-fix-probe-{stamp}",
            "body": "live probe that memory pinned column is migrated",
        },
    )
    assert write_err is None, write_err
    assert written.get("written") == "memory" or written.get("memory"), written

    retrieved, retrieve_err = execute(
        "astloom_memory_retrieve",
        {"query": f"audit-fix-probe-{stamp}"},
    )
    assert retrieve_err is None, retrieve_err
    assert isinstance(retrieved.get("items"), list), retrieved

    # BUG-2: graph tools must finish or return structured timeout (not hang past server budget).
    t0 = time.monotonic()
    explored, explore_err = execute(
        "astloom_code_graph_explore",
        {"query": "chat service", "top_k": 3, "max_depth": 1, "budget_chars": 1500},
        timeout=40.0,
    )
    explore_elapsed = time.monotonic() - t0
    assert explore_elapsed < 38, f"explore hung {explore_elapsed:.1f}s"
    if explore_err is not None:
        assert explore_err.get("code") == -32001, explore_err
        assert "timed out" in str(explore_err.get("message") or "").lower()
    else:
        assert "query" in explored or "seeds" in explored or "sections" in explored or explored.get("seed_ids") is not None

    seed_ids = [str(x) for x in (explored.get("seed_ids") or []) if x]
    if seed_ids:
        callers_payload, callers_err = execute(
            "astloom_code_graph_callers",
            {"symbol_id": seed_ids[0], "max_depth": 1, "top_k": 5},
            timeout=40.0,
        )
        if callers_err is not None:
            assert callers_err.get("code") in {-32001, -32602}, callers_err
        else:
            assert "callers_of" in callers_payload or "nodes" in callers_payload or callers_payload.get("symbol")

        impact_payload, impact_err = execute(
            "astloom_code_graph_impact",
            {"symbol_id": seed_ids[0], "max_depth": 1, "top_k": 5},
            timeout=40.0,
        )
        if impact_err is not None:
            assert impact_err.get("code") in {-32001, -32602}, impact_err
        else:
            assert impact_payload
    else:
        t1 = time.monotonic()
        _callers, callers_err = execute(
            "astloom_code_graph_callers",
            {"qualified_name": "login", "max_depth": 1, "top_k": 5},
            timeout=40.0,
        )
        assert time.monotonic() - t1 < 38
        if callers_err is not None:
            assert callers_err.get("code") in {-32001, -32602}, callers_err

    # BUG-3: quality_audit must not scan the Astloom install as ThinkingSOC,
    # and must finish under the MCP tool budget (no -32001) when the pin is visible.
    audit, audit_err = execute(
        "astloom_quality_audit",
        {"create_tasks": False, "top_n": 5},
        timeout=40.0,
    )
    assert audit_err is None, audit_err
    assert audit.get("degraded") is not True, audit.get("truncated_phases")
    repo = str(audit.get("repo") or "")
    repos = [str(x) for x in (audit.get("repos") or [])]
    joined = " ".join([repo, *repos, str(audit.get("error") or "")])
    assert "/opt/Astloom" not in repo
    assert not any(r.rstrip("/") == "/opt/Astloom" for r in repos)
    assert "astloom_cli" not in repo.lower()
    if audit.get("ok") is False:
        assert "software paths" in str(audit.get("error") or "").lower() or "/opt/ThinkingSOC" in joined
    else:
        assert repo.rstrip("/") == "/opt/ThinkingSOC" or "/opt/ThinkingSOC" in joined

    # Small-batch sync must not hard-timeout (-32001) on large Neo4j scopes / sshfs.
    t_sync = time.monotonic()
    sync_payload, sync_err = execute(
        "astloom_code_graph_sync",
        {"max_files": 1},
        timeout=40.0,
    )
    sync_elapsed = time.monotonic() - t_sync
    assert sync_err is None, sync_err
    assert sync_elapsed < 24.0, f"sync hung {sync_elapsed:.1f}s under MCP budget"
    assert sync_payload.get("sync") or sync_payload.get("ok") is not False

    # BUG-4: missing/unreadable root is not reported as a false "not a directory".
    _ide, ide_err = execute(
        "astloom_code_graph_ide_definition",
        {
            "root_path": "/opt/ThinkingSOC",
            "file_path": "backend/services/chat_service/__init__.py",
            "line": 0,
            "character": 0,
            "language": "python",
        },
    )
    ide_text = _blob(ide_err or _ide)
    if Path("/opt/ThinkingSOC").is_dir():
        assert "does not exist" not in ide_text
        assert "not visible" not in ide_text
    else:
        assert "does not exist" in ide_text or "not visible" in ide_text or "permission" in ide_text
        assert "is not a directory" not in ide_text

    # BUG-5: search fail-soft (lexical) rather than hard embedding DNS failure.
    search, search_err = execute(
        "astloom_code_graph_search",
        {"query": "audit_probe_callee", "top_k": 3},
        timeout=40.0,
    )
    if search_err is not None:
        assert search_err.get("code") == -32001, search_err
        assert "timed out" in str(search_err.get("message") or "").lower()
    else:
        assert "symbols" in search or search.get("degraded") is True
        assert "dns" not in _blob(search.get("error") if "error" in search else {})

    # BUG-8: ThinkingSOC backup_status must not leak pytest fixture jobs.
    backup, backup_err = execute("astloom_backup_status", {})
    assert backup_err is None, backup_err
    job = backup.get("job")
    if job:
        job_blob = _blob(job)
        assert "pytest-of-root" not in job_blob
        scope = job.get("scope") if isinstance(job, dict) else {}
        if isinstance(scope, dict) and scope:
            assert scope.get("project_id") in {None, "", PROJECT}

    # Freshness: ingest does not always stamp last_sync_at; just prove the tool answers.
    fresh, fresh_err = execute("astloom_code_graph_freshness", {})
    if fresh_err is not None:
        assert fresh_err.get("code") == -32001, fresh_err
    else:
        assert "last_sync_at" in fresh or "pending" in _blob(fresh) or fresh.get("ok") is not False

    def timed(tool_name: str, tool_args: dict, *, budget: float = 20.0) -> tuple[dict, dict | None, float]:
        t0 = time.monotonic()
        payload, err = execute(tool_name, tool_args, timeout=40.0)
        elapsed = time.monotonic() - t0
        assert elapsed < budget, f"{tool_name} hung {elapsed:.1f}s (budget {budget}s)"
        if err is not None:
            assert err.get("code") != -32001, err
        return payload, err, elapsed

    unused, unused_err, _ = timed("astloom_code_graph_unused_candidates", {})
    if unused_err is None:
        assert unused.get("candidates") == [] or unused.get("note") or "candidates" in unused

    lang, lang_err, _ = timed("astloom_code_graph_language_profile", {})
    if lang_err is None:
        assert "language_profile" in lang or lang.get("languages") is not None or lang.get("is_polyglot") is not None

    arch, arch_err, _ = timed("astloom_code_graph_architecture_overview", {"top_n": 5})
    if arch_err is None:
        assert "hubs" in arch or "communities" in arch or arch.get("algorithm")

    seed = seed_ids[0] if seed_ids else ""
    community_args = {"symbol_id": seed, "member_limit": 10} if seed else {"qualified_name": "login", "member_limit": 10}
    comm, comm_err, _ = timed("astloom_code_graph_community", community_args)
    if comm_err is None:
        assert comm.get("symbol") or comm.get("community_id") is not None or "members" in comm

    path_args = {"symbol_id": seed, "max_depth": 2, "max_nodes": 20} if seed else {"qualified_name": "login", "max_depth": 2}
    cpath, cpath_err, _ = timed("astloom_code_graph_call_path", path_args)
    if cpath_err is None:
        assert cpath.get("symbol") or "path_ids" in cpath or "path" in cpath

    gen_args = {"symbol_id": seed, "max_symbols": 8} if seed else {"qualified_name": "login", "max_symbols": 8}
    gen, gen_err, _ = timed("astloom_code_graph_generation_context", gen_args)
    if gen_err is None:
        assert gen.get("seed") or gen.get("symbols") is not None or "related" in _blob(gen)

    changed, changed_err, _ = timed(
        "astloom_code_graph_detect_changes",
        {"changed_files": ["backend/services/chat_service/__init__.py"], "include_flows": False},
    )
    if changed_err is None:
        assert changed.get("changed_files") is not None or "review" in _blob(changed) or changed

    if not Path("/opt/ThinkingSOC").is_dir():
        sync_payload, sync_err, sync_elapsed = timed(
            "astloom_code_graph_sync",
            {"root_path": "/opt/ThinkingSOC", "max_files": 1},
            budget=12.0,
        )
        _ = sync_elapsed
        sync_text = _blob(sync_err or sync_payload)
        assert "does not exist" in sync_text or "not visible" in sync_text or "permission" in sync_text

    catalog, catalog_err = execute("astloom_docs_catalog", {"refresh": False, "limit": 5})
    if catalog_err is not None and Path("/opt/ThinkingSOC").is_dir():
        assert catalog_err.get("code") == -32001, catalog_err
    elif catalog_err is None:
        repo = str(catalog.get("repo") or "")
        if catalog.get("ok") is False:
            assert "/opt/Astloom" not in repo or "ThinkingSOC" in repo
            assert "ThinkingSOC" in repo or "not visible" in _blob(catalog) or "does not exist" in _blob(catalog)
        else:
            assert repo.rstrip("/") != "/opt/Astloom"

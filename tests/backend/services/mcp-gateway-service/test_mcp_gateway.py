import json

from mcp_gateway_service.backends.platform import PlatformBackends
from mcp_gateway_service.server import McpGateway, McpGatewayError, handle_message
from mcp_gateway_service.store_factory import build_stores


def gateway():
    return McpGateway(
        profile_id="programming-cursor-mcp",
        tenant_id="t",
        workspace_id="w",
        project_id="p",
        backends=PlatformBackends(
            build_stores(
                {
                    "ASTLOOM_MCP_STORE_MODE": "memory",
                    "ASTLOOM_MCP_GRAPH_MODE": "memory",
                }
            )
        ),
    )


def test_tools_list_is_lazy_facade():
    gw = gateway()
    tools = gw.tools_list()
    names = {t["name"] for t in tools}
    assert names == {"mcp_search_tools", "mcp_execute_tool"}
    assert all("inputSchema" in t for t in tools)
    catalog = {t["name"] for t in gw.catalog_tools()}
    assert "astloom_ping" in catalog
    assert "astloom_guidance_resolve" in catalog
    assert "astloom_create_task" in catalog
    assert "astloom_docs_authoring_standards" in catalog
    assert "astloom_docs_catalog" in catalog
    assert "astloom_quality_audit" in catalog


def test_initialize_and_tools_list_rpc():
    gw = gateway()
    init = handle_message(
        gw,
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert init["result"]["serverInfo"]["name"] == "Astloom-Programming"
    listed = handle_message(gw, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    assert {t["name"] for t in listed["result"]["tools"]} == {
        "mcp_search_tools",
        "mcp_execute_tool",
    }


def test_lazy_search_and_execute():
    gw = gateway()
    search = gw.call_tool("mcp_search_tools", {"query": "guidance resolve", "limit": 5})
    hits = search["structuredContent"]["results"]
    assert hits
    assert any(h["tool_name"] == "astloom_guidance_resolve" for h in hits)
    assert all(h["server_name"] == "Astloom-Programming" for h in hits)
    assert all("inputSchema" in h for h in hits)

    executed = gw.call_tool(
        "mcp_execute_tool",
        {
            "server_name": "Astloom-Programming",
            "tool_name": "astloom_ping",
            "arguments": {},
        },
    )
    assert executed["structuredContent"]["ok"] is True

    via_aliases = gw.call_tool(
        "mcp_execute_tool",
        {"server": "Astloom-Programming", "tool": "astloom_ping", "arguments": {}},
    )
    assert via_aliases["structuredContent"]["ok"] is True


def test_tools_call_wired_backends(monkeypatch):
    from astloom_cli.util import repo_root as astloom_root

    monkeypatch.setattr(
        "astloom_cli.software_paths.software_paths_for_project",
        lambda *a, **k: [str(astloom_root())],
    )
    gw = gateway()
    ping = handle_message(
        gw,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "astloom_ping", "arguments": {}},
        },
    )
    ping_payload = json.loads(ping["result"]["content"][0]["text"])
    assert ping_payload["ok"] is True
    assert ping_payload["backend"] == "in_process"

    memory = gw.call_tool("astloom_memory_retrieve", {"query": "idempotency keys for APIs"})
    memory_payload = memory["structuredContent"]
    assert memory_payload["backend"] == "in_process"
    assert memory_payload["items"]

    graph = gw.call_tool("astloom_code_graph_search", {"query": "hash_password", "top_k": 3})
    assert graph["structuredContent"]["symbols"]

    task = gw.call_tool("astloom_create_task", {"title": "Wire MCP", "instructions": "done"})
    assert task["structuredContent"]["task"]["kind"] == "task"
    assert task["structuredContent"]["task"]["data"]["title"] == "Wire MCP"

    drift = gw.call_tool("astloom_docs_drift_check", {"symbol": "auth.hash_password"})
    assert drift["structuredContent"]["drift"] is True
    assert drift["structuredContent"]["findings"]

    written = gw.call_tool(
        "astloom_write",
        {
            "resource": "memory",
            "title": "Prefer scoped MCP writes",
            "body": "Cursor should persist conventions via astloom_write into memory.",
            "tags": ["cursor", "convention"],
        },
    )
    assert written["structuredContent"]["written"] == "memory"
    assert written["structuredContent"]["memory"]["title"] == "Prefer scoped MCP writes"

    activity = gw.call_tool(
        "astloom_write",
        {"resource": "activity", "summary": "Connected Cursor MCP and wrote a note"},
    )
    assert activity["structuredContent"]["written"] == "activity"

    docs_note = gw.call_tool(
        "astloom_docs_write",
        {
            "mode": "note",
            "title": "Auth hashing notes",
            "body": "# Auth\n\nUse scoped APIs when hashing passwords.",
            "symbol": "auth.hash_password",
            "file_path": "src/auth/hash.py",
        },
    )
    assert docs_note["structuredContent"]["written"] == "document"
    assert docs_note["structuredContent"]["anchor"] is not None

    docs_draft = gw.call_tool(
        "astloom_docs_write",
        {
            "mode": "draft",
            "title": "hash_password draft",
            "body": "Documents password hashing helper.",
            "symbol": "auth.hash_password",
        },
    )
    assert docs_draft["structuredContent"]["written"] == "draft"

    validated = gw.call_tool(
        "astloom_docs_write",
        {
            "mode": "validate",
            "title": "Check FM",
            "symbol": "auth.hash_password",
        },
    )
    assert validated["structuredContent"]["ok"] is True

    from pathlib import Path

    from astloom_cli.util import repo_root

    sample = Path(repo_root()) / "docs" / "07-code-knowledge-graph" / "41-hybrid-documentation-coverage.md"
    if sample.is_file():
        from_disk = gw.call_tool(
            "astloom_docs_write",
            {"mode": "validate", "path": str(sample.relative_to(repo_root()))},
        )
        sc = from_disk["structuredContent"]
        assert sc["ok"] is True
        assert sc["frontmatter"]["doc_id"] == "as.doc.ckg.hybrid-documentation-coverage"
        assert sc.get("source") == "path"

    status = gw.call_tool("astloom_docs_status", {})
    assert "coverage" in status["structuredContent"]
    assert "missing_count" in status["structuredContent"]

    authoring = gw.call_tool("astloom_docs_authoring_standards", {})
    standards = authoring["structuredContent"]["authoring_standards"]
    assert standards["law_id"] == "astloom.documentation_authoring.full_tier"
    assert "doc_id" in standards["required_frontmatter_keys"]
    assert "astloom-documentation-authoring" == standards["skill_name"]
    assert "astloom_docs_catalog" in standards["related_mcp_tools"]
    assert "astloom_quality_audit" in standards["related_mcp_tools"]

    catalog = gw.call_tool(
        "astloom_docs_catalog",
        {"query": "hybrid", "limit": 5, "refresh": False},
    )
    cat = catalog["structuredContent"]
    assert cat["mode"] == "docs_catalog_query"
    assert cat["invents_edges"] is False
    assert cat.get("vocabulary_source") == "observed_frontmatter"
    assert "vocabularies" in cat
    assert "documents" in cat

    qa = gw.call_tool(
        "astloom_quality_audit",
        {"top_n": 5, "severities": ["high", "medium"]},
    )
    qa_body = qa["structuredContent"]
    assert qa_body["maps_to"] == "quality.audit"
    assert "must_remediate" in qa_body
    assert "findings" in qa_body
    assert "agent_instruction" in qa_body

    guidance = gw.call_tool(
        "astloom_guidance_resolve",
        {"task_summary": "start coding with Astloom MCP"},
    )
    bundle = guidance["structuredContent"]["bundle"]
    assert bundle["agents_entry"] is not None
    assert any(r.get("slug") == "mcp-first-astloom" for r in bundle["always_rules"])
    assert any(s["name"] == "astloom-session-bootstrap" for s in bundle["skills"])

    listed = gw.call_tool("astloom_guidance_list_skills", {"query": "docs"})
    skill_names = {s["name"] for s in listed["structuredContent"]["skills"]}
    assert "astloom-docs-sync" in skill_names
    assert "astloom-documentation-authoring" in skill_names

    skill = gw.call_tool(
        "astloom_guidance_get_skill",
        {"name": "astloom-code-graph", "bundle_id": bundle["bundle_id"]},
    )
    assert "astloom_code_graph_search" in skill["structuredContent"]["skill"]["body"]

    authoring_skill = gw.call_tool(
        "astloom_guidance_get_skill",
        {"name": "astloom-documentation-authoring", "bundle_id": bundle["bundle_id"]},
    )
    assert "astloom_docs_authoring_standards" in authoring_skill["structuredContent"]["skill"]["body"]
    assert "Full-tier" in authoring_skill["structuredContent"]["skill"]["body"]


def test_unknown_tool_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTLOOM_MCP_USAGE_LOG_DIR", str(tmp_path / "mcp-usage"))
    monkeypatch.setenv("ASTLOOM_MCP_CLIENT_ID", "cursor-test")
    gw = gateway()
    bad = handle_message(
        gw,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "not_allowed_tool", "arguments": {}},
        },
    )
    assert bad["error"]["code"] == -32601
    events_path = tmp_path / "mcp-usage" / "events.jsonl"
    assert events_path.is_file()
    rows = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
    assert rows[-1]["ok"] is False
    assert rows[-1]["tool"] == "not_allowed_tool"
    assert rows[-1]["error_code"] == -32601
    assert rows[-1]["client_id"] == "cursor-test"


def test_unexpected_tool_exception_returns_jsonrpc_error(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTLOOM_MCP_USAGE_LOG_DIR", str(tmp_path / "mcp-usage"))
    gw = gateway()

    def boom(_name, _arguments=None):
        raise RuntimeError("simulated gateway crash")

    monkeypatch.setattr(gw, "call_tool", boom)
    bad = handle_message(
        gw,
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "astloom_ping", "arguments": {}},
        },
    )
    assert bad["error"]["code"] == -32000
    assert "simulated gateway crash" in bad["error"]["message"]
    rows = [
        json.loads(line)
        for line in (tmp_path / "mcp-usage" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    err = [r for r in rows if r.get("ok") is False]
    assert err
    assert err[-1]["error_code"] == -32000
    assert "simulated gateway crash" in err[-1]["error_message"]
    assert "RuntimeError" in (err[-1].get("error_detail") or "")


def test_write_requires_resource_fields():
    gw = gateway()
    try:
        gw.call_tool("astloom_write", {"resource": "memory", "title": "missing body"})
        assert False, "expected error"
    except McpGatewayError as exc:
        assert "body" in exc.message


def test_create_task_requires_title():
    gw = gateway()
    try:
        gw.call_tool("astloom_create_task", {})
        assert False, "expected error"
    except McpGatewayError as exc:
        assert "title" in exc.message


def test_context_compress_retrieve_round_trip():
    gw = gateway()
    catalog = {t["name"] for t in gw.catalog_tools()}
    assert "astloom_context_compress" in catalog
    assert "astloom_context_retrieve" in catalog
    assert "astloom_context_stats" in catalog
    payload = json.dumps({"rows": [{"n": i, "s": "y" * 300} for i in range(50)]})
    out = gw.call_tool(
        "astloom_context_compress",
        {"payload": payload, "content_type": "json", "ttl_seconds": 120},
    )["structuredContent"]
    assert out.get("ok") is True
    assert out.get("skipped") is False
    assert out.get("chars_saved", 0) > 0
    handle = out["handle"]
    assert handle
    got = gw.call_tool("astloom_context_retrieve", {"handle": handle})["structuredContent"]
    assert got.get("ok") is True
    assert got.get("payload") == payload
    stats = gw.call_tool("astloom_context_stats", {})["structuredContent"]
    assert stats.get("ok") is True
    assert stats["metrics"]["chars_saved"] > 0
    assert stats["metrics"]["pct_saved"] > 0

from mcp_gateway_service.lazy_facade import search_catalog, server_name_aliases


def test_search_ranks_guidance_resolve():
    tools = [
        {
            "name": "astloom_ping",
            "description": "Confirm MCP connectivity",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "astloom_guidance_resolve",
            "description": "Resolve workspace guidance before coding",
            "input_schema": {"type": "object", "properties": {"task_summary": {"type": "string"}}},
        },
    ]
    out = search_catalog(tools, server_name="Astloom-Programming", query="guidance resolve", limit=3)
    assert out["results"][0]["tool_name"] == "astloom_guidance_resolve"
    assert out["results"][0]["server_name"] == "Astloom-Programming"
    assert "inputSchema" in out["results"][0]


def test_search_empty_suggests_keywords():
    out = search_catalog([], server_name="Astloom-Programming", query="zzz", limit=5)
    assert out["results"] == []
    assert "Astloom-Programming" in out["suggestion"]


def test_server_aliases_include_canonical_casefold():
    aliases = server_name_aliases("Astloom-Programming")
    assert "Astloom-Programming" in aliases
    assert "astloom-programming" in aliases  # lower() of canonical


def test_search_prefers_explicit_hybrid_and_suppresses_unrequested_purge():
    tools = [
        {
            "name": "astloom_code_graph_search",
            "description": "Search code graph symbols",
            "input_schema": {},
        },
        {
            "name": "astloom_code_graph_hybrid_search",
            "description": "Hybrid lexical and semantic code graph search",
            "input_schema": {},
        },
        {
            "name": "astloom_code_graph_purge",
            "description": "Purge code graph search data",
            "input_schema": {},
        },
    ]
    out = search_catalog(
        tools,
        server_name="Astloom-Programming",
        query="code graph hybrid search",
        limit=3,
    )
    names = [row["tool_name"] for row in out["results"]]
    assert names[0] == "astloom_code_graph_hybrid_search"
    assert "astloom_code_graph_purge" not in names

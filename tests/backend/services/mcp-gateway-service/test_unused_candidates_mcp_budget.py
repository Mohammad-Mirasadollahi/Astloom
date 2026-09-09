"""unused_candidates MCP soft budget mirrors quality_audit headroom."""

from __future__ import annotations

from mcp_gateway_service.backends.code_graph.query import _unused_candidates_budget_seconds


def test_unused_candidates_budget_leaves_headroom_under_tool_timeout(monkeypatch):
    monkeypatch.setenv("ASTLOOM_MCP_TOOL_TIMEOUT_SECONDS", "25")
    monkeypatch.setenv("ASTLOOM_MCP_UNUSED_CANDIDATES_BUDGET_SECONDS", "40")
    assert _unused_candidates_budget_seconds() == 19.0

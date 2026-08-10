from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest

from change_society.domain.models import DependencyError
from change_society.infrastructure.mcp_tool_gateway import McpToolGateway


def test_mcp_gateway_remote_json_rpc_success():
    def handler(request):
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": "1", "result": {"structuredContent": {"ok": True}}})

    gateway = McpToolGateway(client=httpx.Client(transport=httpx.MockTransport(handler)), remote_url="https://mcp.example/rpc")
    assert gateway.call_tool("fetch_evidence_by_id", {"evidence_id": "ev_1"})["ok"] is True


def test_mcp_gateway_remote_error_payload():
    def handler(request):
        return httpx.Response(200, json={"jsonrpc": "2.0", "error": {"code": -1, "message": "fail"}})

    gateway = McpToolGateway(client=httpx.Client(transport=httpx.MockTransport(handler)), remote_url="https://mcp.example/rpc")
    with pytest.raises(DependencyError) as exc:
        gateway.call_tool("x", {})
    assert exc.value.code == "mcp_tool_remote_error"


def test_mcp_gateway_unknown_tool_without_remote():
    gateway = McpToolGateway()
    with pytest.raises(DependencyError) as exc:
        gateway.call_tool("missing", {})
    assert exc.value.code == "mcp_tool_unavailable"


def test_mcp_gateway_health_lists_local_tools():
    gateway = McpToolGateway(local_handlers={"ping": lambda args: {"pong": True}})
    health = gateway.health()
    assert health["local_tools"] == ["ping"]
    assert health["remote_configured"] is False

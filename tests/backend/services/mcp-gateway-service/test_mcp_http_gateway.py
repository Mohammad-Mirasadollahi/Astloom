"""Tests for MCP HTTP token auth and gateway."""

from __future__ import annotations

import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient

from usage_profile.mcp_tokens import mint_connect_token, verify_connect_token


def test_mint_and_verify_scoped_token(monkeypatch):
    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", "unit-test-secret-key-32chars!!")
    token = mint_connect_token(tenant_id="t", workspace_id="w", project_id="p", ttl_seconds=60)
    scope = verify_connect_token(token)
    assert scope["jti"]
    assert {k: v for k, v in scope.items() if k != "jti"} == {
        "tenant_id": "t",
        "workspace_id": "w",
        "project_id": "p",
    }


def test_verify_rejects_wrong_project_header(monkeypatch):
    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", "unit-test-secret-key-32chars!!")
    token = mint_connect_token(tenant_id="t", workspace_id="w", project_id="p")
    with pytest.raises(ValueError, match="project"):
        verify_connect_token(token, project_id="other")


def test_static_token_requires_scope_headers(monkeypatch):
    monkeypatch.setenv("ASTLOOM_MCP_HTTP_TOKEN", "shared-lab-token-value")
    scope = verify_connect_token(
        "shared-lab-token-value",
        tenant_id="t",
        workspace_id="w",
        project_id="p",
        secret="shared-lab-token-value",
    )
    assert scope["project_id"] == "p"
    with pytest.raises(ValueError):
        verify_connect_token("shared-lab-token-value", secret="shared-lab-token-value")


def test_http_mcp_initialize(monkeypatch):
    class Backends:
        def __init__(self) -> None:
            self.close_count = 0

        def close(self) -> None:
            self.close_count += 1

    backends = Backends()
    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", "unit-test-secret-key-32chars!!")
    monkeypatch.setenv("ASTLOOM_MCP_STORE_MODE", "memory")
    monkeypatch.setattr(
        "mcp_gateway_service.server.PlatformBackends.from_env",
        lambda: backends,
    )
    from mcp_gateway_service.http_app import create_http_app

    token = mint_connect_token(tenant_id="t", workspace_id="w", project_id="p")
    app = create_http_app()

    async def run() -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            health = await client.get("/health")
            assert health.status_code == 200
            denied = await client.post(
                "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"}
            )
            assert denied.status_code == 401
            ok = await client.post(
                "/mcp",
                headers={"Authorization": f"Bearer {token}"},
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )
            assert ok.status_code == 200
            assert "result" in ok.json()
            tools = await client.post(
                "/mcp",
                headers={"Authorization": f"Bearer {token}"},
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
            assert tools.status_code == 200
            listed = {t["name"] for t in tools.json()["result"]["tools"]}
            assert listed == {"mcp_search_tools", "mcp_execute_tool"}

    asyncio.run(run())
    assert backends.close_count == 2


def test_http_health_remains_responsive_during_blocking_tool(monkeypatch):
    class Backends:
        def close(self) -> None:
            pass

    def blocking_handle_message(_gateway, message):
        if message.get("method") == "tools/call":
            time.sleep(0.25)
        return {"jsonrpc": "2.0", "id": message.get("id"), "result": {}}

    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", "unit-test-secret-key-32chars!!")
    monkeypatch.setattr(
        "mcp_gateway_service.http_app.handle_message",
        blocking_handle_message,
    )
    from mcp_gateway_service.http_app import create_http_app

    token = mint_connect_token(tenant_id="t", workspace_id="w", project_id="p")
    app = create_http_app(backends=Backends())

    async def run() -> None:
        async with (
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as tool_client,
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as health_client,
        ):
            request = asyncio.create_task(
                tool_client.post(
                    "/mcp",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {}},
                )
            )
            started_at = time.perf_counter()
            health_request = asyncio.create_task(health_client.get("/health"))
            health = await health_request
            health_elapsed = time.perf_counter() - started_at
            await asyncio.sleep(0.3)
            await request

            assert health.status_code == 200
            assert health_elapsed < 0.1

    asyncio.run(run())

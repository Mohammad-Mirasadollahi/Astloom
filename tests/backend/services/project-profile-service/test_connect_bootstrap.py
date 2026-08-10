"""Tests for connect bootstrap API."""

import asyncio

from httpx import ASGITransport, AsyncClient

from project_profile_service.api import app
from project_profile_service.core import ProjectProfileService
from project_profile_service.testing import InMemoryStore

H = {"X-Tenant-Id": "t", "X-Workspace-Id": "w", "X-Actor-Id": "owner", "Idempotency-Key": "one"}


class ApiClient:
    def __init__(self, api):
        self.api = api

    def request(self, method: str, url: str, **kwargs):
        async def execute():
            async with AsyncClient(transport=ASGITransport(app=self.api), base_url="http://test") as client:
                return await client.request(method, url, **kwargs)

        return asyncio.run(execute())

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)


def test_connect_bootstrap_register_activate_and_mcp(monkeypatch):
    monkeypatch.delenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", raising=False)
    monkeypatch.delenv("ASTLOOM_MCP_HTTP_PUBLIC_URL", raising=False)
    monkeypatch.delenv("ASTLOOM_MCP_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("ASTLOOM_MCP_HTTP_TOKEN", raising=False)
    client = ApiClient(app(ProjectProfileService(InMemoryStore())))
    response = client.post(
        "/api/v1/projects/p/connect/bootstrap",
        headers={**H, "Idempotency-Key": "bootstrap-one"},
        json={"name": "Demo", "usage_profile": "programming-cursor-mcp"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scope"]["project_id"] == "p"
    assert body["usage_profile"] == "programming-cursor-mcp"
    assert "Astloom-Programming" in body["mcp_stdio_fallback"]["mcpServers"]
    assert body["mcp"]["transport"] == "stdio"


def test_connect_bootstrap_http_transport(monkeypatch):
    monkeypatch.delenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", raising=False)
    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", "unit-test-secret-key-32chars!!")
    monkeypatch.setenv("ASTLOOM_MCP_HTTP_PUBLIC_URL", "http://astloom.example.internal:32500")
    client = ApiClient(app(ProjectProfileService(InMemoryStore())))
    response = client.post(
        "/api/v1/projects/p/connect/bootstrap",
        headers={**H, "Idempotency-Key": "bootstrap-http"},
        json={
            "name": "Demo",
            "usage_profile": "programming-cursor-mcp",
            "source_path": "/opt/ThinkingSOC",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mcp"]["transport"] == "streamable_http"
    assert body["mcp"]["url"].endswith("/mcp")
    assert "Authorization" in body["mcp"]["headers"]
    assert body["project"]["code_source"]["server_path"] == "/opt/ThinkingSOC"


def test_connect_sources_status_ingest_deferred(monkeypatch):
    monkeypatch.delenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", raising=False)
    monkeypatch.delenv("ASTLOOM_MCP_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("ASTLOOM_MCP_HTTP_TOKEN", raising=False)
    client = ApiClient(app(ProjectProfileService(InMemoryStore())))
    client.post(
        "/api/v1/projects/p/connect/bootstrap",
        headers={**H, "Idempotency-Key": "boot"},
        json={"name": "Demo"},
    )
    sources = client.post(
        "/api/v1/projects/p/connect/sources",
        headers=H,
        json={"server_path": "/opt/ThinkingSOC"},
    )
    assert sources.status_code == 200
    status = client.get("/api/v1/projects/p/connect/status", headers=H)
    assert status.json()["code_source"]["server_path"] == "/opt/ThinkingSOC"
    ingest = client.post("/api/v1/projects/p/connect/ingest", headers=H, json={})
    assert ingest.status_code == 200
    assert ingest.json()["ingest"]["status"] in ("deferred", "ok", "failed")


def test_health():
    client = ApiClient(app(ProjectProfileService(InMemoryStore())))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

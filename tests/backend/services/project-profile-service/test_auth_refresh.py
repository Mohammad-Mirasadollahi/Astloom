"""Auth: bootstrap secret, long-lived access token, Bearer on connect routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from project_profile_service.api import build_app
from project_profile_service.core import ProjectProfileService
from project_profile_service.testing import InMemoryStore

H = {"X-Tenant-Id": "t", "X-Workspace-Id": "w", "X-Actor-Id": "owner", "Idempotency-Key": "one"}


def _client() -> TestClient:
    return TestClient(build_app(ProjectProfileService(InMemoryStore())))


def test_bootstrap_without_secret_rejected_when_configured(monkeypatch):
    monkeypatch.setenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", "op-secret-123456")
    response = _client().post(
        "/api/v1/projects/p/connect/bootstrap",
        headers=H,
        json={"name": "Demo"},
    )
    assert response.status_code == 401


def test_bootstrap_with_secret_returns_access_token(monkeypatch):
    monkeypatch.setenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", "op-secret-123456")
    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", "unit-test-secret-key-32chars!!")
    response = _client().post(
        "/api/v1/projects/p/connect/bootstrap",
        headers=H,
        json={"name": "Demo", "bootstrap_secret": "op-secret-123456"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert "refresh_token" not in body
    assert body["expires_in"] == 86400 * 30
    assert "ca_pem" in body


def test_bootstrap_without_configured_secret_still_works(monkeypatch):
    """Backward-compatible: no ASTLOOM_CONNECT_BOOTSTRAP_SECRET → dev/lab default open."""
    monkeypatch.delenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", raising=False)
    response = _client().post(
        "/api/v1/projects/p/connect/bootstrap",
        headers=H,
        json={"name": "Demo"},
    )
    assert response.status_code == 200


def test_bootstrap_rate_limited(monkeypatch):
    monkeypatch.delenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", raising=False)
    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", "unit-test-secret-key-32chars!!")
    client = _client()
    for _ in range(10):
        assert client.post(
            "/api/v1/projects/p/connect/bootstrap",
            headers=H,
            json={"name": "Demo"},
        ).status_code == 200
    blocked = client.post(
        "/api/v1/projects/p/connect/bootstrap",
        headers=H,
        json={"name": "Demo"},
    )
    assert blocked.status_code == 429


def test_connect_route_requires_bearer_when_enforcement_enabled(monkeypatch):
    monkeypatch.delenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", raising=False)
    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", "unit-test-secret-key-32chars!!")
    client = _client()
    client.post("/api/v1/projects/p/connect/bootstrap", headers=H, json={"name": "Demo"})

    missing_bearer = client.post(
        "/api/v1/projects/p/connect/sources",
        headers=H,
        json={"server_path": "/opt/demo-app"},
    )
    assert missing_bearer.status_code == 401


def test_connect_route_accepts_valid_bearer(monkeypatch):
    monkeypatch.delenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", raising=False)
    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", "unit-test-secret-key-32chars!!")
    client = _client()
    bootstrap = client.post("/api/v1/projects/p/connect/bootstrap", headers=H, json={"name": "Demo"})
    access_token = bootstrap.json()["access_token"]

    authed = client.post(
        "/api/v1/projects/p/connect/sources",
        headers={**H, "Authorization": f"Bearer {access_token}"},
        json={"server_path": "/opt/demo-app"},
    )
    assert authed.status_code == 200

    status_resp = client.get(
        "/api/v1/projects/p/connect/status",
        headers={**H, "Authorization": f"Bearer {access_token}"},
    )
    assert status_resp.status_code == 200


def test_connect_ingest_requires_bearer_when_enforcement_enabled(monkeypatch):
    monkeypatch.delenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", raising=False)
    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", "unit-test-secret-key-32chars!!")
    client = _client()
    client.post("/api/v1/projects/p/connect/bootstrap", headers=H, json={"name": "Demo"})

    missing_bearer = client.post(
        "/api/v1/projects/p/connect/ingest",
        headers=H,
        json={},
    )
    assert missing_bearer.status_code == 401


def test_registry_revoke_blocks_status(monkeypatch):
    """Access tokens are hashed at rest and checked for revocation via app.state.token_registry."""
    from usage_profile.mcp_tokens import verify_connect_token

    monkeypatch.delenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", raising=False)
    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", "unit-test-secret-key-32chars!!")
    app = build_app(ProjectProfileService(InMemoryStore()))
    client = TestClient(app)
    bootstrap = client.post("/api/v1/projects/p/connect/bootstrap", headers=H, json={"name": "Demo"})
    access_token = bootstrap.json()["access_token"]

    still_active = client.get(
        "/api/v1/projects/p/connect/status",
        headers={**H, "Authorization": f"Bearer {access_token}"},
    )
    assert still_active.status_code == 200

    jti = verify_connect_token(access_token, secret="unit-test-secret-key-32chars!!")["jti"]
    app.state.token_registry.revoke(jti)

    revoked = client.get(
        "/api/v1/projects/p/connect/status",
        headers={**H, "Authorization": f"Bearer {access_token}"},
    )
    assert revoked.status_code == 401


def test_connect_status_rejects_bearer_scoped_to_wrong_project(monkeypatch):
    monkeypatch.delenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", raising=False)
    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", "unit-test-secret-key-32chars!!")
    client = _client()
    bootstrap = client.post("/api/v1/projects/p/connect/bootstrap", headers=H, json={"name": "Demo"})
    access_token = bootstrap.json()["access_token"]

    wrong_project = client.get(
        "/api/v1/projects/other-project/connect/status",
        headers={**H, "Authorization": f"Bearer {access_token}"},
    )
    assert wrong_project.status_code == 401

    wrong_tenant = client.get(
        "/api/v1/projects/p/connect/status",
        headers={**H, "X-Tenant-Id": "other-tenant", "Authorization": f"Bearer {access_token}"},
    )
    assert wrong_tenant.status_code == 401

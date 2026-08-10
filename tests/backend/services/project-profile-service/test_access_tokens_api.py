"""Access-token create (TTL including 0=unlimited) and revoke-by-id API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from project_profile_service.api import build_app
from project_profile_service.core import ProjectProfileService
from project_profile_service.testing import InMemoryStore
from usage_profile.mcp_tokens import verify_connect_token

H = {"X-Tenant-Id": "t", "X-Workspace-Id": "w", "X-Actor-Id": "owner", "Idempotency-Key": "one"}
SECRET = "unit-test-secret-key-32chars!!"


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("ASTLOOM_MCP_TOKEN_SECRET", SECRET)
    monkeypatch.delenv("ASTLOOM_CONNECT_BOOTSTRAP_SECRET", raising=False)
    return TestClient(build_app(ProjectProfileService(InMemoryStore())))


def _bootstrap_bearer(client: TestClient) -> str:
    response = client.post(
        "/api/v1/projects/p/connect/bootstrap",
        headers=H,
        json={"name": "Demo"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    assert token.startswith("as1.")
    return token


def test_create_access_token_with_custom_ttl(monkeypatch):
    client = _client(monkeypatch)
    bearer = _bootstrap_bearer(client)
    response = client.post(
        "/api/v1/projects/p/access-tokens",
        headers={**H, "Authorization": f"Bearer {bearer}"},
        json={"ttl_seconds": 3600},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["expires_in"] == 3600
    assert body["token_id"]
    assert body["access_token"].startswith("as1.")
    claims = verify_connect_token(body["access_token"], secret=SECRET)
    assert claims["jti"] == body["token_id"]
    assert claims["project_id"] == "p"


def test_create_access_token_ttl_zero_is_non_expiring(monkeypatch):
    client = _client(monkeypatch)
    bearer = _bootstrap_bearer(client)
    response = client.post(
        "/api/v1/projects/p/access-tokens",
        headers={**H, "Authorization": f"Bearer {bearer}"},
        json={"ttl_seconds": 0},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["expires_in"] == 0
    claims = verify_connect_token(body["access_token"], secret=SECRET)
    # Payload exp=0 must still verify as active (non-expiring).
    assert claims["jti"] == body["token_id"]
    registry = client.app.state.token_registry
    record = registry.get(body["token_id"])
    assert record is not None
    assert record.expires_at is None


def test_create_access_token_rejects_negative_ttl(monkeypatch):
    client = _client(monkeypatch)
    bearer = _bootstrap_bearer(client)
    response = client.post(
        "/api/v1/projects/p/access-tokens",
        headers={**H, "Authorization": f"Bearer {bearer}"},
        json={"ttl_seconds": -1},
    )
    assert response.status_code == 400


def test_revoke_access_token_by_id(monkeypatch):
    client = _client(monkeypatch)
    bearer = _bootstrap_bearer(client)
    created = client.post(
        "/api/v1/projects/p/access-tokens",
        headers={**H, "Authorization": f"Bearer {bearer}"},
        json={"ttl_seconds": 0},
    ).json()
    token_id = created["token_id"]
    minted = created["access_token"]

    # New token works on status before revoke.
    ok = client.get(
        "/api/v1/projects/p/connect/status",
        headers={**{k: v for k, v in H.items() if k != "Idempotency-Key"}, "Authorization": f"Bearer {minted}"},
    )
    assert ok.status_code == 200, ok.text

    revoked = client.delete(
        f"/api/v1/projects/p/access-tokens/{token_id}",
        headers={**{k: v for k, v in H.items() if k != "Idempotency-Key"}, "Authorization": f"Bearer {bearer}"},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json() == {"revoked": True, "token_id": token_id}

    blocked = client.get(
        "/api/v1/projects/p/connect/status",
        headers={**{k: v for k, v in H.items() if k != "Idempotency-Key"}, "Authorization": f"Bearer {minted}"},
    )
    assert blocked.status_code == 401


def test_revoke_unknown_token_id_is_404(monkeypatch):
    client = _client(monkeypatch)
    bearer = _bootstrap_bearer(client)
    response = client.delete(
        "/api/v1/projects/p/access-tokens/does-not-exist",
        headers={**{k: v for k, v in H.items() if k != "Idempotency-Key"}, "Authorization": f"Bearer {bearer}"},
    )
    assert response.status_code == 404


def test_revoke_other_project_token_is_404(monkeypatch):
    client = _client(monkeypatch)
    bearer_p = _bootstrap_bearer(client)
    created = client.post(
        "/api/v1/projects/p/access-tokens",
        headers={**H, "Authorization": f"Bearer {bearer_p}"},
        json={"ttl_seconds": 3600},
    ).json()
    # Bootstrap a second project and try to revoke p's token from q's scope.
    other = client.post(
        "/api/v1/projects/q/connect/bootstrap",
        headers={**H, "Idempotency-Key": "two"},
        json={"name": "Other"},
    )
    assert other.status_code == 200
    bearer_q = other.json()["access_token"]
    response = client.delete(
        f"/api/v1/projects/q/access-tokens/{created['token_id']}",
        headers={
            **{k: v for k, v in H.items() if k != "Idempotency-Key"},
            "Authorization": f"Bearer {bearer_q}",
        },
    )
    assert response.status_code == 404

import asyncio

from httpx import ASGITransport, AsyncClient

from identity_access_service.api import app
from identity_access_service.core import IdentityAccessService
from identity_access_service.testing import InMemoryStore


H = {"X-Tenant-Id": "t", "X-Workspace-Id": "w", "X-Actor-Id": "admin", "Idempotency-Key": "one"}


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


def test_upsert_principal_and_authorize():
    store = InMemoryStore()
    client = ApiClient(app(IdentityAccessService(store)))
    created = client.post(
        "/api/v1/projects/p/principals",
        headers=H,
        json={"subject": "dev@example.com", "roles": ["developer"], "permissions": ["task:write"]},
    )
    assert created.status_code == 200
    allowed = client.post(
        "/api/v1/projects/p/authorize",
        headers=H,
        json={"subject": "dev@example.com", "action": "task:write", "resource": "task"},
    )
    assert allowed.json()["decision"]["allowed"] is True
    denied = client.post(
        "/api/v1/projects/p/authorize",
        headers=H,
        json={"subject": "dev@example.com", "action": "admin:all", "resource": "tenant"},
    )
    assert denied.json()["decision"]["allowed"] is False
    assert store.outbox()[-1]["event_type"] == "principal.upserted"


def test_unknown_subject_denied():
    client = ApiClient(app(IdentityAccessService(InMemoryStore())))
    decision = client.post(
        "/api/v1/projects/p/authorize",
        headers=H,
        json={"subject": "nobody", "action": "read", "resource": "x"},
    )
    assert decision.json()["decision"]["allowed"] is False


def test_admin_matrix_authorize_emits_audit_event():
    store = InMemoryStore()
    client = ApiClient(app(IdentityAccessService(store)))
    client.post(
        "/api/v1/projects/p/principals",
        headers=H,
        json={
            "subject": "ops@example.com",
            "roles": ["integration_admin"],
            "permissions": [],
        },
    )
    allowed = client.post(
        "/api/v1/projects/p/authorize",
        headers=H,
        json={"subject": "ops@example.com", "action": "adapter.install", "resource": "connector"},
    )
    assert allowed.json()["decision"]["allowed"] is True
    events = [e for e in store.outbox() if e.get("event_type") == "admin.authorize"]
    assert events
    assert events[-1]["allowed"] is True
    assert events[-1]["action"] == "adapter.install"


def test_roles_required():
    client = ApiClient(app(IdentityAccessService(InMemoryStore())))
    bad = client.post("/api/v1/projects/p/principals", headers=H, json={"subject": "x", "roles": []})
    assert bad.status_code == 400


def test_revoke_principal_denies_access(tmp_path):
    from identity_access_service.core import Scope
    from identity_access_service.testing import DictStore

    path = tmp_path / "identity.json"
    store = DictStore(str(path))
    client = ApiClient(app(IdentityAccessService(store)))
    created = client.post(
        "/api/v1/projects/p/principals",
        headers=H,
        json={"subject": "ops@example.com", "roles": ["operator"], "permissions": ["read"]},
    )
    principal_id = created.json()["principal"]["id"]
    revoked = client.post(f"/api/v1/projects/p/principals/{principal_id}:revoke", headers=H)
    assert revoked.json()["principal"]["status"] == "revoked"
    decision = client.post(
        "/api/v1/projects/p/authorize",
        headers=H,
        json={"subject": "ops@example.com", "action": "read", "resource": "x"},
    )
    assert decision.json()["decision"]["allowed"] is False
    listed = client.get("/api/v1/projects/p/principals", headers=H)
    assert listed.json()["items"][0]["status"] == "revoked"
    reloaded = DictStore(str(path))
    assert reloaded.get_principal(principal_id, Scope("t", "w", "p"))["status"] == "revoked"

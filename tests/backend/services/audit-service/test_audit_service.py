import asyncio

from httpx import ASGITransport, AsyncClient

from audit_service.api import app
from audit_service.core import AuditService, Scope
from audit_service.testing import InMemoryStore


H = {"X-Tenant-Id": "t", "X-Workspace-Id": "w", "X-Actor-Id": "agent", "Idempotency-Key": "one"}


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


def test_idempotent_audit_record_and_timeline():
    store = InMemoryStore()
    client = ApiClient(app(AuditService(store)))
    body = {"action": "task.merged", "entity_ref": "task:1", "evidence_refs": ["diff:1"]}
    created = client.post("/api/v1/projects/p/audit/events", headers={**H, "X-Correlation-Id": "c1"}, json=body)
    assert created.status_code == 200
    event_id = created.json()["event"]["id"]
    again = client.post("/api/v1/projects/p/audit/events", headers={**H, "X-Correlation-Id": "c1"}, json=body)
    assert again.json()["event"]["id"] == event_id
    timeline = client.get("/api/v1/projects/p/audit/timeline", headers=H, params={"correlation_id": "c1"})
    assert timeline.json()["items"][0]["id"] == event_id
    assert store.outbox()[-1]["event_type"] == "audit.recorded"


def test_audit_events_are_project_scoped():
    client = ApiClient(app(AuditService(InMemoryStore())))
    client.post(
        "/api/v1/projects/p/audit/events",
        headers={**H, "X-Correlation-Id": "c1"},
        json={"action": "a", "entity_ref": "e", "evidence_refs": []},
    )
    other = client.get(
        "/api/v1/projects/p/audit/timeline",
        headers={**H, "X-Tenant-Id": "other"},
        params={"correlation_id": "c1"},
    )
    assert other.json()["items"] == []


def test_validation_requires_action_and_entity():
    client = ApiClient(app(AuditService(InMemoryStore())))
    bad = client.post("/api/v1/projects/p/audit/events", headers=H, json={"action": ""})
    assert bad.status_code == 400


def test_evidence_trail_and_immutability(tmp_path):
    from audit_service.testing import DictStore

    path = tmp_path / "audit.json"
    store = DictStore(str(path))
    client = ApiClient(app(AuditService(store)))
    body = {"action": "task.merged", "entity_ref": "task:42", "evidence_refs": ["diff:9"]}
    created = client.post("/api/v1/projects/p/audit/events", headers={**H, "X-Correlation-Id": "c2"}, json=body)
    event_id = created.json()["event"]["id"]
    trail = client.get("/api/v1/projects/p/audit/evidence", headers=H, params={"entity_ref": "task:42"})
    assert trail.json()["items"][0]["id"] == event_id
    fetched = client.get(f"/api/v1/projects/p/audit/events/{event_id}", headers=H)
    assert fetched.json()["event"]["immutable"] is True
    reloaded = DictStore(str(path))
    assert reloaded.get_audit_event(event_id, Scope("t", "w", "p"))["entity_ref"] == "task:42"
    try:
        reloaded.put_audit_event(created.json()["event"])
        raise AssertionError("expected immutable conflict")
    except Exception as exc:
        assert "immutable" in str(exc)

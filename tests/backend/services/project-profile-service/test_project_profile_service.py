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


def test_register_project_and_group():
    store = InMemoryStore()
    client = ApiClient(app(ProjectProfileService(store)))
    group = client.post(
        "/api/v1/project-groups",
        headers=H,
        json={"name": "payments", "member_project_ids": ["p"], "share_policy": "explicit_opt_in"},
    )
    assert group.status_code == 200
    group_id = group.json()["group"]["id"]
    project = client.post(
        "/api/v1/projects/p/profile",
        headers={**H, "Idempotency-Key": "two"},
        json={"name": "Pay API", "domain_pack": "default", "feature_profile": "default", "project_group_id": group_id},
    )
    assert project.json()["project"]["isolation"] == "strict"
    fetched = client.get("/api/v1/projects/p/profile", headers=H)
    assert fetched.json()["project"]["name"] == "Pay API"
    assert any(e["event_type"] == "project.registered" for e in store.outbox())


def test_register_project_denied_by_admin_matrix():
    from project_profile_service.core import ValidationError

    store = InMemoryStore()
    svc = ProjectProfileService(store)
    from project_profile_service.core import Scope

    try:
        svc.register_project(
            Scope("t", "w", "p-deny"),
            "viewer",
            "corr",
            "deny-key",
            {"name": "Nope", "actor_roles": ["viewer"]},
        )
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "project.create" in str(exc)


def test_idempotent_project_register():
    client = ApiClient(app(ProjectProfileService(InMemoryStore())))
    a = client.post("/api/v1/projects/p/profile", headers=H, json={"name": "A"})
    b = client.post("/api/v1/projects/p/profile", headers=H, json={"name": "A"})
    assert a.json()["project"]["id"] == b.json()["project"]["id"]


def test_name_required():
    client = ApiClient(app(ProjectProfileService(InMemoryStore())))
    bad = client.post("/api/v1/projects/p/profile", headers=H, json={"name": ""})
    assert bad.status_code == 400


def test_update_feature_profile(tmp_path):
    from project_profile_service.core import Scope
    from project_profile_service.testing import DictStore

    path = tmp_path / "profile.json"
    store = DictStore(str(path))
    client = ApiClient(app(ProjectProfileService(store)))
    client.post("/api/v1/projects/p/profile", headers=H, json={"name": "Pay API"})
    updated = client.request(
        "PATCH",
        "/api/v1/projects/p/profile",
        headers=H,
        json={"domain_pack": "payments", "feature_profile": "strict-review"},
    )
    assert updated.status_code == 200
    assert updated.json()["project"]["domain_pack"] == "payments"
    assert updated.json()["project"]["feature_profile"] == "strict-review"
    reloaded = DictStore(str(path))
    assert reloaded.get_project("p", Scope("t", "w", "p"))["feature_profile"] == "strict-review"


def test_activate_programming_usage_profile_and_export_cursor_mcp():
    store = InMemoryStore()
    client = ApiClient(app(ProjectProfileService(store)))
    created = client.post(
        "/api/v1/projects/p/profile",
        headers=H,
        json={"name": "Eng", "usage_profile": "programming-cursor-mcp"},
    )
    assert created.status_code == 200
    assert created.json()["project"]["usage_profile"] == "programming-cursor-mcp"

    activated = client.post(
        "/api/v1/projects/p/usage-profile:activate",
        headers=H,
        json={"usage_profile": "programming-cursor-mcp"},
    )
    assert activated.status_code == 200
    assert activated.json()["project"]["usage_profile"] == "programming-cursor-mcp"

    effective = client.get("/api/v1/projects/p/usage-profile/effective", headers=H)
    assert effective.status_code == 200
    assert effective.json()["effective"]["profile_id"] == "programming-cursor-mcp"
    assert effective.json()["effective"]["mcp"]["server_name"] == "Astloom-Programming"

    cursor = client.get("/api/v1/projects/p/usage-profile/cursor-mcp", headers=H)
    assert cursor.status_code == 200
    servers = cursor.json()["cursor_mcp"]["mcpServers"]
    assert "Astloom-Programming" in servers
    assert servers["Astloom-Programming"]["env"]["ASTLOOM_USAGE_PROFILE"] == "programming-cursor-mcp"

    listed = client.get("/api/v1/usage-profiles", headers=H)
    assert "programming-cursor-mcp" in listed.json()["items"]

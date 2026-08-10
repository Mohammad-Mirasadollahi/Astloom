import asyncio

from httpx import ASGITransport, AsyncClient

from orchestration_service.api import app
from orchestration_service.core import OrchestrationService
from orchestration_service.testing import InMemoryStore


H = {"X-Tenant-Id": "t", "X-Workspace-Id": "w", "X-Actor-Id": "orch", "Idempotency-Key": "one"}


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


def test_open_batch_route_and_close():
    store = InMemoryStore()
    client = ApiClient(app(OrchestrationService(store)))
    batch = client.post("/api/v1/projects/p/work-batches", headers=H, json={"title": "migration", "task_ids": ["t1"]})
    assert batch.status_code == 200
    batch_id = batch.json()["batch"]["id"]
    routed = client.post(
        "/api/v1/projects/p/assignments",
        headers={**H, "Idempotency-Key": "two"},
        json={"task_id": "t1", "agent_type": "backend", "batch_id": batch_id},
    )
    assert routed.json()["assignment"]["status"] == "assigned"
    closed = client.post(f"/api/v1/projects/p/work-batches/{batch_id}:close", headers=H)
    assert closed.json()["batch"]["status"] == "closed"
    assert any(e["event_type"] == "task.routed" for e in store.outbox())


def test_idempotent_batch_open():
    client = ApiClient(app(OrchestrationService(InMemoryStore())))
    a = client.post("/api/v1/projects/p/work-batches", headers=H, json={"title": "x"})
    b = client.post("/api/v1/projects/p/work-batches", headers=H, json={"title": "x"})
    assert a.json()["batch"]["id"] == b.json()["batch"]["id"]


def test_route_requires_task_and_agent():
    client = ApiClient(app(OrchestrationService(InMemoryStore())))
    bad = client.post("/api/v1/projects/p/assignments", headers=H, json={"task_id": ""})
    assert bad.status_code == 400


def test_complete_assignment_and_list(tmp_path):
    from orchestration_service.core import Scope
    from orchestration_service.testing import DictStore

    path = tmp_path / "orch.json"
    store = DictStore(str(path))
    client = ApiClient(app(OrchestrationService(store)))
    batch = client.post("/api/v1/projects/p/work-batches", headers=H, json={"title": "coord"})
    batch_id = batch.json()["batch"]["id"]
    routed = client.post(
        "/api/v1/projects/p/assignments",
        headers={**H, "Idempotency-Key": "asg"},
        json={"task_id": "t9", "agent_type": "frontend", "batch_id": batch_id},
    )
    assignment_id = routed.json()["assignment"]["id"]
    done = client.post(f"/api/v1/projects/p/assignments/{assignment_id}:complete", headers=H)
    assert done.json()["assignment"]["status"] == "completed"
    listed = client.get("/api/v1/projects/p/assignments", headers=H, params={"batch_id": batch_id})
    assert listed.json()["items"][0]["status"] == "completed"
    reloaded = DictStore(str(path))
    assert reloaded.get_assignment(assignment_id, Scope("t", "w", "p"))["status"] == "completed"


def test_agent_ticket_lifecycle_and_concurrency():
    store = InMemoryStore()
    client = ApiClient(app(OrchestrationService(store)))
    created = client.post(
        "/api/v1/projects/p/agent-tickets",
        headers={**H, "Idempotency-Key": "atk-1"},
        json={"title": "ship adapter", "agent_id": "agent-1", "task_id": "task-9", "agent_type": "backend"},
    )
    assert created.status_code == 200
    ticket = created.json()["ticket"]
    assert ticket["status"] == "assigned"
    ticket_id = ticket["id"]

    claimed = client.post(
        f"/api/v1/projects/p/agent-tickets/{ticket_id}:claim",
        headers={**H, "Idempotency-Key": "atk-claim"},
        json={"expected_version": 1},
    )
    assert claimed.json()["ticket"]["status"] == "claimed"
    started = client.post(
        f"/api/v1/projects/p/agent-tickets/{ticket_id}:start",
        headers={**H, "Idempotency-Key": "atk-start"},
        json={"expected_version": 2},
    )
    assert started.json()["ticket"]["status"] == "in_progress"
    blocked = client.post(
        f"/api/v1/projects/p/agent-tickets/{ticket_id}:block",
        headers={**H, "Idempotency-Key": "atk-block"},
        json={"expected_version": 3, "reason": "waiting on review gate"},
    )
    assert blocked.json()["ticket"]["status"] == "blocked"
    resumed = client.post(
        f"/api/v1/projects/p/agent-tickets/{ticket_id}:start",
        headers={**H, "Idempotency-Key": "atk-resume"},
        json={"expected_version": 4},
    )
    assert resumed.json()["ticket"]["status"] == "in_progress"
    review = client.post(
        f"/api/v1/projects/p/agent-tickets/{ticket_id}:submit-review",
        headers={**H, "Idempotency-Key": "atk-review"},
        json={"expected_version": 5, "changeset_id": "cs_1", "changeset_revision": "1"},
    )
    assert review.json()["ticket"]["status"] == "review"
    done = client.post(
        f"/api/v1/projects/p/agent-tickets/{ticket_id}:complete",
        headers={**H, "Idempotency-Key": "atk-done"},
        json={"expected_version": 6},
    )
    assert done.json()["ticket"]["status"] == "completed"
    conflict = client.post(
        f"/api/v1/projects/p/agent-tickets/{ticket_id}:complete",
        headers={**H, "Idempotency-Key": "atk-conflict"},
        json={"expected_version": 1},
    )
    assert conflict.status_code == 409
    listed = client.get("/api/v1/projects/p/agent-tickets", headers=H, params={"status": "completed"})
    assert listed.json()["items"][0]["id"] == ticket_id
    other = client.get(
        f"/api/v1/projects/other/agent-tickets/{ticket_id}",
        headers={**H, "X-Workspace-Id": "w"},
    )
    assert other.status_code == 404
    assert any(e["event_type"] == "AgentTicketCompleted" for e in store.outbox())


def test_agent_ticket_reassign_and_cancel():
    client = ApiClient(app(OrchestrationService(InMemoryStore())))
    created = client.post(
        "/api/v1/projects/p/agent-tickets",
        headers={**H, "Idempotency-Key": "atk-r1"},
        json={"title": "retry", "agent_id": "a1"},
    )
    ticket_id = created.json()["ticket"]["id"]
    reassigned = client.post(
        f"/api/v1/projects/p/agent-tickets/{ticket_id}:reassign",
        headers={**H, "Idempotency-Key": "atk-r2"},
        json={"expected_version": 1, "agent_id": "a2", "agent_type": "frontend"},
    )
    assert reassigned.json()["ticket"]["agent_id"] == "a2"
    assert reassigned.json()["ticket"]["status"] == "assigned"
    canceled = client.post(
        f"/api/v1/projects/p/agent-tickets/{ticket_id}:cancel",
        headers={**H, "Idempotency-Key": "atk-r3"},
        json={"expected_version": 2, "reason": "obsolete"},
    )
    assert canceled.json()["ticket"]["status"] == "canceled"


def test_agent_ticket_created_fail_idempotency_and_start_from_review():
    store = InMemoryStore()
    client = ApiClient(app(OrchestrationService(store)))
    created = client.post(
        "/api/v1/projects/p/agent-tickets",
        headers={**H, "Idempotency-Key": "atk-created"},
        json={"title": "unassigned work"},
    )
    assert created.status_code == 200
    assert created.json()["ticket"]["status"] == "created"
    assert created.json()["ticket"]["agent_id"] is None
    replay = client.post(
        "/api/v1/projects/p/agent-tickets",
        headers={**H, "Idempotency-Key": "atk-created"},
        json={"title": "unassigned work"},
    )
    assert replay.json()["ticket"]["id"] == created.json()["ticket"]["id"]

    ticket_id = created.json()["ticket"]["id"]
    assigned = client.post(
        f"/api/v1/projects/p/agent-tickets/{ticket_id}:reassign",
        headers={**H, "Idempotency-Key": "atk-assign"},
        json={"expected_version": 1, "agent_id": "agent-9"},
    )
    assert assigned.json()["ticket"]["status"] == "assigned"
    claimed = client.post(
        f"/api/v1/projects/p/agent-tickets/{ticket_id}:claim",
        headers={**H, "Idempotency-Key": "atk-c2"},
        json={"expected_version": 2},
    )
    assert claimed.status_code == 200
    started = client.post(
        f"/api/v1/projects/p/agent-tickets/{ticket_id}:start",
        headers={**H, "Idempotency-Key": "atk-s2"},
        json={"expected_version": 3},
    )
    assert started.json()["ticket"]["status"] == "in_progress"
    review = client.post(
        f"/api/v1/projects/p/agent-tickets/{ticket_id}:submit-review",
        headers={**H, "Idempotency-Key": "atk-rev2"},
        json={"expected_version": 4},
    )
    assert review.json()["ticket"]["status"] == "review"
    resumed = client.post(
        f"/api/v1/projects/p/agent-tickets/{ticket_id}:start",
        headers={**H, "Idempotency-Key": "atk-from-review"},
        json={"expected_version": 5},
    )
    assert resumed.json()["ticket"]["status"] == "in_progress"

    failed_ticket = client.post(
        "/api/v1/projects/p/agent-tickets",
        headers={**H, "Idempotency-Key": "atk-fail-create"},
        json={"title": "will fail", "agent_id": "agent-fail"},
    )
    fail_id = failed_ticket.json()["ticket"]["id"]
    failed = client.post(
        f"/api/v1/projects/p/agent-tickets/{fail_id}:fail",
        headers={**H, "Idempotency-Key": "atk-fail"},
        json={"expected_version": 1, "reason": "executor crashed"},
    )
    assert failed.status_code == 200
    assert failed.json()["ticket"]["status"] == "failed"
    assert failed.json()["ticket"]["fail_reason"] == "executor crashed"
    assert any(e["event_type"] == "AgentTicketFailed" for e in store.outbox())

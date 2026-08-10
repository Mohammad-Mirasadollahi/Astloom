import asyncio

from httpx import ASGITransport, AsyncClient

from core_data_service.api import app
from core_data_service.core import CoreData, Kind, Scope
from core_data_service.testing import InMemoryStore


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


def task():
    return {"title": "implement store", "assignee_type": "backend", "instructions": "write it", "acceptance_criteria": ["tests"]}


def decision():
    return {
        "title": "records persist",
        "context": "phase one",
        "options_considered": ["db", "files"],
        "chosen_option": "db",
        "consequences": ["migrations"],
        "owner": "platform",
    }


def test_idempotent_task_transition_scope_and_task_board():
    store = InMemoryStore()
    client = ApiClient(app(CoreData(store)))
    url = "/api/v1/projects/p/tasks"

    created = client.post(url, headers=H, json=task())
    assert created.status_code == 200
    assert client.post(url, headers=H, json=task()).json()["record"]["id"] == created.json()["record"]["id"]

    task_id = created.json()["record"]["id"]
    transitioned = client.post(
        url + "/" + task_id + ":transition",
        headers={**H, "Idempotency-Key": "two"},
        json={"status": "ready", "reason": "triaged", "expected_version": 1},
    )
    assert transitioned.json()["task"]["status"] == "ready"
    assert client.get(url, headers={**H, "X-Tenant-Id": "other"}).json()["items"] == []
    assert client.get("/api/v1/projects/p/task-board", headers=H).json()["board"]["ready"][0]["id"] == task_id
    assert store.outbox()[-1]["event_type"] == "task.state_changed"


def test_decision_supersession_keeps_old_record_through_api():
    service = CoreData(InMemoryStore())
    client = ApiClient(app(service))
    created = client.post("/api/v1/projects/p/decisions", headers={**H, "Idempotency-Key": "d1"}, json={**decision(), "status": "active"})
    old_id = created.json()["record"]["id"]

    superseded = client.post(
        f"/api/v1/projects/p/decisions/{old_id}:supersede",
        headers={**H, "Idempotency-Key": "d2"},
        json={**decision(), "title": "records persist in postgres later"},
    )
    assert superseded.status_code == 200
    assert superseded.json()["decision"]["status"] == "active"
    assert service.store.get(old_id, Scope("t", "w", "p")).status == "superseded"
    history = client.get("/api/v1/projects/p/decision-history", headers=H).json()["items"]
    assert {item["status"] for item in history} == {"active", "superseded"}


def test_critical_issue_requires_task_or_escalation_and_can_create_tasks():
    client = ApiClient(app(CoreData(InMemoryStore())))
    issue = {"title": "production outage", "description": "api is down", "severity": "critical", "evidence_refs": ["incident-1"]}

    rejected = client.post("/api/v1/projects/p/issues", headers=H, json=issue)
    assert rejected.status_code == 400
    assert "task_specs or escalation_reason" in rejected.text

    accepted = client.post(
        "/api/v1/projects/p/issues",
        headers={**H, "Idempotency-Key": "critical-1", "X-Correlation-Id": "corr-critical"},
        json={**issue, "task_specs": [task()]},
    )
    assert accepted.status_code == 200
    issue_id = accepted.json()["record"]["id"]
    assert accepted.json()["tasks"][0]["data"]["issue_id"] == issue_id
    assert client.get("/api/v1/projects/p/open-issues", headers=H).json()["items"][0]["id"] == issue_id
    assert client.get("/api/v1/projects/p/evidence-bundles/incident-1", headers=H).json()["items"][0]["id"] == issue_id
    related = client.get("/api/v1/projects/p/related-work?correlation_id=corr-critical", headers=H).json()["items"]
    assert {item["kind"] for item in related} == {"issue", "task"}


def test_redaction_validation_and_event_contract():
    store = InMemoryStore()
    client = ApiClient(app(CoreData(store)))
    response = client.post(
        "/api/v1/projects/p/activities",
        headers=H,
        json={"action_type": "command", "action_summary": "token=hidden", "evidence_refs": ["cmd-1"]},
    )
    assert response.status_code == 200
    assert "hidden" not in response.text
    assert client.post("/api/v1/projects/p/tasks", json=task()).status_code == 400

    event = store.outbox()[0]
    assert event["event_type"] == "activity.recorded"
    assert event["event_version"] == 1
    assert event["source"] == "core-data-service"
    assert event["tenant_id"] == "t"
    assert event["evidence_refs"] == ["cmd-1"]


def test_issue_lifecycle_and_idempotent_supersede_links():
    store = InMemoryStore()
    service = CoreData(store)
    client = ApiClient(app(service))
    scope = Scope("t", "w", "p")

    issue = client.post(
        "/api/v1/projects/p/issues",
        headers={**H, "Idempotency-Key": "issue-1"},
        json={"title": "flake", "description": "intermittent failure", "severity": "high"},
    )
    issue_id = issue.json()["record"]["id"]
    triaged = client.post(
        f"/api/v1/projects/p/issues/{issue_id}:transition",
        headers={**H, "Idempotency-Key": "issue-triage"},
        json={"status": "triaged", "reason": "confirmed", "expected_version": 1},
    )
    assert triaged.status_code == 200
    assert triaged.json()["issue"]["status"] == "triaged"

    created = client.post(
        "/api/v1/projects/p/decisions",
        headers={**H, "Idempotency-Key": "dec-active"},
        json={**decision(), "status": "active"},
    )
    old_id = created.json()["record"]["id"]
    headers = {**H, "Idempotency-Key": "dec-supersede"}
    body = {**decision(), "title": "records persist with supersedes link"}
    first = client.post(f"/api/v1/projects/p/decisions/{old_id}:supersede", headers=headers, json=body)
    second = client.post(f"/api/v1/projects/p/decisions/{old_id}:supersede", headers=headers, json=body)
    assert first.status_code == 200
    assert second.json()["decision"]["id"] == first.json()["decision"]["id"]
    new_id = first.json()["decision"]["id"]
    assert service.store.get(new_id, scope).data["supersedes"] == old_id
    assert service.store.get(old_id, scope).data["superseded_by"] == new_id
    related = client.get(f"/api/v1/projects/p/related-work?entity_id={old_id}", headers=H).json()["items"]
    assert {item["id"] for item in related} >= {old_id, new_id}


def test_list_pagination_has_more():
    client = ApiClient(app(CoreData(InMemoryStore())))
    for index in range(3):
        client.post(
            "/api/v1/projects/p/activities",
            headers={**H, "Idempotency-Key": f"act-{index}"},
            json={"action_type": "command", "action_summary": f"step {index}"},
        )
    page = client.get("/api/v1/projects/p/activities?page_size=2", headers=H).json()
    assert len(page["items"]) == 2
    assert page["page"]["has_more"] is True


def test_changeset_api_create_approve_and_discussion():
    store = InMemoryStore()
    client = ApiClient(app(CoreData(store)))
    created = client.post(
        "/api/v1/projects/p/changesets",
        headers={**H, "Idempotency-Key": "cs-api-1"},
        json={"title": "API patch", "artifact_ref": "artifact://api-1"},
    )
    assert created.status_code == 200
    cs_id = created.json()["record"]["id"]
    opened = client.post(
        f"/api/v1/projects/p/changesets/{cs_id}:transition",
        headers={**H, "Idempotency-Key": "cs-api-open"},
        json={"status": "open", "reason": "ready"},
    )
    assert opened.status_code == 200
    client.post(
        f"/api/v1/projects/p/changesets/{cs_id}:transition",
        headers={**H, "Idempotency-Key": "cs-api-review"},
        json={"status": "in_review", "reason": "review"},
    )
    approved = client.post(
        f"/api/v1/projects/p/changesets/{cs_id}:approve",
        headers={**H, "X-Actor-Id": "reviewer", "Idempotency-Key": "cs-api-approve"},
        json={"status": "approved", "reason": "lgtm"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["changeset"]["status"] == "approved"
    discussion = client.post(
        "/api/v1/projects/p/discussion-comments",
        headers={**H, "Idempotency-Key": "dc-api-1"},
        json={
            "target_kind": "changeset",
            "target_id": cs_id,
            "body": "ship it",
            "author_ref": "reviewer",
        },
    )
    assert discussion.status_code == 200
    assert discussion.json()["record"]["kind"] == "discussion_comment"


def test_changeset_api_approve_after_changes_requested():
    store = InMemoryStore()
    client = ApiClient(app(CoreData(store)))
    created = client.post(
        "/api/v1/projects/p/changesets",
        headers={**H, "Idempotency-Key": "cs-cr-1"},
        json={"title": "Needs rework", "artifact_ref": "artifact://cr-1"},
    )
    cs_id = created.json()["record"]["id"]
    client.post(
        f"/api/v1/projects/p/changesets/{cs_id}:transition",
        headers={**H, "Idempotency-Key": "cs-cr-open"},
        json={"status": "open", "reason": "ready"},
    )
    client.post(
        f"/api/v1/projects/p/changesets/{cs_id}:transition",
        headers={**H, "Idempotency-Key": "cs-cr-review"},
        json={"status": "in_review", "reason": "review"},
    )
    client.post(
        f"/api/v1/projects/p/changesets/{cs_id}:transition",
        headers={**H, "Idempotency-Key": "cs-cr-req"},
        json={"status": "changes_requested", "reason": "nits"},
    )
    approved = client.post(
        f"/api/v1/projects/p/changesets/{cs_id}:approve",
        headers={**H, "X-Actor-Id": "reviewer", "Idempotency-Key": "cs-cr-approve"},
        json={"status": "approved", "reason": "fixed"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["changeset"]["status"] == "approved"


def test_delete_record_removes_task_and_is_idempotent():
    service = CoreData(InMemoryStore())
    scope = Scope("t", "w", "p")
    created = service.create(
        Kind.TASK,
        scope,
        "agent",
        "corr-del",
        "task-del-1",
        task(),
    )
    service.delete_record(
        scope,
        "agent",
        "corr-del",
        "del-key-1",
        created.id,
        kind=Kind.TASK,
        reason="retention_purge",
    )
    try:
        service.store.get(created.id, scope)
        raise AssertionError("expected missing record after delete")
    except Exception as exc:
        assert "not found" in str(exc).lower()
    # Idempotent replay does not raise.
    service.delete_record(
        scope,
        "agent",
        "corr-del",
        "del-key-1",
        created.id,
        kind=Kind.TASK,
        reason="retention_purge",
    )
    events = [e for e in service.store.outbox() if e["event_type"] == "task.deleted"]
    assert len(events) == 1

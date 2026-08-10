import asyncio

from httpx import ASGITransport, AsyncClient

from rule_engine_service.api import app
from rule_engine_service.core import ConflictError, NotFoundError, RuleEngineService, Scope
from rule_engine_service.testing import InMemoryStore


SCOPE = Scope("t", "w", "p")
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


def security_rule(**extra):
    return {
        "title": "Block unsafe production auth changes",
        "natural_language_rule": "Production authentication and security changes require human approval",
        "severity": "critical",
        "owner": "security-lead",
        "evaluation_mode": "hybrid",
        "domain": "security",
        "match_tags": ["security", "auth", "production"],
        "examples": ["changed auth middleware without approval"],
        "counterexamples": ["docs-only edit"],
        "required_approval_role": "security-approver",
        "precedence": 200,
        **extra,
    }


def test_sensitive_change_blocks_for_approval_with_rationale_and_evidence():
    store = InMemoryStore()
    service = RuleEngineService(store)

    rule = service.create_rule(SCOPE, "agent", "corr", "rule-1", security_rule())
    assert service.create_rule(SCOPE, "agent", "corr", "rule-1", security_rule()).id == rule.id

    result = service.evaluate_rules(
        SCOPE,
        "agent",
        "corr",
        "eval-1",
        {
            "subject_ref": "change-auth-1",
            "summary": "Update production auth middleware",
            "change_type": "code",
            "tags": ["security", "auth", "production"],
            "paths": ["src/auth/middleware.py"],
            "evidence_refs": ["diff-1"],
        },
    )
    assert result["blocked"] is True
    assert result["final_verdict"] == "escalate"
    evaluation = result["evaluations"][0]
    assert evaluation["rationale"]
    assert "diff-1" in evaluation["evidence_refs"]
    assert result["approvals"]
    assert result["approvals"][0]["status"] == "requested"
    assert service.get_approval_queue(SCOPE)[0].id == result["approvals"][0]["id"]

    resolved = service.resolve_approval(
        SCOPE,
        "human",
        "corr",
        "resolve-1",
        result["approvals"][0]["id"],
        "approved",
        "temporary waiver with rollback plan",
    )
    assert resolved.status.value == "approved"
    assert store.outbox()[-1]["event_type"] == "ApprovalResolved"
    assert service.list_evaluations(Scope("other", "w", "p")) == []


def test_api_schema_change_routes_downstream_tasks_and_semantic_evidence():
    store = InMemoryStore()
    service = RuleEngineService(store)
    service.create_rule(
        SCOPE,
        "agent",
        "corr",
        "rule-api",
        {
            "title": "API contract changes need downstream updates",
            "natural_language_rule": "Public API and schema changes must update clients docs and tests",
            "severity": "high",
            "owner": "platform",
            "evaluation_mode": "semantic",
            "domain": "engineering",
            "match_tags": ["api", "schema"],
            "examples": ["openapi field removed"],
            "precedence": 150,
        },
    )

    result = service.evaluate_rules(
        SCOPE,
        "agent",
        "corr",
        "eval-api",
        {
            "subject_ref": "change-api-1",
            "summary": "Remove field from public API schema",
            "change_type": "api",
            "tags": ["api", "schema", "contract"],
            "paths": ["openapi.yaml", "migrations/0002.sql"],
            "evidence_refs": ["pr-22"],
            "linked_task": "task-existing",
        },
    )
    assert result["impact"] is not None
    assignees = {task["assignee_type"] for task in result["tasks"]}
    assert {"frontend", "docs", "qa", "data", "backend"} <= assignees
    semantic = [item for item in result["evaluations"] if item["used_llm"]]
    assert semantic
    assert semantic[0]["rationale"]
    assert "pr-22" in semantic[0]["evidence_refs"]

    feedback = service.record_feedback(SCOPE, "agent", "corr", "fb-1", semantic[0]["id"], "true_positive", "correct block")
    assert feedback.label == "true_positive"
    assert any(event["event_type"] == "TaskRouted" for event in store.outbox())

    replay = service.evaluate_rules(
        SCOPE,
        "agent",
        "corr",
        "eval-api",
        {
            "subject_ref": "change-api-1",
            "summary": "Remove field from public API schema",
            "change_type": "api",
            "tags": ["api", "schema", "contract"],
            "paths": ["openapi.yaml", "migrations/0002.sql"],
            "evidence_refs": ["pr-22"],
            "linked_task": "task-existing",
        },
    )
    assert replay["impact"] is not None
    assert replay["tasks"]
    assert {task["assignee_type"] for task in replay["tasks"]} == assignees


def test_revenue_and_compliance_domains_block_for_approval():
    service = RuleEngineService(InMemoryStore())
    for domain, tags, subject_ref in (
        ("revenue", ["revenue", "billing"], "change-revenue-1"),
        ("compliance", ["compliance", "production"], "change-compliance-1"),
    ):
        service.create_rule(
            SCOPE,
            "agent",
            "corr",
            f"rule-{domain}",
            {
                "title": f"Block {domain} changes",
                "natural_language_rule": f"{domain} sensitive changes require approval",
                "severity": "critical",
                "owner": f"{domain}-lead",
                "evaluation_mode": "deterministic",
                "domain": domain,
                "match_tags": tags,
                "required_approval_role": f"{domain}-approver",
                "precedence": 180,
            },
        )
        result = service.evaluate_rules(
            SCOPE,
            "agent",
            "corr",
            f"eval-{domain}",
            {
                "subject_ref": subject_ref,
                "summary": f"Update {domain} controls",
                "tags": tags,
                "paths": [f"src/{domain}.py"],
                "evidence_refs": [f"diff-{domain}"],
            },
        )
        assert result["blocked"] is True
        assert result["final_verdict"] == "escalate"
        assert result["approvals"]
        assert result["evaluations"][0]["rationale"]
        assert f"diff-{domain}" in result["evaluations"][0]["evidence_refs"]


def test_low_risk_deterministic_allow_and_shadow_mode():
    service = RuleEngineService(InMemoryStore())
    service.create_rule(
        SCOPE,
        "agent",
        "corr",
        "rule-docs",
        {
            "title": "Docs only changes are low risk",
            "natural_language_rule": "Documentation-only edits are allowed",
            "severity": "low",
            "owner": "docs",
            "evaluation_mode": "deterministic",
            "domain": "engineering",
            "match_tags": ["docs"],
            "state": "shadow",
        },
    )
    shadow = service.run_shadow(
        SCOPE,
        "agent",
        "corr",
        "shadow-1",
        {"subject_ref": "change-docs-1", "summary": "Fix typo", "tags": ["docs"], "paths": ["README.md"]},
    )
    assert shadow["shadow"] is True
    assert shadow["blocked"] is False
    assert shadow["final_verdict"] == "allow"


def test_in_memory_store_scope_idempotency_and_not_found():
    store = InMemoryStore()
    service = RuleEngineService(store)
    rule = service.create_rule(SCOPE, "agent", "corr", "rule-1", security_rule())
    assert store.get_rule(rule.id, SCOPE).title.startswith("Block")
    assert store.list_rules(Scope("other", "w", "p")) == []

    store.remember(SCOPE, "create_rule", "dup", {"title": "a"}, rule.id)
    assert store.idempotent(SCOPE, "create_rule", "dup", {"title": "a"}) == rule.id
    try:
        store.idempotent(SCOPE, "create_rule", "dup", {"title": "b"})
        raise AssertionError("expected idempotency conflict")
    except ConflictError:
        pass

    try:
        store.get_rule("missing", SCOPE)
        raise AssertionError("expected not found")
    except NotFoundError:
        pass

    event = store.outbox()[0]
    assert event["event_type"] == "RuleCreated"
    assert event["event_version"] == 1
    assert event["producer"] == "rule-engine-service"
    assert event["tenant_id"] == "t"
    assert event["project_id"] == "p"


def test_api_sensitive_block_approval_and_health_smoke():
    store = InMemoryStore()
    client = ApiClient(app(RuleEngineService(store)))
    created = client.post(
        "/api/v1/projects/p/rules",
        headers={**H, "Idempotency-Key": "api-rule"},
        json=security_rule(),
    )
    assert created.status_code == 200

    evaluated = client.post(
        "/api/v1/projects/p/evaluations",
        headers={**H, "Idempotency-Key": "api-eval"},
        json={
            "subject_ref": "change-auth-api",
            "summary": "Update production auth middleware",
            "change_type": "code",
            "tags": ["security", "auth", "production"],
            "paths": ["src/auth/middleware.py"],
            "evidence_refs": ["diff-api"],
        },
    )
    assert evaluated.status_code == 200
    body = evaluated.json()
    assert body["blocked"] is True
    assert body["approvals"]
    approval_id = body["approvals"][0]["id"]
    evaluation_id = body["evaluations"][0]["id"]

    queue = client.get("/api/v1/projects/p/approval-queue", headers=H)
    assert queue.json()["items"][0]["id"] == approval_id
    explain = client.get(f"/api/v1/projects/p/evaluations/{evaluation_id}:explain", headers=H)
    assert explain.json()["explanation"]["used_llm"] in {True, False}
    assert explain.json()["explanation"]["evidence_refs"]

    resolved = client.post(
        f"/api/v1/projects/p/approvals/{approval_id}:resolve",
        headers={**H, "Idempotency-Key": "api-resolve"},
        json={"status": "approved", "reason": "rollback plan ready"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["approval"]["status"] == "approved"
    health = client.get("/api/v1/projects/p/rule-health", headers=H)
    assert health.json()["health"]["rule_count"] == 1
    assert client.post("/api/v1/projects/p/rules", json=security_rule()).status_code == 400


def test_api_contract_routes_are_registered():
    routes = {route.path for route in app(RuleEngineService(InMemoryStore())).routes}
    assert "/api/v1/projects/{project_id}/rules" in routes
    assert "/api/v1/projects/{project_id}/rules/{rule_id}:update-version" in routes
    assert "/api/v1/projects/{project_id}/evaluations" in routes
    assert "/api/v1/projects/{project_id}/evaluations:shadow" in routes
    assert "/api/v1/projects/{project_id}/approvals" in routes
    assert "/api/v1/projects/{project_id}/approvals/{approval_id}:resolve" in routes
    assert "/api/v1/projects/{project_id}/task-routes" in routes
    assert "/api/v1/projects/{project_id}/rule-feedback" in routes
    assert "/api/v1/projects/{project_id}/evaluations/{evaluation_id}:explain" in routes
    assert "/api/v1/projects/{project_id}/approval-queue" in routes
    assert "/api/v1/projects/{project_id}/anomalies" in routes
    assert "/api/v1/projects/{project_id}/rule-health" in routes


def test_trust_below_floor_escalates_high_risk():
    service = RuleEngineService(InMemoryStore())
    service.create_rule(SCOPE, "agent", "corr", "rule-trust", security_rule())
    result = service.evaluate_rules(
        SCOPE,
        "agent",
        "corr",
        "eval-trust",
        {
            "subject_ref": "change-auth-trust",
            "summary": "Update production auth middleware",
            "change_type": "code",
            "tags": ["security", "auth", "production"],
            "paths": ["src/auth/middleware.py"],
            "evidence_refs": ["diff-trust"],
            "agent_trust_level": "standard",
            "provider": "standard",
        },
    )
    assert result["blocked"] is True
    assert result["final_verdict"] == "escalate"
    assert any("below high-risk floor" in (e.get("rationale") or "") for e in result["evaluations"])
